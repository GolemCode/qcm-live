"""Commande de l'enseignant, `qcm-live` (INS-03, SAV-01, SAV-02).

Le script installé (config/install.py) lance `python -m config.launcher` avec le Python de
l'environnement de l'application ; uv n'intervient plus.

- `qcm-live` : sauvegarde des données, puis mode classe (config/classroom.py), et ouverture
  du navigateur sur l'espace enseignant (`--sans-navigateur` pour s'en passer).
- `qcm-live sauvegarder` : une sauvegarde, à la demande.
- `qcm-live restaurer [archive]` : remplace les données par une sauvegarde, après
  confirmation, en sauvegardant d'abord les données actuelles.
- `qcm-live compte` : crée un compte enseignant.

Les données (base, réglages) sont dans `QCM_DATA_DIR`, que le script installé fixe ; à
défaut, `~/.local/share/qcm-live` (Windows : `%LOCALAPPDATA%\\qcm-live`). Le fichier
`reglages.env` de ce dossier porte la clé secrète ; une variable déjà présente dans
l'environnement l'emporte sur lui.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import threading
import webbrowser
from collections.abc import Sequence
from pathlib import Path

from config import backup, classroom

SETTINGS_FILE = "reglages.env"
NOTHING_CHANGED = "Rien n'a été changé."


def default_data_dir() -> Path:
    if sys.platform == "win32":  # pragma: no cover — Windows
        return (
            Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "qcm-live"
        )
    base = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(base) / "qcm-live"


def data_dir() -> Path:
    return Path(os.environ.get("QCM_DATA_DIR") or default_data_dir())


def read_settings(text: str) -> dict[str, str]:
    """Lignes `NOM=valeur` ; lignes vides et commentaires (`#`) ignorés."""
    found = {}
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            name, value = line.split("=", 1)
            found[name.strip()] = value.strip()
    return found


def load_settings(folder: Path) -> bool:
    """Charge `reglages.env` dans l'environnement, sans écraser ce qui y est déjà."""
    try:
        text = (folder / SETTINGS_FILE).read_text(encoding="utf-8")
    except OSError:
        return False
    for name, value in read_settings(text).items():
        os.environ.setdefault(name, value)
    os.environ.setdefault("QCM_DATA_DIR", str(folder))
    return True


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="qcm-live",
        description="QCM Live : lance l'application en mode classe (par défaut).",
    )
    classroom.add_server_arguments(parser)
    parser.add_argument(
        "--sans-navigateur", action="store_true", help="ne pas ouvrir le navigateur"
    )
    commands = parser.add_subparsers(dest="command", metavar="commande")
    commands.add_parser("sauvegarder", help="sauvegarder les données maintenant")
    restore = commands.add_parser("restaurer", help="restaurer une sauvegarde")
    restore.add_argument("archive", nargs="?", type=Path, help="sauvegarde à restaurer")
    commands.add_parser("compte", help="créer un compte enseignant")
    return parser.parse_args(argv)


def database() -> Path:
    from django.conf import settings

    return Path(settings.DATABASES["default"]["NAME"])


def save_now() -> Path | None:
    """Sauvegarde la base, si elle existe déjà ; affiche et rend le chemin de l'archive."""
    current = database()
    if not current.is_file() or current.stat().st_size == 0:
        return None
    path = backup.save(current, backup.default_folder())
    print(f"Sauvegarde : {path}", flush=True)
    return path


def ask(question: str) -> str:
    try:
        return input(question).strip().lower()
    except (EOFError, KeyboardInterrupt):  # sans terminal, ou Ctrl+C : non
        print()
        return ""


def choose_archive() -> Path | None:
    found = backup.archives(backup.default_folder())
    if not found:
        print(f"Aucune sauvegarde dans {backup.default_folder()}.")
        return None
    print("Sauvegardes, de la plus récente à la plus ancienne :")
    for number, path in enumerate(found, start=1):
        print(f"  {number}. {path.name}")
    answer = ask("Numéro de la sauvegarde à restaurer : ")
    if not answer.isdigit() or not 1 <= int(answer) <= len(found):
        return None
    return found[int(answer) - 1]


def known_migrations() -> set[tuple[str, str]]:
    from django.db.migrations.loader import MigrationLoader

    return set(MigrationLoader(None, ignore_no_migrations=True).disk_migrations)


def restore(archive: Path | None) -> int:
    from django.core.management import call_command

    archive = archive or choose_archive()
    if archive is None:
        print(NOTHING_CHANGED)
        return 1
    with tempfile.TemporaryDirectory(prefix="qcm-live-") as work:
        try:
            extracted = backup.extract(archive, Path(work), known_migrations())
        except backup.BackupError as error:
            print(error)
            print(NOTHING_CHANGED)
            return 1
        answer = ask(
            f"Remplacer les données actuelles par {archive.name} ? Elles seront d'abord "
            "sauvegardées. [o/N] "
        )
        if answer not in {"o", "oui"}:
            print(NOTHING_CHANGED)
            return 1
        save_now()
        backup.restore(extracted, database())
    call_command("migrate", interactive=False, verbosity=0)
    print(f"Données restaurées depuis {archive.name}.")
    return 0


def setup_django() -> None:
    import django

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()


def main(argv: Sequence[str] | None = None) -> int:  # pragma: no cover — testé de bout en bout
    args = parse_args(argv)
    folder = data_dir()
    if not load_settings(folder):
        print(
            f"QCM Live n'est pas installé dans {folder} ({SETTINGS_FILE} manquant) : relancez "
            f"l'installation (voir {classroom.GUIDE_URL}).",
            file=sys.stderr,
        )
        return 1
    if args.command is None:

        def open_browser(url: str) -> None:
            if not args.sans_navigateur:
                threading.Thread(target=webbrowser.open, args=(url,), daemon=True).start()

        return classroom.serve(
            args.adresse, args.port, before_migrate=save_now, on_ready=open_browser
        )
    setup_django()
    if args.command == "sauvegarder":
        if save_now() is None:
            print("Aucune donnée à sauvegarder.")
        return 0
    if args.command == "restaurer":
        return restore(args.archive)
    from django.core.management import call_command

    call_command("migrate", interactive=False, verbosity=0)
    call_command("createsuperuser")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
