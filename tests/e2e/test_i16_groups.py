"""Incrément 16 : année des groupes (GRP-04) et données d'avant I16 (MIG-02)."""

from datetime import datetime

import pytest
from django.utils import timezone
from playwright.sync_api import Page, expect

from roster.models import StudentGroup
from tests.e2e.live_setup import STUDENTS
from tests.e2e.live_ui import board_code, fill_launch, leave_board, open_sessions
from tests.e2e.roster_ui import open_groups, student_rows, submit_group
from tests.factories import current_year, make_group, make_question, make_quiz
from tests.migrations import leaves, migrate

CSV = "00123;DURAND Élise\n42;MARTIN Léo\n".encode()
YEAR_ERROR = "Année au format 2025-2026 : deux années qui se suivent."
SAME_YEAR = "Un groupe porte déjà ce nom cette année-là."


def row(page: Page, text: str):
    return page.get_by_role("row").filter(has_text=text)


# --- GRP-04 : l'année du groupe -------------------------------------------------------------


@pytest.mark.spec("GRP-04")
def test_group_year_is_checked_and_shown(teacher_page: Page):
    page = teacher_page
    open_groups(page)
    page.get_by_role("link", name="Importer un groupe").click()
    expect(page.get_by_label("Année")).to_have_value(current_year())  # prérempli

    for wrong in ["2025", "2025-2027", "2026-2025", "25-26", "2025/2026", "2025-2026-2027"]:
        submit_group(page, "ITI4", CSV, wrong)
        expect(page.get_by_role("alert")).to_contain_text(YEAR_ERROR)
    submit_group(page, "ITI4", CSV, "")
    expect(page.get_by_role("alert")).to_contain_text("Année")
    assert not StudentGroup.objects.exists()

    submit_group(page, "ITI4", CSV, "2025-2026")  # tout juste accepté
    expect(page.get_by_role("heading", name="ITI4", level=1)).to_be_visible()
    expect(page.get_by_role("main")).to_contain_text("2025-2026")
    expect(student_rows(page)).to_have_count(2)

    # Même nom, même année : refusé ; même nom, autre année : un autre groupe.
    open_groups(page)
    page.get_by_role("link", name="Importer un groupe").click()
    submit_group(page, "ITI4", CSV, "2025-2026")
    expect(page.get_by_role("alert")).to_contain_text(SAME_YEAR)
    submit_group(page, "ITI4", CSV, "2026-2027")
    expect(page.get_by_role("heading", name="ITI4", level=1)).to_be_visible()
    expect(page.get_by_role("main")).to_contain_text("2026-2027")

    open_groups(page)
    expect(row(page, "ITI4")).to_have_count(2)
    expect(row(page, "2025-2026")).to_contain_text("ITI4")
    expect(row(page, "2026-2027")).to_contain_text("ITI4")
    assert sorted(StudentGroup.objects.values_list("name", "year")) == [
        ("ITI4", "2025-2026"),
        ("ITI4", "2026-2027"),
    ]


@pytest.mark.spec("GRP-04")
def test_year_follows_the_group_into_its_sessions(teacher_page: Page, live_server):
    """Choix au lancement, tableau en attente, liste des sessions, résultats ; l'année de la
    session reste celle du lancement, même si le groupe disparaît."""
    page = teacher_page
    make_quiz("Contrôle", [make_question("Q1")])
    old = make_group("ITI4", STUDENTS, "2025-2026")
    make_group("ITI4", STUDENTS, "2026-2027")

    open_sessions(page)
    page.get_by_role("link", name="Lancer une session").click()
    expect(page.get_by_label("Groupe", exact=True).locator("option")).to_have_text(
        ["ITI4 — 2025-2026", "ITI4 — 2026-2027"]
    )
    fill_launch(page, "Contrôle", "ITI4 — 2025-2026", 1, 30)
    code = board_code(page)
    expect(page.get_by_role("main")).to_contain_text("Groupe ITI4 — 2025-2026")

    old.delete()
    leave_board(page)
    expect(row(page, code)).to_contain_text("ITI4 — 2025-2026")
    page.goto(f"{live_server.url}/prof/sessions/{code}/resultats/")
    expect(page.get_by_role("main")).to_contain_text("Groupe ITI4 — 2025-2026")


# --- MIG-02 : groupes et sessions d'avant I16 ----------------------------------------------

BEFORE = [("roster", "0002_student_list_number"), ("live", "0007_session_source_questions")]
ROSTER = [{"list_number": 1, "student_number": "00123", "name": "DURAND Élise"}]
CONTENT = {
    "questions": [
        {
            "text": "Capitale de la France ?",
            "multiple": False,
            "ordered": False,
            "scoring": "",
            "choices": [
                {"text": "Paris", "correct": True, "points": None, "none": False},
                {"text": "Lyon", "correct": False, "points": None, "none": False},
            ],
        }
    ]
}


@pytest.fixture
def old_apps(transactional_db):
    """Base ramenée à l'état d'avant I16 ; remise à jour à la fin, même en cas d'échec."""
    apps = migrate(BEFORE)
    yield apps
    migrate(leaves())


def at(year: int, month: int, day: int) -> datetime:
    return timezone.make_aware(datetime(year, month, day, 12))


def make_old_data(apps) -> None:
    """Deux groupes, dont un sans session, et des sessions lancées de part et d'autre d'une
    rentrée, dont une d'un groupe supprimé depuis."""
    StudentGroup = apps.get_model("roster", "StudentGroup")
    for name in ("ITI4", "TD neuf"):
        group = StudentGroup.objects.create(name=name)
        group.students.create(list_number=1, student_number="00123", name="DURAND Élise")
    Session = apps.get_model("live", "Session")
    common = {"quiz_title": "Contrôle", "content": CONTENT, "roster": ROSTER}
    common |= {"n_questions": 1, "shown": 1, "seconds": 30}
    for code, group, launched, started in [
        ("222222", "ITI4", at(2026, 10, 5), True),
        ("111111", "ITI4", at(2025, 10, 1), True),  # la première : l'année du groupe
        ("333333", "ITI4", at(2026, 8, 31), False),  # fin août : année précédente
        ("444444", "TD supprimé", at(2026, 9, 1), True),  # rentrée : nouvelle année
    ]:
        session = Session.objects.create(code=code, group_name=group, **common)
        Session.objects.filter(pk=session.pk).update(
            created_at=launched, started_at=launched if started else None
        )


@pytest.mark.spec("MIG-02")
def test_groups_and_sessions_from_before_i16(teacher_page: Page, old_apps):
    page = teacher_page
    make_old_data(old_apps)

    migrate(leaves())

    open_groups(page)
    expect(page.get_by_role("row")).to_have_count(3)  # l'en-tête et les deux groupes
    expect(row(page, "ITI4")).to_contain_text("2025-2026")
    expect(row(page, "TD neuf")).to_contain_text(current_year())
    page.get_by_role("link", name="ITI4").click()
    expect(student_rows(page)).to_have_count(1)

    open_sessions(page)
    for code, label in [
        ("111111", "ITI4 — 2025-2026"),
        ("222222", "ITI4 — 2026-2027"),
        ("333333", "ITI4 — 2025-2026"),
        ("444444", "TD supprimé — 2026-2027"),
    ]:
        expect(row(page, code)).to_contain_text(label)
