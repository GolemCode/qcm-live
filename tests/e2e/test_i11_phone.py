"""Incrément 11 : refonte du téléphone (direction « Signalétique ») et réseau lent.

- ETU-10 : « Envoi en cours… » jusqu'à la confirmation, renvoi automatique chaque seconde tant
  que le créneau dure, réponse non enregistrée signalée sur le moment ou à l'écran suivant,
  trace des envois gardée par le navigateur.
- ETU-11 : « Connexion perdue » après 3 secondes sans réponse du serveur.
- FIN-02 : message de fin selon ce que le serveur a confirmé.
- VIS-04 : bandeau, attente, déroulement, cibles tactiles, largeur.
- ACC-02 : axe-core, contraste et clavier dans tous les états du téléphone.

Le réseau du téléphone est simulé par Playwright (`Network`) : requêtes coupées, retenues, ou
perdues au retour (le serveur les reçoit, le téléphone ne voit pas la réponse).
"""

from __future__ import annotations

import contextlib
import io
import itertools
import re
import time
from collections.abc import Callable, Iterator
from typing import cast

import pytest
from PIL import Image
from playwright.sync_api import Error, FloatRect, Locator, Page, Route, ViewportSize, expect

from bank.models import Quiz
from live.models import Answer, Session
from live.views import CLEARED, SAVED, TOO_LATE
from roster.models import StudentGroup
from tests.e2e.a11y import axe_violations, contrast, keyboard_problems, low_contrasts
from tests.e2e.conftest import assert_fits_width
from tests.e2e.live_setup import STUDENTS, expect_slot, make_live, open_board, started
from tests.e2e.live_ui import (
    LIVE_MS,
    SIGNAL,
    add_time,
    background,
    choose,
    clear_answer,
    enter_code,
    expect_time_bar,
    identify,
    identity,
    phone_choices,
    phone_color,
    phones_joined,
    save_status,
    start,
    time_bar,
    timer,
)
from tests.factories import jump_to, make_group, make_question, make_quiz, make_session

SENDING = "Envoi en cours…"
PREVIOUS_LOST = "Votre réponse précédente n'a pas été enregistrée."
OFFLINE = "Connexion perdue"
OVER = "Session terminée."
TRANSMITTED = "Vos réponses ont été transmises à l'enseignant."


def not_transmitted(n: int) -> str:
    if n == 1:
        return "1 réponse n'a pas pu être transmise : signalez-le à l'enseignant."
    return f"{n} réponses n'ont pas pu être transmises : signalez-le à l'enseignant."


ANSWERS = re.compile(r"/s/\d{6}/reponse/$")  # envoi d'une réponse
EVERYTHING = re.compile(r"/s/\d{6}/")  # tout ce que le téléphone demande à la session

CAPITAL = "Capitale de la France ?"
SKY = "Couleur du ciel ?"


class Network:
    """Réseau du téléphone `phone` pour les adresses `url` : coupé (`cut`), sans réponse
    (`hold`), ou perdu au retour (`lose`). `restore` le rétablit (toute interception du
    téléphone cesse), et relâche les requêtes retenues. `posts` donne l'heure de chaque envoi
    de réponse intercepté."""

    def __init__(self, phone: Page, url: re.Pattern[str]) -> None:
        self.phone = phone
        self.url = re.compile(f".*{url.pattern}")
        self.posts: list[float] = []
        self.held: list[Route] = []

    def _seen(self, route: Route) -> None:
        if ANSWERS.search(route.request.url):
            self.posts.append(time.monotonic())

    def cut(self) -> None:
        def handler(route: Route) -> None:
            self._seen(route)
            route.abort()

        self.phone.route(self.url, handler)

    def hold(self) -> None:
        def handler(route: Route) -> None:
            self._seen(route)
            self.held.append(route)

        self.phone.route(self.url, handler)

    def lose(self) -> None:
        def handler(route: Route) -> None:
            self._seen(route)
            route.fetch()  # le serveur reçoit la requête et répond…
            route.abort()  # … mais la réponse n'arrive jamais au téléphone

        self.phone.route(self.url, handler)

    def release(self) -> None:
        """Relâche les requêtes retenues."""
        for route in self.held:
            with contextlib.suppress(Error):  # requête déjà abandonnée par la page
                route.continue_()
        self.held.clear()

    def restore(self) -> None:
        self.release()
        # Attendre la fin des interceptions en cours : aucune ne doit survivre au test. Une
        # requête encore retenue par un autre `Network` du même téléphone ferait attendre sans
        # fin : la fixture `networks` les relâche toutes d'abord.
        self.phone.unroute_all(behavior="wait")


@pytest.fixture
def networks() -> Iterator[Callable[[Page, re.Pattern[str]], Network]]:
    """Fabrique de `Network`, rétablis à la fin du test."""
    made: list[Network] = []

    def make(phone: Page, url: re.Pattern[str]) -> Network:
        made.append(Network(phone, url))
        return made[-1]

    yield make
    for network in made:  # d'abord toutes les requêtes retenues, puis les interceptions
        network.release()
    for network in made:
        network.restore()


def recorded(session: Session, number: str) -> dict[str, list[str]]:
    """Réponses enregistrées par le serveur pour l'étudiant `number` : texte des propositions
    choisies, par énoncé."""
    questions = Session.objects.get(pk=session.pk).questions
    found = {}
    for answer in Answer.objects.filter(participant__session=session, participant__number=number):
        question = questions[answer.question]
        found[question["text"]] = sorted(question["choices"][i]["text"] for i in answer.choices)
    return found


def wait_recorded(screen: Page, session: Session, number: str, expected: dict) -> None:
    for _ in range(LIVE_MS // 50):
        if recorded(session, number) == expected:
            return
        screen.wait_for_timeout(50)
    assert recorded(session, number) == expected


def watch_status(phone: Page) -> None:
    """Note chaque texte que prend l'état de l'envoi, jusqu'au prochain chargement de la page."""
    phone.evaluate(
        """() => {
          const el = document.querySelector("[role=status]");
          window.seenStatus = [el.textContent];
          new MutationObserver(() => window.seenStatus.push(el.textContent))
            .observe(el, { childList: true, characterData: true, subtree: true });
        }"""
    )


def statuses(phone: Page) -> list[str]:
    return [text.strip() for text in phone.evaluate("window.seenStatus")]


def offline_alert(phone: Page) -> Locator:
    return phone.get_by_role("alert").filter(has_text=OFFLINE)


def expect_back_online(phone: Page) -> None:
    """Plus d'alerte : ni le texte, ni le bandeau, même vide."""
    expect(offline_alert(phone)).to_have_count(0, timeout=LIVE_MS)
    expect(phone.locator(".offline")).to_be_hidden()


def end_message(phone: Page) -> Locator:
    return phone.get_by_role("main")


# --- ETU-10 : réseau lent -----------------------------------------------------------------


@pytest.mark.spec("ETU-10")
def test_slow_network_says_sending_until_confirmed(
    teacher_page: Page, live_server, new_phone, networks
):
    session = make_live(1, shown=1)
    (phone,) = started(teacher_page, live_server.url, new_phone, session, ["00123"])
    expect_slot(phone, 0)
    watch_status(phone)
    network = networks(phone, ANSWERS)
    network.hold()  # le serveur ne répond pas encore

    choose(phone, "Paris")
    expect(save_status(phone)).to_have_text(SENDING)
    choose(phone, "Lyon")  # changé avant la confirmation : c'est la dernière qui compte
    phone.wait_for_timeout(1_500)
    expect(save_status(phone)).to_have_text(SENDING)
    assert recorded(session, "00123") == {}

    network.restore()
    expect(save_status(phone)).to_have_text(SAVED)
    wait_recorded(phone, session, "00123", {CAPITAL: ["Lyon"]})
    # « Réponse enregistrée » n'est apparu qu'une fois, à la confirmation de la dernière réponse,
    # et non à celle de « Paris ».
    seen = statuses(phone)
    assert seen.count(SAVED) == 1 and seen[-1] == SAVED, seen
    expect(phone.get_by_label("Lyon", exact=True)).to_be_checked()


@pytest.mark.spec("ETU-10")
@pytest.mark.spec("FIN-02")
def test_confirmation_of_a_replaced_answer_confirms_nothing(
    teacher_page: Page, live_server, new_phone, networks
):
    """L'étudiant change d'avis pendant un envoi lent : « Paris » arrive et sa confirmation
    revient, mais « Lyon », la dernière réponse, n'arrive jamais. La confirmation de « Paris »
    ne vaut pas pour « Lyon » : non enregistrée à l'échéance, non transmise à la fin."""
    session = make_live(1, shown=1)
    (phone,) = started(teacher_page, live_server.url, new_phone, session, ["00123"])
    expect_slot(phone, 0)
    jump_to(session, 21)
    expect(timer(phone)).to_have_text(re.compile(r"^0:0[7-9]$"), timeout=LIVE_MS)
    watch_status(phone)
    # L'état du direct se perd aussi : le téléphone reste sur ce créneau, et on lit ce qu'il
    # y affiche à l'échéance.
    networks(phone, re.compile(r"/s/\d{6}/etat/$")).cut()
    network = networks(phone, ANSWERS)
    network.hold()

    choose(phone, "Paris")
    for _ in range(40):
        if network.held:
            break
        phone.wait_for_timeout(50)
    choose(phone, "Lyon")  # « Paris » est encore en route
    network.held.pop().continue_()  # seul « Paris » passe ; « Lyon » reste bloqué
    wait_recorded(phone, session, "00123", {CAPITAL: ["Paris"]})

    expect(save_status(phone)).to_have_text(TOO_LATE, timeout=14_000)
    assert SAVED not in statuses(phone)
    network.restore()
    jump_to(session, 31)
    expect(end_message(phone)).to_contain_text(not_transmitted(1), timeout=LIVE_MS + 1_000)
    expect(phone.get_by_text(TRANSMITTED)).to_have_count(0)
    assert recorded(session, "00123") == {CAPITAL: ["Paris"]}


@pytest.mark.spec("ETU-10")
@pytest.mark.spec("FIN-02")
def test_send_trace_belongs_to_one_session(teacher_page: Page, live_server, new_phone, networks):
    """Le même téléphone sert à deux sessions dans la journée : un envoi en attente dans la
    première n'est ni repris ni compté dans la seconde."""
    first = make_live(1, shown=1)
    phone = new_phone()
    started(teacher_page, live_server.url, lambda: phone, first, ["00123"])
    expect_slot(phone, 0)
    network = networks(phone, ANSWERS)
    network.cut()
    choose(phone, "Paris")
    expect(save_status(phone)).to_have_text(SENDING)  # jamais confirmé

    second = make_session(
        Quiz.objects.get(title="Contrôle"), StudentGroup.objects.get(name="TD1"), shown=1
    )
    started(teacher_page, live_server.url, lambda: phone, second, ["00123"])
    expect_slot(phone, 0)
    phone.wait_for_timeout(1_000)
    for label in phone_choices(phone):
        expect(phone.get_by_label(label, exact=True)).not_to_be_checked()
    expect(save_status(phone)).to_have_text("")
    network.restore()
    jump_to(second, 31)
    expect(end_message(phone)).to_have_text(
        re.compile(r"^\s*Session terminée\.\s*$"), timeout=LIVE_MS + 1_000
    )
    phone.wait_for_timeout(1_000)
    expect(end_message(phone)).to_have_text(re.compile(r"^\s*Session terminée\.\s*$"))


@pytest.mark.spec("ETU-10")
def test_failed_send_is_retried_every_second(teacher_page: Page, live_server, new_phone, networks):
    session = make_live(1, shown=1)
    (phone,) = started(teacher_page, live_server.url, new_phone, session, ["00123"])
    expect_slot(phone, 0)
    network = networks(phone, ANSWERS)
    network.cut()

    choose(phone, "Paris")
    expect(save_status(phone)).to_have_text(SENDING)
    phone.wait_for_timeout(3_200)
    expect(save_status(phone)).to_have_text(SENDING)
    posts = list(network.posts)
    assert 3 <= len(posts) <= 5, posts  # le premier envoi, puis un par seconde
    gaps = [b - a for a, b in itertools.pairwise(posts)]
    assert all(gap >= 0.7 for gap in gaps), gaps
    assert recorded(session, "00123") == {}

    network.restore()  # sans rien toucher, la réponse finit par passer
    expect(save_status(phone)).to_have_text(SAVED, timeout=LIVE_MS)
    wait_recorded(phone, session, "00123", {CAPITAL: ["Paris"]})


@pytest.mark.spec("ETU-10")
@pytest.mark.spec("FIN-02")
@pytest.mark.spec("ACC-02")  # état verrouillé à l'échéance
def test_answer_lost_at_the_deadline_is_reported(
    teacher_page: Page, live_server, new_phone, networks
):
    """Le téléphone perd tout le réseau avant l'échéance : il le dit sur le moment, puis à
    l'écran suivant, puis à la fin."""
    session = make_live(2, shown=1)
    (phone,) = started(teacher_page, live_server.url, new_phone, session, ["00123"])
    expect_slot(phone, 0)
    jump_to(session, 25)
    expect(timer(phone)).to_have_text(re.compile(r"^0:0[3-5]$"), timeout=LIVE_MS)
    watch_status(phone)
    network = networks(phone, EVERYTHING)
    network.cut()

    choose(phone, "Paris")
    expect(save_status(phone)).to_have_text(SENDING)
    # À l'échéance, le téléphone, toujours sur ce créneau, dit que la réponse est perdue.
    expect(save_status(phone)).to_have_text(TOO_LATE, timeout=7_000)
    expect(phone.locator("body")).to_have_attribute("data-page", "running:0")
    # Les propositions sont verrouillées : aucun autre choix ne peut partir ni être compté.
    for label in phone_choices(phone):
        expect(phone.get_by_label(label, exact=True)).to_be_disabled()
    expect(phone.get_by_role("button", name="Effacer ma réponse")).to_be_disabled()
    assert_accessible(phone, "échéance, propositions verrouillées")
    sent = len(network.posts)
    phone.wait_for_timeout(2_000)
    assert len(network.posts) == sent, "renvoi après la fin du créneau"
    assert SAVED not in statuses(phone)
    assert recorded(session, "00123") == {}

    # Le réseau revient : l'écran suivant le rappelle.
    network.restore()
    expect_slot(phone, 1, timeout=LIVE_MS + 1_000)
    expect(phone.get_by_text(PREVIOUS_LOST, exact=True)).to_be_visible(timeout=LIVE_MS)
    choose(phone, "Bleu")
    expect(save_status(phone)).to_have_text(SAVED)

    jump_to(session, 61)
    expect(end_message(phone)).to_contain_text(OVER, timeout=LIVE_MS)
    expect(end_message(phone)).to_contain_text(not_transmitted(1), timeout=LIVE_MS)
    expect(phone.get_by_text(TRANSMITTED)).to_have_count(0)


@pytest.mark.spec("ETU-10")
@pytest.mark.spec("FIN-02")
def test_answer_received_without_confirmation_counts(
    teacher_page: Page, live_server, new_phone, networks
):
    """Le serveur enregistre la réponse, mais sa confirmation se perd : le téléphone ne l'affiche
    pas comme enregistrée, puis apprend du serveur, à l'échéance, qu'elle est arrivée à temps.
    L'état du direct se perd aussi : le téléphone reste sur ce créneau, et on lit ce qu'il y
    affiche à l'échéance."""
    session = make_live(2, shown=1)
    (phone,) = started(teacher_page, live_server.url, new_phone, session, ["00123"])
    expect_slot(phone, 0)
    jump_to(session, 24)
    # Le compte à rebours doit s'être recalé avant que l'état du direct ne se perde.
    expect(timer(phone)).to_have_text(re.compile(r"^0:0[4-6]$"), timeout=LIVE_MS)
    watch_status(phone)
    network = networks(phone, re.compile(r"/s/\d{6}/(reponse|etat)/$"))
    network.lose()

    choose(phone, "Paris")
    wait_recorded(phone, session, "00123", {CAPITAL: ["Paris"]})
    phone.wait_for_timeout(1_000)
    expect(save_status(phone)).to_have_text(SENDING)
    assert SAVED not in statuses(phone)

    # À l'échéance, toujours sur ce créneau : le serveur dit l'avoir reçue.
    expect(save_status(phone)).to_have_text(SAVED, timeout=8_000)
    expect(phone.locator("body")).to_have_attribute("data-page", "running:0")
    assert TOO_LATE not in statuses(phone)

    network.restore()
    expect_slot(phone, 1, timeout=LIVE_MS + 1_000)
    phone.wait_for_timeout(1_500)  # le temps de demander au serveur ce qu'il a enregistré
    expect(phone.get_by_text(PREVIOUS_LOST)).to_have_count(0)
    choose(phone, "Bleu")
    expect(save_status(phone)).to_have_text(SAVED)

    jump_to(session, 61)
    expect(end_message(phone)).to_contain_text(TRANSMITTED, timeout=LIVE_MS)
    wait_recorded(phone, session, "00123", {CAPITAL: ["Paris"], SKY: ["Bleu"]})


@pytest.mark.spec("ETU-10")
@pytest.mark.spec("FIN-02")
def test_next_screen_and_end_ask_the_server(teacher_page: Page, live_server, new_phone, networks):
    """La réponse arrive au serveur, sa confirmation se perd, puis tout le réseau tombe avant
    l'échéance : le téléphone ne peut rien savoir sur le moment. Le réseau revenu, l'écran
    suivant (premier créneau), puis la fin (dernier créneau) demandent au serveur, et ne
    signalent aucune perte."""
    session = make_live(2, shown=1)
    (phone,) = started(teacher_page, live_server.url, new_phone, session, ["00123"])

    for slot, (choice, recorded_so_far) in enumerate(
        [("Paris", {CAPITAL: ["Paris"]}), ("Bleu", {CAPITAL: ["Paris"], SKY: ["Bleu"]})]
    ):
        expect_slot(phone, slot, timeout=LIVE_MS + 1_000)
        jump_to(session, 30 * slot + 24)
        expect(timer(phone)).to_have_text(re.compile(r"^0:0[4-6]$"), timeout=LIVE_MS)
        lost = networks(phone, ANSWERS)
        lost.lose()
        choose(phone, choice)
        wait_recorded(phone, session, "00123", recorded_so_far)
        lost.restore()
        down = networks(phone, EVERYTHING)
        down.cut()
        expect(save_status(phone)).to_have_text(TOO_LATE, timeout=8_000)  # il ne peut savoir
        if slot == 1:
            jump_to(session, 61)  # la session se termine pendant la coupure
        down.restore()
        if slot == 0:
            expect_slot(phone, 1, timeout=LIVE_MS + 1_000)
            phone.wait_for_timeout(1_500)  # le temps de demander au serveur
            expect(phone.get_by_text(PREVIOUS_LOST)).to_have_count(0)

    expect(end_message(phone)).to_contain_text(TRANSMITTED, timeout=LIVE_MS + 1_000)
    expect(end_message(phone)).not_to_contain_text("pas pu être transmise")


@pytest.mark.spec("ETU-10")
@pytest.mark.spec("FIN-02")
def test_refused_storage_still_reports_on_the_moment(
    teacher_page: Page, live_server, new_phone, networks
):
    """Stockage local refusé (navigation privée stricte, mémoire pleine) : le créneau affiché
    dit quand même que la réponse est perdue ; la fin, sans trace, n'affirme rien."""
    session = make_live(1, shown=1)
    phone = new_phone()
    phone.add_init_script("Storage.prototype.setItem = () => { throw new Error('plein'); };")
    (phone,) = started(teacher_page, live_server.url, lambda: phone, session, ["00123"])
    expect_slot(phone, 0)
    jump_to(session, 25)
    expect(timer(phone)).to_have_text(re.compile(r"^0:0[3-5]$"), timeout=LIVE_MS)
    network = networks(phone, EVERYTHING)
    network.cut()
    choose(phone, "Paris")
    expect(save_status(phone)).to_have_text(SENDING)
    expect(save_status(phone)).to_have_text(TOO_LATE, timeout=7_000)
    network.restore()
    expect(end_message(phone)).to_have_text(
        re.compile(r"^\s*Session terminée\.\s*$"), timeout=LIVE_MS + 1_000
    )
    phone.wait_for_timeout(1_000)
    expect(end_message(phone)).to_have_text(re.compile(r"^\s*Session terminée\.\s*$"))


@pytest.mark.spec("ETU-10")
def test_reloaded_phone_resumes_a_pending_answer(
    teacher_page: Page, live_server, new_phone, networks
):
    session = make_live(1, shown=1)
    (phone,) = started(teacher_page, live_server.url, new_phone, session, ["00123"])
    expect_slot(phone, 0)
    choose(phone, "Paris")
    expect(save_status(phone)).to_have_text(SAVED)
    network = networks(phone, ANSWERS)
    network.cut()
    choose(phone, "Lyon")
    expect(save_status(phone)).to_have_text(SENDING)

    phone.reload()  # la page se recharge ; l'envoi de « Lyon » est toujours en attente
    expect(phone.get_by_label("Lyon", exact=True)).to_be_checked()
    expect(phone.get_by_label("Paris", exact=True)).not_to_be_checked()
    expect(save_status(phone)).to_have_text(SENDING)
    assert recorded(session, "00123") == {CAPITAL: ["Paris"]}

    network.restore()
    expect(save_status(phone)).to_have_text(SAVED, timeout=LIVE_MS)
    wait_recorded(phone, session, "00123", {CAPITAL: ["Lyon"]})
    # Sans envoi en attente, un rechargement réaffiche la réponse enregistrée (ETU-07).
    phone.reload()
    expect(phone.get_by_label("Lyon", exact=True)).to_be_checked()
    expect(save_status(phone)).to_have_text("")


# --- ETU-11 : perte de connexion ----------------------------------------------------------


@pytest.mark.spec("ETU-11")
def test_connection_lost_after_three_seconds(teacher_page: Page, live_server, new_phone, networks):
    session = make_live(1, shown=1)
    (phone,) = phones_joined(new_phone, live_server.url, session.code, ["00123"])
    phone.wait_for_timeout(1_500)  # le téléphone suit le direct
    expect(offline_alert(phone)).to_have_count(0)

    # En attente : plus de réseau du tout. L'alerte paraît 3 s après la dernière réponse du
    # serveur, mesurées dans la page (l'alerte est vérifiée tous les quarts de seconde).
    phone.evaluate(
        """() => {
          const alert = document.querySelector("[role=alert]");
          new MutationObserver(() => {
            if (!alert.hidden && window.lostAfter === undefined)
              window.lostAfter = performance.now() - window.qcm.lastContact;
          }).observe(alert, { attributes: true });
        }"""
    )
    phone.context.set_offline(True)
    phone.wait_for_timeout(1_500)
    expect(offline_alert(phone)).to_have_count(0)  # pas avant 3 secondes
    expect(offline_alert(phone)).to_be_visible(timeout=3_000)
    lost_after = phone.evaluate("window.lostAfter")
    assert 3_000 <= lost_after <= 3_400, lost_after
    phone.context.set_offline(False)
    expect_back_online(phone)

    # En déroulement : un réseau qui ne répond plus, sans erreur.
    open_board(teacher_page, live_server.url, session)
    start(teacher_page)
    expect_slot(phone, 0)
    phone.wait_for_timeout(1_000)
    network = networks(phone, EVERYTHING)
    network.hold()
    phone.wait_for_timeout(1_500)
    expect(offline_alert(phone)).to_have_count(0)
    expect(offline_alert(phone)).to_be_visible(timeout=3_000)
    network.restore()
    expect_back_online(phone)


# --- FIN-02 : message de fin ----------------------------------------------------------------


@pytest.mark.spec("FIN-02")
def test_end_counts_the_answers_not_transmitted(
    teacher_page: Page, live_server, new_phone, networks
):
    """Une réponse par créneau : la dernière donnée. Premier créneau, « Paris » est confirmé
    puis remplacé par « Lyon », jamais transmis ; deuxième, rien ne passe ; troisième, aucune
    réponse."""
    session = make_live(3, shown=1)
    (phone,) = started(teacher_page, live_server.url, new_phone, session, ["00123"])
    expect_slot(phone, 0)
    choose(phone, "Paris")
    expect(save_status(phone)).to_have_text(SAVED)
    network = networks(phone, ANSWERS)
    network.cut()
    choose(phone, "Lyon")
    expect(save_status(phone)).to_have_text(SENDING)

    jump_to(session, 32)
    expect_slot(phone, 1)
    expect(phone.get_by_text(PREVIOUS_LOST, exact=True)).to_be_visible(timeout=LIVE_MS)
    choose(phone, "Bleu")
    expect(save_status(phone)).to_have_text(SENDING)
    jump_to(session, 62)
    expect_slot(phone, 2)

    jump_to(session, 91)
    expect(end_message(phone)).to_contain_text(OVER, timeout=LIVE_MS)
    expect(end_message(phone)).to_contain_text(not_transmitted(2), timeout=LIVE_MS)
    expect(phone.get_by_text(TRANSMITTED)).to_have_count(0)
    phone.reload()
    expect(end_message(phone)).to_contain_text(not_transmitted(2), timeout=LIVE_MS)
    assert recorded(session, "00123") == {CAPITAL: ["Paris"]}


@pytest.mark.spec("FIN-02")
def test_end_affirms_nothing_it_cannot_know(teacher_page: Page, live_server, new_phone):
    """Aucune réponse donnée (rien choisi, ou tout effacé), ou trace des envois perdue :
    « Session terminée. » seulement."""
    session = make_live(1, shown=1)
    silent, forgetful, hesitant = started(
        teacher_page, live_server.url, new_phone, session, ["00123", "42", "7"]
    )
    expect_slot(forgetful, 0)
    choose(forgetful, phone_choices(forgetful)[0])
    expect(save_status(forgetful)).to_have_text(SAVED)
    forgetful.evaluate("() => localStorage.clear()")  # stockage effacé par le navigateur
    choose(hesitant, phone_choices(hesitant)[0])
    expect(save_status(hesitant)).to_have_text(SAVED)
    clear_answer(hesitant)
    expect(save_status(hesitant)).to_have_text(CLEARED)

    jump_to(session, 31)
    for phone in (silent, forgetful, hesitant):
        expect(end_message(phone)).to_have_text(re.compile(r"^\s*Session terminée\.\s*$"))
        phone.wait_for_timeout(1_000)  # rien n'est ajouté ensuite
        expect(end_message(phone)).to_have_text(re.compile(r"^\s*Session terminée\.\s*$"))


# --- VIS-04 : présentation du téléphone -----------------------------------------------------

INK_CSS = "rgb(17, 17, 17)"  # l'encre, telle que la donne getComputedStyle
WHITE_CSS = "rgb(255, 255, 255)"
LONG_NAME = ("2190031", "DE LA FONTAINE-MARCHAND Marie-Charlotte")
SMALL_PHONE = ViewportSize(width=360, height=740)
LONG_CHOICES = [
    (
        f"Proposition {i} : une réponse plutôt longue, qui tient sur plusieurs lignes même sur "
        "un téléphone, pour obliger la page à défiler",
        i == 1,
    )
    for i in range(1, 8)
] + [("Anticonstitutionnellementextraordinairementinterminable", False)]


def style(locator: Locator, prop: str) -> str:
    return locator.evaluate("(e, p) => getComputedStyle(e)[p]", prop)


def box(locator: Locator) -> FloatRect:
    found = locator.bounding_box()
    assert found, locator
    return found


def assert_bar_stands_out(phone: Page) -> None:
    """La barre du temps se détache du fond de la page, même sur la couleur 1, jaune comme
    elle : sous sa partie jaune, un filet contraste d'au moins 3:1 avec ce jaune (WCAG 1.4.11).
    Mesuré sur une capture, dans la partie encore pleine de la barre."""
    bar = box(time_bar(phone))
    clip = FloatRect(x=bar["x"] + 4, y=bar["y"], width=1, height=bar["height"] + 6)
    image = Image.open(io.BytesIO(phone.screenshot(clip=clip))).convert("RGB")
    column = [cast(tuple[int, int, int], image.getpixel((0, y))) for y in range(image.height)]
    yellow = [contrast(pixel, SIGNAL) < 1.2 for pixel in column]
    start = yellow.index(True)  # haut de la partie jaune de la barre
    end = yellow.index(False, start) if False in yellow[start:] else len(yellow)
    # Sous la barre, avant le fond de la page (jaune lui aussi sur la couleur 1) : le filet.
    below = column[end : end + 12]
    assert below and any(contrast(pixel, SIGNAL) >= 3 for pixel in below), column


def band(phone: Page) -> Locator:
    return phone.get_by_role("banner")


def expect_band_code(phone: Page, code: str) -> None:
    """Bandeau noir : « QCM Live » et le code de session, groupé par trois."""
    expect(band(phone)).to_contain_text("QCM Live")
    expect(band(phone).get_by_role("heading", name=f"Session {code}", level=1)).to_be_visible()
    groups = band(phone).get_by_text(re.compile(r"^\d{3}$"))
    expect(groups).to_have_text([code[:3], code[3:]])
    assert background(band(phone)) == INK_CSS


TARGETS = (
    "button, input:not([type=hidden]):not([type=radio]):not([type=checkbox]), select, textarea, "
    "label:has(input[type=radio]), label:has(input[type=checkbox])"
)


def assert_phone_layout(phone: Page, where: str) -> None:
    """Cibles tactiles d'au moins 48 px, et aucun défilement horizontal, en Pixel 7 comme sur un
    petit téléphone de 360 px de large."""
    phone.wait_for_load_state("load")
    pixel = phone.viewport_size
    assert pixel
    for size in (pixel, SMALL_PHONE):
        phone.set_viewport_size(size)
        assert_fits_width(phone, mobile=True)
        small = phone.evaluate(
            """(selector) => [...document.querySelectorAll(selector)]
                .filter(e => e.checkVisibility())
                .map(e => [e.textContent.trim().slice(0, 30) || e.name, e.getBoundingClientRect()])
                .filter(([, r]) => r.width < 48 || r.height < 48)
                .map(([n, r]) => `${n} : ${Math.round(r.width)} x ${Math.round(r.height)}`)""",
            TARGETS,
        )
        assert small == [], (where, size, small)
    phone.set_viewport_size(pixel)


@pytest.mark.spec("VIS-04")
def test_phone_band_and_waiting_screen(live_server, new_phone):
    session = make_live(1, shown=1, students=[*STUDENTS, LONG_NAME])
    phone = new_phone()
    phone.goto(f"{live_server.url}/")
    expect(band(phone)).to_have_text(re.compile(r"^\s*QCM Live\s*$"))  # session pas encore connue
    assert background(band(phone)) == INK_CSS
    assert_phone_layout(phone, "saisie du code")

    enter_code(phone, live_server.url, session.code)
    expect_band_code(phone, session.code)
    assert_phone_layout(phone, "saisie du numéro")
    identify(phone, "123")  # absent du groupe : refusé
    expect(phone.get_by_role("alert")).to_be_visible()
    assert_phone_layout(phone, "numéro refusé")

    identify(phone, LONG_NAME[0])
    expect_band_code(phone, session.code)
    main = phone.get_by_role("main")
    parts = [
        main.get_by_text("Vous êtes", exact=True),
        main.get_by_text(LONG_NAME[1], exact=True),
        main.get_by_text(LONG_NAME[0]),
        main.get_by_text("En attente du démarrage"),
    ]
    tops = [box(part)["y"] for part in parts]
    assert tops == sorted(tops), tops  # dans cet ordre, de haut en bas
    name = parts[1]
    assert float(style(name, "fontSize").removesuffix("px")) >= 28  # le nom en grand
    assert int(style(name, "fontWeight")) >= 700
    expect(identity(phone)).to_have_text(f"Vous êtes {LONG_NAME[1]}")
    assert_phone_layout(phone, "attente")


@pytest.mark.spec("VIS-04")
def test_running_phone_layout(teacher_page: Page, live_server, new_phone, networks):
    quiz = make_quiz("Long", [make_question("Question longue ?", LONG_CHOICES)])
    session = make_session(quiz, make_group("TD1", [*STUDENTS, LONG_NAME]), shown=1)
    (phone,) = started(teacher_page, live_server.url, new_phone, session, [LONG_NAME[0]])
    expect_slot(phone, 0)
    expect_band_code(phone, session.code)

    # En haut : le numéro, la forme et « Couleur 1 », puis le temps restant et sa barre.
    assert phone_color(phone) == 1
    badge = phone.get_by_text("Couleur 1", exact=True)
    shape = phone.get_by_role("img", name="rond")
    expect(shape).to_be_visible()
    number = phone.locator("main p").filter(has_text="Couleur 1").get_by_text("1", exact=True)
    expect(number).to_be_visible()
    assert float(style(number, "fontSize").removesuffix("px")) >= 32  # le numéro, en grand
    choices = phone.get_by_role("group", name="Propositions").locator("label")
    expect(choices).to_have_count(8)
    assert box(badge)["y"] < box(choices.first)["y"]
    assert box(badge)["y"] < 0.25 * phone.viewport_size["height"]  # type: ignore[index]
    expect(timer(phone)).to_have_text(re.compile(r"^0:(2\d|30)$"))
    band_box, bar_box = box(band(phone)), box(time_bar(phone))
    assert abs(bar_box["y"] - (band_box["y"] + band_box["height"])) <= 2, (band_box, bar_box)
    expect_time_bar(phone, 30)
    assert_bar_stands_out(phone)
    jump_to(session, 15)
    expect(timer(phone)).to_have_text(re.compile(r"^0:1[3-5]$"), timeout=LIVE_MS)
    expect_time_bar(phone, 30)
    add_time(teacher_page)  # le téléphone ne recharge pas sa page : sa barre se recale
    expect(timer(phone)).to_have_text(re.compile(r"^0:2[3-5]$"), timeout=LIVE_MS)
    expect_time_bar(phone, 40)

    # La proposition choisie passe en noir plein, texte blanc ; les autres non.
    third = choices.nth(2)
    third.click()
    expect(save_status(phone)).to_have_text(SAVED)
    assert (background(third), style(third, "color")) == (INK_CSS, WHITE_CSS)
    for i in (0, 1, 3):
        assert background(choices.nth(i)) != INK_CSS, i
    # Elle suit la réponse : une autre choisie, puis plus aucune après l'effacement.
    choices.nth(1).click()
    expect(save_status(phone)).to_have_text(SAVED)
    assert [background(choices.nth(i)) == INK_CSS for i in range(8)] == [i == 1 for i in range(8)]
    clear_answer(phone)
    expect(save_status(phone)).to_have_text(CLEARED)
    assert not any(background(choices.nth(i)) == INK_CSS for i in range(8))
    third.click()
    expect(save_status(phone)).to_have_text(SAVED)

    # L'état de l'envoi et « Effacer ma réponse » restent en bas de l'écran pendant le défilement.
    status = save_status(phone)
    clear = phone.get_by_role("button", name="Effacer ma réponse")
    height = phone.viewport_size["height"]  # type: ignore[index]
    assert phone.evaluate("() => document.documentElement.scrollHeight > innerHeight + 200")
    for scroll in ("0", "document.documentElement.scrollHeight"):
        phone.evaluate(f"() => window.scrollTo(0, {scroll})")
        phone.wait_for_timeout(100)
        for item in (status, clear):
            expect(item).to_be_in_viewport(ratio=1)
            assert box(item)["y"] > 0.7 * height, (scroll, box(item))
    # En bas de la page, la dernière proposition n'est pas cachée par ces boutons.
    last = choices.last
    expect(last).to_be_in_viewport(ratio=1)
    assert box(last)["y"] + box(last)["height"] <= box(status)["y"] + 1

    # En pied : le nom et le numéro de l'étudiant.
    footer = phone.get_by_role("contentinfo")
    expect(footer).to_contain_text(LONG_NAME[1])
    expect(footer).to_contain_text(LONG_NAME[0])

    assert_phone_layout(phone, "déroulement")
    network = networks(phone, ANSWERS)
    network.hold()
    choices.nth(4).click()
    expect(status).to_have_text(SENDING)
    assert_phone_layout(phone, "envoi")
    network.restore()


@pytest.mark.spec("VIS-04")
def test_connection_lost_and_end_screens(teacher_page: Page, live_server, new_phone):
    quiz = make_quiz("Long", [make_question("Question longue ?", LONG_CHOICES)])
    session = make_session(quiz, make_group("TD1", [*STUDENTS, LONG_NAME]), shown=1)
    (phone,) = started(teacher_page, live_server.url, new_phone, session, [LONG_NAME[0]])
    expect_slot(phone, 0)
    phone.context.set_offline(True)
    expect(offline_alert(phone)).to_be_visible(timeout=5_000)
    expect(offline_alert(phone)).to_be_in_viewport(ratio=1)
    # L'alerte reste à l'écran quand les propositions font défiler la page.
    phone.evaluate("() => window.scrollTo(0, document.documentElement.scrollHeight)")
    assert phone.evaluate("() => window.scrollY") > 200
    expect(offline_alert(phone)).to_be_in_viewport(ratio=1)
    assert_phone_layout(phone, "connexion perdue")
    phone.context.set_offline(False)

    jump_to(session, 31)
    expect(end_message(phone)).to_contain_text(OVER, timeout=LIVE_MS + 1_000)
    expect_band_code(phone, session.code)
    assert_phone_layout(phone, "fin")


# --- ACC-02 : accessibilité de tous les états du téléphone ----------------------------------


def assert_accessible(phone: Page, where: str) -> None:
    assert axe_violations(phone) == [], where
    assert low_contrasts(phone) == [], where
    assert keyboard_problems(phone) == [], where


@pytest.mark.spec("ACC-02")
def test_every_phone_state_is_accessible(teacher_page: Page, live_server, new_phone, networks):
    base = live_server.url
    students = [(f"10{i}", f"ÉTUDIANT {i}") for i in range(1, 7)]
    questions = [
        make_question(f"Q{i} ?", [(f"Choix {i}{c}", c == "a") for c in "abc"], multiple=i in (2, 5))
        for i in range(1, 7)
    ]
    session = make_session(
        make_quiz("Six", questions), make_group("TD6", students), shown=6, seconds=30
    )

    phone = new_phone()
    phone.goto(f"{base}/")
    assert_accessible(phone, "saisie du code")
    phone.get_by_label("Code de session").fill("000000")
    phone.get_by_role("button", name="Rejoindre").click()
    expect(phone.get_by_role("alert")).to_be_visible()
    assert_accessible(phone, "code refusé")
    enter_code(phone, base, session.code)
    assert_accessible(phone, "saisie du numéro")
    identify(phone, "999")
    expect(phone.get_by_role("alert")).to_be_visible()
    assert_accessible(phone, "numéro refusé")
    identify(phone, students[0][0])
    expect(identity(phone)).to_be_visible()
    assert_accessible(phone, "attente")

    others = phones_joined(new_phone, base, session.code, [n for n, _ in students[1:]])
    open_board(teacher_page, base, session)
    start(teacher_page)
    phones = [phone, *others]
    colors = set()
    for screen in phones:  # les six couleurs, texte blanc sur le bleu compris
        expect_slot(screen, 0)
        colors.add(phone_color(screen))
        assert_accessible(screen, f"déroulement, couleur {phone_color(screen)}")
        assert_phone_layout(screen, "propositions courtes")  # 48 px même pour « Choix 1a »
    assert colors == set(range(1, 7))

    # Sur un téléphone à question simple : choisie, effacée, envoi, connexion perdue.
    simple = next(p for p in phones if p.get_by_role("radio").count())
    choose(simple, phone_choices(simple)[0])
    expect(save_status(simple)).to_have_text(SAVED)
    assert_accessible(simple, "réponse enregistrée")
    clear_answer(simple)
    expect(save_status(simple)).to_have_text(CLEARED)
    assert_accessible(simple, "réponse effacée")
    network = networks(simple, ANSWERS)
    network.hold()
    choose(simple, phone_choices(simple)[1])
    expect(save_status(simple)).to_have_text(SENDING)
    assert_accessible(simple, "envoi en cours")
    network.restore()
    expect(save_status(simple)).to_have_text(SAVED)

    multiple = next(p for p in phones if p.get_by_role("checkbox").count())
    choose(multiple, phone_choices(multiple)[0])
    expect(save_status(multiple)).to_have_text(SAVED)
    assert_accessible(multiple, "question multiple, case cochée")

    multiple.context.set_offline(True)
    expect(offline_alert(multiple)).to_be_visible(timeout=5_000)
    assert_accessible(multiple, "connexion perdue")
    multiple.context.set_offline(False)
    expect(offline_alert(multiple)).to_have_count(0, timeout=LIVE_MS)

    # Écran suivant après une réponse perdue, puis fin avec une réponse non transmise.
    network = networks(simple, ANSWERS)
    network.cut()
    choose(simple, phone_choices(simple)[2])
    expect(save_status(simple)).to_have_text(SENDING)
    jump_to(session, 31)
    expect_slot(simple, 1)
    expect(simple.get_by_text(PREVIOUS_LOST, exact=True)).to_be_visible(timeout=LIVE_MS)
    assert_accessible(simple, "réponse précédente perdue")
    jump_to(session, 6 * 30 + 1)
    expect(end_message(simple)).to_contain_text(not_transmitted(1), timeout=LIVE_MS + 1_000)
    assert_accessible(simple, "fin, réponse non transmise")
    expect(end_message(multiple)).to_contain_text(TRANSMITTED, timeout=LIVE_MS + 1_000)
    assert_accessible(multiple, "fin, réponses transmises")
