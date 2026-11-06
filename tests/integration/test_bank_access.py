"""Banque et QCM : réservés à l'enseignant connecté ; suppression uniquement en POST."""

import pytest
from django.urls import reverse

from bank.models import Choice, Question, Quiz, QuizItem

pytestmark = pytest.mark.django_db


@pytest.fixture
def quiz():
    question = Question.objects.create(text="Q", kind=Question.Kind.SIMPLE)
    Choice.objects.create(question=question, text="oui", correct=True, position=0)
    Choice.objects.create(question=question, text="non", correct=False, position=1)
    quiz = Quiz.objects.create(title="QCM")
    QuizItem.objects.create(quiz=quiz, question=question, position=1)
    return quiz


def bank_urls(quiz):
    question = quiz.questions.get()
    return [
        reverse("question-list"),
        reverse("question-create"),
        reverse("question-update", args=[question.pk]),
        reverse("question-delete", args=[question.pk]),
        reverse("quiz-list"),
        reverse("quiz-create"),
        reverse("quiz-detail", args=[quiz.pk]),
        reverse("quiz-update", args=[quiz.pk]),
        reverse("quiz-delete", args=[quiz.pk]),
    ]


@pytest.mark.parametrize("method", ["get", "post"])
def test_anonymous_is_redirected_to_login(client, quiz, method):
    for url in bank_urls(quiz):
        response = getattr(client, method)(url)
        assert response.status_code == 302, url
        assert response["Location"].startswith(reverse("login")), url
    assert Question.objects.count() == 1
    assert Quiz.objects.count() == 1


def test_get_on_delete_only_asks_for_confirmation(admin_client, quiz):
    question = quiz.questions.get()
    assert admin_client.get(reverse("question-delete", args=[question.pk])).status_code == 200
    assert admin_client.get(reverse("quiz-delete", args=[quiz.pk])).status_code == 200
    assert Question.objects.count() == 1
    assert Quiz.objects.count() == 1


def test_unknown_objects_give_404(admin_client):
    assert admin_client.get(reverse("question-update", args=[999])).status_code == 404
    assert admin_client.get(reverse("quiz-detail", args=[999])).status_code == 404


def test_quiz_scales_feed_scoring(quiz):
    quiz.multiple_p = -1
    simple, multiple = quiz.simple_scale(), quiz.multiple_scale()
    assert (simple.b, simple.m, simple.v, simple.p) == (1, 0, 0, None)
    assert multiple.p == -1
