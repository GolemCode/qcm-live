"""Contenu du QR code affiché sur le téléphone à la fin de la session (FIN-01) — pur.

Texte brut, lisible par n'importe quelle application de lecture :

    Session 482913
    Étudiant 00123
    Q2 A
    Q1 BD
    Q3 -

Une ligne par question, dans l'ordre où l'étudiant l'a eue. La référence est le rang de la
question dans le QCM figé (Q1 à Qn) ; les lettres sont celles du tableau (ordre canonique,
A = 0), et `-` signifie aucune réponse.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from bank.scoring import LETTERS

NO_ANSWER = "-"


def letters(choices: Iterable[int]) -> str:
    """Lettres du tableau des propositions choisies, dans l'ordre ; "" si aucune."""
    return "".join(LETTERS[i] for i in sorted(choices))


def question_ref(index: int) -> str:
    """Référence de la question d'indice `index` du QCM figé."""
    return f"Q{index + 1}"


def receipt(code: str, number: str, received: Iterable[tuple[int, Sequence[int]]]) -> str:
    """`received` : (indice de la question, propositions choisies), dans l'ordre reçu."""
    lines = [f"Session {code}", f"Étudiant {number}"]
    lines += [f"{question_ref(q)} {letters(chosen) or NO_ANSWER}" for q, chosen in received]
    return "\n".join(lines)
