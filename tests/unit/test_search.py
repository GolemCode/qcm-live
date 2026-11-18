"""Recherche dans la banque (BAN-11) : pliage, correspondance, tris."""

from __future__ import annotations

import pytest

from bank.search import ALPHABETICAL, OLDEST, RECENT, SORTS, fold, matches, sort_key


@pytest.mark.parametrize(
    "text,folded",
    [
        ("École", "ecole"),
        ("ÉTÉ", "ete"),
        ("Œuvre", "œuvre"),  # ligature : sans décomposition, mais en minuscule
        ("Straße", "strasse"),  # casefold, pas seulement lower
        ("ça", "ca"),
        ("", ""),
    ],
)
def test_fold(text, folded):
    assert fold(text) == folded


def test_matches_statement_or_choice_ignoring_case_and_accents():
    texts = ["Où est l'École normale ?", "Paris", "LYON"]
    assert matches("ecole", texts)
    assert matches("ÉCOLE NORM", texts)
    assert matches("lyon", texts)
    assert matches("  paris  ", texts)  # espaces autour ignorés
    assert not matches("rome", texts)
    assert not matches("ecole paris", texts)  # une seule chaîne, pas des mots épars
    assert matches("", texts) and matches("   ", [])  # sans texte : tout correspond
    assert not matches("x", [])


def test_sorts():
    questions = [(1, "Zèbre ?"), (2, "été ?"), (3, "Eau ?"), (4, "arbre ?"), (5, "Ecole ?")]

    def order(sort: str) -> list[int]:
        return [pk for pk, text in sorted(questions, key=lambda q: sort_key(sort, *q))]

    assert order(RECENT) == [5, 4, 3, 2, 1]
    assert order(OLDEST) == [1, 2, 3, 4, 5]
    assert order(ALPHABETICAL) == [4, 3, 5, 2, 1]  # arbre, Eau, Ecole, été, Zèbre
    assert list(SORTS) == [RECENT, OLDEST, ALPHABETICAL]  # le défaut en premier


def test_alphabetical_ties_are_broken_by_exact_text_then_rank():
    questions = [(3, "eau ?"), (1, "Eau ?"), (2, "Eau ?")]
    ordered = sorted(questions, key=lambda q: sort_key(ALPHABETICAL, *q))
    assert ordered == [(1, "Eau ?"), (2, "Eau ?"), (3, "eau ?")]
