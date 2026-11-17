"""Incrément 17, réponses du commanditaire aux questions de I16 : une question déjà posée se
masque au lieu de se supprimer (BAN-07), et les QCM se listent par titre (BAN-03, SES-01)."""

import pytest
from django.utils import timezone
from playwright.sync_api import Page, expect

from tests.e2e.amc_ui import expect_recap, upload_amc
from tests.e2e.bank_ui import (
    open_bank,
    open_quiz,
    question_card,
    quiz_question_items,
)
from tests.e2e.live_ui import fill_launch, open_sessions
from tests.factories import (
    make_group,
    make_participant,
    make_question,
    make_quiz,
    make_session,
    new_version,
)

STUDENTS = [(1, "00123", "DURAND Élise"), (2, "42", "MARTIN Léo"), (3, "7", "Ng Anh")]
CAPITAL, CAPITAL_V2 = "Capitale de la France ?", "Capitale de la France, en un mot ?"
CHOICES = [("Paris", True), ("Lyon", False)]


@pytest.mark.spec("BAN-07")
def test_question_posed_in_a_session_is_hidden_not_deleted(teacher_page: Page):
    """La question posée à ITI4 est supprimée de la banque : elle quitte la banque et ses QCM,
    mais sa nouvelle version reste « déjà posée », et un import ne la partage pas."""
    page = teacher_page
    capital = make_question(CAPITAL, CHOICES)
    first = make_quiz("Séance 1", [capital])
    session = make_session(first, make_group("ITI4", STUDENTS, "2025-2026"))
    make_participant(session, 1)
    make_participant(session, 2)
    session.start(timezone.now())
    # VER-02 : la nouvelle version ne remplace l'ancienne que dans « Nouveau » ;
    # « Séance 1 » garde l'ancienne, qui reste donc dans la banque.
    new_version(capital, CAPITAL_V2, CHOICES, only=make_quiz("Nouveau", [capital]))

    open_bank(page)
    question_card(page, CAPITAL).get_by_role("link", name="Supprimer").click()
    main = page.get_by_role("main")
    expect(main).to_contain_text("Elle sera retirée des QCM : Séance 1.")
    expect(main).to_contain_text("Elle a servi dans une session")
    page.get_by_role("button", name="Supprimer").click()
    expect(page.get_by_role("status")).to_contain_text("Question supprimée")
    expect(question_card(page, CAPITAL)).to_have_count(0)
    expect(question_card(page, CAPITAL_V2)).to_be_visible()
    open_quiz(page, "Séance 1")
    expect(quiz_question_items(page)).to_have_count(0)

    # CMP-03 : la nouvelle version compte toujours l'ancienne, posée à deux étudiants.
    open_sessions(page)
    page.get_by_role("link", name="Lancer une session").click()
    fill_launch(page, "Nouveau", "ITI4", 1, 30)
    posed = page.get_by_role("list", name="Questions déjà posées").get_by_role("listitem")
    expect(posed).to_have_count(1)
    expect(posed).to_contain_text(f"{CAPITAL_V2} — posée à 2 étudiants sur 3")

    # IMP-07 : comme une ancienne version, la question masquée n'est jamais partagée.
    upload_amc(page, f"* {CAPITAL}\n+ Paris\n- Lyon\n")
    expect_recap(page)
    expect(page.get_by_role("main")).to_contain_text("dont 0 déjà dans la banque")
