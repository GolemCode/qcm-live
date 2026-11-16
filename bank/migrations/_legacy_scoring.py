"""Barème d'une question d'après celui de son QCM avant I12, pour les migrations bank 0002
et live 0005.

Copie figée : une évolution de `bank.scoring` ne doit pas changer ce que ces migrations
écrivent. Le préfixe `_` écarte ce module du chargeur de migrations de Django.
"""

from __future__ import annotations

from decimal import Decimal

BASE = {"b": Decimal(1), "m": Decimal(0), "v": Decimal(0)}


def _plain(value: Decimal) -> Decimal:
    return Decimal(0) if value == 0 else Decimal(format(value.normalize(), "f"))


def legacy_scoring(
    *, multiple: bool, n_choices: int, b: Decimal, m: Decimal, v: Decimal, p: Decimal | None
) -> str:
    """Les mêmes notes et la même note maximale qu'avant I12 (b, m, v, plancher p des
    multiples). Les valeurs de base sont omises."""
    directives = {name: _plain(value) for name, value in (("b", b), ("m", m), ("v", v))}
    directives = {name: value for name, value in directives.items() if value != BASE[name]}
    if multiple and p is not None:
        directives["p"] = _plain(p)
        if p > b * n_choices:  # avant I12, la note maximale ignorait le plancher
            directives["MAX"] = _plain(b * n_choices)
    return ",".join(f"{name}={value}" for name, value in directives.items())
