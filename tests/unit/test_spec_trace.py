"""Le mécanisme de traçabilité lui-même : s'il est faux, « terminé » ne veut rien dire."""

import pytest

from tests import spec_trace
from tests.spec_trace import Coverage, Requirement

SPEC = """
# Titre
- **[AAA-01]** (I0) Première exigence.
- **[AAA-02]** (I1) Deuxième exigence.
  - **[BBB-01]** (I2) Exigence imbriquée.
- Puce sans identifiant.
Texte **[CCC-01]** (I0) hors puce : ignoré.
"""


def test_parse_spec_extracts_ids_and_increments():
    reqs = spec_trace.parse_spec(SPEC)
    assert reqs == {
        "AAA-01": Requirement("AAA-01", 0),
        "AAA-02": Requirement("AAA-02", 1),
        "BBB-01": Requirement("BBB-01", 2),
    }


def test_parse_spec_rejects_duplicates():
    with pytest.raises(ValueError, match="AAA-01"):
        spec_trace.parse_spec("- **[AAA-01]** (I0) a\n- **[AAA-01]** (I1) b\n")


def test_missing_requirements_only_counts_passed_e2e_up_to_increment():
    reqs = spec_trace.parse_spec(SPEC)
    coverage = {
        "AAA-01": Coverage(passed_e2e=["test_a"]),
        "AAA-02": Coverage(passed_other=["test_unit_only"]),
    }
    missing = spec_trace.missing_requirements(reqs, coverage, up_to=1)
    assert [r.id for r in missing] == ["AAA-02"]  # BBB-01 (I2) pas encore exigible
    assert [r.id for r in spec_trace.missing_requirements(reqs, coverage, up_to=2)] == [
        "AAA-02",
        "BBB-01",
    ]


def test_missing_requirements_single_increment():
    reqs = spec_trace.parse_spec(SPEC)
    missing = spec_trace.missing_requirements(reqs, {}, up_to=0, only=2)
    assert [r.id for r in missing] == ["BBB-01"]


def test_report_lines_show_status():
    reqs = spec_trace.parse_spec(SPEC)
    lines = spec_trace.report_lines(reqs, {"AAA-01": Coverage(passed_e2e=["t1"])}, up_to=1)
    assert "OK" in lines[0] and "AAA-01" in lines[0] and "t1" in lines[0]
    assert "MANQUE" in lines[1] and "AAA-02" in lines[1]
    assert len(lines) == 2


def test_is_e2e():
    assert spec_trace.is_e2e("tests/e2e/test_x.py::test_y")
    assert not spec_trace.is_e2e("tests/unit/test_x.py::test_y")


def test_real_spec_and_pyproject_are_consistent():
    reqs = spec_trace.parse_spec(spec_trace.SPEC_FILE.read_text(encoding="utf-8"))
    assert len(reqs) >= 20
    inc = spec_trace.current_increment(spec_trace.PYPROJECT.read_text(encoding="utf-8"))
    assert inc >= 0
