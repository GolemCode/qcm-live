"""Bases de test laissées par un pytest tué (une par processus, voir `config/settings.py`)."""

from __future__ import annotations

import os
import re
from pathlib import Path

TEST_DATABASE = re.compile(r"^\.test-db-(\d+)\.sqlite3")


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:  # processus d'un autre compte : il existe
        pass
    return True


def remove_stale(folder: Path) -> None:
    """Supprime les bases de test (et leurs journaux SQLite) dont le processus n'existe plus.

    Un pytest qui se termine normalement détruit sa base ; un pytest tué (contre-épreuve
    interrompue, délai dépassé) la laisse derrière lui.
    """
    for path in folder.glob(".test-db-*.sqlite3*"):
        match = TEST_DATABASE.match(path.name)
        if match and not _alive(int(match.group(1))):
            path.unlink(missing_ok=True)
