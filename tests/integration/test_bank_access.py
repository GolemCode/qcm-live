"""Banque et QCM : réservés à l'enseignant connecté ; suppression uniquement en POST."""

import pytest
from django.urls import reverse

from bank.forms import QuestionForm
from bank.models import Question, Quiz
from tests.factories import make_question, make_quiz

pytestmark = pytest.mark.django_db


@pytest.fixture
def quiz():
    return make_quiz("QCM", [make_question("Q")])


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


def test_invalid_order_number_reports_only_its_own_error(admin_client):
    first, second = make_question("Q-1"), make_question("Q-2")
    response = admin_client.post(
        reverse("quiz-create"),
        {
            "title": "T",
            "simple_b": 1,
            "simple_m": 0,
            "simple_v": 0,
            "multiple_b": 1,
            "multiple_m": 0,
            "multiple_v": 0,
            f"order_{first.pk}": "0",
            f"order_{second.pk}": "",
        },
    )
    errors = response.context["form"].errors
    assert set(errors) == {f"order_{first.pk}"}
    assert Quiz.objects.count() == 0


def test_save_without_commit_writes_nothing():
    form = QuestionForm(
        {"text": "Q", "kind": "simple", "choice_A": "a", "correct_A": "on", "choice_B": "b"}
    )
    assert form.is_valid()
    question = form.save(commit=False)
    assert question.pk is None
    assert Question.objects.count() == 0
