"""Réseau et téléphones (CLA-02 à CLA-04), via le client Django : choix d'une adresse, essai
d'un téléphone, accès."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest
from django.core.cache import cache
from django.urls import reverse
from django.utils.html import escape

from config import firewall, join

pytestmark = pytest.mark.django_db

LAN = [
    {"address": "192.168.1.20", "interface": "wlp2s0", "virtual": False},
    {"address": "192.168.137.1", "interface": "Partage de connexion", "virtual": False},
]


@pytest.fixture(autouse=True)
def _forget_choice():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def teacher(client, django_user_model):
    user = django_user_model.objects.create_user("prof", password="mot-de-passe-de-test")
    client.force_login(user)
    return client


@pytest.fixture
def lan(settings, monkeypatch):
    settings.LAN_ADDRESSES = LAN
    settings.JOIN_URL = "http://192.168.1.20:8000/"
    monkeypatch.setattr("config.firewall.detect", lambda: [])


def test_network_page_requires_login(client):
    response = client.get(reverse("network"))
    assert response.status_code == 302
    assert response["Location"].startswith(reverse("login"))
    assert client.get(reverse("trial-state", args=["x" * 22])).status_code == 302


@pytest.mark.usefixtures("lan")
def test_a_forged_address_is_refused(teacher):
    """Seules les adresses trouvées au démarrage, donc acceptées par ALLOWED_HOSTS."""
    response = teacher.post(reverse("network"), {"address": "evil.example"})
    assert response.status_code == 400
    assert "rien n'a changé" in response.text
    assert cache.get(join.CHOICE_KEY) is None


@pytest.mark.usefixtures("lan")
def test_choosing_an_address_without_a_session_returns_to_the_page(teacher):
    response = teacher.post(reverse("network"), {"address": "192.168.137.1", "session": "000000"})
    assert response.status_code == 302
    assert response["Location"] == reverse("network")  # session inconnue : pas de tableau
    page = teacher.get(reverse("network"))
    assert "http://192.168.137.1:8000/" in page.text
    assert "Retour au tableau" not in page.text


def test_join_url_with_an_imposed_address(settings, rf):
    """`--adresse pc-prof.local` : proposée en plus des adresses du PC, et projetée."""
    settings.LAN_ADDRESSES = LAN
    settings.JOIN_URL = "http://pc-prof.local:8000/"
    request = rf.get("/")
    assert [item["address"] for item in join.addresses()] == [
        "pc-prof.local",
        "192.168.1.20",
        "192.168.137.1",
    ]
    assert join.join_url(request) == "http://pc-prof.local:8000/"
    assert join.choose("192.168.1.20")
    assert join.join_url(request) == "http://192.168.1.20:8000/"


def test_join_url_outside_class_mode_is_the_address_of_the_request(settings, rf):
    settings.LAN_ADDRESSES = []
    settings.JOIN_URL = ""
    request = rf.get("/", HTTP_HOST="localhost:8765")
    assert join.join_url(request) == "http://localhost:8765/"
    assert not join.choose("192.168.1.20")


def test_a_choice_no_longer_offered_is_ignored(settings, rf):
    settings.LAN_ADDRESSES = LAN
    settings.JOIN_URL = "http://192.168.1.20:8000/"
    cache.set(join.CHOICE_KEY, "10.0.0.9")
    assert join.join_url(rf.get("/")) == "http://192.168.1.20:8000/"


def test_with_host_keeps_scheme_and_port():
    assert join.with_host("http://a:8000/", "b") == "http://b:8000/"
    assert join.with_host("https://a/", "b") == "https://b/"


def test_trial_token(client, teacher):
    token = join.new_trial()
    assert len(token) >= 16
    state = reverse("trial-state", args=[token])
    assert teacher.get(state).json() == {"connected": False}
    page = client.get(reverse("trial", args=[token]))
    assert page.status_code == 200
    assert "Connexion réussie" in page.text
    assert teacher.get(state).json() == {"connected": True}
    assert client.post(reverse("trial", args=[token])).status_code == 405


def test_unknown_trial_token(client, teacher):
    assert client.get(reverse("trial", args=["inconnu"])).status_code == 404
    assert teacher.get(reverse("trial-state", args=["inconnu"])).status_code == 404


@pytest.mark.parametrize("platform", ["linux", "win32"])
def test_the_firewall_is_never_opened_only_probed(teacher, settings, monkeypatch, platform):
    """CLA-03 : détection, conseils et page « Réseau » ne lancent que les sondes `PROBES`.
    `subprocess.Popen` porte `run`, `call`, `check_output` et `os.popen` ; `os.system` et
    `os.posix_spawn` sont interceptés à part. Toute autre commande fait échouer le test."""
    settings.LAN_ADDRESSES = LAN
    settings.JOIN_URL = "http://192.168.1.20:8000/"
    launched: list[list[str]] = []

    class FakePopen:
        returncode = 0

        def __init__(self, args, **kwargs):
            launched.append(list(args))
            self.args = args
            self.text = kwargs.get("text") or kwargs.get("encoding")

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def communicate(self, input=None, timeout=None):  # signature de Popen
            out = '{"NetworkCategory":0}'
            return (out, "") if self.text else (out.encode(), b"")

        def poll(self):
            return 0

        def wait(self, timeout=None):
            return 0

        def kill(self):
            pass

    def forbidden(*args, **kwargs):
        pytest.fail(f"commande lancée hors des sondes : {args}")

    monkeypatch.setattr(subprocess, "Popen", FakePopen)
    for name in ("system", "posix_spawn", "posix_spawnp"):
        monkeypatch.setattr(os, name, forbidden, raising=False)
    monkeypatch.setattr(firewall, "ufw_enabled", lambda: True)
    monkeypatch.setattr(sys, "platform", platform)

    found = firewall.detect()
    assert found == (["ufw", "firewalld"] if platform == "linux" else ["windows-public"])
    advices = firewall.advices(8000)  # port de JOIN_URL, celui que la page affiche
    response = teacher.get(reverse("network"))
    assert response.status_code == 200
    for advice in advices:
        for command in advice.commands:
            assert escape(command) in response.text  # affichée, à copier
    assert launched, "aucune sonde lancée : le test ne vérifie rien"
    assert all(command in firewall.PROBES for command in launched), launched
