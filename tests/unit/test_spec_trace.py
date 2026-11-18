"""Le mécanisme de traçabilité lui-même : s'il est faux, « terminé » ne veut rien dire."""

import pytest

from tests import spec_trace
from tests.spec_trace import Coverage, Declared, Requirement

SPEC = """
# Titre
- **[AAA-01]** (I0) Première exigence.
- **[AAA-02]** (I1) Deuxième exigence.
  - **[BBB-01]** (I2) Exigence imbriquée.
- **[DDD-01]** (ID) Exigence d'un incrément à lettre.
- Puce sans identifiant.
Texte **[CCC-01]** (I0) hors puce : ignoré.
"""


def test_parse_spec_extracts_ids_and_increments():
    reqs = spec_trace.parse_spec(SPEC)
    assert reqs == {
        "AAA-01": Requirement("AAA-01", "0"),
        "AAA-02": Requirement("AAA-02", "1"),
        "BBB-01": Requirement("BBB-01", "2"),
        "DDD-01": Requirement("DDD-01", "D"),
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
    missing = spec_trace.missing_requirements(reqs, coverage, up_to=Declared(1))
    assert [r.id for r in missing] == ["AAA-02"]  # BBB-01 (I2), DDD-01 (ID) pas exigibles
    assert [r.id for r in spec_trace.missing_requirements(reqs, coverage, up_to=Declared(2))] == [
        "AAA-02",
        "BBB-01",
    ]


def test_lettered_increment_is_due_once_declared():
    reqs = spec_trace.parse_spec(SPEC)
    declared = Declared(1, frozenset({"D"}))
    missing = spec_trace.missing_requirements(reqs, {}, up_to=declared)
    assert [r.id for r in missing] == ["AAA-01", "AAA-02", "DDD-01"]  # les lettres après
    only = spec_trace.missing_requirements(reqs, {}, up_to=Declared(0), only="D")
    assert [r.id for r in only] == ["DDD-01"]
    assert str(declared) == "I0..I1, ID"


def test_declared_increments_read_from_pyproject():
    text = '[tool.qcm]\nincrement = 17\nlettered = ["D"]\n'
    assert spec_trace.current_increment(text) == Declared(17, frozenset({"D"}))
    assert spec_trace.current_increment("[tool.qcm]\nincrement = 3\n") == Declared(3)


@pytest.mark.parametrize(("typed", "expected"), [("d", "D"), ("D", "D"), ("07", "7"), (12, "12")])
def test_increment_typed_for_accept_is_normalised(typed, expected):
    assert spec_trace.normalise(typed) == expected


@pytest.mark.parametrize("typed", ["ID", "I17", "", "d1"])
def test_increment_typed_for_accept_refuses_what_names_no_increment(typed):
    with pytest.raises(ValueError, match="Incrément invalide"):
        spec_trace.normalise(typed)


def test_missing_requirements_single_increment():
    reqs = spec_trace.parse_spec(SPEC)
    missing = spec_trace.missing_requirements(reqs, {}, up_to=Declared(0), only="2")
    assert [r.id for r in missing] == ["BBB-01"]


def test_report_lines_show_status():
    reqs = spec_trace.parse_spec(SPEC)
    lines = spec_trace.report_lines(
        reqs, {"AAA-01": Coverage(passed_e2e=["t1"])}, up_to=Declared(1)
    )
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
    assert inc.number >= 0
    known = {req.increment for req in reqs.values()}
    assert inc.letters <= known, inc.letters  # une lettre déclarée a ses exigences


# --- I15 : `make accept` reprend le résultat du dernier `make verify` vert sur le même état.


def _repo(path):
    import subprocess

    def git(*args):
        subprocess.run(["git", *args], cwd=path, check=True, capture_output=True)

    git("init", "-q")
    (path / ".gitignore").write_text("ignored.txt\n")
    (path / "code.py").write_text("x = 1\n")
    (path / "rex").mkdir()
    (path / "rex" / "I1.md").write_text("# I1\n")
    (path / "REX.md").write_text("# REX\n")
    git("add", ".")
    return path


def test_state_key_follows_code_but_not_the_rex(tmp_path):
    repo = _repo(tmp_path)
    before = spec_trace.state_key(repo)
    (repo / "rex" / "I1.md").write_text("# I1\nAudit spec-auditor : abc1234\n")
    (repo / "rex" / "I2.md").write_text("# I2\n")
    (repo / "REX.md").write_text("# REX\n| I2 |\n")
    (repo / "ignored.txt").write_text("rien\n")
    assert spec_trace.state_key(repo) == before
    (repo / "code.py").write_text("x = 2\n")
    assert spec_trace.state_key(repo) != before


def test_state_key_sees_new_and_deleted_files(tmp_path):
    repo = _repo(tmp_path)
    before = spec_trace.state_key(repo)
    (repo / "new.py").write_text("")
    with_new = spec_trace.state_key(repo)
    assert with_new != before
    (repo / "new.py").unlink()
    (repo / "code.py").unlink()  # suivi, mais supprimé
    assert spec_trace.state_key(repo) not in (before, with_new)


def test_record_is_reused_only_for_the_same_state():
    coverage = {"AAA-01": Coverage(passed_e2e=["tests/e2e/test_a.py::test_x"])}
    text = spec_trace.dump_record("abc", coverage, "2026-11-17T18:00:00+01:00")
    assert spec_trace.load_record(text, "abc") == (coverage, "2026-11-17T18:00:00+01:00")
    assert spec_trace.load_record(text, "autre") is None


@pytest.mark.parametrize(
    "text",
    [
        "",
        "{",
        "[]",
        '{"state": "abc"}',
        '{"state": "abc", "finished_at": 1, "coverage": {"A": {"x": 1}}}',
    ],
)
def test_damaged_record_means_rerun(text):
    assert spec_trace.load_record(text, "abc") is None
