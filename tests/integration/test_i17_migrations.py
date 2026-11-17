"""Migration d'I17 : un énoncé ou une proposition d'avant I17, banque et copie figée d'une
session, s'affiche à l'identique une fois lu en LaTeX léger (CNT-01 à CNT-04)."""

import pytest

from bank.content import Text, parse
from bank.models import Choice, Question
from live.models import Session
from tests.migrations import leaves, migrate

BEFORE = [("bank", "0006_image"), ("live", "0008_extension_seconds_session_group_year")]
OLD = "Prix : 5 $ et C:\\temp\\$x$ ?"
OLD_CHOICE = "a \\\\ b"

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def old_apps():
    apps = migrate(BEFORE)
    yield apps
    migrate(leaves())


def old_data(apps):
    question = apps.get_model("bank", "Question").objects.create(text=OLD)
    question.choices.create(text=OLD_CHOICE, correct=True, position=0)
    question.choices.create(text="Sans rien", correct=False, position=1)
    choices = [{"text": OLD_CHOICE, "correct": True, "points": None, "none": False}]
    content = {
        "questions": [
            {"text": OLD, "multiple": False, "ordered": False, "scoring": "", "choices": choices}
        ]
    }
    apps.get_model("live", "Session").objects.create(
        code="333333",
        quiz_title="Ancien",
        group_name="TD1",
        content=content,
        roster=[],
        n_questions=1,
        shown=1,
        seconds=10,
    )


def test_old_texts_show_unchanged(old_apps):
    old_data(old_apps)
    migrate(leaves())
    question = Question.objects.get()
    assert parse(question.text) == [Text(OLD)]
    choices = [choice.text for choice in Choice.objects.order_by("position")]
    assert parse(choices[0]) == [Text(OLD_CHOICE)]
    assert choices[1] == "Sans rien"
    frozen = Session.objects.get().content["questions"][0]
    assert frozen["text"] == question.text
    assert frozen["choices"][0]["text"] == choices[0]


def test_backward_restores_the_old_texts(old_apps):
    old_data(old_apps)
    migrate(leaves())
    apps = migrate(BEFORE)
    assert apps.get_model("bank", "Question").objects.get().text == OLD
    choice = apps.get_model("bank", "Choice").objects.get(position=0)
    assert choice.text == OLD_CHOICE
    frozen = apps.get_model("live", "Session").objects.get().content["questions"][0]
    assert (frozen["text"], frozen["choices"][0]["text"]) == (OLD, OLD_CHOICE)
