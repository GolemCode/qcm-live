"""Incrément 7 : mode classe (CLA-01).

Ces tests ne passent pas par le serveur de test de Django (`live_server`) : ils lancent
l'application comme l'enseignant en classe, avec `make classe`, dans un processus à part.
Le serveur lit la base de test, où les fabriques créent les préconditions.

- Le PC de l'enseignant ouvre l'application en local (`localhost`).
- Les téléphones ouvrent l'adresse projetée au tableau, celle du PC sur le réseau local.
- L'environnement demande le mode debug (`DJANGO_DEBUG=1`) : le mode classe doit l'ignorer.
- Le serveur démarre avec `.env.test` : les tests ne chargent jamais la vraie clé (`.env`).
"""

from __future__ import annotations

import http.client
import os
import queue
import re
import signal
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from http.cookiejar import CookieJar
from pathlib import Path

import pytest
from django.conf import global_settings, settings
from django.utils import timezone
from playwright.sync_api import Page, expect

from live.models import Answer, Participant
from tests.e2e.conftest import TEACHER_PASSWORD, TEACHER_USERNAME, login
from tests.e2e.live_setup import expect_slot, make_live, open_board
from tests.e2e.live_ui import (
    choose,
    identity,
    join,
    open_results,
    qr_text,
    results_rows,
    save_status,
    start,
)
from tests.factories import jump_to

REPO = Path(__file__).resolve().parents[2]
STARTUP_S = 60  # migrations comprises ; en pratique quelques secondes
PHONE_URL_RE = re.compile(r"téléphones?.*?(http://\S+)", re.IGNORECASE)
CLASS_SIZE = 40


@dataclass
class Classroom:
    local_url: str  # sur le PC de l'enseignant, sans « / » final
    phone_url: str  # annoncée dans le terminal, avec « / » final
    output: list[str]


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("", 0))
        return sock.getsockname()[1]


@contextmanager
def class_mode(*make_args: str) -> Iterator[Classroom]:
    """`make classe` lancé sur un port libre, sur la base de test : comme en classe."""
    port = _free_port()
    env = {**os.environ, "DJANGO_DB_PATH": str(settings.DATABASES["default"]["NAME"])}
    env["DJANGO_DEBUG"] = "1"  # comme dans le .env de développement
    process = subprocess.Popen(
        [
            "make",
            "--no-print-directory",
            "classe",
            "ENV_FILE=.env.test",
            f"PORT={port}",
            *make_args,
        ],
        cwd=REPO,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,  # pour arrêter make, uv et le serveur d'un coup
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
                    pytest.fail("le mode classe n'a pas annoncé d'adresse :\n" + "".join(output))
                continue
            if match := PHONE_URL_RE.search(line):
                phone_url = match.group(1)
        assert any("--env-file .env.test" in line for line in output), "".join(output)
        yield Classroom(f"http://localhost:{port}", phone_url, output)
    finally:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=10)


@pytest.fixture
def classroom(transactional_db) -> Iterator[Classroom]:
    with class_mode() as server:
        yield server


@pytest.fixture(autouse=True)
def _steady_clock() -> None:
    """Remplace celui de tests/conftest.py : le serveur du mode classe, lancé à part, lit
    l'horloge système. Les tests doivent lire la même pour placer le déroulement (`jump_to`)."""


@pytest.fixture(autouse=True)
def _fast_password_hasher(settings) -> None:
    """Remplace celui de tests/conftest.py : le serveur du mode classe, lancé à part, ne
    connaît pas le hachage MD5 rapide des tests. Les comptes sont hachés comme en production."""
    settings.PASSWORD_HASHERS = global_settings.PASSWORD_HASHERS


@pytest.mark.spec("CLA-01")
def test_class_mode_end_to_end_from_phones_on_local_network(
    classroom: Classroom, teacher, page: Page, new_phone
):
    session = make_live(1, shown=1, seconds=60)

    # L'adresse annoncée dans le terminal est celle du PC sur le réseau local.
    host = urllib.parse.urlsplit(classroom.phone_url).hostname or ""
    assert host not in {"localhost", ""} and not host.startswith("127."), classroom.phone_url

    # L'enseignant ouvre l'application en local : le tableau projette pourtant l'adresse
    # du réseau local, la seule que les téléphones peuvent joindre.
    login(page, classroom.local_url)
    expect(page.get_by_role("heading", name="Espace enseignant")).to_be_visible()
    open_board(page, classroom.local_url, session)
    hint = page.get_by_text(re.compile(r"^Sur votre téléphone, ouvrez "))
    projected = re.search(r"http://\S+", hint.inner_text())
    assert projected and projected.group(0) == classroom.phone_url

    # Serveur de production local, sans mode debug.
    response = page.request.get(classroom.local_url + "/")
    assert "waitress" in response.headers.get("server", ""), response.headers
    missing = page.request.get(classroom.local_url + "/page-inexistante/")
    assert missing.status == 404
    assert "DEBUG = True" not in missing.text() and "URLconf" not in missing.text()
    assert "<h1>Page introuvable</h1>" in missing.text()  # en français, comme l'interface
    # La politique de sécurité du contenu reste en place.
    assert "default-src 'self'" in response.headers.get("content-security-policy", "")

    # Un téléphone ouvre l'adresse projetée, telle qu'affichée.
    phone = new_phone()
    base = classroom.phone_url.rstrip("/")
    join(phone, base, session.code, "00123")
    expect(identity(phone)).to_have_text("Vous êtes DURAND Élise")
    stylesheet = phone.locator("link[rel=stylesheet]").first.get_attribute("href")
    assert stylesheet
    css = phone.request.get(urllib.parse.urljoin(base + "/", stylesheet))
    assert css.status == 200 and "text/css" in css.headers["content-type"]

    # L'espace enseignant ne s'ouvre que sur le PC : pas depuis le réseau de l'école.
    for path in ("/prof/", "/prof/connexion/", f"/prof/sessions/{session.code}/resultats/"):
        refused = phone.request.get(base + path, max_redirects=0)
        assert refused.status == 403, path
        assert "réservé au PC de l'enseignant" in refused.text()
    # Y compris les envois de formulaire, avec un jeton CSRF valide pris sur la page étudiant.
    cookies = {c["name"]: c["value"] for c in phone.context.cookies()}
    csrf = cookies["csrftoken"]
    credentials = {"username": TEACHER_USERNAME, "password": TEACHER_PASSWORD}
    for path, data in (
        ("/prof/connexion/", credentials),
        (f"/prof/sessions/{session.code}/demarrer/", {}),
    ):
        refused = phone.request.post(
            base + path, form={**data, "csrfmiddlewaretoken": csrf}, max_redirects=0
        )
        assert refused.status == 403, path
        assert "réservé au PC de l'enseignant" in refused.text()
    # Une connexion réussie aurait renouvelé la session du téléphone.
    after = {c["name"]: c["value"] for c in phone.context.cookies()}
    assert after["sessionid"] == cookies["sessionid"]
    session.refresh_from_db()
    assert session.started_at is None  # toujours en attente

    # Déroulement en direct : le téléphone suit le tableau (JavaScript servi) et répond.
    start(page)
    expect_slot(phone, 0)
    choose(phone, "Paris")
    expect(save_status(phone)).to_have_text("Réponse enregistrée")
    assert Answer.objects.filter(participant__number="00123").count() == 1

    # Fin : le QR code sur le téléphone, la note sur le PC de l'enseignant.
    jump_to(session, 61)
    assert qr_text(phone).splitlines() == [f"Session {session.code}", "Étudiant 00123", "Q1 A"]
    page.reload()
    open_results(page)
    assert results_rows(page)[0][:3] == ["00123", "DURAND Élise", "1"]


class _Phone:
    """Un téléphone réduit à ses requêtes HTTP : cookies, formulaires et jeton CSRF."""

    TOKEN_RE = re.compile(r'name="csrfmiddlewaretoken" value="([^"]+)"')
    SLOT_RE = re.compile(r'name="slot" value="([^"]+)"')

    def __init__(self, base: str, code: str) -> None:
        self.page_url = f"{base}/s/{code}/"
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))

    def send(self, url: str, data: dict[str, str] | None = None) -> tuple[int, str]:
        body = urllib.parse.urlencode(data).encode() if data is not None else None
        try:
            with self.opener.open(url, body, timeout=30) as response:
                return response.status, response.read().decode()
        except urllib.error.HTTPError as error:
            return error.code, error.read().decode(errors="replace")

    def form(self) -> dict[str, str]:
        status, html = self.send(self.page_url)
        assert status == 200, html[:500]
        fields = {"csrfmiddlewaretoken": self.TOKEN_RE.search(html).group(1)}  # type: ignore[union-attr]
        if slot := self.SLOT_RE.search(html):
            fields["slot"] = slot.group(1)
        return fields


def _all_at_once[T](actions: list[Callable[[], T]]) -> list[T]:
    """Lance les actions au même instant (une par téléphone) et rend leurs résultats."""
    barrier = threading.Barrier(len(actions))

    def run(action: Callable[[], T]) -> T:
        barrier.wait()
        return action()

    with ThreadPoolExecutor(len(actions)) as pool:
        return list(pool.map(run, actions))


@pytest.mark.spec("CLA-01")
def test_class_mode_serves_a_whole_class_answering_at_the_same_instant(classroom: Classroom):
    """Toute la classe valide son numéro au même instant, puis répond au même instant : aucune
    requête n'échoue (SQLite et le serveur tiennent la charge d'une classe)."""
    students = [(str(1000 + i), f"ÉTUDIANT{i:02d} Test") for i in range(CLASS_SIZE)]
    session = make_live(1, shown=1, seconds=60, students=students)
    base = classroom.phone_url.rstrip("/")
    phones = [_Phone(base, session.code) for _ in students]
    tokens = _all_at_once([phone.form for phone in phones])

    joined = _all_at_once(
        [
            lambda p=p, t=t, n=n: p.send(p.page_url, {**t, "number": n})
            for p, t, (n, _) in zip(phones, tokens, students, strict=True)
        ]
    )
    assert [status for status, _ in joined] == [200] * CLASS_SIZE
    assert Participant.objects.filter(session=session).count() == CLASS_SIZE
    ranks = Participant.objects.filter(session=session).values_list("rank", flat=True)
    assert sorted(ranks) == list(range(CLASS_SIZE))

    session.start(timezone.now())
    forms = _all_at_once([phone.form for phone in phones])
    answered = _all_at_once(
        [
            lambda p=p, f=f: p.send(f"{p.page_url}reponse/", {**f, "choice": "0"})
            for p, f in zip(phones, forms, strict=True)
        ]
    )
    assert [status for status, _ in answered] == [200] * CLASS_SIZE
    assert Answer.objects.filter(participant__session=session).count() == CLASS_SIZE
    assert not any("Traceback" in line for line in classroom.output), "".join(classroom.output)


@pytest.mark.spec("CLA-01")
def test_class_mode_announces_the_address_imposed_by_the_teacher(
    transactional_db, teacher, page: Page
):
    """La détection choisit la mauvaise interface (VPN, WSL) : `make classe ADRESSE=…`."""
    session = make_live(1, shown=1, seconds=60)
    with class_mode("ADRESSE=pc-prof.local") as server:
        port = urllib.parse.urlsplit(server.local_url).port
        assert server.phone_url == f"http://pc-prof.local:{port}/"
        login(page, server.local_url)
        open_board(page, server.local_url, session)
        expect(page.get_by_text(re.compile(r"^Sur votre téléphone, ouvrez "))).to_contain_text(
            f"http://pc-prof.local:{port}/ puis"
        )
        # Les téléphones qui ouvrent cette adresse sont acceptés par le serveur.
        assert _status(port, host="pc-prof.local") == 200
        assert _status(port, host="autre.local") == 400


def _status(port: int | None, *, host: str) -> int:
    """Statut de la page d'accueil demandée au serveur local sous le nom d'hôte `host`."""
    connection = http.client.HTTPConnection("localhost", port, timeout=10)
    try:
        connection.request("GET", "/", headers={"Host": host})
        return connection.getresponse().status
    finally:
        connection.close()
