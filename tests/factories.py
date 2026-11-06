"""Données de test fictives créées en base, en passant par les formulaires de l'application.

Passer par les formulaires garantit que les préconditions respectent les mêmes règles que
l'interface : une fabrique ne peut pas produire une donnée que l'enseignant ne pourrait pas
créer. À réserver aux *préconditions* : quand un test vérifie la création elle-même, il passe
par l'interface (tests/e2e/bank_ui.py).
"""

from __future__ import annotations

from collections.abc import Sequence

from bank.forms import LETTERS, QuestionForm, QuizForm
from bank.models import AMC_DEFAULTS, Question, Quiz

YES_NO = (("oui", True), ("non", False))


def _saved(form):
    assert form.is_valid(), form.errors
    return form.save()


def make_question(
    text: str, choices: Sequence[tuple[str, bool]] = YES_NO, *, multiple: bool = False
) -> Question:
    data = {"text": text, "kind": Question.Kind.MULTIPLE if multiple else Question.Kind.SIMPLE}
    for letter, (label, correct) in zip(LETTERS, choices, strict=False):
        data[f"choice_{letter}"] = label
        if correct:
            data[f"correct_{letter}"] = "on"
    return _saved(QuestionForm(data))


def make_quiz(title: str, questions: Sequence[Question], **scale: str) -> Quiz:
    defaults = {"b": AMC_DEFAULTS.b, "m": AMC_DEFAULTS.m, "v": AMC_DEFAULTS.v}
    data = {
        f"{kind}_{key}": value for kind in ("simple", "multiple") for key, value in defaults.items()
    }
    data |= {"title": title, **scale}
    data |= {QuizForm.order_field(q): position for position, q in enumerate(questions, start=1)}
    return _saved(QuizForm(data))
