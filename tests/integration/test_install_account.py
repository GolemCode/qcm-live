"""Compte de l'enseignant à l'installation (INS-01), via la base de test."""

from __future__ import annotations

import pytest
from django.contrib.auth import authenticate
from django.contrib.auth.models import User

from config import install, launcher

pytestmark = pytest.mark.django_db


def test_account_from_the_environment(monkeypatch, capsys):
    monkeypatch.setenv("DJANGO_SUPERUSER_USERNAME", "prof")
    monkeypatch.setenv("DJANGO_SUPERUSER_PASSWORD", "mot-de-passe-de-test")
    install.create_account(interactive=False)
    assert authenticate(username="prof", password="mot-de-passe-de-test")
    assert User.objects.get(username="prof").is_superuser
    assert "Compte enseignant créé : prof." in capsys.readouterr().out


def test_without_terminal_nor_environment_the_account_is_left_for_later(monkeypatch, capsys):
    monkeypatch.delenv("DJANGO_SUPERUSER_USERNAME", raising=False)
    monkeypatch.delenv("DJANGO_SUPERUSER_PASSWORD", raising=False)
    install.create_account(interactive=False)
    assert not User.objects.exists()
    assert "qcm-live compte" in capsys.readouterr().out


@pytest.mark.parametrize("typed", [[""], ["prof", KeyboardInterrupt], [EOFError]])
def test_interactive_account_left_for_later(monkeypatch, capsys, typed):
    monkeypatch.delenv("DJANGO_SUPERUSER_USERNAME", raising=False)
    monkeypatch.delenv("DJANGO_SUPERUSER_PASSWORD", raising=False)
    replies = iter(typed)

    def typing(prompt: str = "") -> str:
        reply = next(replies)
        if isinstance(reply, str):
            return reply
        raise reply

    monkeypatch.setattr("builtins.input", typing)
    monkeypatch.setattr("getpass.getpass", typing)
    install.create_account(interactive=True)
    assert not User.objects.exists()
    assert "qcm-live compte" in capsys.readouterr().out


def keyboard(*typed: str):
    """Réponses tapées, dans l'ordre, et questions posées."""
    replies, asked = iter(typed), []

    def answer(prompt: str) -> str:
        asked.append(prompt)
        return next(replies)

    return answer, asked


def test_prompt_account_asks_again_until_the_answers_are_accepted(capsys):
    User.objects.create_user("pris", password="mot-de-passe-de-test")
    read, asked = keyboard("a b!", "pris", " prof ")
    secret, secret_asked = keyboard(
        "Bleu-Tableau-91", "Bleu-Tableau-92",  # diffèrent
        "court", "court",  # trop court
        "12345678901", "12345678901",  # que des chiffres
        "password123", "password123",  # trop courant
        "Bleu-Tableau-91", "Bleu-Tableau-91",
    )  # fmt: skip
    assert launcher.prompt_account(read, secret) == "prof"
    assert asked == ["Identifiant : "] * 3
    assert secret_asked[:2] == [
        "Mot de passe (il ne s'affiche pas) : ",
        "Mot de passe, à nouveau : ",
    ]
    out = capsys.readouterr().out
    assert "utilisateur valide" in out  # refus en français
    assert "Cet identifiant est déjà pris." in out
    assert "Les deux mots de passe diffèrent." in out
    assert "trop court" in out and "entièrement numérique" in out and "trop courant" in out
    assert "Compte enseignant créé : prof." in out
    assert authenticate(username="prof", password="Bleu-Tableau-91")
    assert User.objects.get(username="prof").is_superuser


def test_prompt_account_with_an_empty_username_creates_nothing():
    read, _ = keyboard("  ")
    assert launcher.prompt_account(read, keyboard()[0]) is None
    assert not User.objects.exists()


def test_an_interrupted_first_install_still_asks_for_the_account(monkeypatch, capsys):
    """Relancée après une première installation interrompue (base créée, aucun compte), la
    mise à jour demande encore le compte, sans proposer la démonstration."""
    monkeypatch.setenv("DJANGO_SUPERUSER_USERNAME", "prof")
    monkeypatch.setenv("DJANGO_SUPERUSER_PASSWORD", "mot-de-passe-de-test")
    monkeypatch.setattr(install, "wants_demo", lambda interactive: pytest.fail("démo proposée"))
    install.first_steps(first=False, interactive=False)
    assert User.objects.get(username="prof").is_superuser


def test_an_update_with_an_account_asks_nothing(monkeypatch):
    User.objects.create_superuser("prof", password="mot-de-passe-de-test")
    monkeypatch.setattr(install, "create_account", lambda interactive: pytest.fail("compte"))
    monkeypatch.setattr(install, "wants_demo", lambda interactive: pytest.fail("démo"))
    install.first_steps(first=False, interactive=True)
