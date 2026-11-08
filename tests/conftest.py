"""Configuration commune des tests : branchement de la traçabilité SPEC.md."""

from __future__ import annotations

import functools
import time
from datetime import timedelta

import pytest
from django.utils import timezone

from tests import spec_trace

# Exigence → résultats, les tests étant identifiés par leur nodeid complet (pas de collision
# entre deux tests de même nom dans des fichiers différents).
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


@pytest.fixture(autouse=True)
def _fast_password_hasher(settings) -> None:
    """PBKDF2 (≈ 1 M itérations) coûte ~0,3 s par création ou connexion : inutile en test."""
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture(autouse=True)
def _steady_clock(monkeypatch) -> None:
    """Le serveur de test lit une horloge sans saut. L'horloge système peut être corrigée en
    arrière (sur un PC sous WSL2 : -1,9 s toutes les 32 s), ce qui fait échouer au hasard tout
    test à faible marge. L'application, elle, garde l'horloge système : voir REX.md, section R."""
    wall, monotonic = timezone.now(), time.monotonic()
    monkeypatch.setattr(
        timezone, "now", lambda: wall + timedelta(seconds=time.monotonic() - monotonic)
    )


@functools.cache
def _requirements() -> dict[str, spec_trace.Requirement]:
    return spec_trace.parse_spec(spec_trace.SPEC_FILE.read_text(encoding="utf-8"))


@functools.cache
def _current_increment() -> int:
    return spec_trace.current_increment(spec_trace.PYPROJECT.read_text(encoding="utf-8"))


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    known = _requirements()
    unknown = []
    for item in items:
        ids = [arg for mark in item.iter_markers("spec") for arg in mark.args]
        unknown += [f"{item.nodeid} → {req_id}" for req_id in ids if req_id not in known]
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
    if not passed and not (report.failed or report.skipped):
        return
    for req_id in ids:
        cov = _coverage.setdefault(req_id, spec_trace.Coverage())
        if passed:
            target = cov.passed_e2e if spec_trace.is_e2e(report.nodeid) else cov.passed_other
            target.append(report.nodeid)
        else:
            cov.not_passed.append(report.nodeid)
            # Un échec au démontage annule le succès de ce même test.
            if report.nodeid in cov.passed_e2e:
                cov.passed_e2e.remove(report.nodeid)


def _missing(config: pytest.Config) -> list[spec_trace.Requirement]:
    return spec_trace.missing_requirements(
        _requirements(),
        _coverage,
        up_to=_current_increment(),
        only=config.getoption("--spec-inc"),
    )


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    if session.config.getoption("--spec-check") and _missing(session.config):
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_terminal_summary(terminalreporter, exitstatus: int, config: pytest.Config) -> None:
    if not config.getoption("--spec-check"):
        return
    only = config.getoption("--spec-inc")
    up_to = _current_increment()
    scope = f"incrément I{only}" if only is not None else f"incréments I0..I{up_to}"
    terminalreporter.section(f"Couverture de SPEC.md ({scope})")
    for line in spec_trace.report_lines(_requirements(), _coverage, up_to=up_to, only=only):
        terminalreporter.write_line(line)
    missing = _missing(config)
    if missing:
        terminalreporter.write_line(
            f"ÉCHEC : {len(missing)} exigence(s) sans test E2E passé : "
            + ", ".join(r.id for r in missing),
            red=True,
            bold=True,
        )
    else:
        terminalreporter.write_line("Toutes les exigences exigibles sont vérifiées.", green=True)
