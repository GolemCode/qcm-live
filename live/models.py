"""Sessions en direct et étudiants qui les rejoignent."""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING

from django.db import models

from roster.csv_import import MAX_NAME_LENGTH, MAX_NUMBER_LENGTH

if TYPE_CHECKING:
    from django.db.models.fields.related_descriptors import RelatedManager

CODE_LENGTH = 6
MAX_SHOWN = 6  # SES-01 : de 1 à 6 questions affichées en même temps
MIN_SECONDS, MAX_SECONDS = 5, 600


def random_code() -> str:
    """Identifiant de session : 6 chiffres, à saisir sur le pavé numérique du téléphone."""
    return f"{secrets.randbelow(10**CODE_LENGTH):0{CODE_LENGTH}d}"


class Session(models.Model):
    """Une session lancée. Le QCM et le groupe y sont copiés au lancement (SES-03)."""

    code = models.CharField(max_length=CODE_LENGTH, unique=True)
    quiz_title = models.CharField(max_length=200)
    group_name = models.CharField(max_length=100)
    content = models.JSONField()  # live.snapshot.freeze_quiz
    roster = models.JSONField()  # live.snapshot.freeze_group
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
    def n_questions(self) -> int:
        return len(self.content["questions"])

    def student_name(self, number: str) -> str | None:
        """Nom de l'étudiant de ce numéro dans la liste figée, ou None s'il n'en fait pas partie."""
        return next((s["name"] for s in self.roster if s["number"] == number), None)


class Participant(models.Model):
    """Un étudiant identifié dans une session. Numéro et nom sont copiés : supprimer le groupe
    n'efface rien (CLAUDE.md, architecture)."""

    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="participants")
    number = models.CharField(max_length=MAX_NUMBER_LENGTH)
    name = models.CharField(max_length=MAX_NAME_LENGTH)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["joined_at", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["session", "number"], name="unique_participant_number"),
        ]

    def __str__(self) -> str:
        return f"{self.session} {self.number}"
