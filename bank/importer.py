"""Import d'un fichier AMC-TXT analysé (IMP-01, IMP-07) : questions partagées, QCM ordonné.

Les questions nouvelles sont créées par `QuestionForm`, avec les mêmes règles que l'interface.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from django.db import transaction

from bank.amc_txt import ParsedChoice, ParsedFile, ParsedQuestion, parse
from bank.forms import SLOTS, QuestionForm
from bank.models import SOURCE_NAME_MAX_LENGTH, Question, Quiz, QuizItem
from bank.scoring import plain

NOTHING_TO_IMPORT = "Aucune question de ce fichier ne peut être importée."


class AlreadyImported(ValueError):
    """Le même fichier, octet pour octet, a déjà donné un QCM (IMP-07)."""

    def __init__(self, quiz: Quiz) -> None:
        super().__init__(f"Fichier déjà importé : QCM « {quiz.title} ».")
        self.quiz = quiz


@dataclass(frozen=True)
class Preview:
    parsed: ParsedFile
    sha256: str
    shared: tuple[bool, ...]  # par question : déjà dans la banque, elle sera partagée

    @property
    def existing(self) -> int:
        return sum(self.shared)

    def rows(self) -> list[tuple[ParsedQuestion, bool]]:
        return list(zip(self.parsed.questions, self.shared, strict=True))


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def key_of(question: Question) -> tuple:
    """Même clé que `ParsedQuestion.key`, pour une question de la banque."""
    choices = tuple(ParsedChoice(c.text, c.correct, c.points) for c in question.choices.all())
    multiple = question.kind == Question.Kind.MULTIPLE
    return (
        multiple,
        question.text,
        choices,
        question.scoring,
        question.none_of_these,
        question.ordered,
    )


def find_existing(question: ParsedQuestion) -> Question | None:
    """La question identique de la banque (IMP-07), la plus ancienne s'il y en a plusieurs."""
    kind = Question.Kind.MULTIPLE if question.multiple else Question.Kind.SIMPLE
    candidates = Question.objects.filter(text=question.text, kind=kind).prefetch_related("choices")
    return next((c for c in candidates if key_of(c) == question.key()), None)


def preview(data: bytes, filename: str) -> Preview:
    """Analyse sans rien créer ; `AmcSyntaxError` ou `AlreadyImported` si le fichier est refusé."""
    digest = sha256(data)
    if quiz := Quiz.objects.filter(source_sha256=digest).first():
        raise AlreadyImported(quiz)
    parsed = parse(data, filename)
    shared = tuple(find_existing(q) is not None for q in parsed.questions)
    return Preview(parsed, digest, shared)


def form_data(question: ParsedQuestion) -> dict[str, str]:
    data = {
        "text": question.text,
        "kind": Question.Kind.MULTIPLE if question.multiple else Question.Kind.SIMPLE,
        "scoring": question.scoring,
    }
    data |= {"none_of_these": "on"} if question.none_of_these else {}
    data |= {"ordered": "on"} if question.ordered else {}
    for letter, choice in zip(SLOTS, question.choices, strict=False):
        data[f"choice_{letter}"] = choice.text
        data |= {f"correct_{letter}": "on"} if choice.correct else {}
        data |= {} if choice.points is None else {f"points_{letter}": str(plain(choice.points))}
    return data


def create_question(question: ParsedQuestion) -> Question:
    form = QuestionForm(form_data(question))
    if not form.is_valid():  # l'analyse écarte déjà ce que le formulaire refuserait
        raise ValueError(f"Question de la ligne {question.line} refusée : {form.errors.as_text()}")
    form.instance.amc_group = question.label
    return form.save()


@transaction.atomic
def import_quiz(data: bytes, filename: str) -> Quiz:
    """Crée le QCM, ses questions nouvelles, et partage celles déjà dans la banque."""
    found = preview(data, filename)
    if not found.parsed.questions:
        raise ValueError(NOTHING_TO_IMPORT)
    quiz = Quiz.objects.create(
        title=found.parsed.title,
        source_name=filename[:SOURCE_NAME_MAX_LENGTH],
        source_sha256=found.sha256,
    )
    QuizItem.objects.bulk_create(
        QuizItem(quiz=quiz, question=find_existing(q) or create_question(q), position=position)
        for position, q in enumerate(found.parsed.questions, start=1)
    )
    return quiz
