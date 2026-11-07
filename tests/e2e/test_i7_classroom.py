"""Incrément 7 : mode classe (CLA-01).

Ces tests ne passent pas par le serveur de test de Django (`live_server`) : ils lancent
l'application comme l'enseignant en classe, avec `make classe`, dans un processus à part.
Le serveur lit la base de test, où les fabriques créent les préconditions.

- Le PC de l'enseignant ouvre l'application en local (`localhost`).
- Les téléphones ouvrent l'adresse projetée au tableau, celle du PC sur le réseau local.
- Le fichier `.env` demande le mode debug (`DJANGO_DEBUG=1`) : le mode classe doit l'ignorer.
"""

from __future__ import annotations

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
from collections.abc import Iterator
from dataclasses import dataclass
from http.cookiejar import CookieJar
from pathlib import Path

import pytest
from django.conf import global_settings, settings
from django.utils import timezone
from playwright.sync_api import Page, expect

from live.models import Answer, Participant, Session
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


@pytest.fixture
def classroom(transactional_db) -> Iterator[Classroom]:
    """`make classe` lancé sur un port libre, sur la base de test : comme en classe."""
    port = _free_port()
    env = {**os.environ, "DJANGO_DB_PATH": str(settings.DATABASES["default"]["NAME"])}
    env["DJANGO_DEBUG"] = "1"  # comme dans le .env de développement
    process = subprocess.Popen(
        ["make", "--no-print-directory", "classe", f"PORT={port}"],
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
        yield Classroom(f"http://localhost:{port}", phone_url, output)
    finally:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=10)


@pytest.fixture
def class_teacher(transactional_db, django_user_model, settings):
    """Compte enseignant haché comme en production : le serveur du mode classe ne connaît
    pas le hachage MD5 rapide réservé aux tests."""
    settings.PASSWORD_HASHERS = global_settings.PASSWORD_HASHERS
    return django_user_model.objects.create_user(TEACHER_USERNAME, password=TEACHER_PASSWORD)


def _host(url: str) -> str:
    return urllib.parse.urlsplit(url).hostname or ""


@pytest.mark.spec("CLA-01")
def test_class_mode_end_to_end_from_phones_on_local_network(
    classroom: Classroom, class_teacher, page: Page, new_phone
):
    session = make_live(1, shown=1, seconds=60)

    # L'adresse annoncée dans le terminal est celle du PC sur le réseau local.
    host = _host(classroom.phone_url)
    assert host not in {"localhost", ""} and not host.startswith("127."), classroom.phone_url
    assert classroom.phone_url == f"{classroom.phone_url.rstrip('/')}/"

    # L'enseignant ouvre l'application en local : le tableau projette pourtant l'adresse
    # du réseau local, la seule que les téléphones peuvent joindre.
    login(page, classroom.local_url)
    expect(page.get_by_role("heading", name="Espace enseignant")).to_be_visible()
    open_board(page, classroom.local_url, session)
    hint = page.get_by_text(re.compile(r"^Sur votre téléphone, ouvrez "))
    expect(hint).to_contain_text(classroom.phone_url)
    projected = re.search(r"http://\S+", hint.inner_text())
    assert projected and projected.group(0) == classroom.phone_url

    # Serveur de production local, sans mode debug.
    response = page.request.get(classroom.local_url + "/")
    assert "waitress" in response.headers.get("server", ""), response.headers
    missing = page.request.get(classroom.local_url + "/page-inexistante/")
    assert missing.status == 404
    assert "DEBUG = True" not in missing.text() and "URLconf" not in missing.text()
    assert "Page introuvable" in missing.text()  # en français, comme toute l'interface
    # La politique de sécurité du contenu reste en place.
    assert "default-src 'self'" in response.headers.get("content-security-policy", "")

    # Un téléphone ouvre l'adresse projetée, telle qu'affichée.
    phone = new_phone()
    base = projected.group(0).rstrip("/")
    join(phone, base, session.code, "00123")
    expect(identity(phone)).to_have_text("Vous êtes DURAND Élise")
    stylesheet = phone.locator("link[rel=stylesheet]").first.get_attribute("href")
    assert stylesheet
    css = phone.request.get(urllib.parse.urljoin(base + "/", stylesheet))
    assert css.status == 200 and "text/css" in css.headers["content-type"]

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

    def _send(self, url: str, data: dict[str, str] | None = None) -> tuple[int, str]:
        body = urllib.parse.urlencode(data).encode() if data is not None else None
        try:
            with self.opener.open(url, body, timeout=30) as response:
                return response.status, response.read().decode()
        except urllib.error.HTTPError as error:
            return error.code, error.read().decode(errors="replace")

    def form(self) -> dict[str, str]:
        status, html = self._send(self.page_url)
        assert status == 200, html[:500]
        fields = {"csrfmiddlewaretoken": self.TOKEN_RE.search(html).group(1)}  # type: ignore[union-attr]
        if slot := self.SLOT_RE.search(html):
            fields["slot"] = slot.group(1)
        return fields

    def post(self, url: str, data: dict[str, str]) -> tuple[int, str]:
        return self._send(url, data)


def _all_at_once(actions) -> list:
    """Lance les actions au même instant (une par téléphone) et rend leurs résultats."""
    barrier = threading.Barrier(len(actions))
    results: list = [None] * len(actions)

    def run(i: int) -> None:
        barrier.wait()
        try:
            results[i] = actions[i]()
        except Exception as error:
            results[i] = error

    threads = [threading.Thread(target=run, args=(i,)) for i in range(len(actions))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return results


@pytest.mark.spec("CLA-01")
def test_class_mode_serves_a_whole_class_answering_at_the_same_instant(classroom: Classroom):
    """Toute la classe valide son numéro au même instant, puis répond au même instant : aucune
    requête n'échoue (SQLite et le serveur tiennent la charge d'une classe)."""
    students = [(str(1000 + i), f"ÉTUDIANT{i:02d} Test") for i in range(CLASS_SIZE)]
    session = make_live(1, shown=1, seconds=60, students=students)
    base = classroom.phone_url.rstrip("/")
    phones = [_Phone(base, session.code) for _ in students]
    tokens = [phone.form() for phone in phones]

    joined = _all_at_once(
        [
            lambda p=p, t=t, n=n: p.post(p.page_url, {**t, "number": n})
            for p, t, (n, _) in zip(phones, tokens, students, strict=True)
        ]
    )
    assert [r if isinstance(r, Exception) else r[0] for r in joined] == [200] * CLASS_SIZE
    assert Participant.objects.filter(session=session).count() == CLASS_SIZE
    ranks = Participant.objects.filter(session=session).values_list("rank", flat=True)
    assert sorted(ranks) == list(range(CLASS_SIZE))

    Session.objects.get(pk=session.pk).start(timezone.now())
    forms = [phone.form() for phone in phones]
    answered = _all_at_once(
        [
            lambda p=p, f=f: p.post(f"{p.page_url}reponse/", {**f, "choice": "0"})
            for p, f in zip(phones, forms, strict=True)
        ]
    )
    assert [r if isinstance(r, Exception) else r[0] for r in answered] == [200] * CLASS_SIZE, [
        r if isinstance(r, Exception) else r[1][:200] for r in answered if r[0] != 200
    ]
    assert Answer.objects.filter(participant__session=session).count() == CLASS_SIZE
    assert not any("Traceback" in line for line in classroom.output), "".join(classroom.output)
