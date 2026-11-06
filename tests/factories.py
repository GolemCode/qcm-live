"""Données de test fictives créées directement en base.

À réserver aux *préconditions* : quand un test vérifie la création elle-même, il passe par
l'interface (tests/e2e/bank_ui.py).
"""

from __future__ import annotations

from collections.abc import Sequence

from bank.models import Choice, Question, Quiz, QuizItem

YES_NO = (("oui", True), ("non", False))


def make_question(
    text: str, choices: Sequence[tuple[str, bool]] = YES_NO, *, multiple: bool = False
) -> Question:
    kind = Question.Kind.MULTIPLE if multiple else Question.Kind.SIMPLE
    question = Question.objects.create(text=text, kind=kind)
    Choice.objects.bulk_create(
        Choice(question=question, text=label, correct=correct, position=position)
        for position, (label, correct) in enumerate(choices)
    )
    return question


def make_quiz(title: str, questions: Sequence[Question], **scale) -> Quiz:
    quiz = Quiz.objects.create(title=title, **scale)
    QuizItem.objects.bulk_create(
        QuizItem(quiz=quiz, question=question, position=position)
        for position, question in enumerate(questions, start=1)
    )
    return quiz
