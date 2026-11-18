"""Mode classe (CLA-01 à CLA-03) : réglages imposés, terminal et port."""

from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

from config import classroom
from config.firewall import advice
from config.network import LanAddress

WLAN = LanAddress(address="192.168.1.23", interface="wlp2s0", virtual=False)
DOCKER = LanAddress(address="172.17.0.1", interface="docker0", virtual=True)


def test_classroom_environ_forces_production_and_announces_the_lan_address():
    assert classroom.classroom_environ("192.168.1.23", 8000, [WLAN, DOCKER]) == {
        "DJANGO_DEBUG": "0",
        "QCM_JOIN_URL": "http://192.168.1.23:8000/",
        "QCM_LAN_ADDRESSES": json.dumps([WLAN, DOCKER]),
        "QCM_TEACHER_LOCAL_ONLY": "1",
    }


def test_projected_address_is_the_imposed_one_or_the_most_likely():
    assert classroom.projected("pc-prof.local", [WLAN]) == "pc-prof.local"
    assert classroom.projected(None, [WLAN, DOCKER]) == "192.168.1.23"
    assert classroom.projected(None, []) == "127.0.0.1"


def test_banner_gives_the_phone_address_and_the_teacher_address():
    text = classroom.banner("http://192.168.1.23:8000/", 8000)
    assert "http://192.168.1.23:8000/" in text
    assert "http://localhost:8000/prof/" in text
    assert classroom.GUIDE_URL in text
    assert "Ctrl+C" in text
    assert "Pare-feu" not in text


def test_banner_lists_every_address_with_its_card_and_the_firewall_advice():
    text = classroom.banner(
        "http://192.168.1.23:8000/", 8000, [WLAN, DOCKER], [advice("ufw", 8000)]
    )
    assert "  192.168.1.23     wlp2s0\n" in text
    assert "  172.17.0.1       docker0 (réseau virtuel)\n" in text
    assert "Changer d'adresse" in text
    assert "    sudo ufw allow 8000/tcp\n" in text
    assert "QCM Live ne modifie jamais le pare-feu" in text
    # Seule la première ligne qui parle des téléphones donne une adresse (lue par les tests).
    phone_lines = [line for line in text.splitlines() if "téléphone" in line and "http" in line]
    assert phone_lines == ["  Sur les téléphones des étudiants, ouvrir : http://192.168.1.23:8000/"]


def test_port_free_and_port_taken():
    with socket.socket() as taken:
        taken.bind(("", 0))
        taken.listen()
        port = taken.getsockname()[1]
        assert not classroom.port_free(port)
    assert classroom.port_free(port)
    message = classroom.port_taken(8000)
    assert "Le port 8000 est déjà utilisé" in message
    assert "QCM Live est peut-être déjà lancé" in message
    assert "--port 8001" in message


def test_non_numeric_port_is_refused():
    with pytest.raises(SystemExit):
        classroom.parse_args(["--port", "abc"])


@pytest.mark.parametrize(
    "address", ["http://192.168.1.23", "192.168.1.23:8000", "fe80::1", "192.168.1.23/", ""]
)
def test_address_must_be_a_bare_host(address):
    with pytest.raises(SystemExit):
        classroom.parse_args(["--adresse", address])


@pytest.mark.parametrize("address", ["192.168.1.23", "pc-prof.local", "PC-PROF"])
def test_address_accepts_an_ipv4_address_or_a_host_name(address):
    assert classroom.parse_args(["--adresse", address]).address == address


def test_default_port_and_detected_address():
    args = classroom.parse_args([])
    assert args.port == 8000
    assert args.address is None
    assert classroom.parse_args(["--port", "8123", "--adresse", "10.1.2.3"]).address == "10.1.2.3"


def test_demo_option_names_the_demo_database():
    assert classroom.parse_args([]).demo is None
    assert classroom.parse_args(["--demo", "demo.sqlite3"]).demo == Path("demo.sqlite3")


def test_reset_demo_removes_the_demo_database_and_its_sqlite_files(tmp_path):
    database = tmp_path / classroom.DEMO_DATABASE
    names = ["demo.sqlite3", "demo.sqlite3-wal", "demo.sqlite3-shm", "demo.sqlite3-journal"]
    for name in [*names, "db.sqlite3", "demo.sqlite3.bak"]:
        (tmp_path / name).write_text("x")
    classroom.reset_demo(database)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["db.sqlite3", "demo.sqlite3.bak"]
    classroom.reset_demo(database)  # déjà absente : rien à faire


@pytest.mark.parametrize("name", ["db.sqlite3", "demo.sqlite", "autre.sqlite3"])
def test_reset_demo_never_removes_another_database(tmp_path, name):
    """Garde-fou (DEM-03) : la base de l'enseignant n'est jamais effacée."""
    database = tmp_path / name
    database.write_text("x")
    with pytest.raises(ValueError, match=r"demo\.sqlite3"):
        classroom.reset_demo(database)
    assert database.exists()
