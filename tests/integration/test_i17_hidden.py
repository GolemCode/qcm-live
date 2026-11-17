"""I17 : cas limites d'une question masquée (BAN-07) : ni modifiable, ni réimportée."""

import pytest
from django.urls import reverse
from django.utils import timezone

from bank.importer import import_quiz
from bank.models import Question
from tests.factories import make_group, make_session

pytestmark = pytest.mark.django_db

FILE = b"""* Alpha ?
+ a
- b

* Beta ?
+ c
- d
"""


def masked_alpha():
    """Le QCM importé de FILE, lancé et démarré, puis sa question Alpha supprimée."""
    quiz = import_quiz(FILE, "f.txt")
    session = make_session(quiz, make_group("ITI4", [(1, "1", "A")], "2025-2026"))
    session.start(timezone.now())
    alpha = quiz.ordered_questions()[0]
    alpha.remove()
    alpha.refresh_from_db()
    assert alpha.hidden
    return quiz, alpha


def test_hidden_question_cannot_be_edited_nor_deleted(admin_client):
    _, alpha = masked_alpha()
    for name in ("question-update", "question-delete"):
        assert admin_client.get(reverse(name, args=[alpha.pk])).status_code == 404
    assert admin_client.post(reverse("question-delete", args=[alpha.pk])).status_code == 404


def test_reimport_does_not_bring_a_hidden_question_back():
    quiz, alpha = masked_alpha()
    import_quiz(FILE, "f.txt")
    first = quiz.ordered_questions()[0]
    assert first.text == "Alpha ?"
    assert first != alpha
    alpha.refresh_from_db()
    assert alpha.hidden
    assert not alpha.quizzes.exists()


def test_unused_question_is_really_deleted():
    quiz = import_quiz(FILE, "f.txt")
    beta = quiz.ordered_questions()[1]
    beta.remove()
    assert not Question.objects.filter(pk=beta.pk).exists()
