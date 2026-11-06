"""Hook Stop : avant de rendre la main, `make check` doit passer si le code a changé.

L'état vérifié (commit courant, modifications, contenu des fichiers non suivis) est
mémorisé après un succès dans <git-dir>/claude-last-green : aucun contrôle n'est relancé
tant que rien n'a changé. En cas d'échec, Claude est renvoyé au travail (code 2) ;
une seule relance par arrêt (`stop_hook_active`).
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
    """Empreinte de l'état du dépôt : commit, diff suivi, et contenu des fichiers non suivis."""
    digest = hashlib.sha256()
    for args in (("rev-parse", "HEAD"), ("diff", "HEAD"), ("status", "--porcelain")):
        digest.update(git(project, *args).encode())
    for name in sorted(git(project, "ls-files", "--others", "--exclude-standard").splitlines()):
        path = project / name
        if path.is_file():
            digest.update(name.encode())
            digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def marker_path(project: Path) -> Path:
    """Fichier témoin dans le vrai dossier git (aussi correct dans un worktree)."""
    git_dir = git(project, "rev-parse", "--absolute-git-dir").strip()
    return Path(git_dir or project / ".git") / "claude-last-green"


def main() -> int:
    payload = json.load(sys.stdin)
    if payload.get("stop_hook_active"):
        return 0
    project = Path(os.environ.get("CLAUDE_PROJECT_DIR", "."))
    marker = marker_path(project)
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
