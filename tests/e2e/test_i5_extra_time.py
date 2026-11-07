"""Incrément 5 : temps additionnel (+10 s) et effacement d'une réponse simple."""

import re
import time

import pytest
from playwright.sync_api import Page, expect

from live.models import Answer
from live.views import CLEARED, SAVED, TOO_LATE
from tests.e2e.live_setup import (
    QUESTIONS,
    STUDENTS,
    expect_slot,
    make_live,
    open_board,
    started,
)
from tests.e2e.live_ui import (
    LIVE_MS,
    add_time,
    add_time_button,
    card,
    choose,
    clear_answer,
    clear_button,
    phone_choices,
    phones_joined,
    save_status,
    start,
    timer_shows,
)
from tests.factories import jump_to, make_group, make_question, make_quiz, make_session


@pytest.mark.spec("TPS-01")
def test_added_time_in_real_time(teacher_page: Page, live_server, new_phone):
    """Temps réel, sans avance artificielle : t = 5 s et +10 s, le créneau dure 15 s ; le
    suivant commence ensuite, avec ses 5 s entières."""
    page = teacher_page
    session = make_live(2, shown=1, seconds=5)
    (phone,) = started(page, live_server.url, new_phone, session, ["00123"])
    t0 = time.monotonic()
    expect_slot(phone, 0)

    add_time(page)
    timer_shows(page, 12, 15)
    timer_shows(phone, 12, 15)

    # Passé l'échéance d'origine (5 s), le créneau continue et une réponse est acceptée.
    page.wait_for_timeout(max(0, 6.5 - (time.monotonic() - t0)) * 1000)
    expect_slot(phone, 0)
    choose(phone, phone_choices(phone)[0])
    expect(save_status(phone)).to_have_text(SAVED)
    assert Answer.objects.filter(participant__session=session, question=0).exists()

    # Le second créneau commence 15 s après le départ, et non 10 s.
    expect_slot(phone, 1, timeout=15_000)
    assert 13.5 <= time.monotonic() - t0 <= 15 + LIVE_MS / 1000
    expect(card(page, 1).get_by_role("heading")).to_have_text("Couleur du ciel ?", timeout=LIVE_MS)
    timer_shows(phone, 3, 5)  # attendu : le compte à rebours se remplit après le rechargement
    timer_shows(page, 3, 5)


@pytest.mark.spec("TPS-01")
def test_added_time_accumulates_and_shifts_next_slots(teacher_page: Page, live_server, new_phone):
    page = teacher_page
    session = make_live(2, shown=1)  # deux créneaux de 30 s
    phones = phones_joined(new_phone, live_server.url, session.code, ["00123", "42"])
    open_board(page, live_server.url, session)
    expect(add_time_button(page)).to_have_count(0)  # pas avant le démarrage
    start(page)

    jump_to(session, 20)  # 10 s restantes
    for screen in (page, *phones):
        timer_shows(screen, 8, 10)
    add_time(page)
    timer_shows(page, 18, 20)
    add_time(page)  # les ajouts se cumulent
    timer_shows(page, 28, 30)
    for phone in phones:  # tous les téléphones suivent
        timer_shows(phone, 28, 30)

    # Pendant le temps ajouté (2,5 s restantes sur 50) : le même créneau, réponse acceptée.
    jump_to(session, 47.5)
    for phone in phones:
        expect_slot(phone, 0)
        choose(phone, phone_choices(phone)[0])
        expect(save_status(phone)).to_have_text(SAVED)
    assert Answer.objects.filter(participant__session=session).count() == 2

    # Le créneau suivant est décalé de 20 s : il va de 50 à 80 s.
    jump_to(session, 50.5)
    for phone in phones:
        expect_slot(phone, 1)
        timer_shows(phone, 28, 30)
    expect(card(page, 1).get_by_role("heading")).to_have_text("Couleur du ciel ?", timeout=LIVE_MS)
    timer_shows(page, 28, 30)
    jump_to(session, 77.5)
    for phone in phones:
        choose(phone, phone_choices(phone)[0])
        expect(save_status(phone)).to_have_text(SAVED)
    jump_to(session, 80.5)
    for screen in (page, *phones):
        expect(screen.get_by_role("main")).to_contain_text("Session terminée", timeout=LIVE_MS)
    expect(add_time_button(page)).to_have_count(0)  # pas après la fin


@pytest.mark.spec("TPS-01")
def test_added_time_belongs_to_current_slot_only(teacher_page: Page, live_server, new_phone):
    """Un ajout au second créneau l'allonge, lui seul. N = 2 : le tableau reste sur le même
    groupe, sans se recharger, et « +10 s » vise pourtant le second créneau."""
    page = teacher_page
    session = make_live(3, shown=2)
    (phone,) = started(page, live_server.url, new_phone, session, ["00123"])
    jump_to(session, 40)  # second créneau, 20 s restantes
    expect_slot(phone, 1)
    timer_shows(page, 18, 20)  # le tableau est passé au second créneau
    add_time(page)
    timer_shows(page, 28, 30)
    timer_shows(phone, 28, 30)
    jump_to(session, 69.5)  # le second créneau finit à 70 s
    expect_slot(phone, 1)
    jump_to(session, 70.5)
    expect_slot(phone, 2)
    timer_shows(phone, 28, 30)  # le troisième dure ses 30 s
    expect(card(page, 1).get_by_role("heading")).to_have_text("Deux plus deux ?")


@pytest.mark.spec("ETU-09")
def test_student_clears_single_answer(teacher_page: Page, live_server, new_phone, reversed_choices):
    page = teacher_page
    session = make_live(1, shown=1)
    (phone,) = started(page, live_server.url, new_phone, session, ["00123"])
    expect(phone.get_by_role("group", name="Propositions")).to_be_visible(timeout=LIVE_MS)
    answers = Answer.objects.filter(participant__session=session)

    choose(phone, "Lyon")
    expect(save_status(phone)).to_have_text(SAVED)
    clear_answer(phone)
    expect(save_status(phone)).to_have_text(CLEARED)
    expect(phone.get_by_role("radio", checked=True)).to_have_count(0)
    assert not answers.exists()  # non-réponse (v), et non plus une mauvaise réponse
    phone.reload()
    expect(phone.get_by_role("radio")).to_have_count(3)
    expect(phone.get_by_role("radio", checked=True)).to_have_count(0)

    choose(phone, "Paris")  # on peut encore répondre après avoir effacé
    expect(save_status(phone)).to_have_text(SAVED)
    assert answers.get().choices == [0]

    # Après l'échéance, l'effacement est refusé et la réponse reste.
    phone.route(re.compile(r".*/etat/$"), lambda route: route.abort())
    jump_to(session, 30.5)
    clear_answer(phone)
    expect(save_status(phone)).to_have_text(TOO_LATE)
    assert answers.get().choices == [0]


@pytest.mark.spec("ETU-09")
def test_multiple_question_cleared_by_unchecking_everything(
    teacher_page: Page, live_server, new_phone
):
    page = teacher_page
    text = "Lesquels sont pairs ?"
    quiz = make_quiz("M", [make_question(text, QUESTIONS[text], multiple=True)])
    session = make_session(quiz, make_group("TD1", STUDENTS), shown=1)
    (phone,) = started(page, live_server.url, new_phone, session, ["00123"])
    expect(phone.get_by_role("group", name="Propositions")).to_be_visible(timeout=LIVE_MS)

    expect(clear_button(phone)).to_have_count(0)
    choose(phone, "2")
    choose(phone, "4")
    expect(save_status(phone)).to_have_text(SAVED)
    choose(phone, "2")
    expect(save_status(phone)).to_have_text(SAVED)
    choose(phone, "4")  # plus rien de coché
    expect(save_status(phone)).to_have_text(CLEARED)
    assert not Answer.objects.filter(participant__session=session).exists()
