"""Hook Stop : avant de rendre la main, la qualité et la procédure doivent être au rendez-vous.

Qualité : `make check` doit passer si le code a changé. L'état vérifié (commit courant,
modifications, contenu des fichiers non suivis) est mémorisé après un succès dans
<git-dir>/claude-last-green : aucun contrôle n'est relancé tant que rien n'a changé.

Procédure : sur une branche d'incrément, ou sur main juste après une fusion, les étapes
qui se lisent dans git, dans REX.md et sur GitHub doivent être faites.

En cas d'échec, Claude est renvoyé au travail (code 2), une seule fois par arrêt
(`stop_hook_active`). C'est donc un rappel, pas un blocage : s'arrêter reste possible pour
poser une question au commanditaire ou attendre la CI. Le rappel revient à chaque arrêt, même
sans nouveau commit : l'arrêt prématuré de I6 survenait justement après une revue sans commit.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

INC_BRANCH = re.compile(r"^inc/(\d+|r)-")
INC_MERGE = re.compile(r"^Incrément (\d+|R)\b")
# Ligne écrite une fois l'audit fait : une simple mention de l'agent ne suffit pas.
AUDIT_LINE = re.compile(r"^Audit spec-auditor : [0-9a-f]{7,}", re.MULTILINE)


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


def rex_section(rex: str, increment: str) -> str:
    """La section de REX.md d'un incrément (`## I6 …`, `## R …`), vide si elle manque."""
    match = re.search(
        rf"^## I?{increment}\b.*?(?=^## |\Z)", rex, re.MULTILINE | re.DOTALL | re.IGNORECASE
    )
    return match.group(0) if match else ""


def increment_gaps(increment: str, rex: str, pr_state: str | None) -> list[str]:
    """Ce qu'il reste à faire sur une branche d'incrément, d'après ce que l'on peut constater.

    Revues et contrôle visuel ne laissent pas de trace vérifiable : l'audit n'est contrôlé que
    par la ligne déclarée dans le REX. Le reste de la procédure dépend du skill `increment`.
    """
    gaps: list[str] = []
    section = rex_section(rex, increment)
    if not section:
        gaps.append("REX.md n'a pas de section pour cet incrément.")
    if not AUDIT_LINE.search(section):
        gaps.append(
            "L'audit n'est pas consigné : lancer l'agent spec-auditor, puis écrire dans le REX "
            "la ligne « Audit spec-auditor : <commit> »."
        )
    if pr_state is None:
        gaps.append("Aucune PR ouverte (ou gh indisponible) : pousser la branche et ouvrir la PR.")
    elif pr_state == "OPEN":
        gaps.append("La PR n'est pas fusionnée : attendre la CI verte, puis `gh pr merge --merge`.")
    elif pr_state == "MERGED":
        gaps.append(f"PR fusionnée : revenir sur main, puis poser le tag inc-{increment}.")
    return gaps


def missing_tag(last_merge: str, tags: set[str]) -> list[str]:
    """Sur main : le tag de la dernière fusion d'incrément, s'il manque."""
    merged = INC_MERGE.match(last_merge)
    tag = f"inc-{merged.group(1).lower()}" if merged else None
    return [f"Poser et pousser le tag {tag}."] if tag and tag not in tags else []


def pull_request_state(project: Path) -> str | None:
    try:
        out = subprocess.run(
            ["gh", "pr", "view", "--json", "state", "--jq", ".state"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
            cwd=project,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None


def project_gaps(project: Path) -> list[str]:
    branch = git(project, "rev-parse", "--abbrev-ref", "HEAD").strip()
    if branch == "main":
        return missing_tag(
            git(project, "log", "--first-parent", "-1", "--format=%s").strip(),
            set(git(project, "tag", "--list", "inc-*").split()),
        )
    match = INC_BRANCH.match(branch)
    if not match:
        return []
    rex_file = project / "REX.md"
    rex = rex_file.read_text(encoding="utf-8") if rex_file.exists() else ""
    return increment_gaps(match.group(1), rex, pull_request_state(project))


def quality_problem(project: Path) -> str | None:
    marker = marker_path(project)
    key = state_key(project)
    if marker.exists() and marker.read_text() == key:
        return None
    result = subprocess.run(
        ["make", "check"], capture_output=True, text=True, check=False, cwd=project
    )
    if result.returncode != 0:
        tail = "\n".join((result.stdout + result.stderr).splitlines()[-60:])
        return "`make check` échoue : corriger avant de déclarer le travail terminé.\n" + tail
    marker.write_text(key)
    return None


def procedure_problem(project: Path) -> str | None:
    gaps = project_gaps(project)
    if not gaps:
        return None
    return (
        "Procédure d'incrément inachevée (skill `increment`). Un rapport de revue n'est pas "
        "un message final : continuer. Si tu attends vraiment le commanditaire ou la CI, "
        "redis-le clairement et arrête-toi.\n- " + "\n- ".join(gaps)
    )


def main() -> int:
    payload = json.load(sys.stdin)
    if payload.get("stop_hook_active"):
        return 0
    project = Path(os.environ.get("CLAUDE_PROJECT_DIR", "."))
    problem = quality_problem(project) or procedure_problem(project)
    if problem:
        print(problem, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
