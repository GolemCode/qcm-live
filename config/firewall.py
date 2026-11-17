"""Pare-feu du PC (CLA-03) : le détecter et dire comment laisser passer les téléphones.

QCM Live ne modifie jamais le pare-feu : la détection ne fait que lire (un fichier, l'état
d'un service, le profil du réseau sous Windows), et les commandes proposées sont à copier par
l'enseignant, qui juge s'il veut les lancer. Rien ne l'impose techniquement : cela tient au
code ci-dessous, qui ne lance que les sondes de `PROBES`. Un test d'intégration le vérifie pour
`detect`, `advices` et la page « Réseau », sur les lancements par `subprocess`, `os.system` et
`os.posix_spawn` (tests/integration/test_network.py).

Chaque détection est un identifiant : `ufw`, `firewalld`, `windows-public` (Windows, réseau
en profil « Public », qui bloque les connexions entrantes).
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from config.network import TIMEOUT_S, powershell_items

UFW_CONF = Path("/etc/ufw/ufw.conf")
FIREWALLD_PROBE = ["systemctl", "is-active", "--quiet", "firewalld"]
WINDOWS_PROBE = [
    "powershell",
    "-NoProfile",
    "-NonInteractive",
    "-Command",
    "Get-NetConnectionProfile | Select-Object NetworkCategory | ConvertTo-Json -Compress",
]
PROBES = (FIREWALLD_PROBE, WINDOWS_PROBE)  # les seules commandes lancées


@dataclass(frozen=True)
class Advice:
    text: str
    commands: tuple[str, ...]  # à copier, jamais lancées par QCM Live


def advice(found: str, port: int) -> Advice:
    if found == "ufw":
        return Advice(
            "Le pare-feu ufw est actif. Pour ouvrir le port aux téléphones, dans un terminal :",
            (f"sudo ufw allow {port}/tcp",),
        )
    if found == "firewalld":
        return Advice(
            "Le pare-feu firewalld est actif. Pour ouvrir le port aux téléphones, dans un "
            "terminal :",
            (
                f"sudo firewall-cmd --permanent --add-port={port}/tcp",
                "sudo firewall-cmd --reload",
            ),
        )
    if found == "windows-public":
        return Advice(
            "Le réseau est en profil « Public » : Windows y bloque les téléphones. Passez-le "
            "en profil « Privé » (Paramètres, Réseau et Internet, propriétés du réseau), ou, "
            "dans PowerShell lancé en administrateur :",
            (
                'New-NetFirewallRule -DisplayName "QCM Live" -Direction Inbound '
                f"-Protocol TCP -LocalPort {port} -Action Allow",
            ),
        )
    raise ValueError(found)


def ufw_enabled(conf: Path = UFW_CONF) -> bool:
    """`ENABLED=yes` dans la configuration d'ufw, lisible sans droits d'administrateur."""
    try:
        text = conf.read_text(encoding="utf-8")
    except OSError:
        return False
    return any(line.strip().replace(" ", "") == "ENABLED=yes" for line in text.splitlines())


def public_network(powershell_json: str) -> bool:
    """Sortie de `Get-NetConnectionProfile` : un réseau en profil Public (0 sous Windows
    PowerShell 5.1)."""
    items = powershell_items(powershell_json)
    return any(item.get("NetworkCategory") in (0, "Public") for item in items)


def _probe(command: list[str]) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(  # noqa: S603 — sondes fixes, en lecture seule (PROBES)
            command, capture_output=True, text=True, timeout=TIMEOUT_S, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None


def detect() -> list[str]:
    """Pare-feu actifs qui peuvent bloquer les téléphones (lecture seule)."""
    if sys.platform == "win32":
        result = _probe(WINDOWS_PROBE)
        try:
            public = bool(result and result.returncode == 0 and public_network(result.stdout))
        except (ValueError, AttributeError):
            public = False
        return ["windows-public"] if public else []
    found = []
    if ufw_enabled():
        found.append("ufw")
    result = _probe(FIREWALLD_PROBE)
    if result and result.returncode == 0:
        found.append("firewalld")
    return found


def advices(port: int) -> list[Advice]:
    """Conseils pour chaque pare-feu détecté, avec le port réellement servi."""
    return [advice(found, port) for found in detect()]
