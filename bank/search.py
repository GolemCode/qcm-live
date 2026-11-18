"""Recherche dans la banque (BAN-11) : texte comparé sans majuscules ni accents, et tris.
Module pur, sans Django."""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable

PER_PAGE = 20

RECENT, OLDEST, ALPHABETICAL = "", "anciennes", "alpha"  # "" : le tri par défaut
SORTS = {
    RECENT: "Plus récentes d'abord",
    OLDEST: "Plus anciennes d'abord",
    ALPHABETICAL: "Énoncé de A à Z",
}


def fold(text: str) -> str:
    """Texte sans accents ni majuscules : « École » et « ecole » se confondent."""
    bare = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
    return bare.casefold()


def matches(needle: str, texts: Iterable[str]) -> bool:
    """Le texte cherché figure-t-il dans l'un de ces textes ? Un texte vide figure partout."""
    folded = fold(needle.strip())
    return not folded or any(folded in fold(text) for text in texts)


def sort_key(sort: str, pk: int, plain_text: str) -> tuple[object, ...]:
    """Clé de tri d'une question : son rang (`pk`, croissant à la création) ou son énoncé en
    texte brut, l'énoncé exact puis le rang départageant."""
    if sort == ALPHABETICAL:
        return fold(plain_text), plain_text, pk
    return (-pk,) if sort == RECENT else (pk,)
