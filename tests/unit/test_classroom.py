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


def test_lan_address_falls_back_to_loopback_without_network(monkeypatch):
    monkeypatch.setattr(socket, "socket", lambda *a: _FakeSocket(None))
    assert classroom.lan_address() == "127.0.0.1"


def test_lan_address_on_this_machine_is_an_ipv4_address():
    socket.inet_aton(classroom.lan_address())


def test_classroom_environ_forces_production_and_announces_the_lan_address():
    env = classroom.classroom_environ({"DJANGO_DEBUG": "1"}, "192.168.1.23", 8000)
    assert env == {
        "DJANGO_DEBUG": "0",
        "DJANGO_ALLOWED_HOSTS": "localhost,127.0.0.1,192.168.1.23",
        "QCM_JOIN_URL": "http://192.168.1.23:8000/",
    }


def test_classroom_environ_keeps_the_allowed_hosts_already_configured():
    env = classroom.classroom_environ({"DJANGO_ALLOWED_HOSTS": "pc-prof"}, "10.0.0.5", 8080)
    assert env["DJANGO_ALLOWED_HOSTS"] == "pc-prof,10.0.0.5"
    assert env["QCM_JOIN_URL"] == "http://10.0.0.5:8080/"


def test_banner_gives_the_phone_address_and_the_teacher_address():
    text = classroom.banner("http://192.168.1.23:8000/", 8000)
    assert "http://192.168.1.23:8000/" in text
    assert "http://localhost:8000/prof/" in text
    assert "Ctrl+C" in text


@pytest.mark.parametrize("argv", [["--port", "0"], ["--port", "70000"], ["--port", "abc"]])
def test_invalid_port_is_refused(argv):
    with pytest.raises(SystemExit):
        classroom.parse_args(argv)


def test_default_port_and_detected_address(monkeypatch):
    args = classroom.parse_args([])
    assert args.port == 8000
    assert args.adresse is None
    assert classroom.parse_args(["--port", "8123", "--adresse", "10.1.2.3"]).adresse == "10.1.2.3"
