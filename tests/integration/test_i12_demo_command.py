"""Commande `demo` (DEM-02), appelée dans le processus de test pour la couverture du code."""

import re
from io import StringIO

import pytest
from django.contrib.auth import authenticate
from django.core.management import call_command

from bank.models import Quiz
from roster.models import StudentGroup

pytestmark = pytest.mark.django_db


def demo() -> str:
    out = StringIO()
    call_command("demo", stdout=out)
    match = re.search(r"^Mot de passe : (\S+)$", out.getvalue(), re.MULTILINE)
    assert match, out.getvalue()
    return match.group(1)


def test_demo_creates_then_reuses_and_changes_the_password():
    first = demo()
    assert authenticate(username="demo", password=first)
    quiz, group = Quiz.objects.get(), StudentGroup.objects.get()
    assert (group.name, group.students.count()) == ("Démo", 6)
    second = demo()
    assert second != first
    assert authenticate(username="demo", password=first) is None
    assert authenticate(username="demo", password=second)
    assert (Quiz.objects.get(), StudentGroup.objects.get()) == (quiz, group)
