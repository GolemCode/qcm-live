"""Déroulement d'une session (SPEC DER-01, DER-02, ETU-05, ETU-06) — fonctions pures.

- Les questions défilent par groupes de N, dans l'ordre du QCM ; le dernier peut être plus court.
- Un groupe de n questions dure n créneaux de t secondes, synchronisés pour tous.
- Rotation : au créneau `step` d'un groupe, l'étudiant de rang `rank` répond à la question
  (rank + step) mod n du groupe. Sur n créneaux, il les voit toutes, une fois chacune, et deux
  rangs voisins n'ont jamais la même question au même moment.
- La couleur d'une question est son rang dans le groupe (1 à n), au tableau comme au téléphone.
- Temps additionnel (TPS-01) : des secondes ajoutées à un créneau l'allongent et décalent
  d'autant les suivants. Le déroulement se calcule sur les échéances cumulées, sans jamais
  toucher à l'heure de démarrage, ce qui ferait reculer le créneau en cours.
"""

from __future__ import annotations

import bisect
import itertools
import random
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import cached_property


@dataclass(frozen=True)
class Slot:
    index: int  # rang du créneau dans la session (0, 1, …)
    group: int  # rang de son groupe
    step: int  # rang du créneau dans son groupe
    size: int  # nombre de questions de son groupe

    def color(self, rank: int) -> int:
        """Couleur (1 à n) de la question de l'étudiant de rang `rank` pendant ce créneau."""
        return (rank + self.step) % self.size + 1


@dataclass(frozen=True)
class Position:
    slot: Slot
    remaining: float  # secondes restantes dans le créneau


@dataclass(frozen=True)
class Schedule:
    n_questions: int
    shown: int  # N : questions affichées en même temps
    seconds: int  # t : durée d'un créneau
    extra: Mapping[int, int] = field(default_factory=dict)  # secondes ajoutées, par créneau

    @cached_property
    def groups(self) -> list[list[int]]:
        indexes = list(range(self.n_questions))
        return [indexes[i : i + self.shown] for i in range(0, self.n_questions, self.shown)]

    @cached_property
    def slots(self) -> list[Slot]:
        slots = []
        for group, questions in enumerate(self.groups):
            for step in range(len(questions)):
                slots.append(Slot(len(slots), group, step, len(questions)))
        return slots

    @cached_property
    def deadlines(self) -> list[int]:
        """Fin de chaque créneau, en secondes après le démarrage, temps ajouté compris."""
        lengths = (self.seconds + self.extra.get(slot.index, 0) for slot in self.slots)
        return list(itertools.accumulate(lengths))

    @property
    def duration(self) -> int:
        return self.deadlines[-1]

    def position(self, elapsed: float) -> Position | None:
        """Créneau en cours `elapsed` secondes après le démarrage ; None une fois terminé."""
        elapsed = max(elapsed, 0.0)
        index = bisect.bisect_right(self.deadlines, elapsed)  # une échéance ouvre le suivant
        if index >= len(self.slots):
            return None
        return Position(self.slots[index], self.deadlines[index] - elapsed)

    def question_for(self, slot: Slot, rank: int) -> int:
        """Indice, dans le QCM, de la question de l'étudiant de rang `rank` pendant ce créneau."""
        return self.groups[slot.group][slot.color(rank) - 1]


def shuffled(n_choices: int, seed: str) -> list[int]:
    """Ordre d'affichage des propositions : une permutation stable propre à `seed`
    (un étudiant et une question)."""
    order = list(range(n_choices))
    random.Random(seed).shuffle(order)  # noqa: S311 — mélange d'affichage, pas de sécurité
    return order
