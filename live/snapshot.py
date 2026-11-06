"""Copies figées, au lancement d'une session, du QCM et de la liste du groupe (SES-03).

La session ne dépend plus ensuite ni de la banque ni des groupes : les modifier ou les
supprimer ne change rien à une session lancée. Les types décrivent le JSON enregistré.
"""

from __future__ import annotations

from typing import TypedDict

from bank.models import Quiz
from roster.models import StudentGroup


class FrozenChoice(TypedDict):
    text: str
    correct: bool


class FrozenQuestion(TypedDict):
    ref: str  # référence stable de la question (QR code, I6), même si elle est supprimée
    text: str
    multiple: bool
    choices: list[FrozenChoice]  # ordre canonique : A, B, C… au tableau


class FrozenQuiz(TypedDict):
    scales: dict[str, dict[str, str | None]]  # bank.scoring.Scale.to_json, par type
    questions: list[FrozenQuestion]  # ordre du QCM


class FrozenStudent(TypedDict):
    number: str
    name: str


def freeze_quiz(quiz: Quiz) -> FrozenQuiz:
    return {
        "scales": {kind: scale.to_json() for kind, scale in quiz.scales().items()},
        "questions": [
            {
                "ref": f"Q{question.pk}",
                "text": question.text,
                "multiple": question.kind == question.Kind.MULTIPLE,
                "choices": [
                    {"text": choice.text, "correct": choice.correct}
                    for choice in question.choices.all()
                ],
            }
            for question in quiz.ordered_questions().prefetch_related("choices")
        ],
    }


def freeze_group(group: StudentGroup) -> list[FrozenStudent]:
    """Étudiants dans l'ordre du fichier importé."""
    return [{"number": s.number, "name": s.name} for s in group.students.all()]
