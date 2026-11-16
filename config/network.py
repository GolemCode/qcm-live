"""Adresses du PC sur les réseaux locaux (CLA-02), sans Django.

Le mode classe annonce l'adresse que les téléphones ouvrent. Une adresse devinée ne suffit
pas : en partage de connexion, celle de la route par défaut n'est pas celle du réseau où sont
les téléphones, et une carte virtuelle (Docker, VPN, machine virtuelle) peut passer devant.
On liste donc toutes les adresses IPv4 du PC, avec le nom de leur carte, dans l'ordre où
elles ont le plus de chances de convenir ; l'enseignant en change sans redémarrer (page
« Réseau et téléphones »).

- Linux : `ip -j -4 addr show up` (toutes les adresses de chaque carte) ; à défaut, `ioctl`
  (bibliothèque standard, seule l'adresse principale de chaque carte).
- Windows : `Get-NetIPAddress` en PowerShell.
- Partout : l'adresse de la route par défaut, par une socket UDP « connectée » sans envoi.
"""

from __future__ import annotations

import ipaddress
import json
import socket
import struct
import subprocess
import sys
from collections.abc import Iterable
from typing import TypedDict

# Adresse de documentation (RFC 5737) : « connecter » une socket UDP vers elle choisit
# l'interface de la route par défaut, sans envoyer aucun paquet.
PROBE = ("192.0.2.1", 9)
TIMEOUT_S = 10
# Cartes virtuelles : conteneurs, machines virtuelles, VPN. Elles restent proposées, en
# dernier : les téléphones de la salle n'y sont presque jamais. Linux : début du nom de la
# carte ; Windows : un mot de son nom (« vEthernet (WSL) », « VirtualBox Host-Only »…).
VIRTUAL_PREFIXES = (
    "docker", "br-", "veth", "virbr", "vmnet", "vboxnet", "lxc", "lxdbr", "podman", "cni",
    "flannel", "tun", "tap", "wg", "tailscale", "zt",
)  # fmt: skip
VIRTUAL_WORDS = ("vethernet", "virtualbox", "vmware", "hyper-v", "openvpn", "wireguard", "zerotier")
# Réseau ouvert par le PC lui-même (partage de connexion du PC) : les téléphones y sont.
# Windows (« Point d'accès mobile ») donne toujours 192.168.137.1 ; NetworkManager, 10.42.x.1.
HOTSPOT_WINDOWS = "192.168.137.1"
HOTSPOT_NM = ipaddress.ip_network("10.42.0.0/16")


class LanAddress(TypedDict):
    address: str
    interface: str
    virtual: bool


def is_virtual(interface: str) -> bool:
    name = interface.lower()
    return name.startswith(VIRTUAL_PREFIXES) or any(word in name for word in VIRTUAL_WORDS)


def is_hotspot(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return address == HOTSPOT_WINDOWS or (ip in HOTSPOT_NM and address.endswith(".1"))


def usable(address: str) -> bool:
    """Une adresse qu'un téléphone peut joindre : ni boucle locale, ni adresse automatique
    (169.254, carte sans réseau), ni adresse non IPv4."""
    try:
        ip = ipaddress.IPv4Address(address)
    except ValueError:
        return False
    return not (ip.is_loopback or ip.is_link_local or ip.is_unspecified or ip.is_multicast)


def rank(found: Iterable[tuple[str, str]], default: str | None) -> list[LanAddress]:
    """Adresses `(adresse, carte)` utilisables, sans doublon, de la plus probable à la moins
    probable : réseau ouvert par le PC, adresse de la route par défaut, autres adresses
    privées, autres adresses, et enfin les cartes virtuelles."""
    seen: dict[str, str] = {}
    for address, interface in found:
        if usable(address) and address not in seen:
            seen[address] = interface

    def key(item: tuple[str, str]) -> int:
        address, interface = item
        if is_virtual(interface):
            return 4
        if is_hotspot(address):
            return 0
        if address == default:
            return 1
        return 2 if ipaddress.IPv4Address(address).is_private else 3

    ordered = sorted(seen.items(), key=key)  # tri stable : l'ordre du système à égalité
    return [{"address": a, "interface": i, "virtual": is_virtual(i)} for a, i in ordered]


def default_route_address() -> str | None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        try:
            probe.connect(PROBE)
            return probe.getsockname()[0]
        except OSError:
            return None


def parse_ip_json(text: str) -> list[tuple[str, str]]:
    """Sortie de `ip -j -4 addr show up` : adresses des cartes actives, hors boucle locale."""
    return [
        (info["local"], card["ifname"])
        for card in json.loads(text or "[]")
        if "LOOPBACK" not in card.get("flags", [])
        for info in card.get("addr_info", [])
        if "local" in info
    ]


def parse_powershell_json(text: str) -> list[tuple[str, str]]:
    """Sortie de `Get-NetIPAddress | ConvertTo-Json` : adresses en service (« Preferred »,
    4 sous Windows PowerShell 5.1). Un seul résultat arrive comme un objet, pas une liste."""
    data = json.loads(text or "[]")
    items = data if isinstance(data, list) else [data]
    return [
        (item["IPAddress"], item["InterfaceAlias"])
        for item in items
        if item.get("AddressState") in (4, "Preferred")
    ]


IFF_UP, IFF_LOOPBACK = 0x1, 0x8
SIOCGIFFLAGS, SIOCGIFADDR = 0x8913, 0x8915


def ioctl_addresses() -> list[tuple[str, str]]:  # pragma: no cover — repli sans `ip`
    """Adresse principale de chaque carte active, hors boucle locale (Linux)."""
    import fcntl

    found = []
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        for _, name in socket.if_nameindex():
            request = struct.pack("256s", name.encode()[:15])
            try:
                flags = struct.unpack("H", fcntl.ioctl(sock, SIOCGIFFLAGS, request)[16:18])[0]
                if not flags & IFF_UP or flags & IFF_LOOPBACK:
                    continue
                raw = fcntl.ioctl(sock, SIOCGIFADDR, request)[20:24]
            except OSError:  # carte sans adresse IPv4
                continue
            found.append((socket.inet_ntoa(raw), name))
    return found


def _run(command: list[str]) -> str:
    return subprocess.run(  # noqa: S603 — commandes fixes, en lecture seule
        command, capture_output=True, text=True, encoding="utf-8", timeout=TIMEOUT_S, check=True
    ).stdout


POWERSHELL_ADDRESSES = (
    "[Console]::OutputEncoding = [Text.Encoding]::UTF8; "
    "Get-NetIPAddress -AddressFamily IPv4 | "
    "Select-Object IPAddress,InterfaceAlias,AddressState | ConvertTo-Json -Compress"
)


def system_addresses() -> list[tuple[str, str]]:  # pragma: no cover — dépend de la machine
    """Adresses IPv4 du PC, avec le nom de leur carte, lues sur le système."""
    try:
        if sys.platform == "win32":
            return parse_powershell_json(
                _run(
                    [
                        "powershell",
                        "-NoProfile",
                        "-NonInteractive",
                        "-Command",
                        POWERSHELL_ADDRESSES,
                    ]
                )
            )
        return parse_ip_json(_run(["ip", "-j", "-4", "addr", "show", "up"]))
    except (OSError, subprocess.SubprocessError, ValueError, KeyError):
        pass
    if sys.platform != "win32":
        try:
            return ioctl_addresses()
        except OSError:
            pass
    try:
        hostname = socket.gethostname()
        return [(a, hostname) for a in socket.gethostbyname_ex(hostname)[2]]
    except OSError:
        return []


def lan_addresses() -> list[LanAddress]:  # pragma: no cover — dépend de la machine
    """Adresses du PC que les téléphones peuvent joindre, la plus probable en tête."""
    default = default_route_address()
    found = system_addresses()
    if default and default not in {a for a, _ in found}:
        found.append((default, "route par défaut"))
    return rank(found, default)
