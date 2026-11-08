"""Incrément 9 : le tableau n'affiche que les énoncés, le téléphone que les propositions
(AFF-01), et 4 questions s'affichent à la fois par défaut (SES-06).

Les textes sont des marqueurs uniques : les chercher dans le code de la page ne donne aucun
faux positif, et couvre aussi ce qui serait envoyé sans être visible.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, ViewportSize, expect

from tests.e2e.live_setup import STUDENTS, expect_slot, open_board
from tests.e2e.live_ui import (
    LIVE_MS,
    board_code,
    card,
    launch_session,
    open_results,
    open_sessions,
    phone_choices,
    phone_color,
    phones_joined,
    start,
)
from tests.factories import jump_to, make_group, make_question, make_quiz, make_session

CHOICES = {f"ÉNONCÉ-{q} ?": [(f"RÉPONSE-{q}-{c}", c == 1) for c in (1, 2, 3)] for q in (1, 2, 3)}
STATEMENTS = list(CHOICES)
ALL_CHOICES = [label for choices in CHOICES.values() for label, _ in choices]


def make_marked_session(shown: int = 2):
    """Trois questions, dont la dernière multiple : un groupe de 2, puis un groupe de 1."""
    questions = [
        make_question(text, choices, multiple=text == STATEMENTS[2])
        for text, choices in CHOICES.items()
    ]
    return make_session(
        make_quiz("Contrôle", questions), make_group("TD1", STUDENTS), shown=shown, seconds=30
    )


def assert_shows_none(content: str, *forbidden: str) -> None:
    present = [text for text in forbidden if text in content]
    assert present == [], present


def state(page: Page, url: str) -> str:
    response = page.request.get(url)
    assert response.ok, url
    return response.text()


@pytest.mark.spec("AFF-01")
def test_board_has_only_statements_and_phone_only_choices(
    teacher_page: Page, live_server, new_phone
):
    page = teacher_page
    session = make_marked_session()
    code = session.code
    phones = phones_joined(new_phone, live_server.url, code, ["00123", "42"])
    board_state = f"{live_server.url}/prof/sessions/{code}/etat/"
    phone_state = f"{live_server.url}/s/{code}/etat/"
    everything = (*STATEMENTS, *ALL_CHOICES)

    # En attente : ni énoncé ni proposition, nulle part.
    open_board(page, live_server.url, session)
    assert_shows_none(page.content(), *everything)
    for phone in phones:
        assert_shows_none(phone.content(), *everything)

    start(page)
    # Créneaux 0 et 1, puis créneau 2 : (énoncés du groupe au tableau, questions de chaque rang).
    plan = [
        (STATEMENTS[:2], [STATEMENTS[0], STATEMENTS[1]]),
        (STATEMENTS[:2], [STATEMENTS[1], STATEMENTS[0]]),
        (STATEMENTS[2:], [STATEMENTS[2], STATEMENTS[2]]),
    ]
    for slot, (on_board, on_phones) in enumerate(plan):
        jump_to(session, slot * 30 + 1)
        expect(card(page, 1).get_by_role("heading")).to_have_text(on_board[0], timeout=LIVE_MS)
        for color, statement in enumerate(on_board, start=1):
            expect(card(page, color).get_by_role("heading")).to_have_text(statement)
        expect(card(page, len(on_board) + 1)).to_have_count(0)

        # Le tableau : les énoncés de son groupe, aucune proposition, même invisible.
        board_html = page.content()
        assert_shows_none(board_html, *ALL_CHOICES)
        assert_shows_none(board_html, *(s for s in STATEMENTS if s not in on_board))
        assert_shows_none(state(page, board_state), *everything)

        for phone, statement in zip(phones, on_phones, strict=True):
            expect_slot(phone, slot)
            # Le téléphone : les propositions de sa question, aucun énoncé, même invisible.
            own = [label for label, _ in CHOICES[statement]]
            assert sorted(phone_choices(phone)) == sorted(own)
            phone_html = phone.content()
            assert_shows_none(phone_html, *STATEMENTS)
            assert_shows_none(phone_html, *(c for c in ALL_CHOICES if c not in own))
            assert_shows_none(state(phone, phone_state), *everything)

    # Terminée : plus rien, ni au tableau, ni sur le téléphone, ni dans les résultats.
    jump_to(session, 91)
    expect(page.get_by_role("main")).to_contain_text("Session terminée", timeout=LIVE_MS)
    assert_shows_none(page.content(), *everything)
    for phone in phones:
        expect(phone.get_by_role("main")).to_contain_text("Session terminée", timeout=LIVE_MS)
        assert_shows_none(phone.content(), *everything)

    open_results(page)
    assert_shows_none(page.content(), *everything)
    with page.expect_download() as info:
        page.get_by_role("link", name="Télécharger le CSV").click()
    assert_shows_none(info.value.path().read_text(encoding="utf-8-sig"), *everything)


@pytest.mark.spec("SES-06")
def test_four_questions_at_once_by_default(teacher_page: Page, live_server, new_phone):
    page = teacher_page
    long_text = "Quelle est la proposition exacte parmi celles de votre téléphone ? " * 3
    statements = [f"{i} : {long_text}" for i in range(1, 6)]
    quiz = make_quiz("Cinq", [make_question(text) for text in statements])
    make_group("TD1", STUDENTS)

    open_sessions(page)
    page.get_by_role("link", name="Lancer une session").click()
    page.get_by_label("QCM").select_option(label=quiz.title)
    page.get_by_label("Groupe").select_option(label="TD1")
    # Sans toucher au champ : la valeur par défaut.
    expect(page.get_by_label("Questions affichées en même temps")).to_have_value("4")
    page.get_by_role("button", name="Lancer").click()
    code = board_code(page)
    expect(page.get_by_role("main")).to_contain_text("4 questions à la fois")

    (phone,) = phones_joined(new_phone, live_server.url, code, ["00123"])
    start(page)
    for color in range(1, 5):
        expect(card(page, color).get_by_role("heading")).to_contain_text(f"{color} : ")
    expect(card(page, 5)).to_have_count(0)
    assert phone_color(phone) == 1
    # Les 4 énoncés tiennent à l'écran, sans défilement, même assez longs, y compris sur un
    # projecteur de 720 lignes.
    for width, height in ((1920, 1080), (1280, 720)):
        size = ViewportSize(width=width, height=height)
        page.set_viewport_size(size)
        overflow = page.evaluate(
            "() => document.documentElement.scrollHeight - document.documentElement.clientHeight"
        )
        assert overflow <= 0, (size, overflow)


@pytest.mark.spec("SES-06")
def test_another_value_can_be_chosen_at_launch(teacher_page: Page):
    page = teacher_page
    make_quiz("Trois", [make_question(text) for text in STATEMENTS])
    make_group("TD1", STUDENTS)
    launch_session(page, "Trois", "TD1", shown=2)
    expect(page.get_by_role("main")).to_contain_text("2 questions à la fois")
    start(page)
    expect(card(page, 2).get_by_role("heading")).to_have_text(STATEMENTS[1])
    expect(card(page, 3)).to_have_count(0)
