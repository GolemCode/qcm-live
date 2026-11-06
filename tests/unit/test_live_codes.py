"""Identifiant de session : toujours 6 chiffres, zéros de tête compris."""

from live import models
from live.models import random_code


def test_code_keeps_leading_zeros(monkeypatch):
    monkeypatch.setattr(models.secrets, "randbelow", lambda n: 42)
    assert random_code() == "000042"


def test_code_is_six_digits():
    for _ in range(100):
        code = random_code()
        assert len(code) == 6 and code.isdigit()
