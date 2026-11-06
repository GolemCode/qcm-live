"""Banque de questions réutilisables et QCM (sélection ordonnée de questions + barème)."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from django.db import models

from bank.scoring import Scale

if TYPE_CHECKING:
    from django.db.models.fields.related_descriptors import ManyRelatedManager, RelatedManager

# Libellés des directives AMC, en minuscules comme dans AMC (aussi utilisés par le formulaire).
SCALE_LABELS = {
    "simple_b": "b — réponse juste",
    "simple_m": "m — réponse fausse",
    "simple_v": "v — pas de réponse",
    "multiple_b": "b — case bien traitée",
    "multiple_m": "m — case mal traitée",
    "multiple_v": "v — aucune case cochée",
    "multiple_p": "p — plancher (facultatif)",
}


class Question(models.Model):
    class Kind(models.TextChoices):
        SIMPLE = "simple", "Choix simple"
        MULTIPLE = "multiple", "Choix multiple"

    text = models.TextField("énoncé")
    kind = models.CharField("type", max_length=8, choices=Kind.choices, default=Kind.SIMPLE)

    if TYPE_CHECKING:  # relations inverses, déclarées pour le typage statique
        choices: RelatedManager[Choice]
        quizzes: ManyRelatedManager[Quiz, QuizItem]

    class Meta:
        ordering = ["pk"]

    def __str__(self) -> str:
        return self.text


class Choice(models.Model):
    """Une proposition ; `position` donne l'ordre canonique (A, B, C… au tableau)."""

    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="choices")
    text = models.CharField("proposition", max_length=200)
    correct = models.BooleanField("juste", default=False)
    position = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["question", "position"], name="unique_choice_position")
        ]

    def __str__(self) -> str:
        return self.text


def scale_field(name: str, default: int | None = None) -> models.DecimalField:
    return models.DecimalField(
        SCALE_LABELS[name],
        max_digits=6,
        decimal_places=2,
        default=None if default is None else Decimal(default),
        null=default is None,
        blank=default is None,
    )


class Quiz(models.Model):
    title = models.CharField("titre", max_length=200)
    questions = models.ManyToManyField(Question, through="QuizItem", related_name="quizzes")
    # Barème AMC : une échelle pour les questions simples, une pour les multiples.
    simple_b = scale_field("simple_b", 1)
    simple_m = scale_field("simple_m", 0)
    simple_v = scale_field("simple_v", 0)
    multiple_b = scale_field("multiple_b", 1)
    multiple_m = scale_field("multiple_m", 0)
    multiple_v = scale_field("multiple_v", 0)
    multiple_p = scale_field("multiple_p")  # pas de défaut : pas de plancher

    class Meta:
        ordering = ["title", "pk"]

    def __str__(self) -> str:
        return self.title

    def simple_scale(self) -> Scale:
        return Scale(b=self.simple_b, m=self.simple_m, v=self.simple_v)

    def multiple_scale(self) -> Scale:
        return Scale(b=self.multiple_b, m=self.multiple_m, v=self.multiple_v, p=self.multiple_p)

    def ordered_questions(self) -> models.QuerySet[Question]:
        return self.questions.order_by("quizitem__position")


class QuizItem(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    position = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["quiz", "question"], name="unique_quiz_question"),
            models.UniqueConstraint(fields=["quiz", "position"], name="unique_quiz_position"),
        ]

    def __str__(self) -> str:
        return f"{self.quiz} #{self.position} : {self.question}"
