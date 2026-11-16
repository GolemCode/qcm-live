"""Pare-feu (CLA-03) : détection en lecture seule et commandes à copier."""

from __future__ import annotations

import subprocess
import sys

import pytest

from config import firewall


@pytest.mark.parametrize(
    ("text", "enabled"),
    [
        ("# /etc/ufw/ufw.conf\nENABLED=yes\nLOGLEVEL=low\n", True),
        ("ENABLED = yes\n", True),
        ("ENABLED=no\n", False),
        ("#ENABLED=yes\n", False),
        ("", False),
    ],
)
def test_ufw_enabled_reads_its_configuration(tmp_path, text, enabled):
    conf = tmp_path / "ufw.conf"
    conf.write_text(text, encoding="utf-8")
    assert firewall.ufw_enabled(conf) is enabled


def test_ufw_enabled_without_ufw(tmp_path):
    assert firewall.ufw_enabled(tmp_path / "absent.conf") is False


@pytest.mark.parametrize(
    ("text", "public"),
    [
        ('{"InterfaceAlias":"Wi-Fi","NetworkCategory":0}', True),  # vraie sortie, 5.1
        ('{"NetworkCategory":1}', False),  # Privé
        ('[{"NetworkCategory":2},{"NetworkCategory":"Public"}]', True),
        ('[{"NetworkCategory":"Private"}]', False),
        ("", False),
    ],
)
def test_public_network(text, public):
    assert firewall.public_network(text) is public


def test_advice_gives_the_command_with_the_real_port():
    assert firewall.advice("ufw", 8123).commands == ("sudo ufw allow 8123/tcp",)
    assert firewall.advice("firewalld", 8123).commands == (
        "sudo firewall-cmd --permanent --add-port=8123/tcp",
        "sudo firewall-cmd --reload",
    )
    windows = firewall.advice("windows-public", 8123)
    assert "Privé" in windows.text
    assert "-LocalPort 8123 " in windows.commands[0]
    with pytest.raises(ValueError):
        firewall.advice("inconnu", 8000)


def test_detect_only_runs_read_only_probes(monkeypatch):
    """QCM Live ne modifie jamais le pare-feu : les seules commandes lancées sont les sondes."""
    ran: list[list[str]] = []

    def fake_run(command, **kwargs):
        ran.append(list(command))
        return subprocess.CompletedProcess(command, 0, stdout='{"NetworkCategory":0}')

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(firewall, "ufw_enabled", lambda: True)
    for platform, expected in [("linux", ["ufw", "firewalld"]), ("win32", ["windows-public"])]:
        monkeypatch.setattr(sys, "platform", platform)
        assert firewall.detect() == expected
    assert ran and all(command in firewall.PROBES for command in ran)
    assert not any("allow" in " ".join(c) or "New-NetFirewallRule" in " ".join(c) for c in ran)


def test_detect_without_any_firewall(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(firewall, "ufw_enabled", lambda: False)
    monkeypatch.setattr(
        subprocess, "run", lambda command, **kw: subprocess.CompletedProcess(command, 3)
    )
    assert firewall.detect() == []


def test_detect_when_a_probe_is_missing(monkeypatch):
    def missing(command, **kwargs):
        raise FileNotFoundError(command[0])

    monkeypatch.setattr(subprocess, "run", missing)
    monkeypatch.setattr(firewall, "ufw_enabled", lambda: False)
    for platform in ("linux", "win32"):
        monkeypatch.setattr(sys, "platform", platform)
        assert firewall.detect() == []


def test_detect_on_windows_with_an_unreadable_answer(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(
        subprocess, "run", lambda c, **kw: subprocess.CompletedProcess(c, 0, stdout="pas du json")
    )
    assert firewall.detect() == []
