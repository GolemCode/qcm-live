"""Migrations d'I12 (BAR-01) : le barème d'un QCM passe à ses questions, et une session déjà
lancée garde les mêmes notes.

Chaque test ramène la base à l'état d'avant I12, y crée des données au format ancien, puis
applique les migrations.
"""

from decimal import Decimal as D

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from live.results import grade, max_total

BEFORE = [("bank", "0001_initial"), ("live", "0004_extension")]
AFTER = [("bank", "0002_question_scoring"), ("live", "0005_frozen_question_scoring")]

pytestmark = pytest.mark.django_db(transaction=True)


def migrate(targets):
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(targets)
    return executor.loader.project_state(targets).apps


@pytest.fixture
def old_apps():
    apps = migrate(BEFORE)
    yield apps
    migrate(executor_leaves())


def executor_leaves():
    return MigrationExecutor(connection).loader.graph.leaf_nodes()


def old_question(apps, text, kind, choices):
    question = apps.get_model("bank", "Question").objects.create(text=text, kind=kind)
    for position, correct in enumerate(choices):
        question.choices.create(text=f"{text}-{position}", correct=correct, position=position)
    return question


def test_each_question_takes_the_scoring_of_its_oldest_quiz(old_apps):
    Quiz = old_apps.get_model("bank", "Quiz")
    QuizItem = old_apps.get_model("bank", "QuizItem")
    simple = old_question(old_apps, "S", "simple", [True, False])
    multiple = old_question(old_apps, "M", "multiple", [True, True, False])
    alone = old_question(old_apps, "Seule", "simple", [True, False])
    first = Quiz.objects.create(
        title="Ancien", simple_b=D(2), simple_m=D("-0.5"), multiple_m=D(-1), multiple_p=D(0)
    )
    second = Quiz.objects.create(title="Récent", simple_b=D(5), multiple_b=D(3))
    for quiz in (second, first):  # ordre de création des liens sans effet
        for position, question in enumerate((simple, multiple), start=1):
            QuizItem.objects.create(quiz=quiz, question=question, position=position)

    apps = migrate(AFTER)

    Question = apps.get_model("bank", "Question")
    assert Question.objects.get(pk=simple.pk).scoring == "b=2,m=-0.5"
    assert Question.objects.get(pk=multiple.pk).scoring == "m=-1,p=0"
    assert Question.objects.get(pk=alone.pk).scoring == ""
    assert not hasattr(apps.get_model("bank", "Quiz")(), "simple_b")


def old_content(scales):
    return {
        "scales": scales,
        "questions": [
            {
                "text": "S",
                "multiple": False,
                "choices": [{"text": "a", "correct": True}, {"text": "b", "correct": False}],
            },
            {
                "text": "M",
                "multiple": True,
                "choices": [
                    {"text": "x", "correct": True},
                    {"text": "y", "correct": True},
                    {"text": "z", "correct": False},
                ],
            },
        ],
    }


SCALES = [
    # Barème d'origine, b=1, m=0, v=0 (I6 enregistrait les valeurs en texte, deux décimales).
    {
        "simple": {"b": "1.00", "m": "0.00", "v": "0.00", "p": None},
        "multiple": {"b": "1.00", "m": "0.00", "v": "0.00", "p": None},
    },
    {
        "simple": {"b": "2.00", "m": "-0.50", "v": "-0.25", "p": None},
        "multiple": {"b": "0.50", "m": "-1.00", "v": "-1.00", "p": "-2.00"},
    },
    # Plancher au-dessus de la note maximale : la note maximale ancienne est gardée (MAX).
    {
        "simple": {"b": "1.00", "m": "0.00", "v": "0.00", "p": None},
        "multiple": {"b": "1.00", "m": "0.00", "v": "0.00", "p": "5.00"},
    },
]


def old_marks(scales, answers):
    """Notes et maximum calculés comme avant I12 (b/m/v par type, plancher p des multiples)."""
    s, m = ({k: D(scales[t][k]) for k in "bmv"} for t in ("simple", "multiple"))
    floor = scales["multiple"]["p"]
    simple = s["v"] if 0 not in answers else s["b"] if answers[0] == [0] else s["m"]
    chosen = answers.get(1)
    if not chosen:
        multiple = m["v"]
    else:
        boxes = sum(m["b"] if (i in chosen) == (i in (0, 1)) else m["m"] for i in range(3))
        multiple = boxes if floor is None else max(boxes, D(floor))
    return [simple, multiple], s["b"] + 3 * m["b"]


@pytest.mark.parametrize("scales", SCALES)
def test_a_frozen_session_keeps_its_marks(old_apps, scales):
    Session = old_apps.get_model("live", "Session")
    session = Session.objects.create(
        code="123456",
        quiz_title="Q",
        group_name="G",
        content=old_content(scales),
        roster=[],
        n_questions=2,
        shown=1,
        seconds=10,
    )

    apps = migrate(AFTER)

    content = apps.get_model("live", "Session").objects.get(pk=session.pk).content
    assert "scales" not in content
    assert [q["ordered"] for q in content["questions"]] == [False, False]
    assert all(
        c == c | {"points": None, "none": False} for q in content["questions"] for c in q["choices"]
    )
    for answers in ({}, {0: [0], 1: [0, 1]}, {0: [1], 1: [2]}, {1: [0]}, {1: [0, 1, 2]}):
        marks, maximum = old_marks(scales, answers)
        assert [mark.points for mark in grade(content, answers)] == marks, answers
        assert max_total(content) == maximum
