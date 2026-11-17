"""Commande de l'enseignant (INS-03) : réglages, arguments, choix d'une sauvegarde."""

from __future__ import annotations

import builtins
import os
from pathlib import Path

import pytest

from config import backup, launcher


def test_read_settings_ignores_comments_and_blank_lines():
    text = "# commentaire\n\nDJANGO_SECRET_KEY = abc=def\nVIDE=\nsans-egal\n"
    assert launcher.read_settings(text) == {"DJANGO_SECRET_KEY": "abc=def", "VIDE": ""}


def test_load_settings_never_overrides_the_environment(tmp_path, monkeypatch):
    (tmp_path / "reglages.env").write_text("QCM_A=fichier\nQCM_B=fichier\n", encoding="utf-8")
    monkeypatch.setenv("QCM_A", "environnement")
    monkeypatch.delenv("QCM_B", raising=False)
    monkeypatch.delenv("QCM_DATA_DIR", raising=False)
    assert launcher.load_settings(tmp_path)
    assert os.environ["QCM_A"] == "environnement"
    assert os.environ["QCM_B"] == "fichier"
    assert os.environ["QCM_DATA_DIR"] == str(tmp_path)
    monkeypatch.delenv("QCM_B")


def test_load_settings_without_the_file(tmp_path):
    assert not launcher.load_settings(tmp_path)


def test_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("QCM_DATA_DIR", str(tmp_path))
    assert launcher.data_dir() == tmp_path
    monkeypatch.delenv("QCM_DATA_DIR")
    monkeypatch.setenv("XDG_DATA_HOME", "/x/share")
    assert launcher.data_dir() == Path("/x/share/qcm-live")
    monkeypatch.delenv("XDG_DATA_HOME")
    monkeypatch.setenv("HOME", str(tmp_path))
    assert launcher.data_dir() == tmp_path / ".local" / "share" / "qcm-live"


def test_data_dir_is_absolute(monkeypatch, tmp_path):
    """Il est écrit dans la commande qcm-live et l'icône, lancées depuis un autre dossier."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("QCM_DATA_DIR", "donnees")
    assert launcher.data_dir() == tmp_path / "donnees"


def test_parse_args():
    args = launcher.parse_args([])
    assert (args.command, args.port, args.address, args.no_browser) == (
        None,
        8000,
        None,
        False,
    )
    args = launcher.parse_args(["--port", "8080", "--sans-navigateur"])
    assert (args.port, args.no_browser) == (8080, True)
    assert launcher.parse_args(["sauvegarder"]).command == "sauvegarder"
    args = launcher.parse_args(["restaurer"])
    assert (args.command, args.archive) == ("restaurer", None)
    assert launcher.parse_args(["restaurer", "a.zip"]).archive == Path("a.zip")
    assert launcher.parse_args(["compte"]).command == "compte"
    with pytest.raises(SystemExit):
        launcher.parse_args(["--adresse", "http://x/"])


def answers(monkeypatch, *typed: str | type[BaseException]) -> None:
    replies = iter(typed)

    def fake_input(prompt: str = "") -> str:
        print(prompt, end="")
        reply = next(replies)
        if isinstance(reply, str):
            return reply
        raise reply

    monkeypatch.setattr(builtins, "input", fake_input)


def test_ask_treats_end_of_input_and_ctrl_c_as_no(monkeypatch):
    answers(monkeypatch, " Oui ", EOFError, KeyboardInterrupt)
    assert launcher.ask("?") == "oui"
    assert launcher.ask("?") == ""
    assert launcher.ask("?") == ""


@pytest.fixture
def folder(monkeypatch, tmp_path) -> Path:
    path = tmp_path / "sauvegardes"
    monkeypatch.setattr(backup, "default_folder", lambda: path)
    return path


def test_choose_archive_lists_the_most_recent_first(folder, monkeypatch, capsys):
    folder.mkdir()
    for day in (1, 3, 2):
        (folder / f"qcm-live-2026-01-0{day}-10h00m00s.zip").write_bytes(b"")
    answers(monkeypatch, "2")
    assert launcher.choose_archive() == folder / "qcm-live-2026-01-02-10h00m00s.zip"
    out = capsys.readouterr().out
    assert "  1. qcm-live-2026-01-03-10h00m00s.zip\n  2. qcm-live-2026-01-02" in out


@pytest.mark.parametrize("typed", ["0", "4", "deux", ""])
def test_choose_archive_refuses_a_wrong_number(folder, monkeypatch, typed):
    folder.mkdir()
    for day in (1, 2, 3):
        (folder / f"qcm-live-2026-01-0{day}-10h00m00s.zip").write_bytes(b"")
    answers(monkeypatch, typed)
    assert launcher.choose_archive() is None


def test_choose_archive_without_any_backup(folder, capsys):
    assert launcher.choose_archive() is None
    assert "Aucune sauvegarde" in capsys.readouterr().out
