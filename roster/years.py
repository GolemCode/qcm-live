"""Année universitaire d'un groupe (GRP-04) : « 2025-2026 », de septembre à août."""

from __future__ import annotations

import re
from datetime import date

YEAR_LENGTH = len("2025-2026")
FIRST_MONTH = 9  # la rentrée : septembre ouvre l'année universitaire
YEAR_ERROR = "Année au format 2025-2026 : deux années qui se suivent."
_YEAR = re.compile(r"(\d{4})-(\d{4})", re.ASCII)


def academic_year(day: date) -> str:
    """Année universitaire du jour `day` : de septembre à août."""
    first = day.year if day.month >= FIRST_MONTH else day.year - 1
    return f"{first}-{first + 1}"


def group_label(name: str, year: str) -> str:
    """Un groupe et son année, partout où il est nommé : « ITI4 — 2025-2026 »."""
    return f"{name} — {year}"


def valid_year(text: str) -> bool:
    """« AAAA-AAAA », deux années qui se suivent."""
    match = _YEAR.fullmatch(text)
    return match is not None and int(match[2]) == int(match[1]) + 1
