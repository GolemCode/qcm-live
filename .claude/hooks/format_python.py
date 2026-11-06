"""Hook PostToolUse (Edit/Write) : formate et corrige le fichier Python modifié avec ruff.

Les erreurs que ruff ne sait pas corriger sont renvoyées à Claude (code 2).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def ruff_binary(project: Path) -> Path | None:
    for candidate in (project / ".venv/bin/ruff", project / ".venv/Scripts/ruff.exe"):
        if candidate.exists():
            return candidate
    return None


def main() -> int:
    payload = json.load(sys.stdin)
    file_path = payload.get("tool_input", {}).get("file_path", "")
    if not file_path.endswith(".py") or not Path(file_path).exists():
        return 0
    project = Path(os.environ.get("CLAUDE_PROJECT_DIR", "."))
    ruff = ruff_binary(project)
    if ruff is None:
        return 0
    subprocess.run([ruff, "format", "--quiet", file_path], check=False, cwd=project)
    result = subprocess.run(
        [ruff, "check", "--fix", "--quiet", file_path],
        capture_output=True,
        text=True,
        check=False,
        cwd=project,
    )
    if result.returncode != 0:
        print(f"ruff signale des erreurs non corrigées :\n{result.stdout}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
