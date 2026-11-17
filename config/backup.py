"""Sauvegardes des données de l'enseignant (SAV-01, SAV-02), sans Django.

Une sauvegarde est une archive zip `qcm-live-AAAA-MM-JJ-HHhMMmSSs.zip`, rangée dans un dossier
visible (`~/QCM Live/sauvegardes/`) pour être copiée sur une clé USB. Elle contient la base,
`db.sqlite3`, copiée par l'API de sauvegarde de SQLite : la copie est cohérente même si le
serveur écrit au même moment. Le format zip laisse la place aux images (I17).

- Le lanceur (config/launcher.py) en fait une à chaque lancement, avant les migrations : une
  migration ratée se rattrape en restaurant la sauvegarde du lancement.
- Seules les 10 plus récentes sont gardées. Seuls les fichiers dont le nom suit exactement le
  motif ci-dessus sont comptés et supprimés : rien d'autre du dossier n'est touché.
- Une archive n'est restaurée qu'après vérification : la base est présente, intègre, c'est
  bien une base de QCM Live (table des migrations), et aucune de ses migrations n'est
  inconnue de cette version de l'application (sinon, elle vient d'une version plus récente).
"""

from __future__ import annotations

import re
import sqlite3
import tempfile
import time
import zipfile
from collections.abc import Iterable
from contextlib import closing
from datetime import datetime
from pathlib import Path

KEEP = 10
MEMBER = "db.sqlite3"
NAME_FORMAT = "qcm-live-%Y-%m-%d-%Hh%Mm%Ss.zip"
NAME_RE = re.compile(r"qcm-live-\d{4}-\d{2}-\d{2}-\d{2}h\d{2}m\d{2}s\.zip")
NOT_A_BACKUP = "n'est pas une sauvegarde de QCM Live"


class BackupError(Exception):
    """Archive refusée ; le message est destiné à l'enseignant."""


def default_folder() -> Path:
    return Path.home() / "QCM Live" / "sauvegardes"


def archives(folder: Path) -> list[Path]:
    """Sauvegardes du dossier, de la plus récente à la plus ancienne (le nom porte la date)."""
    if not folder.is_dir():
        return []
    found = [path for path in folder.iterdir() if NAME_RE.fullmatch(path.name)]
    return sorted(found, key=lambda path: path.name, reverse=True)


def _copy(source: Path, target: Path) -> None:
    """Copie de base à base par l'API de sauvegarde de SQLite."""
    with (
        closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as src,
        closing(sqlite3.connect(target)) as dst,
    ):
        src.backup(dst)


def _new_name(folder: Path, now: datetime | None) -> Path:
    """Nom libre ; deux sauvegardes dans la même seconde : la seconde attend la suivante."""
    while True:
        path = folder / (now or datetime.now()).strftime(NAME_FORMAT)
        if not path.exists():
            return path
        if now is not None:
            raise FileExistsError(path)
        time.sleep(0.1)


def save(database: Path, folder: Path, *, now: datetime | None = None, keep: int = KEEP) -> Path:
    """Sauvegarde `database` dans `folder`, garde les `keep` plus récentes et rend le chemin
    de l'archive. Elle contient les empreintes des mots de passe et les sessions : dossier en
    700 (même s'il existait déjà), archive en 600. Sous Windows, chmod est sans effet."""
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    folder.chmod(0o700)
    target = _new_name(folder, now)
    with tempfile.TemporaryDirectory(dir=folder, prefix=".qcm-live-") as work:
        copy = Path(work) / MEMBER
        _copy(database, copy)
        # Écrite sous un autre nom puis renommée : une archive à demi écrite (coupure) ne
        # porte jamais le nom d'une sauvegarde.
        partial = Path(work) / "archive.zip"
        with zipfile.ZipFile(partial, "w", zipfile.ZIP_DEFLATED) as content:
            content.write(copy, MEMBER)
        partial.chmod(0o600)
        partial.replace(target)
    for old in archives(folder)[keep:]:
        old.unlink()
    return target


def _refuse(archive: Path, reason: str) -> BackupError:
    return BackupError(f"{archive.name} {NOT_A_BACKUP} ({reason}).")


def extract(archive: Path, folder: Path, known: Iterable[tuple[str, str]]) -> Path:
    """Vérifie `archive` et en extrait la base dans `folder`. `known` : les migrations
    `(application, nom)` de cette version. Lève BackupError si l'archive est refusée."""
    try:
        with zipfile.ZipFile(archive) as content:
            if MEMBER not in content.namelist():
                raise _refuse(archive, f"aucun fichier {MEMBER}")
            data = content.read(MEMBER)  # lu par son nom : aucun chemin choisi par l'archive
    except (zipfile.BadZipFile, OSError) as error:
        raise _refuse(archive, "ce n'est pas une archive zip lisible") from error
    database = folder / MEMBER
    database.write_bytes(data)
    try:
        # Fermée même en cas de refus : sous Windows, une connexion ouverte verrouille le
        # fichier, et le dossier de travail ne se supprimerait plus.
        with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as db:
            (check,) = db.execute("PRAGMA integrity_check").fetchone()
            if check != "ok":
                raise _refuse(archive, "base abîmée")
            applied = set(db.execute("SELECT app, name FROM django_migrations").fetchall())
    except sqlite3.DatabaseError as error:
        raise _refuse(archive, "base illisible") from error
    if unknown := applied - set(known):
        names = ", ".join(f"{app}.{name}" for app, name in sorted(unknown))
        raise BackupError(
            f"{archive.name} vient d'une version plus récente de QCM Live (migrations "
            f"inconnues : {names}). Mettez QCM Live à jour avant de la restaurer."
        )
    return database


def restore(extracted: Path, database: Path) -> None:
    """Remplace le contenu de `database` par la base vérifiée `extracted`."""
    database.parent.mkdir(parents=True, exist_ok=True)
    _copy(extracted, database)
