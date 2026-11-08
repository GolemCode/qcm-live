"""Incrément 5 : temps additionnel (+10 s) et effacement d'une réponse simple."""

import re
import time

import pytest
from django.utils import timezone
from playwright.sync_api import Page, expect

from live.models import Answer, Extension
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
    seconds_left,
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

    # Le second créneau commence 15 s après le départ, et non 10 s. On date le rechargement de
    # la page du téléphone par son horloge monotone, sans l'attente de Playwright (jusqu'à 1 s).
    expect_slot(phone, 1, timeout=15_000)
    session.refresh_from_db()
    assert session.started_at
    loaded_for = phone.evaluate("performance.now()") / 1000
    reloaded_after = (timezone.now() - session.started_at).total_seconds() - loaded_for
    assert 15 <= reloaded_after <= 15 + LIVE_MS / 1000
    expect(card(page, 1).get_by_role("heading")).to_have_text("Couleur du ciel ?", timeout=LIVE_MS)
    timer_shows(phone, 3, 5)  # attendu : le compte à rebours se remplit après le rechargement
    timer_shows(page, 3, 5)


def test_countdown_ignores_a_step_of_the_wall_clock(teacher_page: Page, live_server, new_phone):
    """Entre deux interrogations de l'état, le décompte ignore l'horloge du navigateur.

    Les interrogations sont coupées : ce test porte sur `qcm.countdown`, pas sur l'écran, qui se
    recale chaque seconde sur le serveur et remonte si l'horloge du serveur recule (REX, R)."""
    page = teacher_page
    session = make_live(2, shown=1)
    (phone,) = started(page, live_server.url, new_phone, session, ["00123"])
    timer_shows(phone, 25, 30)
    # Sans interrogation de l'état : elle recalerait le compte à rebours et masquerait le saut.
    state_url = phone.locator("[data-state-url]").get_attribute("data-state-url")
    phone.route(f"**{state_url}", lambda route: route.abort())
    phone.wait_for_timeout(1100)  # le temps qu'une interrogation en cours se termine
    before = seconds_left(phone)
    phone.evaluate("() => { const real = Date.now.bind(Date); Date.now = () => real() - 5000; }")
    for _ in range(6):
        phone.wait_for_timeout(100)
        assert seconds_left(phone) <= before


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
    phone.reload()  # la couleur reste celle de sa question : rang 0, créneau 1, groupe de 2
    expect(phone.get_by_text("Couleur 2", exact=True)).to_be_visible()
    jump_to(session, 69.5)  # le second créneau finit à 70 s
    expect_slot(phone, 1)
    jump_to(session, 70.5)
    expect_slot(phone, 2)
    timer_shows(phone, 28, 30)  # le troisième dure ses 30 s
    expect(card(page, 1).get_by_role("heading")).to_have_text("Deux plus deux ?")


@pytest.mark.spec("TPS-01")
def test_click_arriving_after_the_slot_adds_nothing(teacher_page: Page, live_server, new_phone):
    """Le tableau n'a pas encore vu la fin du créneau quand l'enseignant clique : le clic vise
    un créneau terminé et n'ajoute rien, ni à lui (pas de retour en arrière) ni au suivant."""
    page = teacher_page
    session = make_live(2, shown=1)
    (phone,) = started(page, live_server.url, new_phone, session, ["00123"])
    timer_shows(page, 28, 30)
    page.route(re.compile(r".*/etat/$"), lambda route: route.abort())  # tableau figé
    jump_to(session, 30.5)
    expect_slot(phone, 1)

    add_time(page)
    expect(page.get_by_role("status")).to_contain_text("Créneau terminé : aucun temps ajouté.")
    expect(card(page, 1).get_by_role("heading")).to_have_text("Couleur du ciel ?")
    timer_shows(page, 28, 29)
    expect_slot(phone, 1)
    timer_shows(phone, 28, 29)
    assert not Extension.objects.exists()


@pytest.mark.spec("ETU-09")
def test_student_clears_single_answer(teacher_page: Page, live_server, new_phone, reversed_choices):
    page = teacher_page
    session = make_live(1, shown=1)
    (phone,) = started(page, live_server.url, new_phone, session, ["00123"])
    expect(phone.get_by_role("group", name="Propositions")).to_be_visible(timeout=LIVE_MS)
    answers = Answer.objects.filter(participant__session=session)
    expect(clear_button(phone)).to_be_disabled()  # rien à effacer

    choose(phone, "Lyon")
    expect(save_status(phone)).to_have_text(SAVED)
    clear_answer(phone)
    expect(save_status(phone)).to_have_text(CLEARED)
    expect(phone.get_by_role("radio", checked=True)).to_have_count(0)
    expect(clear_button(phone)).to_be_disabled()
    assert not answers.exists()  # non-réponse (v), et non plus une mauvaise réponse
    phone.reload()
    expect(phone.get_by_role("radio")).to_have_count(3)
    expect(phone.get_by_role("radio", checked=True)).to_have_count(0)
    expect(clear_button(phone)).to_be_disabled()

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
