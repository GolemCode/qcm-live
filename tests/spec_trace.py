"""Traçabilité SPEC.md ↔ tests.

Chaque exigence de SPEC.md s'écrit `- **[XXX-nn]** (In) texte`. Un test s'y rattache par
`@pytest.mark.spec("XXX-nn")`. Avec `--spec-check`, la session échoue si une exigence
d'un incrément livré (≤ `[tool.qcm] increment`) n'a aucun test E2E *passé* (un test sauté
ne compte pas). Un marqueur qui vise un identifiant inconnu fait toujours échouer la collecte.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC_FILE = ROOT / "SPEC.md"
PYPROJECT = ROOT / "pyproject.toml"
E2E_DIR = "tests/e2e/"

REQUIREMENT_RE = re.compile(r"^\s*-\s+\*\*\[(?P<id>[A-Z]{3}-\d{2})\]\*\*\s+\(I(?P<inc>\d+)\)")


@dataclass(frozen=True)
class Requirement:
    id: str
    increment: int


@dataclass
class Coverage:
    """Résultats des tests rattachés à une exigence."""

    passed_e2e: list[str] = field(default_factory=list)
    passed_other: list[str] = field(default_factory=list)
    not_passed: list[str] = field(default_factory=list)


def parse_spec(text: str) -> dict[str, Requirement]:
    requirements: dict[str, Requirement] = {}
    for line in text.splitlines():
        match = REQUIREMENT_RE.match(line)
        if not match:
            continue
        req_id = match["id"]
        if req_id in requirements:
            raise ValueError(f"Identifiant en double dans SPEC.md : {req_id}")
        requirements[req_id] = Requirement(req_id, int(match["inc"]))
    return requirements


def current_increment(pyproject_text: str) -> int:
    return int(tomllib.loads(pyproject_text)["tool"]["qcm"]["increment"])


def is_e2e(nodeid: str) -> bool:
    return nodeid.startswith(E2E_DIR)


def due_requirements(
    requirements: dict[str, Requirement], *, up_to: int, only: int | None = None
) -> list[Requirement]:
    """Exigences exigibles : celles de l'incrément `only`, sinon toutes celles ≤ `up_to`."""
    due = [
        req
        for req in requirements.values()
        if (req.increment == only if only is not None else req.increment <= up_to)
    ]
    return sorted(due, key=lambda r: (r.increment, r.id))


def missing_requirements(
    requirements: dict[str, Requirement],
    coverage: dict[str, Coverage],
    *,
    up_to: int,
    only: int | None = None,
) -> list[Requirement]:
    """Exigences exigibles sans aucun test E2E passé."""
    return [
        req
        for req in due_requirements(requirements, up_to=up_to, only=only)
        if not coverage.get(req.id, Coverage()).passed_e2e
    ]


def report_lines(
    requirements: dict[str, Requirement],
    coverage: dict[str, Coverage],
    *,
    up_to: int,
    only: int | None = None,
) -> list[str]:
    lines = []
    for req in due_requirements(requirements, up_to=up_to, only=only):
        cov = coverage.get(req.id, Coverage())
        status = "OK " if cov.passed_e2e else "MANQUE"
        tests = ", ".join(cov.passed_e2e) or "aucun test E2E passé"
        lines.append(f"  {status:6} {req.id} (I{req.increment})  {tests}")
    return lines
