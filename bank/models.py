"""Banque de questions réutilisables et QCM (sélection ordonnée de questions + barème)."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from django.db import models

from bank.scoring import Scale

if TYPE_CHECKING:
    from django.db.models.fields.related_descriptors import ManyRelatedManager, RelatedManager

CHOICE_MAX_LENGTH = 200
TITLE_MAX_LENGTH = 200
AMC_DEFAULTS = Scale()  # b=1, m=0, v=0, pas de plancher : source unique des valeurs par défaut


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
    text = models.CharField("proposition", max_length=CHOICE_MAX_LENGTH)
    correct = models.BooleanField("juste", default=False)
    position = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["question", "position"], name="unique_choice_position")
        ]

    def __str__(self) -> str:
        return self.text


def scale_field(default: Decimal | None) -> models.DecimalField:
    """Une directive du barème ; sans défaut, elle est facultative (plancher p)."""
    return models.DecimalField(
        max_digits=6, decimal_places=2, default=default, null=default is None, blank=default is None
    )


class Quiz(models.Model):
    title = models.CharField("titre", max_length=TITLE_MAX_LENGTH)
    questions = models.ManyToManyField(Question, through="QuizItem", related_name="quizzes")
    # Barème AMC : une échelle pour les questions simples, une pour les multiples.
    simple_b = scale_field(AMC_DEFAULTS.b)
    simple_m = scale_field(AMC_DEFAULTS.m)
    simple_v = scale_field(AMC_DEFAULTS.v)
    multiple_b = scale_field(AMC_DEFAULTS.b)
    multiple_m = scale_field(AMC_DEFAULTS.m)
    multiple_v = scale_field(AMC_DEFAULTS.v)
    multiple_p = scale_field(AMC_DEFAULTS.p)

    class Meta:
        ordering = ["title", "pk"]

    def __str__(self) -> str:
        return self.title

    def scales(self) -> dict[str, Scale]:
        """Le barème du QCM : une échelle par type de question."""
        return {
            "simple": Scale(b=self.simple_b, m=self.simple_m, v=self.simple_v),
            "multiple": Scale(
                b=self.multiple_b, m=self.multiple_m, v=self.multiple_v, p=self.multiple_p
            ),
        }

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
