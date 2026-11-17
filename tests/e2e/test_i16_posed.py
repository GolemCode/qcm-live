"""Incrément 16 : questions déjà posées au groupe (CMP-03), au lancement et à la composition.

L'historique, préparé par les fabriques, distingue chaque cas voisin : une autre version de
la question, un étudiant reconnu par son numéro ou par son nom, un homonyme dont le numéro
diffère, un absent, une session jamais démarrée, le même groupe une autre année, un autre
groupe la même année."""

import pytest
from django.utils import timezone
from playwright.sync_api import Page, expect

from bank.models import Quiz
from live.models import Session
from tests.e2e.bank_ui import include_box, open_quiz
from tests.e2e.live_ui import board_code, fill_launch, open_sessions
from tests.factories import (
    current_year,
    make_group,
    make_participant,
    make_question,
    make_quiz,
    make_session,
    new_version,
)

# Le groupe ITI4 de 2025-2026 tel qu'il était lors des séances passées…
BEFORE = [
    (1, "00123", "DURAND Élise"),
    (2, "42", "MARTIN Léo"),
    (3, "7", "Ng Anh"),
    (4, "55", "PETIT Jade"),
]
# … et tel qu'il a été réimporté depuis (n = 5).
NOW = [
    (1, "00123", "DURAND Élise-Marie"),  # même numéro : reconnue
    (2, "", "MARTIN Léo"),  # sans numéro : reconnu par son nom exact
    (3, "99", "Ng Anh"),  # même nom, autre numéro : pas reconnu
    (4, "55", "PETIT Jade"),
    (5, "88", "BERNARD Paul"),  # nouveau
]
CHOICES = ["Paris", "Lyon", "Bleu", "Vert", "Quatre", "Trois", "Pacifique", "Atlantique"]
CAPITAL = "Capitale de la France, en un mot ?"  # nouvelle version de « Capitale de la France ? »
SKY, SUM, OCEAN = "Couleur du ciel ?", "Deux plus deux ?", "Plus grand océan ?"


def played(quiz: Quiz, group, list_numbers, *, start: bool = True) -> Session:
    """Session de `quiz` où se sont identifiés les étudiants de ces n°, démarrée ou non."""
    session = make_session(quiz, group)
    for list_number in list_numbers:
        make_participant(session, list_number)
    if start:
        session.start(timezone.now())
    return session


def history() -> Quiz:
    """Séances passées, puis le QCM « Nouveau » à lancer : les quatre questions."""
    capital = make_question("Capitale de la France ?", [("Paris", True), ("Lyon", False)])
    sky = make_question(SKY, [("Bleu", True), ("Vert", False)])
    total = make_question(SUM, [("Quatre", True), ("Trois", False)])
    ocean = make_question(OCEAN, [("Pacifique", True), ("Atlantique", False)])
    iti4 = make_group("ITI4", BEFORE, "2025-2026")
    played(make_quiz("Séance 1", [capital]), iti4, [1, 2, 3])  # PETIT Jade absente
    played(make_quiz("Séance 2", [sky]), iti4, [3, 4])
    played(make_quiz("Séance 3", [total]), iti4, [1, 2, 3, 4], start=False)
    played(make_quiz("Séance 4", [ocean]), make_group("ITI4", BEFORE, "2024-2025"), [1, 2, 3, 4])
    played(make_quiz("Séance 5", [ocean]), make_group("ITI5", BEFORE, "2025-2026"), [1, 2, 3, 4])
    capital = new_version(capital, CAPITAL, [("Paris", True), ("Lyon", False)])
    iti4.delete()
    make_group("ITI4", NOW, "2025-2026")
    make_group("TD vierge", NOW)
    return make_quiz("Nouveau", [capital, sky, total, ocean])


def posed_items(page: Page):
    return page.get_by_role("list", name="Questions déjà posées").get_by_role("listitem")


@pytest.mark.spec("CMP-03")
def test_launch_lists_questions_already_posed(teacher_page: Page):
    page = teacher_page
    history()
    sessions = Session.objects.count()
    open_sessions(page)
    page.get_by_role("link", name="Lancer une session").click()
    fill_launch(page, "Nouveau", "ITI4 — 2025-2026", 2, 45)

    items = posed_items(page)
    expect(items).to_have_count(2)
    expect(items.filter(has_text=CAPITAL)).to_contain_text("posée à 2 étudiants sur 5")
    expect(items.filter(has_text=SKY)).to_contain_text("posée à 1 étudiant sur 5")
    main = page.get_by_role("main")
    for text in (SUM, OCEAN, *CHOICES):  # ni les autres questions, ni aucune proposition
        expect(main).not_to_contain_text(text)
    assert Session.objects.count() == sessions

    # « Revenir » : le formulaire de lancement, rempli comme il l'était.
    page.get_by_role("button", name="Revenir").click()
    expect(page.get_by_label("QCM").locator("option:checked")).to_have_text("Nouveau")
    expect(page.get_by_label("Groupe", exact=True).locator("option:checked")).to_have_text(
        "ITI4 — 2025-2026"
    )
    expect(page.get_by_label("Questions affichées en même temps")).to_have_value("2")
    expect(page.get_by_label("Temps par question (secondes)")).to_have_value("45")
    assert Session.objects.count() == sessions

    # « Lancer quand même » : la session, avec ces réglages.
    page.get_by_role("button", name="Lancer").click()
    expect(posed_items(page)).to_have_count(2)
    page.get_by_role("button", name="Lancer quand même").click()
    session = Session.objects.get(code=board_code(page))
    assert (session.quiz_title, session.group_name) == ("Nouveau", "ITI4")
    assert (session.n_questions, session.shown, session.seconds) == (4, 2, 45)
    expect(page.get_by_role("main")).to_contain_text("Groupe ITI4 — 2025-2026")


@pytest.mark.spec("CMP-03")
def test_launch_without_history_goes_straight_to_the_board(teacher_page: Page):
    page = teacher_page
    history()
    open_sessions(page)
    page.get_by_role("link", name="Lancer une session").click()
    fill_launch(page, "Nouveau", "TD vierge", 1, 30)
    assert Session.objects.filter(code=board_code(page), group_name="TD vierge").exists()


@pytest.mark.spec("CMP-03")
def test_composition_marks_questions_posed_to_a_group(teacher_page: Page):
    """« Marquer » réaffiche le formulaire tel quel, sans l'enregistrer ni signaler d'erreur."""
    page = teacher_page
    quiz = history()
    open_quiz(page, "Nouveau")
    page.get_by_role("link", name="Modifier le QCM").click()
    expect(page.get_by_role("columnheader", name="Déjà posée")).to_have_count(0)
    page.get_by_label("Titre").fill("")
    include_box(page, SUM).uncheck()
    page.get_by_label("Marquer les questions déjà posées au groupe").select_option(
        label="ITI4 — 2025-2026"
    )
    page.get_by_role("button", name="Marquer").click()

    expect(page.get_by_role("columnheader", name="Déjà posée")).to_be_visible()
    rows = page.get_by_role("row")
    expect(rows.filter(has_text=CAPITAL)).to_contain_text("posée à 2 étudiants sur 5")
    expect(rows.filter(has_text=SKY)).to_contain_text("posée à 1 étudiant sur 5")
    for text in (SUM, OCEAN):
        expect(rows.filter(has_text=text)).not_to_contain_text("posée")
    expect(page.get_by_role("alert")).to_have_count(0)
    expect(page.get_by_label("Titre")).to_have_value("")
    expect(include_box(page, SUM)).not_to_be_checked()
    expect(include_box(page, CAPITAL)).to_be_checked()
    quiz.refresh_from_db()
    assert quiz.title == "Nouveau"
    assert quiz.questions.count() == 4

    # Un autre groupe : rien de marqué ; puis l'enregistrement garde la saisie.
    page.get_by_label("Marquer les questions déjà posées au groupe").select_option(
        label=f"TD vierge — {current_year()}"
    )
    page.get_by_role("button", name="Marquer").click()
    expect(page.get_by_role("main")).not_to_contain_text("posée à")
    page.get_by_label("Titre").fill("Nouveau, sans calcul")
    page.get_by_role("button", name="Enregistrer").click()
    expect(page.get_by_role("heading", name="Nouveau, sans calcul", level=1)).to_be_visible()
    quiz.refresh_from_db()
    assert sorted(quiz.questions.values_list("text", flat=True)) == sorted([CAPITAL, SKY, OCEAN])
