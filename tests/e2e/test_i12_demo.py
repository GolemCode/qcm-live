"""Incrément 12 : fichier de démonstration (DEM-01) et `make demo` (DEM-02).

`make demo` est lancé comme par l'enseignant, dans un processus à part, sur la base de test
(`DJANGO_DB_PATH`) et avec `.env.test` : le test ne charge jamais la vraie clé (`.env`).
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest
from django.conf import global_settings, settings
from playwright.sync_api import Page, expect

from bank.models import Choice, Question, Quiz
from roster.models import StudentGroup
from tests.e2e.amc_ui import NONE_OF_THESE, confirm_import, expect_recap, recap_items, upload_amc
from tests.e2e.bank_ui import open_quizzes, quiz_question_items
from tests.e2e.live_setup import expect_slot, started
from tests.e2e.live_ui import (
    LIVE_MS,
    choose,
    csv_rows,
    download_csv,
    open_results,
    phone_choices,
    results_rows,
    save_status,
)
from tests.factories import jump_to, make_group, make_session

REPO = Path(__file__).resolve().parents[2]
DEMO_FILE = REPO / "demo" / "qcm-demo.txt"
PASSWORD_RE = re.compile(r"Mot de passe\s*:\s*(\S+)")
SECONDS = 30


def demo_title() -> str:
    match = re.search(r"^Title:\s*(.+)$", DEMO_FILE.read_text(encoding="utf-8"), re.MULTILINE)
    assert match, "le fichier de démonstration doit porter un titre"
    return match.group(1).strip()


@pytest.mark.spec("DEM-01")
def test_demo_file_imports_without_skipped_question_and_runs_a_session(
    teacher_page: Page, live_server, new_phone
):
    page = teacher_page
    upload_amc(page, DEMO_FILE.read_bytes(), name=DEMO_FILE.name)
    expect_recap(page)
    expect(recap_items(page, "Questions écartées")).to_have_count(0)
    confirm_import(page)
    expect(page.get_by_role("heading", name=demo_title(), level=1)).to_be_visible()

    # Ce que le fichier couvre en I12.
    quiz = Quiz.objects.get()
    questions = quiz.questions.all()
    expect(quiz_question_items(page)).to_have_count(questions.count())
    assert {q.kind for q in questions} == {Question.Kind.SIMPLE, Question.Kind.MULTIPLE}
    assert questions.filter(kind=Question.Kind.SIMPLE).exclude(scoring="").exists()
    assert questions.filter(kind=Question.Kind.MULTIPLE).exclude(scoring="haut=2").exists()
    assert Choice.objects.filter(question__in=questions, points__isnull=False).exists()
    assert questions.filter(none_of_these=True).exists()
    assert questions.filter(ordered=True).exists()
    assert questions.exclude(amc_group="").exists()
    assert questions.filter(text__contains="\n\n").exists()  # au moins un paragraphe

    # Une session complète, jusqu'aux résultats et au CSV.
    group = make_group("Démo", [("00123", "DURAND Élise")])
    session = make_session(quiz, group, shown=1, seconds=SECONDS)
    (phone,) = started(page, live_server.url, new_phone, session, ["00123"])
    for slot in range(questions.count()):
        jump_to(session, slot * SECONDS + 1)
        expect_slot(phone, slot)
        choices = phone_choices(phone)
        choose(phone, NONE_OF_THESE if NONE_OF_THESE in choices else choices[0])
        expect(save_status(phone)).to_have_text("Réponse enregistrée")
    jump_to(session, questions.count() * SECONDS + 1)
    expect(page.get_by_role("main")).to_contain_text("Session terminée", timeout=LIVE_MS)
    open_results(page)
    (row,) = results_rows(page)
    assert row[:2] == ["00123", "DURAND Élise"]
    _, content = download_csv(page)
    rows = csv_rows(content)
    assert len(rows) == 2
    assert "-" not in rows[1][5::2]  # une lettre par question : chacune a reçu une réponse


# --- DEM-02 : make demo ---------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _fast_password_hasher(settings) -> None:
    """Remplace celui de tests/conftest.py : `make demo`, lancé à part, hache le mot de passe
    comme en production, et le serveur de test doit savoir le vérifier."""
    settings.PASSWORD_HASHERS = global_settings.PASSWORD_HASHERS


def make_demo() -> str:
    """Lance `make demo` sur la base de test et renvoie le mot de passe affiché."""
    env = {**os.environ, "DJANGO_DB_PATH": str(settings.DATABASES["default"]["NAME"])}
    result = subprocess.run(
        ["make", "--no-print-directory", "demo", "ENV_FILE=.env.test"],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    output = result.stdout + result.stderr
    assert result.returncode == 0, output
    assert "--env-file .env.test" in output, output
    match = PASSWORD_RE.search(output)
    assert match, output
    return match.group(1)


def log_in(page: Page, base_url: str, password: str) -> None:
    page.goto(f"{base_url}/prof/")
    page.get_by_label("Identifiant").fill("demo")
    page.get_by_label("Mot de passe").fill(password)
    page.get_by_role("button", name="Se connecter").click()


@pytest.mark.spec("DEM-02")
def test_make_demo_prepares_account_group_and_quiz(page: Page, live_server, transactional_db):
    first = make_demo()
    log_in(page, live_server.url, first)
    expect(page.get_by_role("heading", name="Espace enseignant")).to_be_visible()
    open_quizzes(page)
    expect(page.get_by_role("link", name=demo_title(), exact=True)).to_be_visible()
    page.get_by_role("navigation").get_by_role("link", name="Groupes").click()
    expect(page.get_by_role("main")).to_contain_text("Démo")
    assert (Quiz.objects.count(), StudentGroup.objects.count()) == (1, 1)
    assert StudentGroup.objects.get().students.count() >= 2

    # Relancée : mêmes groupe et QCM, nouveau mot de passe ; l'ancien ne sert plus.
    page.context.clear_cookies()
    second = make_demo()
    assert second != first
    assert (Quiz.objects.count(), StudentGroup.objects.count()) == (1, 1)
    log_in(page, live_server.url, first)
    expect(page.get_by_role("alert")).to_be_visible()
    log_in(page, live_server.url, second)
    expect(page.get_by_role("heading", name="Espace enseignant")).to_be_visible()
