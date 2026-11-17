"""Banque de questions réutilisables, chacune avec son barème AMC, et QCM (sélection ordonnée)."""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING

from django.conf import settings
from django.db import models, transaction

from bank.amc_txt import CHOICE_MAX_LENGTH, GROUP_LABEL_MAX_LENGTH, TITLE_MAX_LENGTH
from bank.scoring import LETTERS, SCORING_MAX_LENGTH

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
    # Version qu'elle remplace (VER-01) : la précédente reste inchangée pour ses sessions.
    previous = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="next_versions"
    )
    # Supprimée de la banque après avoir servi dans une session : gardée pour l'historique
    # (BAN-07, CMP-03), comme une ancienne version.
    hidden = models.BooleanField("masquée", default=False)

    if TYPE_CHECKING:  # relations inverses, déclarées pour le typage statique
        from live.models import Session

        choices: RelatedManager[Choice]
        quizzes: ManyRelatedManager[Quiz, QuizItem]
        next_versions: RelatedManager[Question]
        origins: RelatedManager[QuestionOrigin]
        sessions: ManyRelatedManager[Session, models.Model]

    class Meta:
        ordering = ["pk"]

    def __str__(self) -> str:
        return self.text

    @property
    def none_is_correct(self) -> bool:
        """« Aucune de ces réponses n'est correcte » est la bonne réponse (BAN-09)."""
        return self.none_of_these and not any(choice.correct for choice in self.choices.all())

    def lettered_choices(self) -> list[tuple[str, Choice]]:
        """Propositions avec leur lettre (A, B, C…), « Aucune de ces réponses… » en dernier,
        comme au tableau et dans le CSV (VER-03)."""
        choices = list(self.choices.all())
        if self.none_of_these:
            choices.append(Choice(text=NONE_OF_THESE, correct=self.none_is_correct, position=0))
        return list(zip(LETTERS, choices, strict=False))

    def previous_versions(self) -> list[Question]:
        """Versions qu'elle remplace, de la plus récente à la plus ancienne (VER-03)."""
        versions, current = [], self.previous
        while current is not None:
            versions.append(current)
            current = current.previous
        return versions

    @staticmethod
    def comparable(text: str, *fields: object) -> tuple[object, ...]:
        """Contenu comparable d'une question (VER-01) ; le navigateur renvoie des CRLF."""
        return (text.replace("\r\n", "\n"), *fields)

    def content(self) -> tuple[object, ...]:
        """Ce qu'une modification change : une version n'est créée que s'il diffère (VER-01)."""
        choices = tuple((c.text, c.correct, c.points) for c in self.choices.all())
        fields = (self.kind, self.scoring, self.none_of_these, self.ordered, choices)
        return self.comparable(self.text, *fields)

    @classmethod
    def current(cls) -> models.QuerySet[Question]:
        """Questions de la banque : sans version plus récente, ou encore dans un QCM (VER-03),
        jamais une question masquée (BAN-07)."""
        kept = models.Q(next_versions__isnull=True) | models.Q(quizzes__isnull=False)
        return cls.objects.filter(kept, hidden=False).distinct()

    @transaction.atomic
    def remove(self) -> None:
        """Suppression de la banque (BAN-07) : la question quitte ses QCM. Si elle a servi dans
        une session, elle est seulement masquée, pour que l'historique la compte encore
        (CMP-03) ; son origine est oubliée, comme si elle avait disparu (IMP-10)."""
        if not self.sessions.exists():
            self.delete()
            return
        QuizItem.objects.filter(question=self).delete()
        self.origins.all().delete()
        self.hidden = True
        self.save(update_fields=["hidden"])


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


def title_key(title: str) -> tuple[str, str]:
    """Clé de l'ordre alphabétique des titres, sans tenir compte des majuscules ni des accents
    (« Écologie » entre « Biologie » et « Zoologie »), le titre exact départageant."""
    bare = "".join(c for c in unicodedata.normalize("NFKD", title) if not unicodedata.combining(c))
    return bare.casefold(), title


def by_title(quizzes: Iterable[Quiz]) -> list[Quiz]:
    """QCM triés par titre (BAN-03, SES-01). Le tri se fait ici et non en base : SQLite ne
    compare que les octets, et `Meta.ordering` n'agit pas sur une requête agrégée."""
    return sorted(quizzes, key=lambda quiz: (*title_key(quiz.title), quiz.pk))


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

    def file_ranks(self) -> dict[int, int]:
        """Rang dans le fichier du QCM de chacune de ses questions qui en vient (CMP-04)."""
        if not self.source_sha256:
            return {}
        origins = QuestionOrigin.objects.filter(sha256=self.source_sha256)
        return dict(origins.values_list("question_id", "rank"))

    @transaction.atomic
    def set_questions(self, questions: Sequence[int]) -> None:
        """Remplace ses questions par celles-ci (pk), dans cet ordre."""
        QuizItem.objects.filter(quiz=self).delete()
        QuizItem.objects.bulk_create(
            QuizItem(quiz=self, question_id=pk, position=position)
            for position, pk in enumerate(questions, start=1)
        )


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


class QuestionOrigin(models.Model):
    """D'où vient une question importée : le fichier (son contenu) et son rang, à partir de 1,
    parmi les questions retenues (IMP-10). Suit la question dans ses nouvelles versions."""

    sha256 = models.CharField(max_length=64)
    rank = models.PositiveIntegerField()
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="origins")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["sha256", "rank"], name="unique_origin_rank")
        ]

    def __str__(self) -> str:
        return f"{self.sha256[:8]} #{self.rank} : {self.question}"


class PendingImport(models.Model):
    """Dernier fichier AMC-TXT envoyé par un enseignant, gardé jusqu'à sa confirmation (IMP-01).

    Un nouvel envoi le remplace ; la confirmation, l'annulation ou un refus le suppriment.
    """

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    token = models.CharField(max_length=32)  # désigne cet envoi dans l'adresse du récapitulatif
    name = models.TextField()  # nom du fichier, tel qu'envoyé
    data = models.BinaryField()

    def __str__(self) -> str:
        return self.name
