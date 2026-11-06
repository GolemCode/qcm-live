"""Sessions en direct et étudiants qui les rejoignent."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime
from functools import cached_property
from typing import TYPE_CHECKING, Literal

from django.db import models

from bank.models import TITLE_MAX_LENGTH
from live.schedule import Position, Schedule, Slot, shuffled
from roster.csv_import import MAX_NAME_LENGTH, MAX_NUMBER_LENGTH
from roster.models import GROUP_NAME_MAX_LENGTH

if TYPE_CHECKING:
    from django.db.models.fields.related_descriptors import RelatedManager

    from live.snapshot import FrozenQuestion, FrozenStudent

CODE_LENGTH = 6

Phase = Literal["waiting", "running", "ended"]


@dataclass(frozen=True)
class State:
    """Phase d'une session à un instant donné, et créneau en cours pendant le déroulement."""

    phase: Phase
    position: Position | None = None


def random_code() -> str:
    """Identifiant de session : 6 chiffres, à saisir sur le pavé numérique du téléphone."""
    return f"{secrets.randbelow(10**CODE_LENGTH):0{CODE_LENGTH}d}"


class Session(models.Model):
    """Une session lancée. Le QCM et le groupe y sont copiés au lancement (SES-03)."""

    code = models.CharField(max_length=CODE_LENGTH, unique=True)
    quiz_title = models.CharField(max_length=TITLE_MAX_LENGTH)
    group_name = models.CharField(max_length=GROUP_NAME_MAX_LENGTH)
    content = models.JSONField()  # live.snapshot.FrozenQuiz
    roster = models.JSONField()  # list[live.snapshot.FrozenStudent]
    shown = models.PositiveSmallIntegerField()
    seconds = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)

    if TYPE_CHECKING:
        participants: RelatedManager[Participant]

    class Meta:
        ordering = ["-created_at", "-pk"]

    def __str__(self) -> str:
        return self.code

    @property
    def questions(self) -> list[FrozenQuestion]:
        return self.content["questions"]

    @property
    def students(self) -> list[FrozenStudent]:
        return self.roster

    @property
    def n_questions(self) -> int:
        return len(self.questions)

    @cached_property
    def schedule(self) -> Schedule:
        return Schedule(self.n_questions, self.shown, self.seconds)

    def state(self, now: datetime) -> State:
        if self.started_at is None:
            return State("waiting")
        position = self.schedule.position((now - self.started_at).total_seconds())
        return State("ended") if position is None else State("running", position)

    def student_name(self, number: str) -> str | None:
        """Nom de l'étudiant de ce numéro dans la liste figée, ou None s'il n'en fait pas partie."""
        return next((s["name"] for s in self.students if s["number"] == number), None)


class Participant(models.Model):
    """Un étudiant identifié dans une session. Numéro et nom sont copiés : supprimer le groupe
    n'efface rien (CLAUDE.md, architecture)."""

    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="participants")
    number = models.CharField(max_length=MAX_NUMBER_LENGTH)
    name = models.CharField(max_length=MAX_NAME_LENGTH)
    rank = models.PositiveIntegerField(default=0)  # place dans la rotation (live.schedule)
    joined_at = models.DateTimeField(auto_now_add=True)

    if TYPE_CHECKING:
        answers: RelatedManager[Answer]

    class Meta:
        ordering = ["joined_at", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["session", "number"], name="unique_participant_number"),
        ]

    def __str__(self) -> str:
        return f"{self.session} {self.number}"

    def question_at(self, slot: Slot) -> tuple[int, FrozenQuestion]:
        """Indice et contenu figé de la question de ce participant pendant ce créneau."""
        index = self.session.schedule.question_for(slot, self.rank)
        return index, self.session.questions[index]

    def choice_order(self, question: int) -> list[int]:
        """Ordre d'affichage des propositions de cette question sur son téléphone (ETU-05)."""
        n_choices = len(self.session.questions[question]["choices"])
        return shuffled(n_choices, f"{self.session.code}:{self.pk}:{question}")


class Answer(models.Model):
    """Dernière réponse d'un participant à une question de la copie figée (ETU-07).

    `question` est l'indice de la question dans `session.questions` ; `choices`, les indices
    (ordre canonique, A = 0) des propositions choisies. Pas de ligne : pas de réponse (v).
    """

    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name="answers")
    question = models.PositiveSmallIntegerField()
    choices = models.JSONField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["question"]
        constraints = [
            models.UniqueConstraint(fields=["participant", "question"], name="unique_answer"),
        ]

    def __str__(self) -> str:
        return f"{self.participant} Q{self.question} {self.choices}"
