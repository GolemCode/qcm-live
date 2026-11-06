"""Incrément 3 : lancement d'une session, accueil au tableau, identification des étudiants."""

import re

import pytest
from playwright.sync_api import Page, expect

from bank.models import Question, Quiz
from roster.models import StudentGroup
from tests.e2e.live_ui import (
    board_code,
    connected_count,
    connected_names,
    enter_code,
    fill_launch,
    join,
    launch_session,
    open_sessions,
)
from tests.factories import make_group, make_question, make_quiz

TD1 = [("00123", "DURAND Élise"), ("42", "MARTIN Léo"), ("7", "Ng Anh")]


@pytest.fixture
def quiz_and_group(transactional_db):
    make_quiz("Contrôle 1", [make_question("Q1"), make_question("Q2")])
    make_group("TD1", TD1)
    make_group("TD2", [("55", "ROUX Paul")])


def identity(phone: Page):
    return phone.get_by_text(re.compile(r"^Vous êtes "))


@pytest.mark.spec("SES-01")
def test_launch_session(teacher_page: Page, quiz_and_group):
    page = teacher_page
    empty = make_quiz("QCM vidé", [make_question("Q-temp")])
    Question.objects.filter(text="Q-temp").delete()  # un QCM sans question ne se lance pas
    assert not empty.questions.exists()

    open_sessions(page)
    expect(page.get_by_text("Aucune session")).to_be_visible()
    page.get_by_role("link", name="Lancer une session").click()
    expect(page.get_by_label("QCM").locator("option")).to_have_text(["Contrôle 1"])
    expect(page.get_by_label("Groupe").locator("option")).to_have_text(["TD1", "TD2"])
    expect(page.get_by_label("Questions affichées en même temps")).to_have_value("1")
    expect(page.get_by_label("Temps par question (secondes)")).to_have_value("30")

    for shown, seconds, field in [
        (0, 30, "Questions affichées"),
        (7, 30, "Questions affichées"),
        (1, 4, "Temps par question"),
        (1, 601, "Temps par question"),
    ]:
        fill_launch(page, "Contrôle 1", "TD1", shown, seconds)
        expect(page.get_by_role("alert")).to_contain_text(field)

    # Limites tout juste acceptées.
    fill_launch(page, "Contrôle 1", "TD1", 6, 5)
    first = board_code(page)
    expect(page.get_by_role("main")).to_contain_text("6 questions à la fois")
    expect(page.get_by_role("main")).to_contain_text("5 s par question")
    second = launch_session(page, "Contrôle 1", "TD2", shown=1, seconds=600)
    expect(page.get_by_role("main")).to_contain_text("600 s par question")
    assert first != second

    open_sessions(page)
    for code, group in ((first, "TD1"), (second, "TD2")):
        row = page.get_by_role("row").filter(has=page.get_by_role("link", name=code))
        expect(row).to_contain_text("Contrôle 1")
        expect(row).to_contain_text(group)
    page.get_by_role("link", name=first).click()
    assert board_code(page) == first


@pytest.mark.spec("SES-02")
def test_board_waiting_room(teacher_page: Page, live_server, new_phone, quiz_and_group):
    page = teacher_page
    code = launch_session(page, "Contrôle 1", "TD1")
    board = page.get_by_role("main")
    expect(board).to_contain_text(f"{live_server.url}/")
    expect(board).to_contain_text("Contrôle 1")
    expect(board).to_contain_text("TD1")
    expect(connected_count(page)).to_have_text("Connectés : 0 / 3")
    expect(connected_names(page)).to_have_count(0)

    # Mise à jour en direct, sans recharger le tableau.
    join(new_phone(), live_server.url, code, "00123")
    expect(connected_names(page)).to_have_text(["DURAND Élise"])
    expect(connected_count(page)).to_have_text("Connectés : 1 / 3")
    join(new_phone(), live_server.url, code, "42")
    expect(connected_names(page)).to_have_text(["DURAND Élise", "MARTIN Léo"])
    expect(connected_count(page)).to_have_text("Connectés : 2 / 3")
    expect(board).not_to_contain_text("00123")  # noms seulement, pas les numéros

    page.get_by_role("button", name="Démarrer").click()
    expect(board).to_contain_text("Session démarrée")
    expect(page.get_by_role("button", name="Démarrer")).to_have_count(0)


@pytest.mark.spec("SES-03")
def test_session_frozen_at_launch(teacher_page: Page, live_server, new_phone, quiz_and_group):
    page = teacher_page
    code = launch_session(page, "Contrôle 1", "TD1")
    # Après le lancement, le QCM, ses questions et le groupe disparaissent de la banque.
    Quiz.objects.all().delete()
    Question.objects.all().delete()
    StudentGroup.objects.all().delete()

    page.reload()
    expect(page.get_by_role("main")).to_contain_text("Contrôle 1 (2 questions)")
    expect(page.get_by_role("main")).to_contain_text("TD1")
    expect(connected_count(page)).to_have_text("Connectés : 0 / 3")
    phone = new_phone()
    join(phone, live_server.url, code, "7")
    expect(identity(phone)).to_have_text("Vous êtes Ng Anh")


@pytest.mark.spec("ETU-01")
def test_student_joins_with_code_then_number(
    teacher_page: Page, live_server, new_phone, quiz_and_group
):
    code = launch_session(teacher_page, "Contrôle 1", "TD1")
    phone = new_phone()
    phone.goto(f"{live_server.url}/")
    code_input = phone.get_by_label("Code de session")
    expect(code_input).to_have_attribute("inputmode", "numeric")
    code_input.fill(code)
    phone.get_by_role("button", name="Rejoindre").click()
    number_input = phone.get_by_label("Numéro d'étudiant")
    expect(number_input).to_have_attribute("inputmode", "numeric")
    number_input.fill("00123")
    phone.get_by_role("button", name="Valider").click()
    expect(identity(phone)).to_have_text("Vous êtes DURAND Élise")
    expect(phone.get_by_role("main")).to_contain_text("En attente du démarrage")


@pytest.mark.spec("ETU-02")
def test_refused_codes_and_numbers(teacher_page: Page, live_server, new_phone, quiz_and_group):
    code = launch_session(teacher_page, "Contrôle 1", "TD1")
    phone = new_phone()
    unknown = "000000" if code != "000000" else "111111"
    enter_code(phone, live_server.url, unknown)
    expect(phone.get_by_role("alert")).to_contain_text("Aucune session")

    enter_code(phone, live_server.url, code)
    for number in ("999", "55", "123"):  # inconnu, autre groupe, sans les zéros de tête
        phone.get_by_label("Numéro d'étudiant").fill(number)
        phone.get_by_role("button", name="Valider").click()
        expect(phone.get_by_role("alert")).to_contain_text("ne fait pas partie du groupe")
    expect(identity(phone)).to_have_count(0)

    # Numéro déjà pris par un autre appareil : refusé, le premier appareil garde son identité.
    first = new_phone()
    join(first, live_server.url, code, "00123")
    expect(identity(first)).to_have_text("Vous êtes DURAND Élise")
    phone.get_by_label("Numéro d'étudiant").fill("00123")
    phone.get_by_role("button", name="Valider").click()
    expect(phone.get_by_role("alert")).to_contain_text("déjà utilisé")
    first.reload()
    expect(identity(first)).to_have_text("Vous êtes DURAND Élise")
    expect(connected_count(teacher_page)).to_have_text("Connectés : 1 / 3")


@pytest.mark.spec("ETU-03")
def test_identity_survives_reload(teacher_page: Page, live_server, new_phone, quiz_and_group):
    code = launch_session(teacher_page, "Contrôle 1", "TD1")
    phone = new_phone()
    join(phone, live_server.url, code, "42")
    expect(identity(phone)).to_have_text("Vous êtes MARTIN Léo")

    phone.reload()
    expect(identity(phone)).to_have_text("Vous êtes MARTIN Léo")
    expect(phone.get_by_label("Numéro d'étudiant")).to_have_count(0)
    enter_code(phone, live_server.url, code)  # ressaisir le code mène à son écran
    expect(identity(phone)).to_have_text("Vous êtes MARTIN Léo")

    other = new_phone()  # un autre appareil n'hérite de rien
    enter_code(other, live_server.url, code)
    expect(other.get_by_label("Numéro d'étudiant")).to_be_visible()
    expect(identity(other)).to_have_count(0)
