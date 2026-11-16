"""Incrément 13 : sauvegarde à chaque lancement (SAV-01), sauvegarder et restaurer (SAV-02).

La commande de l'enseignant (`qcm-live`) est lancée depuis le dépôt, dans un processus à part,
comme le fait le script installé (INS-01) :
- `HOME` est un dossier temporaire : les sauvegardes vont dans `~/QCM Live/sauvegardes/` ;
- le dossier de données porte une clé de test, jamais la vraie (`.env`) ;
- la base est la base de test (`DJANGO_DB_PATH`), où les fabriques créent les préconditions ;
- un navigateur factice (`BROWSER`) note l'adresse ouverte au lancement.
"""

from __future__ import annotations

import re
import sqlite3
import zipfile
from datetime import date
from pathlib import Path

import pytest
from django.conf import global_settings
from playwright.sync_api import Page, expect

from roster.models import StudentGroup
from tests.e2e.classroom_ui import (
    LAUNCHER,
    announced,
    browser_recorder,
    data_dir,
    env_on_test_db,
    free_port,
    run,
)
from tests.e2e.conftest import login
from tests.e2e.roster_ui import import_group, open_groups
from tests.factories import make_group

BACKUP_RE = re.compile(r"^qcm-live-\d{4}-\d{2}-\d{2}-\d{2}h\d{2}m\d{2}s\.zip$")


@pytest.fixture(autouse=True)
def _steady_clock() -> None:
    """Remplace celui de tests/conftest.py : le lanceur, à part, lit l'horloge système."""


@pytest.fixture(autouse=True)
def _fast_password_hasher(settings) -> None:
    """Remplace celui de tests/conftest.py : le lanceur, à part, hache comme en production."""
    settings.PASSWORD_HASHERS = global_settings.PASSWORD_HASHERS


@pytest.fixture
def home(tmp_path: Path) -> Path:
    folder = tmp_path / "maison"
    folder.mkdir()
    return folder


@pytest.fixture
def env(home: Path, tmp_path: Path, transactional_db) -> dict[str, str]:
    browser, _ = browser_recorder(tmp_path)
    data = data_dir(home / ".local" / "share" / "qcm-live")
    return env_on_test_db(HOME=str(home), QCM_DATA_DIR=str(data), BROWSER=browser)


def backups(home: Path) -> Path:
    return home / "QCM Live" / "sauvegardes"


def archives(home: Path) -> list[str]:
    """Sauvegardes du dossier, de la plus ancienne à la plus récente."""
    return sorted(p.name for p in backups(home).iterdir() if BACKUP_RE.match(p.name))


def group_names(archive: Path, tmp_path: Path) -> list[str]:
    """Groupes enregistrés dans la base d'une sauvegarde."""
    with zipfile.ZipFile(archive) as content:
        assert content.namelist() == ["db.sqlite3"], content.namelist()
        content.extract("db.sqlite3", tmp_path / "lue")
    with sqlite3.connect(tmp_path / "lue" / "db.sqlite3") as db:
        return [name for (name,) in db.execute("SELECT name FROM roster_studentgroup")]


def launched(env: dict[str, str]):
    port = free_port()
    return announced([*LAUNCHER, "--port", str(port)], port=port, env=env)


@pytest.mark.spec("SAV-01")
def test_each_launch_saves_the_data_and_keeps_the_last_ten(home, env, tmp_path):
    make_group("TD1", [("00123", "DURAND Élise")])
    folder = backups(home)
    folder.mkdir(parents=True)
    old = [folder / f"qcm-live-2026-01-{day:02d}-10h00m00s.zip" for day in range(1, 11)]
    for archive in old:
        archive.write_bytes(b"ancienne sauvegarde")
    # Des fichiers de l'enseignant, rangés là : jamais touchés.
    mine = [folder / "notes.txt", folder / "qcm-live-copie.zip", folder / "qcm-live-2026.zip"]
    for path in mine:
        path.write_bytes(b"a moi")

    with launched(env) as server:
        assert server.phone_url

    kept = archives(home)
    assert len(kept) == 10
    assert not old[0].exists()  # la plus ancienne
    assert [folder / name for name in kept[:9]] == old[1:]
    assert all(path.read_bytes() == b"a moi" for path in mine)
    newest = kept[-1]
    assert newest.startswith(f"qcm-live-{date.today():%Y-%m-%d}-"), newest
    assert group_names(folder / newest, tmp_path) == ["TD1"]


@pytest.mark.spec("SAV-01")
def test_first_launch_creates_the_backup_folder(home, env, tmp_path):
    make_group("TD1", [("00123", "DURAND Élise")])
    with launched(env):
        pass
    (newest,) = archives(home)
    assert group_names(backups(home) / newest, tmp_path) == ["TD1"]
    assert backups(home).stat().st_mode & 0o777 == 0o700  # données personnelles


@pytest.mark.spec("SAV-02")
def test_save_then_restore_round_trip(home, env, teacher, page: Page, tmp_path):
    with launched(env) as server:
        login(page, server.local_url)
        import_group(page, "TD1", "00123;DURAND Élise\n".encode())

        saved = run([*LAUNCHER, "sauvegarder"], env=env)
        assert saved.returncode == 0, saved.stdout + saved.stderr
        before_delete = archives(home)
        assert before_delete[-1] in saved.stdout  # chemin de la sauvegarde affiché

        page.get_by_role("link", name="Supprimer").click()
        page.get_by_role("button", name="Supprimer").click()
        open_groups(page)
        expect(page.get_by_role("link", name="TD1")).to_have_count(0)

    # Sans argument : la liste des sauvegardes, la plus récente en premier, puis confirmation.
    restored = run([*LAUNCHER, "restaurer"], env=env, answers="1\no\n")
    assert restored.returncode == 0, restored.stdout + restored.stderr
    assert re.search(rf"^\s*1\D.*{re.escape(before_delete[-1])}", restored.stdout, re.M)
    assert "Données restaurées" in restored.stdout
    # Les données remplacées ont d'abord été sauvegardées.
    after = archives(home)
    assert len(after) == len(before_delete) + 1
    assert group_names(backups(home) / after[-1], tmp_path) == []

    with launched(env) as server:
        login(page, server.local_url)
        open_groups(page)
        expect(page.get_by_role("link", name="TD1")).to_be_visible()


@pytest.mark.spec("SAV-02")
def test_restore_by_path_asks_for_confirmation(home, env, tmp_path):
    make_group("TD1", [("00123", "DURAND Élise")])
    saved = run([*LAUNCHER, "sauvegarder"], env=env)
    assert saved.returncode == 0, saved.stdout + saved.stderr
    archive = backups(home) / archives(home)[-1]
    make_group("TD2", [("42", "MARTIN Léo")])

    refused = run([*LAUNCHER, "restaurer", str(archive)], env=env, answers="n\n")
    assert refused.returncode != 0
    assert "Rien n'a été changé" in refused.stdout
    assert sorted(_groups()) == ["TD1", "TD2"]

    restored = run([*LAUNCHER, "restaurer", str(archive)], env=env, answers="o\n")
    assert restored.returncode == 0, restored.stdout + restored.stderr
    assert _groups() == ["TD1"]


@pytest.mark.spec("SAV-02")
@pytest.mark.parametrize("case", ["autre zip", "base abîmée", "pas un zip"])
def test_restore_refuses_what_is_not_a_backup(home, env, tmp_path, case):
    make_group("TD1", [("00123", "DURAND Élise")])
    archive = tmp_path / "qcm-live-2026-01-01-10h00m00s.zip"
    if case == "pas un zip":
        archive.write_bytes(b"ceci n'est pas une archive")
    else:
        with zipfile.ZipFile(archive, "w") as content:
            if case == "autre zip":
                content.writestr("photo.jpg", b"\xff\xd8")
            else:
                content.writestr("db.sqlite3", b"SQLite format 3\x00" + b"\x00" * 200)

    refused = run([*LAUNCHER, "restaurer", str(archive)], env=env, answers="o\n")
    assert refused.returncode != 0
    assert "n'est pas une sauvegarde de QCM Live" in refused.stdout + refused.stderr
    assert "Rien n'a été changé" in refused.stdout + refused.stderr
    assert _groups() == ["TD1"]


@pytest.mark.spec("SAV-02")
def test_restore_refuses_a_backup_from_a_newer_version(home, env, tmp_path):
    make_group("TD1", [("00123", "DURAND Élise")])
    saved = run([*LAUNCHER, "sauvegarder"], env=env)
    assert saved.returncode == 0, saved.stdout + saved.stderr
    # La même sauvegarde, comme si une version plus récente y avait appliqué une migration.
    with zipfile.ZipFile(backups(home) / archives(home)[-1]) as content:
        content.extract("db.sqlite3", tmp_path / "lue")
    with sqlite3.connect(tmp_path / "lue" / "db.sqlite3") as db:
        db.execute(
            "INSERT INTO django_migrations (app, name, applied) "
            "VALUES ('roster', '9999_future', '2027-01-01')"
        )
    db.close()
    newer = tmp_path / "plus-recente.zip"
    with zipfile.ZipFile(newer, "w") as content:
        content.write(tmp_path / "lue" / "db.sqlite3", "db.sqlite3")
    StudentGroup.objects.all().delete()

    refused = run([*LAUNCHER, "restaurer", str(newer)], env=env, answers="o\n")
    assert refused.returncode != 0
    assert "version plus récente" in refused.stdout + refused.stderr
    assert _groups() == []


def _groups() -> list[str]:
    return list(StudentGroup.objects.order_by("name").values_list("name", flat=True))
