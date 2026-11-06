"""Hook SessionStart : rappelle où en est le projet, d'après git (source de vérité)."""

from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from pathlib import Path


def run(project: Path, *cmd: str) -> str:
    try:
        out = subprocess.run(
            list(cmd), capture_output=True, text=True, timeout=10, check=False, cwd=project
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip()


def main() -> int:
    project = Path(os.environ.get("CLAUDE_PROJECT_DIR", "."))
    increment = tomllib.loads((project / "pyproject.toml").read_text(encoding="utf-8"))["tool"][
        "qcm"
    ]["increment"]
    lines = [
        "## État du projet QCM Live (hook SessionStart)",
        f"- Branche : {run(project, 'git', 'rev-parse', '--abbrev-ref', 'HEAD')}",
        f"- Incrément déclaré dans pyproject.toml : I{increment}",
        f"- Dernier tag d'incrément : {run(project, 'git', 'describe', '--tags', '--abbrev=0', '--match', 'inc-*') or 'aucun'}",  # noqa: E501
        "- Historique de main (un incrément par ligne) :",
        run(project, "git", "log", "--first-parent", "--oneline", "-8", "origin/main"),
        "- Fichiers modifiés :",
        run(project, "git", "status", "--short") or "(aucun)",
        "- PR ouvertes :",
        run(project, "gh", "pr", "list", "--limit", "5") or "(aucune ou gh indisponible)",
        "Rappel : procédure d'incrément = skill `increment` ; dernière section de REX.md.",
    ]
    if not (project / ".env").exists():
        lines.append("ATTENTION : .env absent — lancer `make setup`.")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
