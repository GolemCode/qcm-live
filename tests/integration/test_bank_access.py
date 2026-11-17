"""Banque et QCM : réservés à l'enseignant connecté ; suppression uniquement en POST."""

import pytest
from django.urls import reverse

from bank.forms import QuestionForm
from bank.models import Question, Quiz
from bank.scoring import SCORING_MAX_LENGTH
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
        reverse("quiz-import"),
        reverse("quiz-import-recap", args=["jeton"]),
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


def test_box_for_a_question_not_offered_is_ignored(admin_client):
    # CMP-04 (I15) : seules comptent les cases des questions proposées ; l'ancien rang,
    # ou une question inconnue, ne compose rien.
    question = make_question("Q-1")
    response = admin_client.post(
        reverse("quiz-create"),
        {"title": "T", "include_999999": "on", f"order_{question.pk}": "1"},
    )
    assert response.context["form"].non_field_errors() == ["Cochez au moins une question."]
    assert Quiz.objects.count() == 0


def test_save_without_commit_writes_nothing():
    form = QuestionForm(
        {"text": "Q", "kind": "simple", "choice_A": "a", "correct_A": "on", "choice_B": "b"}
    )
    assert form.is_valid()
    question = form.save(commit=False)
    assert question.pk is None
    assert Question.objects.count() == 0


def simple_question(scoring: str) -> dict[str, str]:
    return {
        "text": "Q",
        "kind": "simple",
        "scoring": scoring,
        "choice_A": "a",
        "correct_A": "on",
        "choice_B": "b",
    }


def test_scoring_length_is_checked_once_rewritten():
    limit = "b=." + "0" * 195 + "1"  # 199 caractères ; 200 une fois réécrit en 0.000…1
    form = QuestionForm(simple_question(limit))
    assert form.is_valid(), form.errors
    assert len(form.cleaned_data["scoring"]) == SCORING_MAX_LENGTH
    form = QuestionForm(simple_question("b=." + "0" * 196 + "1"))
    assert form.errors["scoring"] == [
        f"Au plus {SCORING_MAX_LENGTH} caractères une fois réécrit (201 ici)."
    ]
