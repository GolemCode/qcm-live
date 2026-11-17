"""Ordre des questions d'un QCM recomposé (CMP-04) : logique pure, sans Django."""

from __future__ import annotations

from collections.abc import Mapping, Sequence


def arrange(
    current: Sequence[int], chosen: Sequence[int], file_ranks: Mapping[int, int]
) -> list[int]:
    """Nouvel ordre des questions `chosen` (dans l'ordre de la banque) d'un QCM qui a `current`.

    Les questions venues du fichier du QCM (`file_ranks` : question -> rang) suivent leur rang,
    si bien qu'une question remise retrouve sa place ; les autres gardent leur ordre, et les
    nouvelles vont à la fin, dans l'ordre de `chosen`. Sans fichier, `file_ranks` est vide.
    """
    wanted = set(chosen)
    from_file = sorted((q for q in chosen if q in file_ranks), key=file_ranks.__getitem__)
    rest = [q for q in dict.fromkeys([*current, *chosen]) if q in wanted and q not in file_ranks]
    return from_file + rest
