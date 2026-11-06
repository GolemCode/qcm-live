"""Copies figées, au lancement d'une session, du QCM et de la liste du groupe (SES-03).

La session ne dépend plus ensuite ni de la banque ni des groupes : les modifier ou les
supprimer ne change rien à une session lancée.
"""

from __future__ import annotations

from bank.models import Quiz
from roster.models import StudentGroup


def freeze_quiz(quiz: Quiz) -> dict:
    """Questions dans l'ordre du QCM, propositions dans l'ordre canonique (A, B…), barème."""
    return {
        "scales": {
            "simple": {
                "b": str(quiz.simple_b),
                "m": str(quiz.simple_m),
                "v": str(quiz.simple_v),
                "p": None,
            },
            "multiple": {
                "b": str(quiz.multiple_b),
                "m": str(quiz.multiple_m),
                "v": str(quiz.multiple_v),
                "p": None if quiz.multiple_p is None else str(quiz.multiple_p),
            },
        },
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


def freeze_group(group: StudentGroup) -> list[dict[str, str]]:
    """Étudiants dans l'ordre du fichier importé."""
    return [{"number": s.number, "name": s.name} for s in group.students.all()]
