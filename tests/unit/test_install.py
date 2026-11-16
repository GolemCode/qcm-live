"""Fin de l'installation (INS-01) : réglages, commande, icône, réponses sans terminal."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from config import install


def test_write_settings_creates_a_secret_once(tmp_path):
    assert install.write_settings(tmp_path)
    path = tmp_path / "reglages.env"
    assert path.stat().st_mode & 0o777 == 0o600
    text = path.read_text()
    assert re.search(r"^DJANGO_SECRET_KEY=\S{60,}$", text, re.M)
    assert not install.write_settings(tmp_path)  # jamais réécrit : la mise à jour le garde
    assert path.read_text() == text


def test_unix_command_quotes_paths_and_passes_arguments(tmp_path):
    data = tmp_path / "Mes données" / "qcm-live"
    app = data / "app"
    script = tmp_path / "qcm-live"
    python = tmp_path / "py"
    python.write_text('#!/bin/sh\nprintf "%s|%s|%s\\n" "$QCM_DATA_DIR" "$PYTHONPATH" "$*"\n')
    python.chmod(0o755)
    script.write_text(install.unix_command(data, app, python))
    script.chmod(0o755)
    result = subprocess.run(
        [str(script), "restaurer", "a b.zip"], capture_output=True, text=True, check=True
    )
    assert result.stdout == f"{data}|{app}|-m config.launcher restaurer a b.zip\n"


def test_windows_command():
    text = install.windows_command(Path("C:/d"), Path("C:/d/app"), Path("C:/d/venv/python.exe"))
    assert text.startswith("@echo off\r\n")
    assert '"C:/d/venv/python.exe" -m config.launcher %*\r\n' in text


def test_desktop_entry_quotes_a_path_with_spaces():
    assert "Exec=/home/a/.local/bin/qcm-live\n" in install.desktop_entry(
        Path("/home/a/.local/bin/qcm-live"), Path("/i.svg")
    )
    assert 'Exec="/home/a b/.local/bin/qcm-live"\n' in install.desktop_entry(
        Path("/home/a b/.local/bin/qcm-live"), Path("/i.svg")
    )


def test_write_launchers(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    command = install.write_launchers(tmp_path / "data", Path("/app"), Path("/venv/bin/python"))
    assert command == tmp_path / ".local" / "bin" / "qcm-live"
    assert command.stat().st_mode & 0o111
    desktop = (tmp_path / ".local" / "share" / "applications" / "qcm-live.desktop").read_text()
    assert f"Exec={command}\n" in desktop
    assert "Icon=/app/static/img/qcm-live.svg\n" in desktop
    assert (install.APP_DIR / "static" / "img" / "qcm-live.svg").is_file()


@pytest.mark.parametrize(
    ("env", "interactive", "typed", "expected"),
    [
        ("oui", False, None, True),
        ("o", False, None, True),
        ("non", True, None, False),  # l'environnement l'emporte : pas de question
        (None, False, None, False),  # sans terminal ni réponse : non
        (None, True, "o", True),
        (None, True, "", False),  # défaut : non
    ],
)
def test_wants_demo(monkeypatch, env, interactive, typed, expected):
    if env is None:
        monkeypatch.delenv("QCM_LIVE_DEMO", raising=False)
    else:
        monkeypatch.setenv("QCM_LIVE_DEMO", env)
    asked = []
    monkeypatch.setattr(install, "ask", lambda q: asked.append(q) or typed)
    assert install.wants_demo(interactive) is expected
    assert bool(asked) == (typed is not None)
