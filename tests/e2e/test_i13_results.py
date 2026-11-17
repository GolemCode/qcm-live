"""Incrément 13 : note sur 20 (RES-03) et notes masquées à l'ouverture (RES-04).

Préconditions : trois questions simples (barème b=1, m=-1, v=0), N = 1, t = 30 s. Au premier
créneau, 00123 répond juste à la question qu'il voit, 42 répond faux à la sienne. Personne ne
répond ensuite. 7 ne se connecte jamais.

- 00123 : 1 / 3 x 20 = 6,666… : 6,67 ;
- 42 : -1, note négative : 0 ;
- 7 : absent, cellule vide.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from live.models import Session
from tests.e2e.live_setup import QUESTIONS, expect_slot, make_live, question_of, started
from tests.e2e.live_ui import (
    LIVE_MS,
    choose,
    csv_rows,
    download_csv,
    open_results,
    phone_choices,
    results_rows,
    results_table,
    save_status,
    show_grades,
)
from tests.factories import jump_to

SCORING = {False: "b=1,m=-1,v=0"}
RIGHT = {"00123": True, "42": False}  # au premier créneau : réponse juste ou fausse


def play(page: Page, base_url: str, new_phone) -> Session:
    session = make_live(3, shown=1, scoring=SCORING)
    numbers = list(RIGHT)
    phones = dict(zip(numbers, started(page, base_url, new_phone, session, numbers), strict=True))
    for number, phone in phones.items():
        expect_slot(phone, 0)
        choices = QUESTIONS[question_of(phone_choices(phone))]
        choose(phone, next(text for text, correct in choices if correct == RIGHT[number]))
        expect(save_status(phone)).to_have_text("Réponse enregistrée")
    jump_to(session, 91)
    expect(page.get_by_role("main")).to_contain_text("Session terminée", timeout=LIVE_MS)
    return session


@pytest.mark.spec("RES-03")
def test_grade_out_of_20_in_csv_and_results_page(teacher_page: Page, live_server, new_phone):
    page = teacher_page
    play(page, live_server.url, new_phone)
    open_results(page)

    _, content = download_csv(page)
    rows = csv_rows(content)
    # Juste après la note maximale, en virgule décimale ; vide pour un absent.
    assert [row[:6] for row in rows] == [
        ["n°", "numéro étudiant", "nom", "note", "note max", "note /20"],
        ["1", "00123", "DURAND Élise", "1", "3", "6,67"],  # 6,666… arrondi au centième
        ["2", "42", "MARTIN Léo", "-1", "3", "0"],  # bornée à 0
        ["3", "7", "Ng Anh", "Absent", "3", ""],
    ]
    assert rows[0][6:] == [f"Q{i} {kind}" for i in range(1, 4) for kind in ("réponse", "points")]

    # La page des résultats porte la même colonne.
    show_grades(page)
    headers = results_table(page).get_by_role("columnheader")
    expect(headers).to_have_text(
        ["N°", "Numéro étudiant", "Nom", "Note", "Note maximale", "Note /20"]
    )
    assert results_rows(page) == [
        ["1", "00123", "DURAND Élise", "1", "3", "6,67"],
        ["2", "42", "MARTIN Léo", "-1", "3", "0"],
        ["3", "7", "Ng Anh", "Absent", "3", ""],
    ]


@pytest.mark.spec("RES-04")
def test_results_page_opens_with_grades_hidden(teacher_page: Page, live_server, new_phone):
    """L'écran du PC est projeté : rien ne s'affiche tant que l'enseignant ne le demande pas."""
    page = teacher_page
    play(page, live_server.url, new_phone)
    open_results(page)

    def nothing_shown() -> None:
        expect(results_table(page)).to_be_hidden()
        for hidden in ("DURAND Élise", "MARTIN Léo", "6,67", "Absent"):
            expect(page.get_by_text(hidden)).to_be_hidden()

    nothing_shown()
    # Le CSV se télécharge sans rien afficher.
    _, content = download_csv(page)
    assert csv_rows(content)[1][:3] == ["1", "00123", "DURAND Élise"]
    nothing_shown()
    # Rouverte, la page masque de nouveau les notes.
    show_grades(page)
    expect(page.get_by_text("DURAND Élise")).to_be_visible()
    page.reload()
    nothing_shown()

    show_grades(page)
    for shown in ("DURAND Élise", "MARTIN Léo", "6,67", "Absent"):
        expect(page.get_by_text(shown, exact=True)).to_be_visible()
