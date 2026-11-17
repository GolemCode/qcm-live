"""Copies figées, au lancement d'une session, du QCM et de la liste du groupe (SES-03).

La session ne dépend plus ensuite ni de la banque ni des groupes : les modifier ou les
supprimer ne change rien à une session lancée. Les types décrivent le JSON enregistré.
"""

from __future__ import annotations

from typing import TypedDict

from bank.models import NONE_OF_THESE, Question, Quiz
from bank.scoring import format_points
from roster.models import StudentGroup


class FrozenChoice(TypedDict):
    text: str
    correct: bool
    points: str | None  # valeur propre (décimal en texte), question simple ; None : b ou m
    none: bool  # « Aucune de ces réponses n'est correcte » (BAN-09), toujours en dernier


class FrozenQuestion(TypedDict):
    text: str
    multiple: bool
    ordered: bool  # BAN-10 : propositions non mélangées sur les téléphones
    scoring: str  # directives AMC, relues par bank.scoring.parse_scoring
    choices: list[FrozenChoice]  # ordre canonique, celui de la banque : A, B, C…


class FrozenQuiz(TypedDict):
    questions: list[FrozenQuestion]  # ordre du QCM


class FrozenStudent(TypedDict):
    list_number: int  # n° de liste : l'identifiant de l'étudiant dans la session (I14)
    student_number: str  # vide s'il manque ; jamais montré sur un téléphone
    name: str


def freeze_question(question: Question) -> FrozenQuestion:
    choices: list[FrozenChoice] = [
        {
            "text": choice.text,
            "correct": choice.correct,
            "points": format_points(choice.points) or None,
            "none": False,
        }
        for choice in question.choices.all()
    ]
    if question.none_of_these:
        right = question.none_is_correct
        choices.append({"text": NONE_OF_THESE, "correct": right, "points": None, "none": True})
    return {
        "text": question.text,
        "multiple": question.kind == question.Kind.MULTIPLE,
        "ordered": question.ordered,
        "scoring": question.scoring,
        "choices": choices,
    }


def freeze_quiz(quiz: Quiz) -> FrozenQuiz:
    questions = quiz.ordered_questions().prefetch_related("choices")
    return {"questions": [freeze_question(question) for question in questions]}


def freeze_group(group: StudentGroup) -> list[FrozenStudent]:
    """Étudiants par n° de liste : `Session.students` garde cet ordre (et la migration
    live.0006 numérote les anciennes listes dans leur ordre enregistré)."""
    return [
        {"list_number": s.list_number, "student_number": s.student_number, "name": s.name}
        for s in group.students.order_by("list_number")
    ]
