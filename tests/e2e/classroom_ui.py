"""Lancer l'application comme en classe, dans un processus à part, et lire son terminal.

Sert au mode classe (`make classe`, CLA-01), à la commande de l'enseignant (`qcm-live`,
INS-03) et à ses sous-commandes de sauvegarde (SAV-01, SAV-02).
"""

from __future__ import annotations

import os
import queue
import re
import signal
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path

import pytest
from django.conf import settings

REPO = Path(__file__).resolve().parents[2]
STARTUP_S = 60  # migrations comprises ; en pratique quelques secondes
PHONE_URL_RE = re.compile(r"téléphones?.*?(http://\S+)", re.IGNORECASE)
# La commande de l'enseignant, lancée depuis le dépôt : le script `qcm-live` installé fait de
# même avec le Python de son environnement (INS-01).
LAUNCHER = [sys.executable, "-m", "config.launcher"]
# Variables propres à Claude Code ou aux tests, que l'enseignant n'a pas.
UNSET = ("UV_ENV_FILE", "DJANGO_SETTINGS_MODULE", "PYTEST_CURRENT_TEST", "BROWSER")


@dataclass
class Classroom:
    local_url: str  # sur le PC de l'enseignant, sans « / » final
    phone_url: str  # annoncée dans le terminal, avec « / » final
    output: list[str]


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("", 0))
        return sock.getsockname()[1]


def clean_env(**extra: str) -> dict[str, str]:
    """Environnement du terminal de l'enseignant, plus `extra`."""
    env = {k: v for k, v in os.environ.items() if k not in UNSET}
    return {**env, **extra}


def env_on_test_db(**extra: str) -> dict[str, str]:
    """Environnement d'un serveur lancé sur la base de test, où les fabriques créent les
    préconditions."""
    return clean_env(DJANGO_DB_PATH=str(settings.DATABASES["default"]["NAME"]), **extra)


def browser_recorder(folder: Path) -> tuple[str, Path]:
    """Navigateur factice, pour la variable BROWSER : il note l'adresse qu'on lui demande
    d'ouvrir. Rend la valeur de BROWSER et le fichier où lire l'adresse."""
    script, record = folder / "navigateur.sh", folder / "navigateur-ouvert.txt"
    script.write_text(f'#!/bin/sh\nprintf "%s" "$1" > "{record}"\n', encoding="utf-8")
    script.chmod(0o755)
    return f"{script} %s", record


def data_dir(folder: Path) -> Path:
    """Dossier de données comme l'installation le prépare (INS-01), avec une clé de test : le
    lanceur ne lit jamais la vraie clé (`.env`)."""
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    (folder / "reglages.env").write_text(
        "DJANGO_SECRET_KEY=cle-de-test-sans-valeur-pour-le-lanceur\n", encoding="utf-8"
    )
    return folder


@contextmanager
def announced(
    command: Sequence[str], *, port: int, env: dict[str, str], cwd: Path = REPO
) -> Iterator[Classroom]:
    """Lance `command`, attend l'adresse des téléphones annoncée dans le terminal, puis arrête
    le processus et tous ses enfants (make, uv, serveur) à la sortie."""
    process = subprocess.Popen(
        list(command),
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,  # pour tout arrêter d'un coup, et sans terminal
    )
    lines: queue.Queue[str] = queue.Queue()
    output: list[str] = []

    def read() -> None:
        assert process.stdout
        for line in process.stdout:
            output.append(line)
            lines.put(line)

    threading.Thread(target=read, daemon=True).start()
    try:
        deadline = time.monotonic() + STARTUP_S
        phone_url = None
        while phone_url is None:
            try:
                line = lines.get(timeout=0.2)
            except queue.Empty:
                if process.poll() is not None or time.monotonic() > deadline:
                    pytest.fail("aucune adresse annoncée :\n" + "".join(output))
                continue
            if match := PHONE_URL_RE.search(line):
                phone_url = match.group(1)
        time.sleep(0.2)  # laisser le terminal finir son annonce (autres adresses, pare-feu)
        yield Classroom(f"http://localhost:{port}", phone_url, output)
    finally:
        with suppress(ProcessLookupError):  # déjà arrêté : son échec est rapporté plus haut
            os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=10)


def run(
    command: Sequence[str], *, env: dict[str, str], answers: str = "", cwd: Path = REPO
) -> subprocess.CompletedProcess[str]:
    """Commande du terminal, avec les réponses `answers` tapées au clavier."""
    return subprocess.run(
        list(command),
        cwd=cwd,
        env=env,
        input=answers,
        capture_output=True,
        text=True,
        timeout=STARTUP_S,
        check=False,
    )


@contextmanager
def class_mode(*make_args: str) -> Iterator[Classroom]:
    """`make classe` lancé sur un port libre, sur la base de test : comme en classe (CLA-01).
    L'environnement demande le mode debug, comme le .env de développement : le mode classe doit
    l'ignorer."""
    port = free_port()
    env = env_on_test_db(DJANGO_DEBUG="1")
    command = ["make", "--no-print-directory", "classe", "ENV_FILE=.env.test", f"PORT={port}"]
    with announced([*command, *make_args], port=port, env=env) as server:
        assert any("--env-file .env.test" in line for line in server.output), server.output
        yield server
