"""Incrément 16, séance : terminer le créneau en cours (TPS-02), « k / n ont répondu » (DER-04).

Le temps retiré se lit en base (`Extension`, une ligne signée par clic) pour placer les sauts
dans le temps : ce que l'écran montre (5 s restantes) est vérifié à part, à la seconde près."""

import re
import time

import pytest
from django.db.models import Sum
from playwright.sync_api import Page, expect

from live.models import Extension
from live.views import CLEARED, SAVED
from tests.e2e.live_setup import expect_slot, make_live, open_board, started
from tests.e2e.live_ui import (
    LIVE_MS,
    add_time,
    answered,
    card,
    choose,
    clear_answer,
    confirm_button,
    end_slot,
    end_slot_button,
    phone_choices,
    phones_joined,
    save_status,
    seconds_left,
    start,
    timer_shows,
)
from tests.factories import jump_to

WALL = 2  # l'horloge de WSL2 recule d'environ 2 s toutes les 32 s (CLAUDE.md)


def added_seconds() -> int:
    """Temps ajouté (positif) ou retiré (négatif) en tout, d'après la base."""
    return Extension.objects.aggregate(total=Sum("seconds"))["total"] or 0


def page_token(phone: Page) -> str | None:
    """Jeton de page du téléphone, lu à l'instant, sans attendre."""
    return phone.locator("body").get_attribute("data-page")


# --- TPS-02 : terminer le créneau en cours ---------------------------------------------------


@pytest.mark.spec("TPS-02")
def test_end_slot_in_real_time(teacher_page: Page, live_server, new_phone):
    """Temps réel : « Confirmer » dure 3 s et ne change rien seul ; confirmé, le créneau finit
    5 s plus tard, au tableau comme au téléphone, et le suivant garde ses 30 s."""
    page = teacher_page
    session = make_live(2, shown=1)
    (phone,) = started(page, live_server.url, new_phone, session, ["00123"])
    expect(confirm_button(page)).to_have_count(0)

    end_slot_button(page).click()
    clicked = time.monotonic()
    expect(confirm_button(page)).to_be_visible()
    page.wait_for_timeout(max(0, 2 - (time.monotonic() - clicked)) * 1000)
    assert confirm_button(page).is_visible()  # encore là à 2 s
    expect(end_slot_button(page)).to_be_visible(timeout=2_500)  # revenu après 3 s
    assert time.monotonic() - clicked >= 2.5
    # Le premier clic seul ne change rien ; un nouveau clic redemande confirmation.
    assert seconds_left(page) >= 20
    end_slot_button(page).click()
    expect(confirm_button(page)).to_be_visible()
    expect(end_slot_button(page)).to_be_visible(timeout=4_000)
    assert seconds_left(page) >= 20
    assert not Extension.objects.exists()

    end_slot(page)
    confirmed = time.monotonic()
    timer_shows(page, 3, 5)
    timer_shows(phone, 3, 5)
    page.wait_for_timeout(max(0, 2 - (time.monotonic() - confirmed)) * 1000)
    assert page_token(phone) == "running:0"  # ces 5 s restent au créneau
    expect_slot(phone, 1, timeout=10_000)
    assert 5 - WALL <= time.monotonic() - confirmed <= 5 + WALL + LIVE_MS / 1000
    expect(card(page, 1).get_by_role("heading")).to_have_text("Couleur du ciel ?", timeout=LIVE_MS)
    timer_shows(phone, 27, 30)  # le suivant dure ses 30 s
    timer_shows(page, 27, 30)


@pytest.mark.spec("TPS-02")
def test_end_slot_shifts_next_slots_and_plus_10_catches_up(
    teacher_page: Page, live_server, new_phone
):
    page = teacher_page
    session = make_live(3, shown=1)
    phones = phones_joined(new_phone, live_server.url, session.code, ["DURAND Élise", "MARTIN Léo"])
    open_board(page, live_server.url, session)
    expect(end_slot_button(page)).to_have_count(0)  # pas avant le démarrage
    start(page)

    jump_to(session, 10)  # 20 s restantes
    timer_shows(page, 18, 20)
    end_slot(page)
    for screen in (page, *phones):
        timer_shows(screen, 3, 5)
    add_time(page)  # le rattrapage d'un clic malheureux
    for screen in (page, *phones):
        timer_shows(screen, 13, 15)

    # Échéance du premier créneau : 30 s, moins le temps retiré (environ 15), plus 10.
    end = 30 + added_seconds()
    assert 23 <= end <= 27, end
    jump_to(session, end - 3)
    for phone in phones:
        expect_slot(phone, 0)
    jump_to(session, end + 0.5)
    for phone in phones:
        expect_slot(phone, 1)
        timer_shows(phone, 28, 30)
    expect(card(page, 1).get_by_role("heading")).to_have_text("Couleur du ciel ?", timeout=LIVE_MS)
    expect(end_slot_button(page)).to_be_visible()  # de nouveau disponible, pour ce créneau
    # Les créneaux suivants gardent leur durée : avancés d'autant.
    jump_to(session, end + 27)
    for phone in phones:
        expect_slot(phone, 1)
    jump_to(session, end + 30.5)
    for phone in phones:
        expect_slot(phone, 2)
        timer_shows(phone, 28, 30)


@pytest.mark.spec("TPS-02")
def test_end_last_slot_ends_the_session_after_5_s(teacher_page: Page, live_server, new_phone):
    """Temps réel, dernier créneau : une réponse reste possible pendant les 5 s, puis la
    session se termine."""
    page = teacher_page
    session = make_live(1, shown=1)
    (phone,) = started(page, live_server.url, new_phone, session, ["00123"])
    jump_to(session, 10)
    timer_shows(page, 18, 20)
    end_slot(page)
    confirmed = time.monotonic()
    timer_shows(page, 3, 5)
    timer_shows(phone, 3, 5)
    choose(phone, phone_choices(phone)[0])
    expect(save_status(phone)).to_have_text(SAVED)
    for screen in (page, phone):
        expect(screen.get_by_role("main")).to_contain_text("Session terminée", timeout=10_000)
    assert time.monotonic() - confirmed <= 5 + WALL + LIVE_MS / 1000
    expect(end_slot_button(page)).to_have_count(0)  # pas après la fin


@pytest.mark.spec("TPS-02")
def test_end_slot_changes_nothing_with_5_s_left(teacher_page: Page, live_server, new_phone):
    page = teacher_page
    session = make_live(2, shown=1)
    (phone,) = started(page, live_server.url, new_phone, session, ["00123"])

    # 4 s restantes : rien ne change.
    jump_to(session, 26)
    timer_shows(page, 2, 4)
    end_slot_button(page).click()
    with page.expect_response(re.compile(r"/terminer/$")):
        confirm_button(page).click()
    assert added_seconds() == 0  # ni retiré, ni ajouté pour remonter à 5 s
    jump_to(session, 30.5)
    expect_slot(phone, 1)
    timer_shows(phone, 28, 30)


@pytest.mark.spec("TPS-02")
def test_end_slot_after_the_slot_changes_nothing(teacher_page: Page, live_server, new_phone):
    """Le tableau n'a pas encore vu la fin du créneau quand l'enseignant confirme : rien n'est
    retiré, ni au créneau fini ni au suivant (comme TPS-01)."""
    page = teacher_page
    session = make_live(2, shown=1)
    (phone,) = started(page, live_server.url, new_phone, session, ["00123"])
    timer_shows(page, 28, 30)
    page.route(re.compile(r".*/etat/$"), lambda route: route.abort())  # tableau figé
    jump_to(session, 30.5)
    expect_slot(phone, 1)

    end_slot(page)
    expect(page.get_by_role("status")).to_contain_text("Créneau terminé")
    expect(card(page, 1).get_by_role("heading")).to_have_text("Couleur du ciel ?")
    timer_shows(page, 27, 29)
    expect_slot(phone, 1)
    timer_shows(phone, 27, 29)
    assert not Extension.objects.exists()


# --- DER-04 : « k / n ont répondu » ---------------------------------------------------------


@pytest.mark.spec("DER-04")
def test_answered_count_for_the_current_slot(teacher_page: Page, live_server, new_phone):
    """n : les connectés (2 sur un groupe de 3) ; k : ceux dont la réponse à leur question du
    créneau est enregistrée. Une réponse effacée ne compte plus ; le créneau suivant repart
    de 0. Le décompte suit sans recharger le tableau."""
    page = teacher_page
    session = make_live(2, shown=1)
    a, b = phones_joined(new_phone, live_server.url, session.code, ["DURAND Élise", "MARTIN Léo"])
    open_board(page, live_server.url, session)
    expect(answered(page)).to_have_count(0)  # pas avant le démarrage
    start(page)
    expect(answered(page)).to_have_text("0 / 2 ont répondu")
    page.evaluate("window.sameBoard = true")

    expect_slot(a, 0)
    choose(a, phone_choices(a)[0])
    expect(save_status(a)).to_have_text(SAVED)
    expect(answered(page)).to_have_text("1 / 2 ont répondu", timeout=LIVE_MS)
    clear_answer(a)
    expect(save_status(a)).to_have_text(CLEARED)
    expect(answered(page)).to_have_text("0 / 2 ont répondu", timeout=LIVE_MS)
    for phone in (a, b):
        choose(phone, phone_choices(phone)[1])
        expect(save_status(phone)).to_have_text(SAVED)
    expect(answered(page)).to_have_text("2 / 2 ont répondu", timeout=LIVE_MS)
    assert page.evaluate("window.sameBoard === true")

    # Créneau suivant : les réponses du premier ne comptent pas.
    jump_to(session, 30.5)
    expect_slot(b, 1)
    expect(answered(page)).to_have_text("0 / 2 ont répondu", timeout=LIVE_MS)
    choose(b, phone_choices(b)[0])
    expect(save_status(b)).to_have_text(SAVED)
    expect(answered(page)).to_have_text("1 / 2 ont répondu", timeout=LIVE_MS)
    jump_to(session, 60.5)
    expect(page.get_by_role("main")).to_contain_text("Session terminée", timeout=LIVE_MS)
    expect(answered(page)).to_have_count(0)
