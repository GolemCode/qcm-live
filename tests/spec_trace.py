"""Traçabilité SPEC.md ↔ tests.

Chaque exigence de SPEC.md s'écrit `- **[XXX-nn]** (In) texte`. Un test s'y rattache par
`@pytest.mark.spec("XXX-nn")`. Avec `--spec-check`, la session échoue si une exigence
d'un incrément livré (≤ `[tool.qcm] increment`) n'a aucun test E2E *passé* (un test sauté
ne compte pas). Un marqueur qui vise un identifiant inconnu fait toujours échouer la collecte.

`make verify` enregistre son résultat (`--spec-record`) avec l'empreinte des fichiers du dépôt ;
`make accept` le reprend tant que cette empreinte n'a pas changé (`tests/accept.py`).
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC_FILE = ROOT / "SPEC.md"
PYPROJECT = ROOT / "pyproject.toml"
E2E_DIR = "tests/e2e/"
RECORD_FILE = ROOT / ".verify-result.json"
# Le REX ne change rien aux tests : l'écrire après `make verify` ne doit pas forcer à le relancer.
STATE_IGNORED = ("REX.md", "rex/")

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


def state_key(root: Path) -> str:
    """Empreinte des fichiers du dépôt : suivis et non suivis non ignorés, contenu compris.

    Un fichier suivi mais supprimé compte comme absent. Le REX est exclu (`STATE_IGNORED`).
    """
    listing = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        capture_output=True,
        check=True,
        cwd=root,
    ).stdout.decode()
    digest = hashlib.sha256()
    for name in sorted(set(filter(None, listing.split("\0")))):
        if name.startswith(STATE_IGNORED):
            continue
        path = root / name
        digest.update(name.encode() + b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest() if path.is_file() else b"-")
    return digest.hexdigest()


def dump_record(state: str, coverage: dict[str, Coverage], finished_at: str) -> str:
    covered = {req_id: asdict(cov) for req_id, cov in sorted(coverage.items())}
    return json.dumps({"state": state, "finished_at": finished_at, "coverage": covered}, indent=1)


def load_record(text: str, state: str) -> tuple[dict[str, Coverage], str] | None:
    """Couverture et date d'un `make verify` vert enregistré, s'il porte sur cet état."""
    try:
        data = json.loads(text)
        if data["state"] != state:
            return None
        coverage = {req_id: Coverage(**cov) for req_id, cov in data["coverage"].items()}
        return coverage, str(data["finished_at"])
    except (ValueError, KeyError, TypeError):
        return None
