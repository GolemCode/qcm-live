"""Incrément 8 : QR code de jonction au tableau (SES-05), plus de QR code en fin de session
(FIN-02).

Le QR code de jonction se lit comme le ferait un vrai téléphone : capture de l'image projetée,
décodage (`qr_text`), puis ouverture de l'adresse décodée sur un autre appareil.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.live_setup import expect_slot, make_live, open_board
from tests.e2e.live_ui import (
    LIVE_MS,
    connected_names,
    identify,
    identity,
    join_hint,
    join_qr,
    phones_joined,
    qr_text,
    start,
    timer,
)
from tests.factories import jump_to

MIN_QR_PX = 300  # sur un écran de 1080 lignes : assez grand pour se lire depuis la salle


@pytest.mark.spec("SES-05")
def test_board_qr_code_opens_the_session_on_a_phone(teacher_page: Page, live_server, new_phone):
    page = teacher_page
    session = make_live(1, shown=1)
    open_board(page, live_server.url, session)

    scanned = qr_text(join_qr(page))
    assert scanned == f"{live_server.url}/s/{session.code}/"
    box = join_qr(page).bounding_box()
    assert box and min(box["width"], box["height"]) >= MIN_QR_PX, box
    # L'adresse et le code restent lisibles, pour un téléphone qui ne lit pas le QR code.
    hint = join_hint(page)
    expect(hint).to_contain_text(f"{live_server.url}/")
    expect(hint).to_contain_text(session.code)

    # Le téléphone arrive directement sur l'écran de la session : il n'y a plus que le numéro.
    phone = new_phone()
    phone.goto(scanned)
    expect(phone.get_by_label("Code de session")).to_have_count(0)
    identify(phone, "00123")
    expect(identity(phone)).to_have_text("Vous êtes DURAND Élise")
    expect(connected_names(page)).to_have_text(["DURAND Élise"], timeout=LIVE_MS)

    # Un téléphone déjà identifié qui relit le QR code retrouve son écran, sans nouvelle saisie.
    phone.goto(scanned)
    expect(identity(phone)).to_have_text("Vous êtes DURAND Élise")
    expect(phone.get_by_label("Numéro d'étudiant")).to_have_count(0)


@pytest.mark.spec("SES-05")
def test_join_qr_code_uses_the_class_mode_address(teacher_page: Page, live_server, settings):
    """Le tableau ouvert en local projette l'adresse du réseau local, dans le QR code comme dans
    le texte. Sans dépendre du réseau du PC, contrairement au test de bout en bout de CLA-01."""
    settings.JOIN_URL = "http://192.168.1.23:8000/"
    session = make_live(1, shown=1)
    open_board(teacher_page, live_server.url, session)
    assert qr_text(join_qr(teacher_page)) == f"http://192.168.1.23:8000/s/{session.code}/"
    expect(join_hint(teacher_page)).to_contain_text("http://192.168.1.23:8000/")


@pytest.mark.spec("SES-05")
def test_join_qr_code_is_gone_once_started(teacher_page: Page, live_server):
    page = teacher_page
    session = make_live(2, shown=1)
    open_board(page, live_server.url, session)
    expect(join_qr(page)).to_be_visible()

    start(page)
    expect(page.get_by_role("img")).to_have_count(0)
    page.reload()
    expect(timer(page)).to_be_visible()
    expect(page.get_by_role("img")).to_have_count(0)

    jump_to(session, 61)
    expect(page.get_by_role("main")).to_contain_text("Session terminée", timeout=LIVE_MS)
    expect(page.get_by_role("img")).to_have_count(0)


@pytest.mark.spec("FIN-02")
def test_phone_only_says_the_session_is_over(teacher_page: Page, live_server, new_phone):
    page = teacher_page
    session = make_live(2, shown=1, seconds=30)
    (phone,) = phones_joined(new_phone, live_server.url, session.code, ["00123"])
    open_board(page, live_server.url, session)
    start(page)
    expect_slot(phone, 0)
    jump_to(session, 61)  # la fin arrive seule, sans recharger à la main

    def says_only_over(screen: Page, timeout: float = LIVE_MS) -> None:
        # Ni QR code, ni réponses, ni note : le code de la session et la fin, rien d'autre.
        over = re.compile(rf"^\s*Session {session.code}\s+Session terminée\.\s*$")
        expect(screen.get_by_role("main")).to_have_text(over, timeout=timeout)
        expect(screen.get_by_role("img")).to_have_count(0)

    says_only_over(phone)
    phone.reload()  # téléphone rechargé, ou sorti de veille
    says_only_over(phone)
    stranger = new_phone()  # téléphone non identifié
    stranger.goto(f"{live_server.url}/s/{session.code}/")
    says_only_over(stranger)
