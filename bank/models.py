"""Banque de questions réutilisables, chacune avec son barème AMC, et QCM (sélection ordonnée)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import models

from bank.amc_txt import CHOICE_MAX_LENGTH, GROUP_LABEL_MAX_LENGTH, TITLE_MAX_LENGTH
from bank.scoring import SCORING_MAX_LENGTH

if TYPE_CHECKING:
    from django.db.models.fields.related_descriptors import ManyRelatedManager, RelatedManager

SOURCE_NAME_MAX_LENGTH = 255
NONE_OF_THESE = "Aucune de ces réponses n'est correcte"


class Question(models.Model):
    class Kind(models.TextChoices):
        SIMPLE = "simple", "Choix simple"
        MULTIPLE = "multiple", "Choix multiple"

    text = models.TextField("énoncé")
    kind = models.CharField("type", max_length=8, choices=Kind.choices, default=Kind.SIMPLE)
    # Directives AMC (bank.scoring) ; vide : la base, b=1, m=0, v=0 (BAR-01).
    scoring = models.CharField("barème", max_length=SCORING_MAX_LENGTH, blank=True)
    none_of_these = models.BooleanField(NONE_OF_THESE, default=False)  # BAN-09
    ordered = models.BooleanField("ordre fixe", default=False)  # BAN-10
    amc_group = models.CharField("étiquette", max_length=GROUP_LABEL_MAX_LENGTH, blank=True)

    if TYPE_CHECKING:  # relations inverses, déclarées pour le typage statique
        choices: RelatedManager[Choice]
        quizzes: ManyRelatedManager[Quiz, QuizItem]

    class Meta:
        ordering = ["pk"]

    def __str__(self) -> str:
        return self.text

    @property
    def none_is_correct(self) -> bool:
        """« Aucune de ces réponses n'est correcte » est la bonne réponse (BAN-09)."""
        return self.none_of_these and not any(choice.correct for choice in self.choices.all())


class Choice(models.Model):
    """Une proposition ; `position` donne l'ordre canonique (A, B, C… au tableau)."""

    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="choices")
    text = models.CharField("proposition", max_length=CHOICE_MAX_LENGTH)
    correct = models.BooleanField("juste", default=False)
    # Valeur propre de la proposition (question simple, AMC-TXT « -{-2} ») ; None : b ou m.
    points = models.DecimalField(max_digits=9, decimal_places=3, null=True, blank=True)
    position = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["question", "position"], name="unique_choice_position")
        ]

    def __str__(self) -> str:
        return self.text


class Quiz(models.Model):
    title = models.CharField("titre", max_length=TITLE_MAX_LENGTH)
    questions = models.ManyToManyField(Question, through="QuizItem", related_name="quizzes")
    # Fichier AMC d'origine (IMP-01, IMP-07) ; vides pour un QCM composé dans l'application.
    source_name = models.CharField(max_length=SOURCE_NAME_MAX_LENGTH, blank=True)
    source_sha256 = models.CharField(max_length=64, blank=True, db_index=True)

    class Meta:
        ordering = ["title", "pk"]

    def __str__(self) -> str:
        return self.title

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
