"""Configuration commune des tests : branchement de la traçabilité SPEC.md."""

from __future__ import annotations

import pytest

from tests import spec_trace

_coverage: dict[str, spec_trace.Coverage] = {}
_spec_ids_by_nodeid: dict[str, list[str]] = {}


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("spec", "traçabilité SPEC.md")
    group.addoption(
        "--spec-check",
        action="store_true",
        help="Échoue si une exigence livrée n'a aucun test E2E passé.",
    )
    group.addoption(
        "--spec-inc",
        type=int,
        default=None,
        help="Restreint le contrôle et le rapport aux exigences de cet incrément.",
    )


def _requirements() -> dict[str, spec_trace.Requirement]:
    return spec_trace.parse_spec(spec_trace.SPEC_FILE.read_text(encoding="utf-8"))


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    known = _requirements()
    unknown = []
    for item in items:
        ids = [arg for mark in item.iter_markers("spec") for arg in mark.args]
        for req_id in ids:
            if req_id not in known:
                unknown.append(f"{item.nodeid} → {req_id}")
        if ids:
            _spec_ids_by_nodeid[item.nodeid] = ids
    if unknown:
        raise pytest.UsageError(
            "Marqueurs spec vers des identifiants absents de SPEC.md :\n  " + "\n  ".join(unknown)
        )


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    ids = _spec_ids_by_nodeid.get(report.nodeid)
    if not ids:
        return
    passed = report.when == "call" and report.passed
    failed_or_skipped = report.failed or report.skipped
    if not passed and not failed_or_skipped:
        return
    for req_id in ids:
        cov = _coverage.setdefault(req_id, spec_trace.Coverage())
        if passed:
            target = cov.passed_e2e if spec_trace.is_e2e(report.nodeid) else cov.passed_other
            target.append(report.nodeid.split("::")[-1])
        else:
            cov.not_passed.append(report.nodeid)
            # Un échec ou un saut annule tout succès antérieur du même test (paramétrage).
            short = report.nodeid.split("::")[-1]
            if short in cov.passed_e2e:
                cov.passed_e2e.remove(short)


def _spec_options(config: pytest.Config) -> tuple[bool, int | None, int]:
    up_to = spec_trace.current_increment(spec_trace.PYPROJECT.read_text(encoding="utf-8"))
    return bool(config.getoption("--spec-check")), config.getoption("--spec-inc"), up_to


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    check, only, up_to = _spec_options(session.config)
    if not check:
        return
    missing = spec_trace.missing_requirements(_requirements(), _coverage, up_to=up_to, only=only)
    if missing:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_terminal_summary(terminalreporter, exitstatus: int, config: pytest.Config) -> None:
    check, only, up_to = _spec_options(config)
    if not check:
        return
    requirements = _requirements()
    scope = f"incrément I{only}" if only is not None else f"incréments I0..I{up_to}"
    terminalreporter.section(f"Couverture de SPEC.md ({scope})")
    for line in spec_trace.report_lines(requirements, _coverage, up_to=up_to, only=only):
        terminalreporter.write_line(line)
    missing = spec_trace.missing_requirements(requirements, _coverage, up_to=up_to, only=only)
    if missing:
        terminalreporter.write_line(
            f"ÉCHEC : {len(missing)} exigence(s) sans test E2E passé : "
            + ", ".join(r.id for r in missing),
            red=True,
            bold=True,
        )
    else:
        terminalreporter.write_line("Toutes les exigences exigibles sont vérifiées.", green=True)
