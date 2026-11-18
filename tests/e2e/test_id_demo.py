"""Incrément D : démonstration complète (DEM-03 à DEM-08) et formules en rouge (CNT-05).

La démonstration complète se lance à part, `qcm-live demo` ou `make demo-complete`, sur une
base séparée recréée à chaque lancement. Son contenu se vérifie ici en préparant la base de
test par la même commande Django (`demo_complete`), puis en la parcourant comme l'enseignant.
"""

from __future__ import annotations

import io
import re
import sqlite3
import zipfile
from datetime import timedelta
from pathlib import Path

import pytest
from django.conf import global_settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone
from playwright.sync_api import Page, expect

from bank.models import Choice, Image, Question, Quiz
from live.models import Answer, Session
from roster.models import StudentGroup
from tests.e2e.amc_ui import confirm_import, expect_recap, recap_items, upload_amc
from tests.e2e.bank_ui import include_box, open_bank, open_quiz, open_quizzes
from tests.e2e.classroom_ui import (
    LAUNCHER,
    REPO,
    announced,
    browser_recorder,
    data_dir,
    env_on_test_db,
    free_port,
)
from tests.e2e.live_ui import (
    board_code,
    csv_rows,
    download_csv,
    fill_launch,
    open_sessions,
    results_rows,
)
from tests.e2e.roster_ui import open_groups
from tests.factories import current_year, make_group

COMPLETE_DIR = REPO / "demo-complet"
FILES = ("fonctions", "probabilites", "python")
PASSWORD_RE = re.compile(r"Mot de passe\s*:\s*(\S+)")
GROUP = "L1 Sciences"
COMPOSED = "Mathématiques : révisions"
GUIDE = REPO / "GUIDE.md"
# Questions de la démonstration légère (demo/qcm-demo.txt) qui relèvent des deux matières.
FROM_LIGHT_DEMO = (
    "Combien de côtés a un hexagone ?",
    "Combien font 7 fois 8 ?",
    "Parmi ces nombres, lesquels sont pairs ?",
    "Lesquelles de ces fractions sont égales à",
    "Lesquels de ces nombres ce programme Python affiche-t-il ?",
    "Quelle figure est dessinée ?",
)


def previous_year() -> str:
    first = int(current_year()[:4]) - 1
    return f"{first}-{first + 1}"


def title_of(name: str) -> str:
    text = next((COMPLETE_DIR / name).glob("*.txt")).read_text(encoding="utf-8")
    match = re.search(r"^Title:\s*(.+)$", text, re.M)
    assert match, name
    return match.group(1).strip()


def folder_archive(folder: Path) -> bytes:
    """Le dossier d'un fichier de démonstration mis en ZIP, comme l'enseignant le ferait."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(folder).as_posix())
    return buffer.getvalue()


def build_demo() -> str:
    """Prépare la base de test par la commande de la démonstration complète ; rend le mot de
    passe affiché."""
    out = io.StringIO()
    call_command("demo_complete", stdout=out)
    match = PASSWORD_RE.search(out.getvalue())
    assert match, out.getvalue()
    return match.group(1)


def log_in(page: Page, base_url: str, password: str) -> None:
    page.goto(f"{base_url}/prof/")
    page.get_by_label("Identifiant").fill("demo")
    page.get_by_label("Mot de passe").fill(password)
    page.get_by_role("button", name="Se connecter").click()


@pytest.fixture
def _production_hasher(settings) -> None:
    """La commande lancée à part hache le mot de passe comme en production : le serveur qui le
    vérifie est le sien, mais la base de test doit rester lisible."""
    settings.PASSWORD_HASHERS = global_settings.PASSWORD_HASHERS


# --- DEM-03 : une commande à part, sur une base séparée -------------------------------------


@pytest.mark.spec("DEM-03")
def test_qcm_live_demo_never_touches_the_teacher_database(
    tmp_path: Path, page: Page, transactional_db, _production_hasher
):
    # La base de l'enseignant : un groupe à lui, aucune session.
    make_group("TD1", [("00123", "DURAND Élise")])
    home = tmp_path / "home"
    data = data_dir(home / ".local" / "share" / "qcm-live")
    browser, opened = browser_recorder(tmp_path)
    env = env_on_test_db(HOME=str(home), QCM_DATA_DIR=str(data), BROWSER=browser)
    demo_db = data / "demo.sqlite3"

    passwords = []
    for launch in range(2):
        port = free_port()
        with announced([*LAUNCHER, "demo", "--port", str(port)], port=port, env=env) as server:
            output = "".join(server.output)
            match = PASSWORD_RE.search(output)
            assert match, output
            assert "Identifiant : demo" in output, output
            passwords.append(match.group(1))
            assert "Sauvegarde" not in output, output
            log_in(page, server.local_url, passwords[-1])
            expect(page.get_by_role("heading", name="Espace enseignant")).to_be_visible()
            open_groups(page)
            main = page.get_by_role("main")
            expect(main.get_by_role("row").filter(has_text=GROUP)).to_have_count(2)
            expect(main).not_to_contain_text("TD1")
            expect(main).not_to_contain_text("Modifié pendant la démonstration")
            assert opened.read_text(encoding="utf-8") == f"{server.local_url}/prof/"
        assert demo_db.is_file()
        if launch == 0:  # ce qu'on y change ne reste pas
            with sqlite3.connect(demo_db) as db:
                db.execute(
                    "UPDATE roster_studentgroup SET name = 'Modifié pendant la démonstration'"
                )
            page.context.clear_cookies()

    assert passwords[0] != passwords[1]
    # La base de l'enseignant n'a pas bougé, et rien n'a été sauvegardé.
    assert list(StudentGroup.objects.values_list("name", flat=True)) == ["TD1"]
    assert not Session.objects.exists() and not Quiz.objects.exists()
    assert not get_user_model().objects.filter(username="demo").exists()
    assert not (home / "QCM Live").exists()


@pytest.mark.spec("DEM-03")
def test_make_demo_complete_uses_its_own_database(
    tmp_path: Path, page: Page, transactional_db, _production_hasher
):
    demo_db = tmp_path / "demo.sqlite3"
    port = free_port()
    command = [
        "make",
        "--no-print-directory",
        "demo-complete",
        "ENV_FILE=.env.test",
        f"PORT={port}",
        f"DEMO_DB={demo_db}",
    ]
    with announced(command, port=port, env=env_on_test_db()) as server:
        output = "".join(server.output)
        match = PASSWORD_RE.search(output)
        assert match, output
        log_in(page, server.local_url, match.group(1))
        open_quizzes(page)
        expect(page.get_by_role("main").get_by_role("link", name=COMPOSED)).to_be_visible()
    assert demo_db.is_file()
    assert not Quiz.objects.exists() and not StudentGroup.objects.exists()


@pytest.mark.spec("DEM-03")
def test_preparing_the_demo_refuses_a_database_with_data(transactional_db):
    from django.core.management.base import CommandError

    make_group("TD1", [("00123", "DURAND Élise")])
    with pytest.raises(CommandError, match="déjà"):
        call_command("demo_complete", stdout=io.StringIO())
    assert not Quiz.objects.exists() and not Session.objects.exists()


@pytest.mark.spec("DEM-03")
def test_install_still_offers_the_light_demo_only(transactional_db):
    # Ce que l'installation lance (INS-01) : le QCM et le groupe légers, aucune session.
    call_command("demo", "--sans-compte", stdout=io.StringIO())
    assert Quiz.objects.count() == 1 and StudentGroup.objects.count() == 1
    assert not Session.objects.exists()


# --- DEM-04 : trois fichiers, deux matières ----------------------------------------------


@pytest.mark.spec("DEM-04")
@pytest.mark.parametrize("name", FILES)
def test_each_demo_file_imports_as_an_archive_without_skipped_question(
    teacher_page: Page, name: str
):
    page = teacher_page
    folder = COMPLETE_DIR / name
    assert len(list(folder.glob("*.txt"))) == 1
    upload_amc(page, folder_archive(folder), name=f"{name}.zip")
    expect_recap(page)
    expect(recap_items(page, "Questions écartées")).to_have_count(0)
    confirm_import(page)
    expect(page.get_by_role("heading", name=title_of(name), level=1)).to_be_visible()

    quiz = Quiz.objects.get()
    questions = quiz.questions.all()
    assert 20 <= questions.count() <= 30, questions.count()
    assert questions.filter(kind=Question.Kind.SIMPLE).exists()
    assert questions.filter(kind=Question.Kind.MULTIPLE).exists()
    assert questions.exclude(scoring="").exists()  # barème particulier
    assert questions.filter(none_of_these=True).exists()
    assert questions.exclude(amc_group="").exists()
    texts = [q.text for q in questions]
    texts += [c.text for c in Choice.objects.filter(question__in=questions)]
    assert sum(text.count("$") // 2 for text in texts) >= 3  # plusieurs formules
    assert any("\\begin{verbatim}" in t or "\\texttt{" in t for t in texts)  # du code
    assert Image.objects.exists()

    # Tout s'affiche : formules rendues par KaTeX, sans erreur ; code ; images chargées.
    expect(page.locator(".katex").nth(2)).to_be_attached()
    expect(page.locator(".math-error")).to_have_count(0)
    expect(page.locator(".code-block, code").first).to_be_visible()
    for image in Image.objects.all():
        shown = page.locator(f'img[src$="/images/{image.name}"]').first
        expect(shown).to_be_visible()
        assert shown.evaluate("img => img.naturalWidth") > 0


@pytest.mark.spec("DEM-04")
def test_demo_files_cover_two_subjects_and_reuse_the_light_demo():
    titles = sorted(title_of(name) for name in FILES)
    subjects = [title.split(" : ")[0] for title in titles]
    assert subjects == ["Informatique", "Mathématiques", "Mathématiques"], titles
    texts = "".join(
        next((COMPLETE_DIR / name).glob("*.txt")).read_text(encoding="utf-8") for name in FILES
    )
    for stem in FROM_LIGHT_DEMO:
        assert stem in texts, stem


@pytest.mark.spec("DEM-04")
def test_complete_demo_imports_the_three_files(teacher_page: Page):
    build_demo()
    open_quizzes(page := teacher_page)
    main = page.get_by_role("main")
    for name in FILES:
        expect(main.get_by_role("link", name=title_of(name), exact=True)).to_be_visible()
    assert Quiz.objects.filter(source_sha256="").count() == 1  # le QCM composé seul


# --- DEM-05 : deux groupes de même nom -----------------------------------------------------


@pytest.mark.spec("DEM-05")
def test_two_groups_with_the_same_name_and_different_years(teacher_page: Page):
    page = teacher_page
    build_demo()
    open_groups(page)
    rows = page.get_by_role("main").get_by_role("row").filter(has_text=GROUP)
    expect(rows).to_have_count(2)
    expect(rows.filter(has_text=current_year())).to_contain_text("70")
    expect(rows.filter(has_text=previous_year())).to_contain_text("24")
    group = StudentGroup.objects.get(name=GROUP, year=current_year())
    assert group.students.count() == 70
    assert StudentGroup.objects.get(name=GROUP, year=previous_year()).students.count() == 24


# --- DEM-06 : une session passée ------------------------------------------------------------


def plain_texts(questions) -> list[str]:
    """Énoncés sans formule ni code : la case « Inclure » les nomme tels quels."""
    texts = [q.text for q in questions if "$" not in q.text and "\\" not in q.text]
    assert texts, "aucun énoncé sans formule ni code"
    return texts


def past_session() -> Session:
    return Session.objects.get(group_name=GROUP)


@pytest.mark.spec("DEM-06")
def test_past_session_has_results_csv_and_grades_from_the_start(teacher_page: Page):
    page = teacher_page
    build_demo()
    session = past_session()
    title = title_of("fonctions")
    assert (session.quiz_title, session.group_year) == (title, current_year())
    assert session.started_at is not None
    assert session.created_at < timezone.now() - timedelta(days=6)
    assert session.state(timezone.now()).phase == "ended"

    open_sessions(page)
    row = page.get_by_role("main").get_by_role("row").filter(has_text=title)
    expect(row).to_contain_text("Terminée")
    row.get_by_role("link", name="Résultats").click()
    expect(page.get_by_role("heading", name="Résultats", level=1)).to_be_visible()
    # Notes masquées à l'ouverture (RES-04), puis affichées.
    expect(page.get_by_role("table", name="Résultats")).to_be_hidden()
    rows = results_rows(page)
    assert len(rows) == 70
    grades = [row[5] for row in rows]
    present = [g for g in grades if re.fullmatch(r"-?\d+(,\d+)?", g)]
    assert 55 <= len(present) < 70, grades  # quelques absents
    assert len(set(present)) >= 8, present  # des notes variées

    _, content = download_csv(page)
    lines = csv_rows(content)
    assert len(lines) == 71
    assert "note /20" in lines[0]
    assert Answer.objects.filter(participant__session=session).count() > 500


@pytest.mark.spec("DEM-06")
def test_past_session_results_are_the_same_at_each_launch(transactional_db):
    build_demo()
    first = [(r.list_number, r.total) for r in past_session().results()]
    for model in (Session, Quiz, Question, StudentGroup, Image):
        model.objects.all().delete()
    build_demo()
    assert [(r.list_number, r.total) for r in past_session().results()] == first


@pytest.mark.spec("DEM-06")
def test_past_questions_are_marked_already_posed(teacher_page: Page):
    page = teacher_page
    build_demo()
    label = f"{GROUP} — {current_year()}"

    # À la composition du QCM de révisions.
    open_quiz(page, COMPOSED)
    page.get_by_role("link", name="Modifier le QCM").click()
    page.get_by_label("Marquer les questions déjà posées au groupe").select_option(label=label)
    page.get_by_role("button", name="Marquer").click()
    # « Marquer » parcourt toute la banque : les questions du fichier posé, et elles seules.
    posed_file = Quiz.objects.get(title=title_of("fonctions")).questions.all()
    rows = page.get_by_role("row")
    expect(rows.filter(has_text="posée à")).to_have_count(posed_file.count())
    for text in plain_texts(posed_file)[:3]:
        expect(rows.filter(has=include_box(page, text))).to_contain_text("posée à")
    composed = Quiz.objects.get(title=COMPOSED).questions.all()
    posed = composed.filter(pk__in=posed_file).count()
    assert 0 < posed < composed.count()

    # Au lancement : la confirmation ; avec le groupe de l'an dernier, aucune.
    open_sessions(page)
    page.get_by_role("link", name="Lancer une session").click()
    fill_launch(page, COMPOSED, label, 2, 30)
    items = page.get_by_role("list", name="Questions déjà posées").get_by_role("listitem")
    expect(items).to_have_count(posed)
    page.get_by_role("button", name="Revenir").click()
    page.get_by_label("Groupe", exact=True).select_option(label=f"{GROUP} — {previous_year()}")
    page.get_by_role("button", name="Lancer").click()
    assert Session.objects.filter(code=board_code(page), group_year=previous_year()).exists()


# --- DEM-07 : QCM composé, nouvelle version ---------------------------------------------------


@pytest.mark.spec("DEM-07")
def test_composed_quiz_takes_questions_from_two_files(teacher_page: Page):
    page = teacher_page
    build_demo()
    composed = Quiz.objects.get(title=COMPOSED)
    assert composed.source_sha256 == ""  # composé, pas importé
    sources = []
    for name in ("fonctions", "probabilites"):
        quiz = Quiz.objects.get(title=title_of(name))
        shared = set(composed.questions.all()) & set(quiz.questions.all())
        sources.append(len(shared))
    assert all(sources), sources
    assert sum(sources) == composed.questions.count()

    open_quiz(page, COMPOSED)
    page.get_by_role("link", name="Modifier le QCM").click()
    for text in plain_texts(composed.questions.all())[:3]:
        expect(include_box(page, text)).to_be_checked()


@pytest.mark.spec("DEM-07")
def test_a_posed_question_has_a_new_version(teacher_page: Page):
    page = teacher_page
    build_demo()
    session = past_session()
    revised = Question.objects.filter(previous__isnull=False, hidden=False)
    assert revised.count() == 1
    question = revised.get()
    assert question.previous in session.source_questions.all()
    assert question.content() != question.previous.content()
    # La nouvelle version est dans le QCM du fichier ; la session garde l'ancienne.
    assert question in Quiz.objects.get(title=title_of("fonctions")).questions.all()
    assert question.previous.text in [q["text"] for q in session.questions]

    open_bank(page)
    expect(page.get_by_text("Versions précédentes (1)")).to_have_count(1)


# --- DEM-08 : le parcours de 10 minutes du guide -------------------------------------------


def walk_section() -> str:
    text = GUIDE.read_text(encoding="utf-8")
    match = re.search(r"^## [^\n]*[Dd]émonstration[^\n]*\n(.*?)(?=^## )", text, re.M | re.S)
    assert match, "GUIDE.md : section de la démonstration introuvable"
    return match.group(0)


@pytest.mark.spec("DEM-08")
def test_guide_walk_starts_from_the_command_and_lasts_ten_minutes():
    section = walk_section()
    assert "qcm-live demo" in section
    assert "10 minutes" in section
    assert "demo.sqlite3" in section or "base à part" in section
    steps = re.findall(r"^\d+\. ", section, re.M)
    assert 5 <= len(steps) <= 12, steps


@pytest.mark.spec("DEM-08")
def test_every_label_quoted_in_the_walk_exists_in_the_application(teacher_page: Page):
    """Le parcours cite des boutons et des liens : chacun doit se trouver sur une page que le
    parcours visite."""
    page = teacher_page
    build_demo()
    seen: list[str] = []

    def collect() -> None:
        seen.append(page.locator("body").inner_text())
        seen.extend(page.locator("option").all_inner_texts())
        seen.extend(page.locator("summary").all_inner_texts())

    label = f"{GROUP} — {current_year()}"
    page.goto(page.url)
    collect()
    open_quizzes(page)
    collect()
    open_quiz(page, COMPOSED)
    collect()
    page.get_by_role("link", name="Modifier le QCM").click()
    page.get_by_label("Marquer les questions déjà posées au groupe").select_option(label=label)
    page.get_by_role("button", name="Marquer").click()
    collect()
    open_bank(page)
    collect()
    open_groups(page)
    collect()
    open_sessions(page)
    collect()
    page.get_by_role("main").get_by_role("link", name="Résultats").first.click()
    collect()
    open_sessions(page)
    page.get_by_role("link", name="Lancer une session").click()
    collect()
    fill_launch(page, COMPOSED, label, 2, 30)
    collect()
    page.get_by_role("button", name="Lancer quand même").click()
    collect()

    pages = "\n".join(seen)
    quoted = re.findall(r"« ([^»]+?) »", walk_section())
    assert len(quoted) >= 8, quoted
    absent = [text for text in quoted if text not in pages]
    assert absent == [], absent


# --- CNT-05 : formules en rouge, vues dès l'import -------------------------------------------

UNKNOWN = r"\SI{3}{\metre\per\second}"  # paquet siunitx, que KaTeX ne connaît pas
MACRO = r"\vect{u}"  # une macro personnelle du fichier LaTeX du professeur


@pytest.mark.spec("CNT-05")
def test_formula_refused_by_katex_shows_in_red_on_the_import_recap(teacher_page: Page):
    page = teacher_page
    amc = (
        "Title: Formules\n\n"
        f"* Une vitesse de [[${UNKNOWN}$]] : combien font [[$x^2$]] si x = 3 ?\n"
        "+ 9\n- 6\n\n"
        f"* Que vaut la norme de [[${MACRO}$]] ?\n"
        "+ 1\n- 0\n"
    )
    upload_amc(page, amc, name="formules.txt")
    expect_recap(page)
    errors = page.locator(".math-error")
    expect(errors).to_have_count(2)
    expect(errors.nth(0)).to_have_text(UNKNOWN)
    expect(errors.nth(1)).to_have_text(MACRO)
    expect(errors.nth(0)).to_have_attribute("title", re.compile(r"\S"))
    color = errors.nth(0).evaluate("e => getComputedStyle(e).textDecorationColor")
    red, green, blue = map(int, re.findall(r"\d+", color)[:3])
    assert red > green + 80 and red > blue + 80, color
    expect(page.locator(".katex").first).to_be_attached()  # x^2, elle, est rendue
    assert not Quiz.objects.exists()  # rien d'importé : c'est avant de confirmer
    expect(recap_items(page, "Questions écartées")).to_have_count(0)


@pytest.mark.spec("CNT-05")
def test_guide_explains_formulas_shown_in_red():
    text = GUIDE.read_text(encoding="utf-8")
    match = re.search(r"^#+ Formules qui s'affichent en rouge\n(.*?)(?=^#+ |\Z)", text, re.M | re.S)
    assert match, "GUIDE.md : section « Formules qui s'affichent en rouge » introuvable"
    section = match.group(1)
    for word in ("KaTeX", "macro", "paquet", "récapitulatif", "survol"):
        assert word in section, word
