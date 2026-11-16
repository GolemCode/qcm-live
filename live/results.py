"""Résultats d'une session (RES-01, RES-02) — fonctions pures, sur la copie figée.

La note suit le barème AMC figé au lancement (bank.scoring, SPEC §3). Une question sans
réponse enregistrée vaut `v`, y compris celles qu'un retardataire a manquées (ETU-08). Un
étudiant du groupe qui ne s'est jamais connecté est absent : il n'a pas de note.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from bank.scoring import LETTERS, Item, max_score, parse_scoring, score

if TYPE_CHECKING:
    from live.snapshot import FrozenQuestion, FrozenQuiz, FrozenStudent

ABSENT = "Absent"
NO_ANSWER = "-"
# Un tableur exécute une cellule qui commence ainsi : les noms viennent d'un fichier extérieur.
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")  # les deux derniers selon l'OWASP

Answers = Mapping[int, Sequence[int]]  # indice de la question -> propositions choisies


@dataclass(frozen=True)
class Mark:
    """Réponse donnée à une question et points obtenus."""

    letters: str  # A = première proposition de la question figée ; "" : pas de réponse
    points: Decimal


@dataclass(frozen=True)
class StudentResult:
    number: str
    name: str
    marks: list[Mark] | None  # une par question, dans l'ordre du QCM ; None : absent

    @property
    def total(self) -> Decimal | None:
        if self.marks is None:
            return None
        return sum((mark.points for mark in self.marks), Decimal(0))

    @property
    def total_text(self) -> str:
        """Note affichée, sur la page comme dans le CSV : « Absent » ou nombre à la française."""
        total = self.total
        return ABSENT if total is None else decimal_fr(total)


def letters(choices: Iterable[int]) -> str:
    """Lettres des propositions choisies, dans l'ordre ; "" si aucune."""
    return "".join(LETTERS[i] for i in sorted(choices))


def none_index(question: FrozenQuestion) -> int | None:
    """Indice de « Aucune de ces réponses n'est correcte », toujours la dernière (BAN-09)."""
    choices = question["choices"]
    return len(choices) - 1 if choices and choices[-1]["none"] else None


def item(question: FrozenQuestion) -> Item:
    """Ce que le calcul de la note demande de la question figée (barème compris)."""
    choices = question["choices"]
    return Item(
        multiple=question["multiple"],
        n_choices=len(choices),
        correct=frozenset(i for i, choice in enumerate(choices) if choice["correct"]),
        scoring=parse_scoring(question["scoring"]),
        points={i: Decimal(c["points"]) for i, c in enumerate(choices) if c["points"] is not None},
        none=none_index(question),
    )


def grade(quiz: FrozenQuiz, answers: Answers) -> list[Mark]:
    """Réponse et points de chaque question du QCM, dans son ordre."""
    marks = []
    for index, question in enumerate(quiz["questions"]):
        chosen = frozenset(answers.get(index, ()))
        marks.append(Mark(letters(chosen), score(item(question), chosen)))
    return marks


def max_total(quiz: FrozenQuiz) -> Decimal:
    return sum((max_score(item(q)) for q in quiz["questions"]), Decimal(0))


def results(
    quiz: FrozenQuiz, students: Sequence[FrozenStudent], present: Mapping[str, Answers]
) -> list[StudentResult]:
    """Un résultat par étudiant du groupe, dans l'ordre du fichier importé. `present` : les
    réponses de chaque étudiant connecté, par numéro."""
    return [
        StudentResult(
            s["number"],
            s["name"],
            grade(quiz, present[s["number"]]) if s["number"] in present else None,
        )
        for s in students
    ]


def decimal_fr(value: Decimal) -> str:
    """Nombre à la française, sans zéro inutile : 1,5 ; 2 ; -0,25."""
    if value == 0:
        return "0"
    return format(value.normalize(), "f").replace(".", ",")


def neutralised(text: str) -> str:
    """Texte venu de l'extérieur, rendu inoffensif pour un tableur (préfixe apostrophe)."""
    return f"'{text}" if text.startswith(FORMULA_PREFIXES) else text


def csv_rows(quiz: FrozenQuiz, rows: Sequence[StudentResult]) -> list[list[str]]:
    """Export CSV : en-tête, puis une ligne par étudiant ; pour chaque question, dans l'ordre
    du QCM, la réponse donnée (`-` : aucune) et les points obtenus."""
    n = len(quiz["questions"])
    maximum = decimal_fr(max_total(quiz))
    header = ["numéro", "nom", "note", "note max"]
    for rank in range(1, n + 1):  # référence d'une question : son rang dans le QCM figé
        header += [f"Q{rank} réponse", f"Q{rank} points"]
    lines = [header]
    for row in rows:
        identity = [neutralised(row.number), neutralised(row.name)]
        cells = [*identity, row.total_text, maximum]
        if row.marks is None:  # absent
            lines.append(cells + [""] * (2 * n))
            continue
        for mark in row.marks:
            cells += [mark.letters or NO_ANSWER, decimal_fr(mark.points)]
        lines.append(cells)
    return lines
