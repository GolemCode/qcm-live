"""Commande `demo` (DEM-02), appelée dans le processus de test pour la couverture du code."""

import re
from io import StringIO

import pytest
from django.contrib.auth import authenticate, get_user_model
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
    # Au format d'I14 (GRP-05) : des n° qui ne se suivent pas, un numéro étudiant vide.
    list_numbers = list(group.students.values_list("list_number", flat=True))
    assert list_numbers != list(range(1, 7))
    assert group.students.filter(student_number="").count() == 1
    second = demo()
    assert second != first
    assert authenticate(username="demo", password=first) is None
    assert authenticate(username="demo", password=second)
    assert (Quiz.objects.get(), StudentGroup.objects.get()) == (quiz, group)


def test_demo_without_account_creates_only_the_quiz_and_the_group():
    """À l'installation (INS-01), l'enseignant a déjà son compte."""
    out = StringIO()
    call_command("demo", "--sans-compte", stdout=out)
    assert "Mot de passe" not in out.getvalue()
    assert not get_user_model().objects.exists()
    assert Quiz.objects.count() == StudentGroup.objects.count() == 1
