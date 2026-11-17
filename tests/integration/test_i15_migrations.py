"""Migration d'I15 (VER-01) : une session lancée avant I15 est rattachée aux questions de la
banque dont le contenu n'a pas changé depuis son lancement.

Le test ramène la base à l'état d'avant I15, y crée des questions et une session au format
ancien (copie figée seule), puis applique les migrations jusqu'au bout.
"""

import pytest

from bank.models import Question
from live.models import Session
from tests.migrations import leaves, migrate

BEFORE = [("bank", "0003_pending_import"), ("live", "0006_participant_list_number")]

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def old_apps():
    apps = migrate(BEFORE)
    yield apps
    migrate(leaves())


def frozen(text, choices, *, multiple=False, scoring="", none=None):
    out = [{"text": t, "correct": c, "points": p, "none": False} for t, c, p in choices]
    if none is not None:
        out.append(
            {
                "text": "Aucune de ces réponses n'est correcte",
                "correct": none,
                "points": None,
                "none": True,
            }
        )
    return {
        "text": text,
        "multiple": multiple,
        "ordered": False,
        "scoring": scoring,
        "choices": out,
    }


def old_question(apps, text, choices, *, kind="simple", scoring="", none_of_these=False):
    question = apps.get_model("bank", "Question").objects.create(
        text=text, kind=kind, scoring=scoring, none_of_these=none_of_these
    )
    for position, (label, correct, points) in enumerate(choices):
        question.choices.create(text=label, correct=correct, points=points, position=position)
    return question


@pytest.mark.spec("VER-01")
def test_old_sessions_are_linked_to_unchanged_questions(old_apps):
    same = old_question(old_apps, "Inchangée ?", [("a", True, None), ("b", False, None)])
    points = old_question(old_apps, "Points ?", [("a", True, "2.000"), ("b", False, "-1.000")])
    multi = old_question(
        old_apps,
        "Multiple ?",
        [("x", True, None), ("y", False, None)],
        kind="multiple",
        scoring="b=2",
        none_of_these=True,
    )
    changed = old_question(old_apps, "Modifiée ?", [("a", True, None), ("b", False, None)])
    old_question(old_apps, "Autre ?", [("a", True, None), ("b", False, None)])
    content = {
        "questions": [
            frozen("Inchangée ?", [("a", True, None), ("b", False, None)]),
            frozen("Points ?", [("a", True, "2"), ("b", False, "-1")]),
            frozen(
                "Multiple ?",
                [("x", True, None), ("y", False, None)],
                multiple=True,
                scoring="b=2",
                none=False,
            ),
            # Modifiée après le lancement : propositions dans un autre ordre.
            frozen("Modifiée ?", [("b", False, None), ("a", True, None)]),
            frozen("Supprimée ?", [("a", True, None), ("b", False, None)]),
        ]
    }
    old_apps.get_model("live", "Session").objects.create(
        code="222222",
        quiz_title="Contrôle",
        group_name="TD1",
        content=content,
        roster=[],
        n_questions=5,
        shown=1,
        seconds=10,
    )

    migrate(leaves())

    linked = Session.objects.get(code="222222").source_questions.order_by("pk")
    assert list(linked.values_list("pk", flat=True)) == [same.pk, points.pk, multi.pk]
    assert not Question.objects.get(pk=changed.pk).sessions.exists()
