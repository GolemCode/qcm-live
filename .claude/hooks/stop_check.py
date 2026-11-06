"""Hook Stop : avant de rendre la main, `make check` doit passer si le code a changé.

L'état vérifié (HEAD + diff + fichiers non suivis) est mémorisé après un succès dans
.git/claude-last-green : aucun contrôle n'est relancé tant que rien n'a changé.
En cas d'échec, Claude est renvoyé au travail (code 2) ; une seule relance par arrêt.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


def git(project: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=False, cwd=project
    ).stdout


def state_key(project: Path) -> str:
    """Empreinte de l'état du dépôt : commit courant, modifications, fichiers non suivis."""
    digest = hashlib.sha256()
    for args in (("rev-parse", "HEAD"), ("diff", "HEAD"), ("status", "--porcelain")):
        digest.update(git(project, *args).encode())
    return digest.hexdigest()


def main() -> int:
    payload = json.load(sys.stdin)
    if payload.get("stop_hook_active"):
        return 0
    project = Path(os.environ.get("CLAUDE_PROJECT_DIR", "."))
    marker = project / ".git" / "claude-last-green"
    key = state_key(project)
    if marker.exists() and marker.read_text() == key:
        return 0
    result = subprocess.run(
        ["make", "check"], capture_output=True, text=True, check=False, cwd=project
    )
    if result.returncode == 0:
        marker.write_text(key)
        return 0
    tail = "\n".join((result.stdout + result.stderr).splitlines()[-60:])
    print(
        "`make check` échoue : corriger avant de déclarer le travail terminé.\n" + tail,
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
