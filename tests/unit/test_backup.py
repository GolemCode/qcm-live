"""Sauvegardes (SAV-01, SAV-02) : nom, rotation, vérification d'une archive, restauration."""

from __future__ import annotations

import sqlite3
import zipfile
from datetime import datetime
from pathlib import Path

import pytest

from config import backup

KNOWN = {("roster", "0001_initial"), ("bank", "0001_initial")}


def make_db(path: Path, groups=("TD1",), migrations=KNOWN) -> Path:
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE django_migrations (app TEXT, name TEXT, applied TEXT)")
        db.executemany(
            "INSERT INTO django_migrations VALUES (?, ?, '2026-01-01')", sorted(migrations)
        )
        db.execute("CREATE TABLE roster_studentgroup (name TEXT)")
        db.executemany("INSERT INTO roster_studentgroup VALUES (?)", [(g,) for g in groups])
    db.close()
    return path


def groups(path: Path) -> list[str]:
    with sqlite3.connect(path) as db:
        found = [name for (name,) in db.execute("SELECT name FROM roster_studentgroup")]
    db.close()
    return found


def test_save_names_the_archive_after_the_time_and_keeps_only_the_database(tmp_path):
    database = make_db(tmp_path / "db.sqlite3")
    folder = tmp_path / "QCM Live" / "sauvegardes"
    path = backup.save(database, folder, now=datetime(2026, 11, 17, 8, 5, 9))
    assert path == folder / "qcm-live-2026-11-17-08h05m09s.zip"
    assert folder.stat().st_mode & 0o777 == 0o700
    with zipfile.ZipFile(path) as content:
        assert content.namelist() == ["db.sqlite3"]
        content.extract("db.sqlite3", tmp_path / "lue")
    assert groups(tmp_path / "lue" / "db.sqlite3") == ["TD1"]
    assert sorted(p.name for p in folder.iterdir()) == [path.name]  # aucun fichier de travail


def test_save_is_readable_by_the_teacher_only(tmp_path):
    """Une archive contient les empreintes des mots de passe et les sessions : dossier en 700
    même s'il existait déjà, archive en 600."""
    database = make_db(tmp_path / "db.sqlite3")
    folder = tmp_path / "sauvegardes"
    folder.mkdir(mode=0o755)
    folder.chmod(0o755)
    path = backup.save(database, folder)
    assert folder.stat().st_mode & 0o777 == 0o700
    assert path.stat().st_mode & 0o777 == 0o600


def test_save_keeps_the_ten_most_recent_and_nothing_else_is_touched(tmp_path):
    database = make_db(tmp_path / "db.sqlite3")
    folder = tmp_path / "sauvegardes"
    for day in range(1, 13):
        backup.save(database, folder, now=datetime(2026, 1, day, 10))
    mine = [folder / "notes.txt", folder / "qcm-live-copie.zip", folder / "qcm-live-2026.zip"]
    for path in mine:
        path.write_text("à moi")
    backup.save(database, folder, now=datetime(2026, 2, 1, 10))
    kept = backup.archives(folder)
    assert len(kept) == 10
    assert kept[0].name == "qcm-live-2026-02-01-10h00m00s.zip"  # la plus récente d'abord
    assert kept[-1].name == "qcm-live-2026-01-04-10h00m00s.zip"
    assert all(path.read_text() == "à moi" for path in mine)


def test_save_in_the_same_second_waits_for_the_next_one(tmp_path):
    database = make_db(tmp_path / "db.sqlite3")
    folder = tmp_path / "sauvegardes"
    first, second = backup.save(database, folder), backup.save(database, folder)
    assert first != second and first.exists() and second.exists()
    with pytest.raises(FileExistsError):  # date imposée : pas d'attente possible
        now = datetime(2026, 1, 1)
        backup.save(database, folder, now=now)
        backup.save(database, folder, now=now)


def test_archives_of_a_missing_folder(tmp_path):
    assert backup.archives(tmp_path / "absent") == []


def archive_with(tmp_path: Path, members: dict[str, bytes], name="a.zip") -> Path:
    path = tmp_path / name
    with zipfile.ZipFile(path, "w") as content:
        for member, data in members.items():
            content.writestr(member, data)
    return path


def test_extract_then_restore_round_trip(tmp_path):
    saved = backup.save(make_db(tmp_path / "old.sqlite3", ["TD1"]), tmp_path / "s")
    current = make_db(tmp_path / "db.sqlite3", ["TD1", "TD2"])
    (tmp_path / "work").mkdir()
    extracted = backup.extract(saved, tmp_path / "work", KNOWN)
    backup.restore(extracted, current)
    assert groups(current) == ["TD1"]


def test_restore_creates_the_database_when_there_is_none(tmp_path):
    saved = backup.save(make_db(tmp_path / "old.sqlite3"), tmp_path / "s")
    (tmp_path / "work").mkdir()
    target = tmp_path / "neuf" / "db.sqlite3"
    backup.restore(backup.extract(saved, tmp_path / "work", KNOWN), target)
    assert groups(target) == ["TD1"]


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        (b"pas une archive", "zip"),
        ({"photo.jpg": b"\xff\xd8"}, "aucun fichier db.sqlite3"),
        ({"db.sqlite3": b"SQLite format 3\x00" + b"\x00" * 200}, "base"),
        ({"db.sqlite3": b"texte"}, "base"),
    ],
)
def test_extract_refuses_what_is_not_a_backup(tmp_path, content, reason):
    if isinstance(content, bytes):
        archive = tmp_path / "a.zip"
        archive.write_bytes(content)
    else:
        archive = archive_with(tmp_path, content)
    with pytest.raises(backup.BackupError, match=backup.NOT_A_BACKUP) as refused:
        backup.extract(archive, tmp_path, KNOWN)
    assert reason in str(refused.value)


def test_extract_refuses_a_readable_but_damaged_base(tmp_path):
    damaged = tmp_path / "abimee.sqlite3"
    with sqlite3.connect(damaged) as db:
        db.execute("CREATE TABLE t (a TEXT)")
        db.execute("CREATE INDEX t_a ON t (a)")
        db.executemany("INSERT INTO t VALUES (?)", [(str(i) * 20,) for i in range(1000)])
        db.commit()
        db.execute("PRAGMA writable_schema = ON")
        db.execute("DELETE FROM sqlite_master WHERE name = 't_a'")
    db.close()
    (tmp_path / "work").mkdir()
    archive = archive_with(tmp_path, {"db.sqlite3": damaged.read_bytes()})
    with pytest.raises(backup.BackupError, match="base abîmée"):
        backup.extract(archive, tmp_path / "work", KNOWN)


def test_extract_refuses_a_sqlite_base_that_is_not_qcm_live(tmp_path):
    with sqlite3.connect(tmp_path / "autre.sqlite3") as db:
        db.execute("CREATE TABLE notes (t TEXT)")
    db.close()
    archive = archive_with(tmp_path, {"db.sqlite3": (tmp_path / "autre.sqlite3").read_bytes()})
    (tmp_path / "work").mkdir()
    with pytest.raises(backup.BackupError, match=backup.NOT_A_BACKUP):
        backup.extract(archive, tmp_path / "work", KNOWN)


@pytest.mark.parametrize(
    "data", [b"pas une base", b""], ids=["pas une base", "sans table des migrations"]
)
def test_extract_closes_the_database_it_refuses(tmp_path, monkeypatch, data):
    """Sous Windows, une connexion restée ouverte verrouille le fichier : le dossier de
    travail ne se supprime plus, et une trace remplace le message de refus."""
    opened = []
    real = sqlite3.connect

    def spy(*args, **kwargs):
        opened.append(real(*args, **kwargs))
        return opened[-1]

    monkeypatch.setattr(sqlite3, "connect", spy)
    (tmp_path / "work").mkdir()
    with pytest.raises(backup.BackupError, match=backup.NOT_A_BACKUP):
        backup.extract(archive_with(tmp_path, {"db.sqlite3": data}), tmp_path / "work", KNOWN)
    assert opened
    for connection in opened:
        with pytest.raises(sqlite3.ProgrammingError, match="closed"):
            connection.execute("SELECT 1")


def test_extract_refuses_a_backup_from_a_newer_version(tmp_path):
    newer = KNOWN | {("roster", "9999_future")}
    saved = backup.save(make_db(tmp_path / "db.sqlite3", migrations=newer), tmp_path / "s")
    (tmp_path / "work").mkdir()
    with pytest.raises(backup.BackupError, match="version plus récente") as refused:
        backup.extract(saved, tmp_path / "work", KNOWN)
    assert "roster.9999_future" in str(refused.value)


def test_extract_reads_the_member_by_its_name_only(tmp_path):
    """Un chemin choisi par l'archive (`../x`) n'est jamais écrit."""
    database = make_db(tmp_path / "db.sqlite3")
    archive = archive_with(
        tmp_path, {"db.sqlite3": database.read_bytes(), "../evade.txt": b"x"}, name="b.zip"
    )
    (tmp_path / "work").mkdir()
    backup.extract(archive, tmp_path / "work", KNOWN)
    assert sorted(p.name for p in (tmp_path / "work").iterdir()) == ["db.sqlite3"]
    assert not (tmp_path / "evade.txt").exists()
