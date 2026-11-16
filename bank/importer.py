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
from bank.scoring import format_points

NOTHING_TO_IMPORT = "Aucune question de ce fichier ne peut être importée."
MATCH_BATCH = 500


class AlreadyImported(ValueError):
    """Le même fichier, octet pour octet, a déjà donné un QCM (IMP-07)."""

    def __init__(self, quiz: Quiz) -> None:
        super().__init__(f"Fichier déjà importé : QCM « {quiz.title} ».")
        self.quiz = quiz


@dataclass(frozen=True)
class Preview:
    parsed: ParsedFile
    sha256: str
    matches: tuple[Question | None, ...]  # par question : l'identique de la banque, partagée

    @property
    def existing(self) -> int:
        return sum(match is not None for match in self.matches)

    def rows(self) -> list[tuple[ParsedQuestion, bool]]:
        rows = zip(self.parsed.questions, self.matches, strict=True)
        return [(question, match is not None) for question, match in rows]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def key_of(question: Question) -> ParsedQuestion:
    """La clé de `ParsedQuestion.key`, pour une question de la banque."""
    return ParsedQuestion(
        line=0,
        text=question.text,
        multiple=question.kind == Question.Kind.MULTIPLE,
        scoring=question.scoring,
        choices=tuple(ParsedChoice(c.text, c.correct, c.points) for c in question.choices.all()),
        none_of_these=question.none_of_these,
        ordered=question.ordered,
    )


def find_existing(questions: tuple[ParsedQuestion, ...]) -> tuple[Question | None, ...]:
    """Pour chaque question, l'identique de la banque (IMP-07), la plus ancienne s'il y en a
    plusieurs. Une requête par tranche d'énoncés : SQLite limite le nombre de paramètres."""
    texts = sorted({q.text for q in questions})
    bank: dict[ParsedQuestion, Question] = {}
    for start in range(0, len(texts), MATCH_BATCH):
        candidates = Question.objects.filter(text__in=texts[start : start + MATCH_BATCH])
        for candidate in candidates.order_by("pk").prefetch_related("choices"):
            bank.setdefault(key_of(candidate), candidate)
    return tuple(bank.get(q.key()) for q in questions)


def preview(data: bytes, filename: str) -> Preview:
    """Analyse sans rien créer ; `AmcSyntaxError` ou `AlreadyImported` si le fichier est refusé."""
    digest = sha256(data)
    if quiz := Quiz.objects.filter(source_sha256=digest).first():
        raise AlreadyImported(quiz)
    parsed = parse(data, filename)
    return Preview(parsed, digest, find_existing(parsed.questions))


def form_data(question: ParsedQuestion) -> dict[str, str]:
    data = {
        "text": question.text,
        "kind": Question.Kind.MULTIPLE if question.multiple else Question.Kind.SIMPLE,
        "scoring": question.scoring,
    }
    if question.none_of_these:
        data["none_of_these"] = "on"
    if question.ordered:
        data["ordered"] = "on"
    for letter, choice in zip(SLOTS, question.choices, strict=False):
        data[f"choice_{letter}"] = choice.text
        if choice.correct:
            data[f"correct_{letter}"] = "on"
        if points := format_points(choice.points):
            data[f"points_{letter}"] = points
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
    rows = zip(found.parsed.questions, found.matches, strict=True)
    QuizItem.objects.bulk_create(
        QuizItem(quiz=quiz, question=match or create_question(q), position=position)
        for position, (q, match) in enumerate(rows, start=1)
    )
    return quiz
