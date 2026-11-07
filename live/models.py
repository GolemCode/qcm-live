"""Sessions en direct et étudiants qui les rejoignent."""

from __future__ import annotations

import secrets
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from functools import cached_property
from typing import TYPE_CHECKING, Literal

from django.db import models, transaction
from django.utils import timezone

from bank.models import TITLE_MAX_LENGTH
from live.receipt import receipt
from live.results import StudentResult, results
from live.schedule import Position, Schedule, Slot, shuffled
from roster.csv_import import MAX_NAME_LENGTH, MAX_NUMBER_LENGTH
from roster.models import GROUP_NAME_MAX_LENGTH

if TYPE_CHECKING:
    from django.db.models.fields.related_descriptors import RelatedManager

    from live.snapshot import FrozenQuestion, FrozenStudent

CODE_LENGTH = 6
EXTRA_SECONDS = 10  # TPS-01 : temps ajouté par un clic de l'enseignant

Phase = Literal["waiting", "running", "ended"]
PHASE_LABELS: dict[Phase, str] = {
    "waiting": "En attente",
    "running": "En cours",
    "ended": "Terminée",
}


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
    # Nombre de questions de la copie figée : les états interrogés chaque seconde calculent
    # le déroulement sans charger ni décoder `content`.
    n_questions = models.PositiveSmallIntegerField()
    shown = models.PositiveSmallIntegerField()
    seconds = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)

    if TYPE_CHECKING:
        participants: RelatedManager[Participant]
        extensions: RelatedManager[Extension]

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

    @cached_property
    def schedule(self) -> Schedule:
        return self._schedule(self.extensions.all())

    def _schedule(self, extensions: models.QuerySet[Extension]) -> Schedule:
        clicks = Counter(extensions.values_list("slot", flat=True))
        extra = {slot: n * EXTRA_SECONDS for slot, n in clicks.items()}
        return Schedule(self.n_questions, self.shown, self.seconds, extra)

    def start(self, now: datetime) -> bool:
        """Démarre la session si elle ne l'est pas déjà ; False si elle l'était (double clic).

        Mise à jour conditionnelle et atomique, qui ne déplace pas l'heure de départ. Les rangs
        de rotation sont renumérotés 0, 1, 2… dans l'ordre d'arrivée : les libérations (SES-04)
        ne laissent pas de trou qui fausserait la répartition des questions.
        """
        with transaction.atomic():
            if not Session.objects.filter(pk=self.pk, started_at__isnull=True).update(
                started_at=now
            ):
                return False
            participants = list(self.participants.order_by("rank", "pk"))
            offset = len(participants) + max((p.rank for p in participants), default=0) + 1
            for participant in participants:  # en deux passes, à cause de l'unicité des rangs
                participant.rank += offset
            Participant.objects.bulk_update(participants, ["rank"])
            for rank, participant in enumerate(participants):
                participant.rank = rank
            Participant.objects.bulk_update(participants, ["rank"])
        self.started_at = now
        return True

    def state(self, now: datetime) -> State:
        if self.started_at is None:
            return State("waiting")
        position = self.schedule.position((now - self.started_at).total_seconds())
        return State("ended") if position is None else State("running", position)

    def add_time(self, slot: str | None, clock: Callable[[], datetime] = timezone.now) -> bool:
        """TPS-01 : ajoute 10 s au créneau `slot` (son rang, tel qu'envoyé par le tableau) s'il
        est en cours ; False sinon (clic arrivé après la fin du créneau, avant le démarrage ou
        après la fin de la session).

        Une ligne par clic : deux clics simultanés s'ajoutent sans se perdre. La ligne est
        écrite d'abord, ce qui prend le verrou d'écriture de la base ; le créneau en cours est
        alors recalculé avec les ajouts déjà validés, sans celui-ci. Un clic arrivé après
        l'échéance est annulé : il ne rouvre pas un créneau terminé. Reste la fenêtre, de
        quelques millisecondes, entre ce calcul et la validation (REX, I5).
        """
        if self.started_at is None:
            return False
        position = self.state(clock()).position
        if position is None or slot != str(position.slot.index):
            return False
        with transaction.atomic():
            added = Extension.objects.create(session=self, slot=position.slot.index)
            others = self._schedule(self.extensions.exclude(pk=added.pk))
            current = others.position((clock() - self.started_at).total_seconds())
            if current is None or current.slot != position.slot:
                transaction.set_rollback(True)
                return False
        vars(self).pop("schedule", None)  # à recalculer avec le temps ajouté
        return True

    def results(self) -> list[StudentResult]:
        """RES-01 : un résultat par étudiant du groupe figé ; les absents n'ont pas de note."""
        present = {p.number: p.answer_map() for p in self.participants.prefetch_related("answers")}
        return results(self.content, self.students, present)

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
            models.UniqueConstraint(fields=["session", "rank"], name="unique_participant_rank"),
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

    def receipt(self) -> str:
        """FIN-01 : contenu du QR code ; les questions dans l'ordre où l'étudiant les a eues,
        y compris celles des créneaux manqués par un retardataire (ETU-08)."""
        answers = self.answer_map()
        received = [self.question_at(slot)[0] for slot in self.session.schedule.slots]
        return receipt(self.session.code, self.number, [(q, answers.get(q, [])) for q in received])

    def answer_map(self) -> dict[int, list[int]]:
        """Propositions choisies, par indice de question ; une question absente : pas de réponse."""
        return {answer.question: answer.choices for answer in self.answers.all()}


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


class Extension(models.Model):
    """10 secondes ajoutées par l'enseignant au créneau `slot` (rang dans la session) : une
    ligne par clic (TPS-01, Session.add_time)."""

    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="extensions")
    slot = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.session} +{EXTRA_SECONDS} s au créneau {self.slot}"
