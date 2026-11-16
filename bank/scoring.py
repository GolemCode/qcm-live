"""Barème d'Auto Multiple Choice, question par question (SPEC.md BAR-01 et §3).

Fonctions pures, sans Django : les propositions sont désignées par leur indice (0, 1, …),
« Aucune de ces réponses n'est correcte » comprise, en dernier.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal

MAX_CHOICES = 8  # propositions saisies, désignées A…H, dans l'ordre de la banque (indice 0 = A)
LETTERS = "ABCDEFGHI"  # I : « Aucune de ces réponses n'est correcte » après 8 propositions

DIRECTIVES = ("b", "m", "v", "e", "d", "p", "haut", "mz", "MAX")
BASE = {"b": Decimal(1), "m": Decimal(0), "v": Decimal(0), "e": Decimal(0), "d": Decimal(0)}
NUMBER_RE = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)")
DIRECTIVE_RE = re.compile(r"([A-Za-z]+)\s*=\s*(.*)")

POINTS_LIMIT = Decimal(1_000_000)
POINTS_STEP = Decimal("0.001")
SCORING_MAX_LENGTH = 200

Scoring = Mapping[str, Decimal]


class ScoringError(ValueError):
    """Barème refusé ; le message, en français, donne la raison."""


def parse_number(text: str) -> Decimal:
    """Valeur d'AMC : un nombre au point décimal, éventuellement signé."""
    if not NUMBER_RE.fullmatch(text.strip()):
        raise ScoringError(f"valeur non numérique : « {text.strip()} »")
    return Decimal(text.strip())


def parse_points(text: str) -> Decimal:
    """Valeur propre d'une proposition (question simple) : comme `Choice.points`, au plus 6
    chiffres avant la virgule et 3 après."""
    value = parse_number(text)
    if abs(value) >= POINTS_LIMIT or value != value.quantize(POINTS_STEP):
        raise ScoringError(f"« {text.strip()} » : au plus 6 chiffres avant la virgule et 3 après")
    return value


def parse_scoring(text: str) -> dict[str, Decimal]:
    """Directives `b=2,m=-0.5` ; chaîne vide : aucune (la base s'applique)."""
    directives: dict[str, Decimal] = {}
    if not text.strip():
        return directives
    for part in text.split(","):
        match = DIRECTIVE_RE.fullmatch(part.strip())
        if not match:
            raise ScoringError(f"« {part.strip()} » n'est pas de la forme directive=valeur")
        name, value = match.groups()
        if name not in DIRECTIVES:
            raise ScoringError(f"directive « {name} » non prise en charge")
        if name in directives:
            raise ScoringError(f"directive « {name} » répétée")
        try:
            directives[name] = parse_number(value)
        except ScoringError as error:
            raise ScoringError(f"{error} pour « {name} »") from None
    return directives


def format_scoring(directives: Scoring) -> str:
    """Forme enregistrée, relue par `parse_scoring` : `b=2,m=-0.5`."""
    return ",".join(f"{name}={value}" for name, value in directives.items())


@dataclass(frozen=True)
class Item:
    """Ce que le calcul d'une question demande, sans son texte."""

    multiple: bool
    n_choices: int  # « Aucune… » comprise
    correct: frozenset[int]
    scoring: Scoring = field(default_factory=dict)
    points: Mapping[int, Decimal] = field(default_factory=dict)  # question simple seulement
    none: int | None = None  # indice de « Aucune de ces réponses n'est correcte »


def score(item: Item, chosen: frozenset[int]) -> Decimal:
    """Note d'une question selon la réponse donnée (`chosen` vide : pas de réponse)."""
    if not chosen <= frozenset(range(item.n_choices)):
        raise ValueError("réponse hors des propositions")
    s = {**BASE, **item.scoring}
    if not chosen:
        return s["v"]
    if not item.multiple:
        if len(chosen) != 1:
            return s["e"]
        (index,) = chosen
        if index in item.points:
            return item.points[index]
        return s.get("mz", s["b"]) if index in item.correct else s["m"]
    if item.none is not None and item.none in chosen and len(chosen) > 1:
        return s["e"]
    others = [i for i in range(item.n_choices) if i != item.none]
    b, m, d, p = s["b"], s["m"], s["d"], s.get("p")
    if s.get("haut"):
        d = s["haut"] - len(others)
        p = Decimal(0) if p is None else p
    elif s.get("mz"):
        d = s["mz"]
        p = Decimal(0) if p is None else p
        b, m = Decimal(0), -(abs(s["mz"]) + abs(p) + 1)
    total = sum((b if (i in chosen) == (i in item.correct) else m for i in others), d)
    return total if p is None else max(total, p)


def max_score(item: Item) -> Decimal:
    """`MAX` s'il est défini ; sinon la note des bonnes réponses cochées, et elles seules."""
    if "MAX" in item.scoring:
        return item.scoring["MAX"]
    return score(item, item.correct)


def plain(value: Decimal) -> Decimal:
    """Sans zéro inutile ni exposant : 2.00 donne 2, -0.50 donne -0.5, 100 reste 100."""
    return Decimal(0) if value == 0 else Decimal(format(value.normalize(), "f"))


def legacy_scoring(
    *, multiple: bool, n_choices: int, b: Decimal, m: Decimal, v: Decimal, p: Decimal | None
) -> str:
    """Barème d'une question d'après celui de son QCM avant I12 (b, m, v, plancher p des
    multiples) : les mêmes notes et la même note maximale. Les valeurs de base sont omises."""
    directives = {name: plain(value) for name, value in (("b", b), ("m", m), ("v", v))}
    directives = {name: value for name, value in directives.items() if value != BASE[name]}
    if multiple and p is not None:
        directives["p"] = plain(p)
        if p > b * n_choices:  # avant I12, la note maximale ignorait le plancher
            directives["MAX"] = plain(b * n_choices)
    return format_scoring(directives)
