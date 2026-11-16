"""Compte de l'enseignant à l'installation (INS-01), via la base de test."""

from __future__ import annotations

import pytest
from django.contrib.auth import authenticate
from django.contrib.auth.models import User

from config import install

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


def test_interactive_account_cancelled(monkeypatch, capsys):
    monkeypatch.delenv("DJANGO_SUPERUSER_USERNAME", raising=False)
    monkeypatch.delenv("DJANGO_SUPERUSER_PASSWORD", raising=False)

    def cancelled(*args, **kwargs):
        raise SystemExit(1)

    monkeypatch.setattr("django.core.management.call_command", cancelled)
    install.create_account(interactive=True)
    assert "qcm-live compte" in capsys.readouterr().out
