"""Barème sur le modèle d'Auto Multiple Choice, sous-ensemble b, m, v, p (SPEC.md §3).

Fonctions pures, sans Django : les propositions sont désignées par leur indice (0, 1, …).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from decimal import Decimal

LETTERS = "ABCDEFGH"  # 2 à 8 propositions, désignées A…H, dans l'ordre de la banque (indice 0 = A)


@dataclass(frozen=True)
class Scale:
    """Une échelle de barème. Valeurs par défaut d'AMC : b=1, m=0, v=0, pas de plancher."""

    b: Decimal = Decimal(1)  # réponse juste (simple) / case bien traitée (multiple)
    m: Decimal = Decimal(0)  # réponse fausse (simple) / case mal traitée (multiple)
    v: Decimal = Decimal(0)  # aucune réponse
    p: Decimal | None = None  # plancher de la somme (questions multiples)

    def to_json(self) -> dict[str, str | None]:
        """Forme sérialisable (décimaux en texte, sans perte), pour les copies figées."""
        return {key: None if value is None else str(value) for key, value in asdict(self).items()}

    @classmethod
    def from_json(cls, data: Mapping[str, str | None]) -> Scale:
        """Lecteur de `to_json` : le barème figé d'une session (notation, I6)."""
        p = data["p"]
        return cls(*(Decimal(str(data[key])) for key in "bmv"), p=None if p is None else Decimal(p))


def score(
    *,
    multiple: bool,
    n_choices: int,
    correct: frozenset[int],
    chosen: frozenset[int],
    scale: Scale,
) -> Decimal:
    """Note d'une question selon la réponse donnée (`chosen` vide : pas de réponse)."""
    if not chosen <= frozenset(range(n_choices)):
        raise ValueError("réponse hors des propositions")
    if not chosen:
        return scale.v
    if not multiple:
        if len(chosen) != 1:
            raise ValueError("une question simple n'admet qu'une seule réponse")
        return scale.b if chosen == correct else scale.m
    total = sum(
        (scale.b if (i in chosen) == (i in correct) else scale.m for i in range(n_choices)),
        Decimal(0),
    )
    return total if scale.p is None else max(total, scale.p)


def max_score(*, multiple: bool, n_choices: int, scale: Scale) -> Decimal:
    """Note maximale d'une question : b, ou b par proposition pour une question multiple."""
    return scale.b * n_choices if multiple else scale.b
