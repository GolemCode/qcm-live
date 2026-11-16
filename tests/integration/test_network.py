"""Réseau et téléphones (CLA-02 à CLA-04), via le client Django : choix d'une adresse, essai
d'un téléphone, accès."""

from __future__ import annotations

import pytest
from django.core.cache import cache
from django.urls import reverse

from config import join

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
    assert join.projected_port(request) == 8000


def test_join_url_outside_class_mode_is_the_address_of_the_request(settings, rf):
    settings.LAN_ADDRESSES = []
    settings.JOIN_URL = ""
    request = rf.get("/", HTTP_HOST="localhost:8765")
    assert join.join_url(request) == "http://localhost:8765/"
    assert not join.choose("192.168.1.20")
    assert join.projected_port(request) == 8765


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
