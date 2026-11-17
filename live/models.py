"""Sessions en direct et étudiants qui les rejoignent."""

from __future__ import annotations

import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from functools import cached_property
from typing import TYPE_CHECKING, Literal

from django.db import IntegrityError, models, transaction
from django.db.models import Max, Sum
from django.utils import timezone

from bank.models import TITLE_MAX_LENGTH
from live.results import StudentResult, none_index, results
from live.schedule import Position, Schedule, Slot, seconds_to_remove, shuffled
from roster.csv_import import MAX_NAME_LENGTH, MAX_STUDENT_NUMBER_LENGTH
from roster.models import GROUP_NAME_MAX_LENGTH
from roster.years import YEAR_LENGTH, group_label

if TYPE_CHECKING:
    from django.db.models.fields.related_descriptors import RelatedManager

    from live.snapshot import FrozenQuestion, FrozenStudent

CODE_LENGTH = 6
EXTRA_SECONDS = 10  # TPS-01 : temps ajouté par un clic de l'enseignant
RANK_ATTEMPTS = 10  # arrivées simultanées : une tentative par conflit de rang

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
    group_year = models.CharField(max_length=YEAR_LENGTH)  # GRP-04, figée comme le nom
    content = models.JSONField()  # live.snapshot.FrozenQuiz
    roster = models.JSONField()  # list[live.snapshot.FrozenStudent]
    # Questions de la banque copiées au lancement : elles sont « utilisées » (VER-01). La
    # session ne les lit jamais, elle n'a que sa copie.
    source_questions = models.ManyToManyField("bank.Question", related_name="sessions", blank=True)
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
    def group_label(self) -> str:
        """Le groupe figé, avec son année (GRP-04) : « ITI4 — 2025-2026 »."""
        return group_label(self.group_name, self.group_year)

    @property
    def questions(self) -> list[FrozenQuestion]:
        return self.content["questions"]

    @property
    def students(self) -> list[FrozenStudent]:
        """Liste figée du groupe, par n° de liste (`freeze_group`)."""
        return self.roster

    @cached_property
    def schedule(self) -> Schedule:
        return self._schedule(self.extensions.all())

    def _schedule(self, extensions: models.QuerySet[Extension]) -> Schedule:
        totals = extensions.order_by().values("slot").annotate(total=Sum("seconds"))
        extra = {row["slot"]: row["total"] for row in totals}
        return Schedule(self.n_questions, self.shown, self.seconds, extra)

    def start(self, now: datetime) -> None:
        """Démarre la session si elle ne l'est pas déjà ; sinon (double clic), rien ne change.

        Mise à jour conditionnelle et atomique, qui ne déplace pas l'heure de départ. Les rangs
        de rotation sont renumérotés 0, 1, 2… dans l'ordre d'arrivée : les libérations (SES-04)
        ne laissent pas de trou qui fausserait la répartition des questions.
        """
        with transaction.atomic():
            if not Session.objects.filter(pk=self.pk, started_at__isnull=True).update(
                started_at=now
            ):
                return
            participants = list(self.participants.order_by("rank", "pk"))
            offset = len(participants) + max((p.rank for p in participants), default=0) + 1
            for participant in participants:  # en deux passes, à cause de l'unicité des rangs
                participant.rank += offset
            Participant.objects.bulk_update(participants, ["rank"])
            for rank, participant in enumerate(participants):
                participant.rank = rank
            Participant.objects.bulk_update(participants, ["rank"])
        self.started_at = now

    def state(self, now: datetime) -> State:
        if self.started_at is None:
            return State("waiting")
        position = self.schedule.position((now - self.started_at).total_seconds())
        return State("ended") if position is None else State("running", position)

    def add_time(self, slot: str | None, clock: Callable[[], datetime] | None = None) -> bool:
        """TPS-01 : ajoute 10 s au créneau `slot` (son rang, tel qu'envoyé par le tableau) s'il
        est en cours ; False sinon (clic arrivé après la fin du créneau, avant le démarrage ou
        après la fin de la session)."""
        return self._change_slot(slot, lambda position: EXTRA_SECONDS, clock)

    def end_slot(self, slot: str | None, clock: Callable[[], datetime] | None = None) -> bool:
        """TPS-02 : ramène à 5 s le temps restant du créneau `slot` s'il est en cours (rien s'il
        en reste 5 ou moins) ; False si ce créneau n'est pas en cours, comme `add_time`."""
        return self._change_slot(
            slot, lambda position: -seconds_to_remove(position.remaining), clock
        )

    def _change_slot(
        self,
        slot: str | None,
        seconds: Callable[[Position], int],
        clock: Callable[[], datetime] | None,
    ) -> bool:
        """Ajoute au créneau `slot`, s'il est en cours, les secondes (retirées si négatives) que
        `seconds` calcule d'après sa position ; False si ce créneau n'est pas en cours.

        Une ligne par clic : deux clics simultanés s'ajoutent sans se perdre. La ligne est
        écrite d'abord, ce qui prend le verrou d'écriture de la base ; le créneau en cours est
        alors recalculé avec les changements déjà validés, sans celui-ci, et c'est de ce calcul
        que vient le nombre de secondes : deux « Terminer » simultanés ne retirent pas deux
        fois. Un clic arrivé après l'échéance est annulé : il ne rouvre pas un créneau terminé.
        Reste la fenêtre, de quelques millisecondes, entre ce calcul et la validation (REX, I5).
        """
        if self.started_at is None:
            return False
        clock = clock or timezone.now  # lue à l'appel, pas figée à la définition
        position = self.state(clock()).position
        if position is None or slot != str(position.slot.index):
            return False
        with transaction.atomic():
            change = Extension.objects.create(session=self, slot=position.slot.index, seconds=0)
            others = self._schedule(self.extensions.exclude(pk=change.pk))
            current = others.position((clock() - self.started_at).total_seconds())
            if current is None or current.slot != position.slot:
                transaction.set_rollback(True)
                return False
            change.seconds = seconds(current)
            if change.seconds:
                change.save(update_fields=["seconds"])
            else:  # rien à changer (TPS-02, 5 s ou moins) : pas de ligne
                transaction.set_rollback(True)
        vars(self).pop("schedule", None)  # à recalculer avec le changement
        return True

    def answered(self, slot: Slot) -> tuple[int, int]:
        """DER-04 : (k, n) au créneau `slot`. n : les connectés ; k : ceux dont une réponse est
        enregistrée pour leur question de ce créneau (une réponse effacée n'a plus de ligne)."""
        expected = {
            (pk, self.schedule.question_for(slot, rank))
            for pk, rank in self.participants.values_list("pk", "rank")
        }
        questions = {question for _, question in expected}
        given = Answer.objects.filter(participant__session=self, question__in=questions)
        k = len(expected & set(given.values_list("participant", "question")))
        return k, len(expected)

    def results(self) -> list[StudentResult]:
        """RES-01 : un résultat par étudiant du groupe figé ; les absents n'ont pas de note."""
        participants = self.participants.prefetch_related("answers")
        present = {p.list_number: p.answer_map() for p in participants}
        return results(self.content, self.students, present)

    def student(self, list_number: int) -> FrozenStudent | None:
        """Étudiant de ce n° dans la liste figée, ou None s'il n'en fait pas partie."""
        return next((s for s in self.students if s["list_number"] == list_number), None)

    def _next_rank(self) -> int:
        """Rotation : rangs successifs 0, 1, 2… (un n° libéré ne crée pas de doublon)."""
        top = self.participants.aggregate(top=Max("rank"))["top"]
        return 0 if top is None else top + 1

    def enrol(self, student: FrozenStudent) -> Participant | None:
        """ETU-13 : le participant de cet étudiant de la liste figée, ou None s'il est déjà pris.

        Les contraintes d'unicité en base sont les seuls arbitres : deux téléphones qui
        confirment le même nom au même instant ne passent pas tous les deux, et deux arrivées
        simultanées n'obtiennent pas le même rang (le second retente avec le rang suivant).
        """
        list_number = student["list_number"]
        for _ in range(RANK_ATTEMPTS):
            try:
                with transaction.atomic():
                    return Participant.objects.create(
                        session=self,
                        list_number=list_number,
                        student_number=student["student_number"],
                        name=student["name"],
                        rank=self._next_rank(),
                    )
            except IntegrityError:
                if self.participants.filter(list_number=list_number).exists():
                    break
        return None


class Participant(models.Model):
    """Un étudiant identifié dans une session, par son n° de liste (ETU-13). N°, numéro étudiant
    et nom sont copiés : supprimer le groupe n'efface rien (CLAUDE.md, architecture)."""

    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="participants")
    list_number = models.PositiveSmallIntegerField()
    student_number = models.CharField(max_length=MAX_STUDENT_NUMBER_LENGTH, blank=True)
    name = models.CharField(max_length=MAX_NAME_LENGTH)
    rank = models.PositiveIntegerField(default=0)  # place dans la rotation (live.schedule)
    joined_at = models.DateTimeField(auto_now_add=True)

    if TYPE_CHECKING:
        answers: RelatedManager[Answer]

    class Meta:
        ordering = ["joined_at", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["session", "list_number"], name="unique_participant_list_number"
            ),
            models.UniqueConstraint(fields=["session", "rank"], name="unique_participant_rank"),
        ]

    def __str__(self) -> str:
        return f"{self.session} n° {self.list_number}"

    def question_at(self, slot: Slot) -> tuple[int, FrozenQuestion]:
        """Indice et contenu figé de la question de ce participant pendant ce créneau."""
        index = self.session.schedule.question_for(slot, self.rank)
        return index, self.session.questions[index]

    def choice_order(self, question: int) -> list[int]:
        """Ordre d'affichage des propositions de cette question sur son téléphone (ETU-05) :
        inchangé pour une question sans « Aucune… » ni ordre fixe, celles d'avant I12."""
        frozen = self.session.questions[question]
        n_choices = len(frozen["choices"])
        if frozen["ordered"]:  # BAN-10 : l'ordre de la banque
            return list(range(n_choices))
        seed = f"{self.session.code}:{self.pk}:{question}"
        if (none := none_index(frozen)) is not None:  # ETU-12 : « Aucune… » reste en dernier
            return [*shuffled(none, seed), none]
        return shuffled(n_choices, seed)

    def answer_map(self) -> dict[int, list[int]]:
        """Propositions choisies, par indice de question ; une question absente : pas de réponse."""
        return {answer.question: answer.choices for answer in self.answers.all()}

    def answers_by_slot(self) -> dict[int, list[int]]:
        """Propositions choisies, par rang du créneau où ce participant a eu la question
        (ETU-10). La rotation lui donne chaque question une fois, dans un seul créneau."""
        schedule = self.session.schedule
        slot_of = {schedule.question_for(slot, self.rank): slot.index for slot in schedule.slots}
        return {slot_of[question]: choices for question, choices in self.answer_map().items()}


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
    """Temps changé par l'enseignant au créneau `slot` (rang dans la session), une ligne par
    clic : 10 secondes ajoutées (TPS-01, Session.add_time) ou, négatives, retirées pour
    terminer le créneau (TPS-02, Session.end_slot)."""

    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="extensions")
    slot = models.PositiveSmallIntegerField()
    seconds = models.SmallIntegerField(default=EXTRA_SECONDS)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.session} {self.seconds:+d} s au créneau {self.slot}"
