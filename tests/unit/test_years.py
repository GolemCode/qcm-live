"""Année universitaire des groupes (GRP-04) : calcul et contrôle du format."""

from datetime import date

import pytest

from roster.years import academic_year, valid_year


@pytest.mark.parametrize(
    ("day", "year"),
    [
        (date(2026, 8, 31), "2025-2026"),
        (date(2026, 9, 1), "2026-2027"),
        (date(2026, 11, 17), "2026-2027"),
        (date(2027, 1, 1), "2026-2027"),
        (date(1999, 12, 31), "1999-2000"),
    ],
)
def test_academic_year_runs_from_september_to_august(day, year):
    assert academic_year(day) == year


@pytest.mark.parametrize("text", ["2025-2026", "1999-2000", "0000-0001"])
def test_two_consecutive_years_are_valid(text):
    assert valid_year(text)


@pytest.mark.parametrize(
    "text",
    [
        "",
        "2025",
        "2025-2025",
        "2025-2027",
        "2026-2025",
        "25-26",
        "2025/2026",
        "2025 - 2026",
        "2025-2026-2027",
        "2025-2026\n",
        "\uff12\uff10\uff12\uff15-\uff12\uff10\uff12\uff16",  # pleine chasse
    ],
)
def test_anything_else_is_refused(text):
    assert not valid_year(text)
