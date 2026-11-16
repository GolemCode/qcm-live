"""Incrément M : chaque pytest a sa propre base de test.

Deux pytest dans le même dépôt partageaient `.test-db.sqlite3` : le hook Stop lançait
`make check` pendant un pytest en arrière-plan (I7, deux fois en I11). Ces tests vérifient
le mécanisme, et non une consigne.
"""

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PRINT_NAME = (
    "import django; django.setup(); from django.conf import settings; "
    "print(settings.DATABASES['default']['TEST']['NAME'])"
)


def _test_database_name() -> str:
    env = {**os.environ, "DJANGO_SETTINGS_MODULE": "config.settings"}
    return subprocess.run(
        [sys.executable, "-c", PRINT_NAME],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def test_each_process_gets_its_own_test_database():
    first, second = _test_database_name(), _test_database_name()
    assert first != second
    assert Path(first).parent == REPO  # à côté du dépôt, ignorée par git
    assert Path(first).name.startswith(".test-db-")


def test_two_pytest_runs_at_once_do_not_collide():
    command = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]
    command.append(str(Path(__file__).with_name("probe_concurrent_db.py")))
    runs = [
        subprocess.Popen(command, cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        for _ in range(2)
    ]
    outputs = [run.communicate(timeout=120)[0].decode() for run in runs]
    assert [run.returncode for run in runs] == [0, 0], "\n".join(outputs)


def _dead_pid() -> int:
    finished = subprocess.Popen(["true"])
    finished.wait()
    return finished.pid


def test_databases_left_by_a_killed_pytest_are_removed(tmp_path):
    from tests.databases import remove_stale

    dead, alive = _dead_pid(), os.getpid()
    names = [
        f".test-db-{dead}.sqlite3",
        f".test-db-{dead}.sqlite3-journal",
        f".test-db-{alive}.sqlite3",
        "db.sqlite3",
        ".test-db-x.sqlite3",
    ]
    for name in names:
        (tmp_path / name).write_text("")
    remove_stale(tmp_path)
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(names[2:])
