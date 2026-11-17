"""Import d'un fichier AMC-TXT analysé (IMP-01, IMP-07, IMP-10) : questions partagées, QCM
ordonné, réimport qui complète le QCM du même fichier.

Les questions nouvelles sont créées par `QuestionForm`, avec les mêmes règles que l'interface.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass

from django.db import transaction

from bank.amc_txt import ParsedChoice, ParsedFile, ParsedQuestion, parse
from bank.composition import arrange
from bank.forms import SLOTS, QuestionForm
from bank.models import SOURCE_NAME_MAX_LENGTH, Question, QuestionOrigin, Quiz
from bank.scoring import format_points

NOTHING_TO_IMPORT = "Aucune question de ce fichier ne peut être importée."
MATCH_BATCH = 500


@dataclass(frozen=True)
class Preview:
    parsed: ParsedFile
    sha256: str
    # Par question : celle de la banque qui la donne (reconnue, ou identique et partagée),
    # ou None si elle sera créée.
    matches: tuple[Question | None, ...]
    target: Quiz | None = None  # QCM du même fichier, que l'import complète (IMP-10)
    present: tuple[bool, ...] = ()  # par question : déjà dans `target`

    @property
    def existing(self) -> int:
        return sum(match is not None for match in self.matches)

    @property
    def already_there(self) -> int:
        return sum(self.present)

    @property
    def added(self) -> int:
        return len(self.parsed.questions) - self.already_there

    def rows(self) -> list[tuple[ParsedQuestion, bool]]:
        """(question, partagée) ; pour un réimport, (question, déjà dans le QCM)."""
        flags = self.present if self.target else [m is not None for m in self.matches]
        return list(zip(self.parsed.questions, flags, strict=True))


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


def find_existing(questions: Sequence[ParsedQuestion]) -> tuple[Question | None, ...]:
    """Pour chaque question, l'identique de la banque (IMP-07), la plus ancienne s'il y en a
    plusieurs, jamais une ancienne version (VER-03). Une requête par tranche d'énoncés :
    SQLite limite le nombre de paramètres."""
    texts = sorted({q.text for q in questions})
    bank: dict[ParsedQuestion, Question] = {}
    for start in range(0, len(texts), MATCH_BATCH):
        candidates = Question.objects.filter(
            text__in=texts[start : start + MATCH_BATCH], next_versions__isnull=True
        )
        for candidate in candidates.order_by("pk").prefetch_related("choices"):
            bank.setdefault(key_of(candidate), candidate)
    return tuple(bank.get(q.key()) for q in questions)


def same_file(digest: str) -> Quiz | None:
    """Le QCM venu du même fichier, octet pour octet, que l'import complète (IMP-10)."""
    return Quiz.objects.filter(source_sha256=digest).order_by("pk").first()


def recognise(questions: Sequence[ParsedQuestion], digest: str, target: Quiz | None):
    """Rang -> question de la banque reconnue comme venue de ce fichier (IMP-10) : par son
    origine ; pour un QCM importé avant I15, sans origine, par identité dans le QCM, puis par
    sa place dans le QCM si personne d'autre ne l'occupe."""
    origins = QuestionOrigin.objects.filter(sha256=digest).select_related("question")
    found = {origin.rank: origin.question for origin in origins}
    if found or target is None:
        return found
    in_quiz = list(target.ordered_questions().prefetch_related("choices"))
    by_key: dict[ParsedQuestion, Question] = {}
    for question in in_quiz:
        by_key.setdefault(key_of(question), question)
    for rank, question in enumerate(questions, start=1):
        if (match := by_key.get(question.key())) and match not in found.values():
            found[rank] = match
    for rank in range(1, min(len(questions), len(in_quiz)) + 1):
        if rank not in found and in_quiz[rank - 1] not in found.values():
            found[rank] = in_quiz[rank - 1]
    return found


def preview(data: bytes, filename: str) -> Preview:
    """Analyse sans rien créer ; `AmcSyntaxError` si le fichier est refusé."""
    digest = sha256(data)
    parsed = parse(data, filename)
    target = same_file(digest)
    known = recognise(parsed.questions, digest, target)
    identical = find_existing(parsed.questions)
    matches: list[Question | None] = []
    for rank, same in enumerate(identical, start=1):
        match = known.get(rank) or same
        matches.append(None if match in matches else match)  # jamais deux fois la même
    present: tuple[bool, ...] = ()
    if target is not None:
        in_quiz = set(target.questions.values_list("pk", flat=True))
        present = tuple(m is not None and m.pk in in_quiz for m in matches)
    return Preview(parsed, digest, tuple(matches), target, present)


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
    """Crée le QCM, ou complète celui du même fichier (IMP-10) : questions nouvelles créées,
    celles déjà dans la banque partagées, chacune à son rang du fichier (CMP-04)."""
    found = preview(data, filename)
    if not found.parsed.questions:
        raise ValueError(NOTHING_TO_IMPORT)
    quiz = found.target or Quiz.objects.create(
        title=found.parsed.title,
        source_name=filename[:SOURCE_NAME_MAX_LENGTH],
        source_sha256=found.sha256,
    )
    rows = zip(found.parsed.questions, found.matches, strict=True)
    questions = [match or create_question(q) for q, match in rows]
    for rank, question in enumerate(questions, start=1):
        QuestionOrigin.objects.update_or_create(
            sha256=found.sha256, rank=rank, defaults={"question": question}
        )
    current = list(quiz.ordered_questions().values_list("pk", flat=True))
    chosen = current + [q.pk for q in questions if q.pk not in current]
    quiz.set_questions(arrange(current, chosen, quiz.file_ranks()))
    return quiz
