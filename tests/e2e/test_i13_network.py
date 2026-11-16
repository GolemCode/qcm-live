"""Incrément 13 : adresses du PC (CLA-02), pare-feu (CLA-03) et test du téléphone (CLA-04).

Sur le serveur de test (`live_server`), les adresses du PC sont des réglages fictifs, comme les
pose le mode classe au démarrage : le choix d'une adresse et ce que projette le tableau ne
dépendent pas des cartes réseau de la machine. Le terminal du mode classe, lui, est vérifié
sur les vraies cartes (`ip`), dans un processus à part (`make classe`).
"""

from __future__ import annotations

import http.client
import json
import re
import subprocess

import pytest
from django.core.cache import cache
from playwright.sync_api import Page, expect

from bank.models import Quiz
from roster.models import StudentGroup
from tests.e2e.classroom_ui import class_mode
from tests.e2e.live_setup import make_live, open_board
from tests.e2e.live_ui import LIVE_MS, join_qr, join_url, qr_text
from tests.factories import make_session

PROJECTED = "http://192.168.1.20:8000/"
LAN_ADDRESSES = [  # comme les classe le mode classe : l'adresse projetée d'office en tête
    {"address": "192.168.1.20", "interface": "wlp2s0", "virtual": False},
    {"address": "192.168.137.1", "interface": "Partage de connexion", "virtual": False},
    {"address": "172.17.0.1", "interface": "docker0", "virtual": True},
]


@pytest.fixture(autouse=True)
def _forget_choice():
    """Le choix d'une adresse vit en mémoire, jusqu'à l'arrêt de l'application."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def lan(settings):
    """Adresses du PC telles que le mode classe les a trouvées au démarrage."""
    settings.LAN_ADDRESSES = LAN_ADDRESSES
    settings.JOIN_URL = PROJECTED


def network_page(page: Page) -> None:
    expect(page.get_by_role("heading", name="Réseau et téléphones", level=1)).to_be_visible()


def trial_qr(page: Page):
    return page.get_by_role("img", name="QR code d'essai pour un téléphone")


def trial_status(page: Page):
    region = page.get_by_role("region", name="Tester avec mon téléphone")
    return region.get_by_role("status")


# --- CLA-02 : adresses du PC, choix sans redémarrer -------------------------------------------


@pytest.mark.spec("CLA-02")
@pytest.mark.usefixtures("lan")
def test_teacher_changes_the_projected_address_from_the_board(teacher_page: Page, live_server):
    page = teacher_page
    session = make_live(1, shown=1)
    open_board(page, live_server.url, session)
    expect(join_url(page)).to_have_text(PROJECTED)

    page.get_by_role("link", name="Changer d'adresse").click()
    network_page(page)
    # Toutes les adresses du PC, avec le nom de leur carte ; la projetée est cochée.
    expect(page.get_by_role("radio")).to_have_count(3)
    expect(page.get_by_label("192.168.1.20 — wlp2s0")).to_be_checked()
    expect(page.get_by_label("172.17.0.1 — docker0 (réseau virtuel)")).not_to_be_checked()
    page.get_by_label("192.168.137.1 — Partage de connexion").check()
    page.get_by_role("button", name="Projeter cette adresse").click()

    # Retour au tableau, sans redémarrer : l'adresse et le QR code ont changé.
    expect(join_url(page)).to_have_text("http://192.168.137.1:8000/")
    assert qr_text(join_qr(page)) == f"http://192.168.137.1:8000/s/{session.code}/"

    # Le choix vaut pour toute session, jusqu'à l'arrêt de l'application.
    other = make_session(Quiz.objects.get(title="Contrôle"), StudentGroup.objects.get(name="TD1"))
    open_board(page, live_server.url, other)
    expect(join_url(page)).to_have_text("http://192.168.137.1:8000/")
    page.get_by_role("link", name="Changer d'adresse").click()
    expect(page.get_by_label("192.168.137.1 — Partage de connexion")).to_be_checked()
    # On revient au tableau sans rien changer.
    page.get_by_role("link", name="Retour au tableau").click()
    expect(join_url(page)).to_have_text("http://192.168.137.1:8000/")


def up_addresses() -> dict[str, str]:
    """Adresses IPv4 des cartes actives de la machine, hors boucle locale et adresses
    automatiques, avec le nom de leur carte, lues par `ip`."""
    found = json.loads(
        subprocess.run(
            ["ip", "-j", "-4", "addr", "show", "up"], capture_output=True, text=True, check=True
        ).stdout
    )
    return {
        info["local"]: card["ifname"]
        for card in found
        if "LOOPBACK" not in card["flags"]
        for info in card["addr_info"]
        if not info["local"].startswith(("127.", "169.254."))
    }


def status_as(port: int, host: str) -> int:
    """Statut de la page d'accueil demandée au serveur local sous le nom d'hôte `host`."""
    connection = http.client.HTTPConnection("localhost", port, timeout=10)
    try:
        connection.request("GET", "/", headers={"Host": f"{host}:{port}"})
        return connection.getresponse().status
    finally:
        connection.close()


@pytest.mark.spec("CLA-02")
def test_terminal_lists_every_address_of_the_pc_with_its_card(transactional_db):
    addresses = up_addresses()
    assert addresses, "aucune carte réseau active : le mode classe ne peut pas se tester ici"
    with class_mode() as server:
        text = "".join(server.output)
        port = int(server.local_url.rsplit(":", 1)[1])
        announced = re.search(r"//([\d.]+):", server.phone_url)
        assert announced and announced.group(1) in addresses, text
        for address, card in addresses.items():
            # Une ligne par adresse, avec le nom de sa carte.
            assert re.search(rf"^.*\b{re.escape(address)}\b.*\b{re.escape(card)}\b", text, re.M), (
                address,
                card,
                text,
            )
            # Les téléphones qui ouvrent l'une ou l'autre sont acceptés : le choix se fait
            # sans redémarrer.
            assert status_as(port, address) == 200, address
        assert "Changer d'adresse" in text  # la façon d'en changer


# --- CLA-03 : pare-feu signalé, jamais ouvert ---------------------------------------------------

FIREWALLS = {
    "ufw": ["sudo ufw allow {port}/tcp"],
    "firewalld": [
        "sudo firewall-cmd --permanent --add-port={port}/tcp",
        "sudo firewall-cmd --reload",
    ],
    "windows-public": ["-LocalPort {port}"],
}


@pytest.mark.spec("CLA-03")
@pytest.mark.parametrize("found", list(FIREWALLS))
def test_network_page_warns_about_a_firewall_with_the_command(
    teacher_page: Page, live_server, monkeypatch, found
):
    monkeypatch.setattr("config.firewall.detect", lambda: [found])
    page = teacher_page
    page.get_by_role("link", name="Réseau et téléphones").click()
    network_page(page)
    region = page.get_by_role("region", name="Pare-feu")
    expect(region).to_contain_text("peut bloquer les téléphones")
    port = live_server.url.rsplit(":", 1)[1]
    commands = " ".join(region.locator("code").all_inner_texts())
    for expected in FIREWALLS[found]:
        assert expected.format(port=port) in commands, commands
    if found == "windows-public":
        expect(region).to_contain_text("Privé")
    # L'application n'ouvre jamais le pare-feu : elle n'en offre pas le moyen.
    expect(region.get_by_role("button")).to_have_count(0)
    expect(region).to_contain_text("QCM Live ne modifie jamais le pare-feu")


@pytest.mark.spec("CLA-03")
def test_network_page_without_firewall(teacher_page: Page, live_server, monkeypatch):
    monkeypatch.setattr("config.firewall.detect", lambda: [])
    page = teacher_page
    page.get_by_role("link", name="Réseau et téléphones").click()
    region = page.get_by_role("region", name="Pare-feu")
    expect(region).to_contain_text("Aucun pare-feu actif détecté")
    expect(region.locator("code")).to_have_count(0)


# --- CLA-04 : tester avec mon téléphone ---------------------------------------------------------


@pytest.mark.spec("CLA-04")
def test_phone_test_from_the_teacher_space(teacher_page: Page, live_server, new_phone):
    page = teacher_page
    page.get_by_role("link", name="Réseau et téléphones").click()
    network_page(page)
    url = qr_text(trial_qr(page))
    assert re.fullmatch(rf"{re.escape(live_server.url)}/essai/[\w-]{{16,}}/", url), url
    expect(trial_status(page)).to_have_text("En attente d'un téléphone…")

    phone = new_phone()
    phone.goto(url)
    expect(phone.get_by_role("heading", name="Connexion réussie")).to_be_visible()
    expect(trial_status(page)).to_have_text("Téléphone connecté", timeout=LIVE_MS)

    # Une adresse d'essai inventée ne mène nulle part.
    token = url.rstrip("/").rsplit("/", 1)[1]
    forged = token[:-1] + ("A" if token[-1] != "A" else "B")
    assert phone.request.get(f"{live_server.url}/essai/{forged}/").status == 404
    assert phone.request.get(f"{live_server.url}/essai/inconnu/").status == 404


@pytest.mark.spec("CLA-04")
def test_phone_test_from_the_board_uses_the_projected_address(
    teacher_page: Page, live_server, new_phone
):
    page = teacher_page
    session = make_live(1, shown=1)
    open_board(page, live_server.url, session)
    projected = join_url(page).inner_text()
    page.get_by_role("link", name="Tester avec mon téléphone").click()
    network_page(page)
    url = qr_text(trial_qr(page))
    assert url.startswith(f"{projected}essai/"), (projected, url)
    phone = new_phone()
    phone.goto(url)
    expect(phone.get_by_role("heading", name="Connexion réussie")).to_be_visible()
    expect(trial_status(page)).to_have_text("Téléphone connecté", timeout=LIVE_MS)
    page.get_by_role("link", name="Retour au tableau").click()
    expect(join_url(page)).to_have_text(projected)


@pytest.mark.spec("CLA-04")
@pytest.mark.usefixtures("lan")
def test_phone_test_follows_the_chosen_address(teacher_page: Page, live_server):
    page = teacher_page
    page.get_by_role("link", name="Réseau et téléphones").click()
    assert qr_text(trial_qr(page)).startswith(f"{PROJECTED}essai/")
    page.get_by_label("192.168.137.1 — Partage de connexion").check()
    page.get_by_role("button", name="Projeter cette adresse").click()
    network_page(page)
    assert qr_text(trial_qr(page)).startswith("http://192.168.137.1:8000/essai/")
