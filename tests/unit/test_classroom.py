"""Mode classe (CLA-01) : adresse du PC sur le réseau local et réglages imposés."""

from __future__ import annotations

import socket

import pytest

from config import classroom


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


def test_lan_address_is_the_one_of_the_default_route(monkeypatch):
    monkeypatch.setattr(socket, "socket", lambda *a: _FakeSocket("192.168.1.23"))
    assert classroom.lan_address() == "192.168.1.23"


def test_lan_address_without_default_route_uses_the_addresses_of_the_pc(monkeypatch):
    """Réseau fermé, sans passerelle (point d'accès de la salle) : pas de route par défaut."""
    monkeypatch.setattr(socket, "socket", lambda *a: _FakeSocket(None))
    monkeypatch.setattr(
        socket, "gethostbyname_ex", lambda name: (name, [], ["127.0.1.1", "192.168.137.1"])
    )
    assert classroom.lan_address() == "192.168.137.1"


def test_lan_address_falls_back_to_loopback_without_network(monkeypatch):
    monkeypatch.setattr(socket, "socket", lambda *a: _FakeSocket(None))
    monkeypatch.setattr(socket, "gethostbyname_ex", lambda name: (name, [], ["127.0.1.1"]))
    assert classroom.lan_address() == "127.0.0.1"


def test_lan_address_falls_back_to_loopback_when_the_name_is_unknown(monkeypatch):
    def unknown(name):
        raise socket.gaierror("unknown")

    monkeypatch.setattr(socket, "socket", lambda *a: _FakeSocket(None))
    monkeypatch.setattr(socket, "gethostbyname_ex", unknown)
    assert classroom.lan_address() == "127.0.0.1"


def test_lan_address_on_this_machine_is_an_ipv4_address():
    socket.inet_aton(classroom.lan_address())


def test_classroom_environ_forces_production_and_announces_the_lan_address():
    assert classroom.classroom_environ("192.168.1.23", 8000) == {
        "DJANGO_DEBUG": "0",
        "QCM_JOIN_URL": "http://192.168.1.23:8000/",
        "QCM_TEACHER_LOCAL_ONLY": "1",
    }


def test_banner_gives_the_phone_address_and_the_teacher_address():
    text = classroom.banner("http://192.168.1.23:8000/", 8000)
    assert "http://192.168.1.23:8000/" in text
    assert "http://localhost:8000/prof/" in text
    assert "Ctrl+C" in text


def test_non_numeric_port_is_refused():
    with pytest.raises(SystemExit):
        classroom.parse_args(["--port", "abc"])


@pytest.mark.parametrize(
    "adresse", ["http://192.168.1.23", "192.168.1.23:8000", "fe80::1", "192.168.1.23/", ""]
)
def test_address_must_be_a_bare_host(adresse):
    with pytest.raises(SystemExit):
        classroom.parse_args(["--adresse", adresse])


@pytest.mark.parametrize("adresse", ["192.168.1.23", "pc-prof.local", "PC-PROF"])
def test_address_accepts_an_ipv4_address_or_a_host_name(adresse):
    assert classroom.parse_args(["--adresse", adresse]).adresse == adresse


def test_default_port_and_detected_address():
    args = classroom.parse_args([])
    assert args.port == 8000
    assert args.adresse is None
    assert classroom.parse_args(["--port", "8123", "--adresse", "10.1.2.3"]).adresse == "10.1.2.3"
