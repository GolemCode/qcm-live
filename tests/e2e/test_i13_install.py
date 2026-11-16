"""Incrément 13 : installation (INS-01), mise à jour (INS-02) et lancement (INS-03).

L'installation se fait comme chez l'enseignant, par `install.sh` lu sur l'entrée standard
(`curl … | sh`), sans terminal, dans un `HOME` temporaire. Deux différences seulement :
- l'archive de l'application est construite depuis l'arbre de travail (`QCM_LIVE_ARCHIVE`),
  au lieu d'être téléchargée depuis GitHub ;
- uv vient du PATH, et ses paquets de son cache (`UV_OFFLINE`) : rien n'est téléchargé.

Sans terminal, les réponses viennent de l'environnement : compte (`DJANGO_SUPERUSER_*`) et
démonstration (`QCM_LIVE_DEMO`). Le lancement se fait ensuite par la commande installée, avec
un PATH réduit au système : uv n'y sert plus.
"""

from __future__ import annotations

import hashlib
import io
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import tarfile
import time
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.bank_ui import open_quizzes
from tests.e2e.classroom_ui import (
    LAUNCHER,
    REPO,
    announced,
    browser_recorder,
    clean_env,
    data_dir,
    free_port,
    run,
)
from tests.e2e.conftest import TEACHER_PASSWORD, TEACHER_USERNAME, login
from tests.e2e.roster_ui import import_group, open_groups

INSTALL_S = 300
GUIDE_URL = "https://github.com/GolemCode/qcm-live/blob/main/GUIDE.md"
INSTALL_LINE = (
    "curl -LsSf https://raw.githubusercontent.com/GolemCode/qcm-live/main/install.sh | sh"
)
DEMO_TITLE = re.search(
    r"^Title:\s*(.+)$", (REPO / "demo" / "qcm-demo.txt").read_text(encoding="utf-8"), re.M
)


def archive(folder: Path, name: str, extra: dict[str, str] | None = None) -> Path:
    """Archive de l'application, comme celle que GitHub sert pour `main` : les fichiers
    suivis ou à suivre de l'arbre de travail, sous un dossier `qcm-live-main/`. Les fichiers
    ignorés (`.env`, bases, environnement) n'y entrent pas."""
    listed = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=REPO,
        capture_output=True,
        check=True,
    ).stdout.decode()
    names = [n for n in listed.split("\0") if n and (REPO / n).is_file()]
    assert ".env" not in names and "db.sqlite3" not in names
    path = folder / name
    with tarfile.open(path, "w:gz") as tar:
        for name_ in names:
            tar.add(REPO / name_, arcname=f"qcm-live-main/{name_}")
        for name_, content in (extra or {}).items():
            data = content.encode()
            info = tarfile.TarInfo(f"qcm-live-main/{name_}")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return path


def uv_cache() -> str:
    return subprocess.run(
        ["uv", "cache", "dir"], capture_output=True, text=True, check=True, env=clean_env()
    ).stdout.strip()


def install(home: Path, package: Path, **answers: str) -> subprocess.CompletedProcess[str]:
    """`curl … | sh` : le script arrive sur l'entrée standard, sans terminal."""
    uv = shutil.which("uv")
    assert uv
    env = {
        "HOME": str(home),
        "PATH": f"{Path(uv).parent}:/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "QCM_LIVE_ARCHIVE": str(package),
        "UV_CACHE_DIR": uv_cache(),
        "UV_OFFLINE": "1",
        "UV_PYTHON": str(Path(sys.executable).resolve()),
        "UV_PYTHON_DOWNLOADS": "never",
        **answers,
    }
    result = subprocess.run(
        ["sh"],
        input=(REPO / "install.sh").read_text(encoding="utf-8"),
        env=env,
        cwd=home,
        capture_output=True,
        text=True,
        timeout=INSTALL_S,
        start_new_session=True,  # sans terminal, comme sous `curl | sh` depuis un menu
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result


ACCOUNT = {
    "DJANGO_SUPERUSER_USERNAME": TEACHER_USERNAME,
    "DJANGO_SUPERUSER_PASSWORD": TEACHER_PASSWORD,
}


def installed_env(home: Path, browser: str) -> dict[str, str]:
    """Le terminal de l'enseignant après l'installation : ni uv ni dépôt."""
    return {"HOME": str(home), "PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "BROWSER": browser}


def data(home: Path) -> Path:
    return home / ".local" / "share" / "qcm-live"


def command(home: Path) -> Path:
    return home / ".local" / "bin" / "qcm-live"


def rows(home: Path, query: str) -> list[tuple]:
    with sqlite3.connect(data(home) / "db.sqlite3") as db:
        found = db.execute(query).fetchall()
    db.close()
    return found


def launch(home: Path, browser: str):
    port = free_port()
    return announced(
        [str(command(home)), "--port", str(port)],
        port=port,
        env=installed_env(home, browser),
        cwd=home,
    )


def wait_for(path: Path) -> str:
    for _ in range(50):
        if path.exists() and path.read_text():
            return path.read_text()
        time.sleep(0.1)
    raise AssertionError(f"{path} jamais écrit")


@pytest.mark.spec("INS-01")
@pytest.mark.spec("INS-03")
def test_install_in_one_command_then_launch(tmp_path: Path, page: Page, new_phone):
    # La commande d'installation est celle du guide de l'enseignant.
    guide = (REPO / "GUIDE.md").read_text(encoding="utf-8")
    assert INSTALL_LINE in guide
    assert "https://raw.githubusercontent.com/GolemCode/qcm-live/main/install.sh" in INSTALL_LINE

    home = tmp_path / "maison"
    home.mkdir()
    result = install(home, archive(tmp_path, "main.tar.gz"), **ACCOUNT, QCM_LIVE_DEMO="oui")
    said = result.stdout + result.stderr

    # Données hors du dossier de l'application, lisibles par l'utilisateur seul.
    assert data(home).stat().st_mode & 0o777 == 0o700
    settings_file = data(home) / "reglages.env"
    assert settings_file.stat().st_mode & 0o777 == 0o600
    assert re.search(r"^DJANGO_SECRET_KEY=\S{40,}$", settings_file.read_text(), re.M)
    assert (data(home) / "db.sqlite3").is_file()
    assert not list((data(home) / "app").glob("*.sqlite3"))
    assert not (data(home) / "app" / ".env").exists()
    # Le compte de l'enseignant et la démonstration.
    assert rows(home, "SELECT username, is_superuser FROM auth_user") == [(TEACHER_USERNAME, 1)]
    assert rows(home, "SELECT name FROM roster_studentgroup") == [("Démo",)]
    # La commande et l'icône du menu des applications.
    assert os.access(command(home), os.X_OK)
    desktop = (home / ".local" / "share" / "applications" / "qcm-live.desktop").read_text()
    assert f"Exec={command(home)}" in desktop
    assert "Name=QCM Live" in desktop and "Terminal=true" in desktop
    icon = re.search(r"^Icon=(.+)$", desktop, re.M)
    assert icon and Path(icon.group(1)).is_file()
    assert "qcm-live" in said and GUIDE_URL in said

    # Lancement par la commande installée : mode classe, navigateur ouvert sur l'espace
    # enseignant, adresse des téléphones et guide cités dans le terminal.
    browser, opened = browser_recorder(tmp_path)
    with launch(home, browser) as server:
        assert wait_for(opened) == f"{server.local_url}/prof/"
        text = "".join(server.output)
        assert GUIDE_URL in text
        assert not re.search(r"//(localhost|127\.)", server.phone_url)
        response = page.request.get(server.local_url + "/")
        assert "waitress" in response.headers.get("server", "")  # serveur de production

        phone = new_phone()
        phone.goto(server.phone_url)
        expect(phone.get_by_label("Code de session")).to_be_visible()

        login(page, server.local_url)
        expect(page.get_by_role("heading", name="Espace enseignant")).to_be_visible()
        open_quizzes(page)
        assert DEMO_TITLE
        expect(page.get_by_role("main")).to_contain_text(DEMO_TITLE.group(1).strip())


@pytest.mark.spec("INS-02")
def test_running_the_install_again_updates_and_keeps_the_data(tmp_path: Path, page: Page):
    home = tmp_path / "maison"
    home.mkdir()
    first = archive(tmp_path, "v1.tar.gz", {"TEMOIN-v1.txt": "v1"})
    install(home, first, **ACCOUNT)  # sans démonstration
    assert (data(home) / "app" / "TEMOIN-v1.txt").exists()
    secret = hashlib.sha256((data(home) / "reglages.env").read_bytes()).hexdigest()
    browser, _ = browser_recorder(tmp_path)
    with launch(home, browser) as server:
        login(page, server.local_url)
        import_group(page, "TD1", "00123;DURAND Élise\n".encode())

    # Même commande, nouvelle version ; le compte et la démonstration ne sont plus proposés.
    second = archive(tmp_path, "v2.tar.gz", {"TEMOIN-v2.txt": "v2"})
    result = install(
        home,
        second,
        DJANGO_SUPERUSER_USERNAME="autre",
        DJANGO_SUPERUSER_PASSWORD="autre-mot-de-passe",
        QCM_LIVE_DEMO="oui",
    )
    assert "Mise à jour" in result.stdout
    assert (data(home) / "app" / "TEMOIN-v2.txt").exists()
    assert not (data(home) / "app" / "TEMOIN-v1.txt").exists()  # le code est remplacé
    assert not (data(home) / "app.new").exists()
    # Les données restent : base, compte, clé secrète (les sessions ouvertes restent valides).
    assert rows(home, "SELECT username FROM auth_user") == [(TEACHER_USERNAME,)]
    assert rows(home, "SELECT name FROM roster_studentgroup") == [("TD1",)]
    assert hashlib.sha256((data(home) / "reglages.env").read_bytes()).hexdigest() == secret

    with launch(home, browser) as server:
        login(page, server.local_url)
        open_groups(page)
        expect(page.get_by_role("link", name="TD1")).to_be_visible()


@pytest.mark.spec("INS-03")
def test_launch_says_when_the_port_is_already_taken(tmp_path: Path):
    env = clean_env(
        HOME=str(tmp_path),
        QCM_DATA_DIR=str(data_dir(tmp_path / "donnees")),
        DJANGO_DB_PATH=str(tmp_path / "db.sqlite3"),
        BROWSER=browser_recorder(tmp_path)[0],
    )
    with socket.socket() as taken:
        taken.bind(("", 0))
        taken.listen()
        port = taken.getsockname()[1]
        result = run([*LAUNCHER, "--port", str(port)], env=env)
    assert result.returncode != 0
    said = result.stdout + result.stderr
    assert f"Le port {port} est déjà utilisé" in said
    assert "QCM Live est peut-être déjà lancé" in said
    assert "Traceback" not in said
