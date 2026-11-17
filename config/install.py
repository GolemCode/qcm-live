"""Fin de l'installation et de la mise à jour (INS-01, INS-02), commune à Linux et Windows.

`install.sh` (ou `install.ps1`) a placé le code dans `<données>/app` et l'environnement Python
dans `<données>/venv`, puis lance `python -m config.install` avec `QCM_DATA_DIR`. Ce module :
1. crée `reglages.env` (clé secrète, droits 600) s'il n'existe pas : une mise à jour le garde,
   donc les sessions ouvertes restent valides ;
2. applique les migrations ;
3. à la première installation seulement (pas encore de base) : crée le compte de
   l'enseignant et propose la démonstration ;
4. écrit la commande `qcm-live` et l'icône du menu des applications (Linux), ou
   `qcm-live.cmd` (Windows ; le raccourci du menu Démarrer vient de `install.ps1`).

Sans terminal (`curl … | sh` lancé hors d'un terminal, tests), les réponses viennent de
l'environnement : `DJANGO_SUPERUSER_USERNAME` et `DJANGO_SUPERUSER_PASSWORD` pour le compte,
`QCM_LIVE_DEMO=oui` pour la démonstration.
"""

from __future__ import annotations

import os
import secrets
import shlex
import sys
from pathlib import Path

from config.classroom import GUIDE_URL
from config.launcher import (
    SETTINGS_FILE,
    ask,
    create_teacher,
    data_dir,
    database,
    load_settings,
    prompt_account,
    setup_django,
    xdg_data_home,
)

APP_DIR = Path(__file__).resolve().parent.parent
YES = {"o", "oui", "y", "yes", "1"}


def write_settings(folder: Path) -> bool:
    """Crée `reglages.env` avec une clé secrète tirée au hasard ; jamais réécrit."""
    path = folder / SETTINGS_FILE
    if path.exists():
        return False
    path.touch(mode=0o600)
    path.chmod(0o600)  # même si le fichier existait vide
    path.write_text(
        "# Réglages de QCM Live, créés à l'installation. Ne pas partager : la clé protège\n"
        "# les sessions de l'enseignant.\n"
        f"DJANGO_SECRET_KEY={secrets.token_urlsafe(50)}\n",
        encoding="utf-8",
    )
    return True


def bin_dir() -> Path:
    return Path.home() / ".local" / "bin"


def unix_command(data: Path, app: Path, python: Path) -> str:
    q = shlex.quote
    return (
        "#!/bin/sh\n"
        "# Lance QCM Live (écrit par l'installation ; voir `qcm-live --help`).\n"
        f"export QCM_DATA_DIR={q(str(data))}\n"
        f"export PYTHONPATH={q(str(app))}\n"
        f'exec {q(str(python))} -m config.launcher "$@"\n'
    )


def windows_command(data: Path, app: Path, python: Path) -> str:
    return (
        "@echo off\r\n"
        "rem Lance QCM Live (écrit par l'installation).\r\n"
        f'set "QCM_DATA_DIR={data}"\r\n'
        f'set "PYTHONPATH={app}"\r\n'
        f'"{python}" -m config.launcher %*\r\n'
    )


def desktop_entry(command: Path, icon: Path) -> str:
    """Icône du menu des applications (spécification freedesktop). Le terminal reste ouvert :
    il donne l'adresse des téléphones, et Ctrl+C arrête QCM Live."""
    exec_ = f'"{command}"' if " " in str(command) else str(command)
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=QCM Live\n"
        "Comment=QCM en direct : lancer le mode classe\n"
        f"Exec={exec_}\n"
        f"Icon={icon}\n"
        "Terminal=true\n"
        "Categories=Education;\n"
    )


def write_launchers(data: Path, app: Path = APP_DIR, python: Path | None = None) -> Path:
    """Écrit la commande `qcm-live` (et l'icône sous Linux) ; rend le chemin de la commande."""
    python = python or Path(sys.executable)
    folder = bin_dir()
    folder.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":  # pragma: no cover — Windows
        command = folder / "qcm-live.cmd"
        command.write_text(windows_command(data, app, python), encoding="utf-8")
        return command
    command = folder / "qcm-live"
    command.write_text(unix_command(data, app, python), encoding="utf-8")
    command.chmod(0o755)
    applications = xdg_data_home() / "applications"
    applications.mkdir(parents=True, exist_ok=True)
    (applications / "qcm-live.desktop").write_text(
        desktop_entry(command, app / "static" / "img" / "qcm-live.svg"), encoding="utf-8"
    )
    return command


def wants_demo(interactive: bool) -> bool:
    answer = os.environ.get("QCM_LIVE_DEMO")
    if answer is None and interactive:
        answer = ask("Ajouter un exemple de démonstration (un QCM et un groupe fictifs) ? [o/N] ")
    return (answer or "").strip().lower() in YES


def create_account(interactive: bool) -> None:
    username = os.environ.get("DJANGO_SUPERUSER_USERNAME")
    password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")
    if username and password:
        create_teacher(username, password)
        return
    if interactive:
        print("Création de votre compte enseignant (identifiant vide : plus tard).")
        if prompt_account():
            return
    print("Créez votre compte enseignant plus tard, dans un terminal : qcm-live compte")


def first_steps(first: bool, interactive: bool) -> None:
    """Compte de l'enseignant tant qu'il n'y en a aucun, même après une première installation
    interrompue ; démonstration proposée à la première installation seulement."""
    from django.contrib.auth import get_user_model
    from django.core.management import call_command

    if not get_user_model().objects.exists():
        create_account(interactive)
    if first and wants_demo(interactive):
        call_command("demo", "--sans-compte")


def main() -> int:  # pragma: no cover — testé de bout en bout (INS-01, INS-02)
    data = data_dir()
    data.mkdir(mode=0o700, parents=True, exist_ok=True)
    data.chmod(0o700)
    write_settings(data)
    load_settings(data)
    setup_django()
    from django.core.management import call_command

    first = not database().exists()
    interactive = sys.stdin.isatty()
    call_command("migrate", interactive=False, verbosity=0)
    first_steps(first, interactive)
    command = write_launchers(data)

    print()
    print("Mise à jour terminée." if not first else "Installation terminée.")
    print("Pour lancer QCM Live : l'icône « QCM Live » du menu des applications, ou la commande")
    print(f"  qcm-live   ({command})")
    if str(command.parent) not in os.environ.get("PATH", "").split(os.pathsep):
        print(
            f"  {command.parent} n'est pas encore dans le PATH : la commande qcm-live marchera "
            "après la prochaine connexion à votre session, ou par son chemin complet."
        )
    print(f"Guide de l'enseignant : {GUIDE_URL}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
