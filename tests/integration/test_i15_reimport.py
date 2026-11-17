"""I15 : cas limites du réimport (IMP-10) et du retrait d'une question (CMP-05)."""

import pytest
from django.urls import reverse

from bank.forms import QuestionForm
from bank.importer import import_quiz, preview
from bank.models import Question

pytestmark = pytest.mark.django_db

FILE = b"""* Alpha ?
+ a
- b

* Beta ?
+ c
- d

* Gamma ?
+ e
- f
"""


def test_question_of_a_later_rank_is_not_taken_by_an_earlier_one():
    # La question du rang 3, modifiée sur place, prend le contenu du rang 1, supprimé : le
    # rang 1 ne doit pas la prendre au rang 3 (sinon le rang 3 serait recréé en double).
    quiz = import_quiz(FILE, "f.txt")
    alpha, _, gamma = quiz.ordered_questions()
    alpha.delete()
    data = {"text": "Alpha ?", "kind": "simple", "choice_A": "a", "correct_A": "on"}
    form = QuestionForm(data | {"choice_B": "b"}, instance=gamma)
    assert form.is_valid()
    form.save()
    found = preview(FILE, "f.txt")
    assert found.matches[0] is None
    assert found.matches[2] == gamma
    import_quiz(FILE, "f.txt")
    assert list(quiz.ordered_questions().values_list("text", flat=True)) == [
        "Alpha ?",
        "Beta ?",
        "Alpha ?",
    ]
    assert Question.objects.count() == 3


def test_removing_a_question_not_in_the_quiz_is_404(admin_client):
    quiz = import_quiz(FILE, "f.txt")
    other = Question.objects.create(text="Ailleurs ?")
    url = reverse("quiz-remove", args=[quiz.pk, other.pk])
    assert admin_client.post(url).status_code == 404
    assert quiz.questions.count() == 3
