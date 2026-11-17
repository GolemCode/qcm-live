"""Adresses du PC (CLA-02) : lecture des cartes et classement, sans Django."""

from __future__ import annotations

import json
import socket
import subprocess

import pytest

from config import network
from config.network import (
    is_hotspot,
    is_virtual,
    parse_ip_json,
    parse_powershell_json,
    rank,
    usable,
)

# Extrait d'une vraie sortie de `ip -j -4 addr show up` (WSL2, réseau miroir), plus une
# carte Docker et une seconde adresse sur la même carte.
IP_JSON = json.dumps(
    [
        {
            "ifname": "lo",
            "flags": ["LOOPBACK", "UP", "LOWER_UP"],
            "addr_info": [{"local": "127.0.0.1"}, {"local": "10.255.255.254"}],
        },
        {
            "ifname": "eth3",
            "flags": ["BROADCAST", "MULTICAST", "UP", "LOWER_UP"],
            "addr_info": [{"local": "10.188.228.62"}, {"local": "10.188.228.63"}],
        },
        {"ifname": "docker0", "flags": ["UP"], "addr_info": [{"local": "172.17.0.1"}]},
        {"ifname": "eth9", "flags": ["UP"], "addr_info": [{"family": "inet"}]},
    ]
)
# Vraie sortie de `Get-NetIPAddress` (Windows PowerShell 5.1, états en nombres : 4 =
# Preferred), raccourcie : une carte sans réseau (169.254, état 1), le Wi-Fi, la boucle.
POWERSHELL_JSON = (
    '[{"IPAddress":"169.254.167.109","InterfaceAlias":"Connexion au réseau local* 2",'
    '"AddressState":1},'
    '{"IPAddress":"10.188.228.62","InterfaceAlias":"Wi-Fi","AddressState":4},'
    '{"IPAddress":"127.0.0.1","InterfaceAlias":"Loopback Pseudo-Interface 1","AddressState":4}]'
)


def test_parse_ip_json_skips_the_loopback_card_and_keeps_every_address():
    assert parse_ip_json(IP_JSON) == [
        ("10.188.228.62", "eth3"),
        ("10.188.228.63", "eth3"),
        ("172.17.0.1", "docker0"),
    ]
    assert parse_ip_json("") == []


def test_parse_powershell_json_keeps_addresses_in_service():
    assert parse_powershell_json(POWERSHELL_JSON) == [
        ("10.188.228.62", "Wi-Fi"),
        ("127.0.0.1", "Loopback Pseudo-Interface 1"),
    ]


def test_parse_powershell_json_with_a_single_address_or_states_as_text():
    """Un seul résultat arrive comme un objet ; PowerShell 7 peut écrire l'état en texte."""
    one = '{"IPAddress":"192.168.137.1","InterfaceAlias":"Hotspot","AddressState":"Preferred"}'
    assert parse_powershell_json(one) == [("192.168.137.1", "Hotspot")]
    assert parse_powershell_json("") == []


def test_powershell_output_with_a_byte_order_mark(monkeypatch):
    """Windows PowerShell 5.1 en UTF-8 peut écrire une marque d'ordre en tête de sa sortie."""
    out = "\ufeff" + json.dumps([{"IPAddress": "192.168.1.20", "InterfaceAlias": "Wi-Fi"}])

    def run(command, **kwargs):
        return subprocess.CompletedProcess(
            command, 0, out.encode("utf-8").decode(kwargs["encoding"])
        )

    monkeypatch.setattr(subprocess, "run", run)
    assert network.powershell_items(network._run(["powershell"])) == [
        {"IPAddress": "192.168.1.20", "InterfaceAlias": "Wi-Fi"}
    ]


@pytest.mark.parametrize(
    ("address", "ok"),
    [
        ("192.168.1.20", True),
        ("10.188.228.62", True),
        ("82.64.1.2", True),
        ("127.0.0.1", False),
        ("127.0.1.1", False),
        ("169.254.12.3", False),
        ("0.0.0.0", False),  # noqa: S104
        ("224.0.0.1", False),
        ("fe80::1", False),
        ("pas une adresse", False),
    ],
)
def test_usable(address, ok):
    assert usable(address) is ok


@pytest.mark.parametrize(
    ("interface", "virtual"),
    [
        ("docker0", True),
        ("br-1a2b3c", True),
        ("veth12ab", True),
        ("virbr0", True),
        ("vboxnet0", True),
        ("tun0", True),
        ("wg0", True),
        ("tailscale0", True),
        ("vEthernet (WSL)", True),
        ("VirtualBox Host-Only Network", True),
        ("VMware Network Adapter VMnet8", True),
        ("OpenVPN Data Channel Offload", True),
        ("wlp2s0", False),
        ("eth0", False),
        ("enp3s0", False),
        ("Wi-Fi", False),
        ("Ethernet", False),
        ("Connexion au réseau local* 2", False),
    ],
)
def test_is_virtual(interface, virtual):
    assert is_virtual(interface) is virtual


@pytest.mark.parametrize(
    ("address", "hotspot"),
    [
        ("192.168.137.1", True),  # Windows, « Point d'accès mobile »
        ("10.42.0.1", True),  # NetworkManager, partage de connexion
        ("10.42.3.1", True),
        ("10.42.0.17", False),  # un client de ce réseau, pas le PC qui l'ouvre
        ("192.168.137.12", False),
        ("192.168.1.1", False),
    ],
)
def test_is_hotspot(address, hotspot):
    assert is_hotspot(address) is hotspot


def test_rank_puts_the_network_opened_by_the_pc_first_and_virtual_cards_last():
    found = [
        ("172.17.0.1", "docker0"),
        ("82.64.1.2", "eth1"),
        ("10.0.0.5", "eth0"),
        ("192.168.1.20", "wlp2s0"),
        ("192.168.137.1", "Connexion au réseau local* 2"),
        ("127.0.0.1", "lo"),
        ("169.254.3.4", "Ethernet"),
        ("192.168.1.20", "wlp2s0"),  # doublon
    ]
    ranked = rank(found, default="192.168.1.20")
    assert [(item["address"], item["virtual"]) for item in ranked] == [
        ("192.168.137.1", False),  # réseau ouvert par le PC : les téléphones y sont
        ("192.168.1.20", False),  # route par défaut
        ("10.0.0.5", False),  # autre adresse privée
        ("82.64.1.2", False),  # adresse publique
        ("172.17.0.1", True),  # carte virtuelle, même si c'est la route par défaut ailleurs
    ]
    assert ranked[0]["interface"] == "Connexion au réseau local* 2"


def test_rank_puts_a_virtual_card_last_even_on_the_default_route():
    ranked = rank([("10.8.0.2", "tun0"), ("192.168.1.20", "wlp2s0")], default="10.8.0.2")
    assert [item["address"] for item in ranked] == ["192.168.1.20", "10.8.0.2"]


def test_rank_without_any_usable_address():
    assert rank([("127.0.0.1", "lo"), ("169.254.1.1", "eth0")], default=None) == []


class _FakeSocket:
    def __init__(self, address: str | None) -> None:
        self.address = address

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        return None

    def connect(self, target) -> None:
        if self.address is None:
            raise OSError("Network is unreachable")

    def getsockname(self):
        return (self.address, 54321)


def test_default_route_address(monkeypatch):
    monkeypatch.setattr(socket, "socket", lambda *a: _FakeSocket("192.168.1.23"))
    assert network.default_route_address() == "192.168.1.23"


def test_default_route_address_without_route(monkeypatch):
    """Réseau fermé, sans passerelle (point d'accès de la salle) : pas de route par défaut."""
    monkeypatch.setattr(socket, "socket", lambda *a: _FakeSocket(None))
    assert network.default_route_address() is None


def test_addresses_of_this_machine_match_ip():
    """Sur la machine de test, la lecture par `ip` et le repli par `ioctl` s'accordent sur
    l'adresse principale de chaque carte."""
    listed = parse_ip_json(
        subprocess.run(
            ["ip", "-j", "-4", "addr", "show", "up"], capture_output=True, text=True, check=True
        ).stdout
    )
    assert set(network.ioctl_addresses()) <= set(listed)
    assert set(network.system_addresses()) == set(listed)
    for item in network.lan_addresses():
        socket.inet_aton(item["address"])
