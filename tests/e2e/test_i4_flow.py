"""Incrément 4 : déroulement d'une session — tableau, téléphones, rotation, réponses."""

import re

import pytest
from playwright.sync_api import Page, expect

from bank.models import Question
from live.models import Answer, Session
from tests.e2e.live_ui import (
    LIVE_MS,
    background,
    card,
    choose,
    connected_count,
    connected_names,
    join,
    manage_participants,
    phone_choices,
    phone_color,
    phones_joined,
    save_status,
    seconds_left,
    start,
    timer,
)
from tests.factories import make_group, make_question, make_quiz, make_session, rewind

# Des propositions distinctes d'une question à l'autre : le téléphone, qui n'affiche jamais
# l'énoncé, se reconnaît à ses propositions.
QUESTIONS = {
    "Capitale de la France ?": [("Paris", True), ("Lyon", False), ("Nice", False)],
    "Couleur du ciel ?": [("Bleu", True), ("Vert", False), ("Rouge", False)],
    "Deux plus deux ?": [("Quatre", True), ("Trois", False), ("Cinq", False)],
    "Lesquels sont pairs ?": [("2", True), ("4", True), ("7", False)],
}
MULTIPLE = {"Lesquels sont pairs ?"}
STUDENTS = [("00123", "DURAND Élise"), ("42", "MARTIN Léo"), ("7", "Ng Anh")]


def question_of(choices: list[str]) -> str:
    """Énoncé de la question dont le téléphone affiche ces propositions (dans le désordre)."""
    for text, expected in QUESTIONS.items():
        if sorted(choices) == sorted(label for label, _ in expected):
            return text
    raise AssertionError(f"propositions inconnues : {choices}")


def expect_slot(phone: Page, slot: int) -> None:
    """Le téléphone affiche le créneau `slot` (jeton de page « running:<slot> »)."""
    expect(phone.locator("main")).to_have_attribute("data-page", f"running:{slot}", timeout=LIVE_MS)


def make_live(n_questions: int, shown: int, seconds: int = 30) -> Session:
    questions = [
        make_question(text, choices, multiple=text in MULTIPLE)
        for text, choices in list(QUESTIONS.items())[:n_questions]
    ]
    group = make_group("TD1", STUDENTS)
    return make_session(make_quiz("Contrôle", questions), group, shown=shown, seconds=seconds)


def open_board(page: Page, base_url: str, session: Session) -> None:
    page.goto(f"{base_url}/prof/sessions/{session.code}/")


def started(page: Page, base_url: str, new_phone, session: Session, numbers=()) -> list[Page]:
    """Les téléphones `numbers` rejoignent la session, puis l'enseignant la démarre."""
    phones = phones_joined(new_phone, base_url, session.code, numbers)
    open_board(page, base_url, session)
    start(page)
    return phones


@pytest.mark.spec("DER-01")
def test_board_shows_groups_with_colours(teacher_page: Page, live_server):
    page = teacher_page
    session = make_live(3, shown=2)
    # Modifié après le lancement : le tableau montre le contenu figé (SES-03).
    Question.objects.filter(text="Capitale de la France ?").update(text="Texte modifié")
    open_board(page, live_server.url, session)
    start(page)

    expect(card(page, 1).get_by_role("heading")).to_have_text("Capitale de la France ?")
    expect(card(page, 1).get_by_role("listitem")).to_have_text(["Paris", "Lyon", "Nice"])
    expect(card(page, 1)).to_contain_text("1")
    expect(card(page, 2).get_by_role("heading")).to_have_text("Couleur du ciel ?")
    expect(card(page, 3)).to_have_count(0)
    assert background(card(page, 1)) != background(card(page, 2))
    assert card(page, 1).locator("ol").get_attribute("type") == "A"

    rewind(session, 60)  # deux créneaux : le groupe suivant, plus court
    expect(card(page, 1).get_by_role("heading")).to_have_text("Deux plus deux ?", timeout=LIVE_MS)
    expect(card(page, 2)).to_have_count(0)
    rewind(session, 30)
    expect(page.get_by_role("main")).to_contain_text("Session terminée", timeout=LIVE_MS)
    expect(card(page, 1)).to_have_count(0)


@pytest.mark.spec("DER-02")
def test_slots_advance_by_themselves_in_real_time(teacher_page: Page, live_server, new_phone):
    """Temps réel, sans avance artificielle : 2 questions, N=2, t=5 s."""
    page = teacher_page
    session = make_live(2, shown=2, seconds=5)
    phone_a, phone_b = started(page, live_server.url, new_phone, session, ["00123", "42"])

    for screen in (page, phone_a, phone_b):
        expect(timer(screen)).to_be_visible(timeout=LIVE_MS)
    first = seconds_left(page)
    assert 3 <= first <= 5
    first_colors = (phone_color(phone_a), phone_color(phone_b))
    assert first_colors[0] != first_colors[1]  # synchronisés, chacun sa question
    page.wait_for_timeout(1_500)
    assert seconds_left(page) < first  # le temps restant décompte

    # Second créneau, sans aucune action : chaque téléphone change de couleur.
    for phone, color in zip((phone_a, phone_b), first_colors, strict=True):
        expect(phone.get_by_text(f"Couleur {3 - color}", exact=True)).to_be_visible(
            timeout=5_000 + LIVE_MS
        )
    expect(card(page, 1)).to_be_visible()  # même groupe : le tableau garde ses 2 questions
    expect(card(page, 2)).to_be_visible()

    rewind(session, 5)  # la transition automatique est prouvée : on avance jusqu'à la fin
    for screen in (page, phone_a, phone_b):
        expect(screen.get_by_role("main")).to_contain_text("Session terminée", timeout=LIVE_MS)


@pytest.mark.spec("ETU-04")
def test_phone_shows_colour_and_choices_only(teacher_page: Page, live_server, new_phone):
    page = teacher_page
    session = make_live(4, shown=2)
    (phone,) = started(page, live_server.url, new_phone, session, ["00123"])

    color = phone_color(phone)
    expect(phone.get_by_role("timer", name="Temps restant")).to_be_visible(timeout=LIVE_MS)
    assert background(phone.locator("body")) == background(card(page, color))
    statement = card(page, color).get_by_role("heading").inner_text()
    assert question_of(phone_choices(phone)) == statement
    html = phone.content()
    for text in QUESTIONS:  # aucun énoncé, nulle part dans la page
        assert text not in html
    for letter in ("A.", "B.", "C."):
        assert letter not in " ".join(phone_choices(phone))
    expect(phone.get_by_role("radio")).to_have_count(3)  # question simple : un seul choix

    # Seul étudiant (rang 0) : au 4e créneau, la question multiple du groupe 2.
    rewind(session, 90)
    expect_slot(phone, 3)
    assert question_of(phone_choices(phone)) == "Lesquels sont pairs ?"
    expect(phone.get_by_role("checkbox")).to_have_count(3)
    assert "Lesquels sont pairs ?" not in phone.content()


@pytest.mark.spec("ETU-05")
def test_choices_shuffled_per_student_and_stable(teacher_page: Page, live_server, new_phone):
    page = teacher_page
    six = [("Un", True), ("Deux", False), ("Trois", False)]
    six += [("Quatre", False), ("Cinq", False), ("Six", False)]
    quiz = make_quiz("Ordre", [make_question("Six propositions", six)])
    session = make_session(quiz, make_group("TD1", STUDENTS), shown=1)
    phones = started(page, live_server.url, new_phone, session, ["00123", "42", "7"])
    expect(card(page, 1).get_by_role("listitem")).to_have_text([label for label, _ in six])

    orders = []
    for phone in phones:
        expect(phone.get_by_role("group", name="Propositions")).to_be_visible(timeout=LIVE_MS)
        order = phone_choices(phone)
        assert sorted(order) == sorted(label for label, _ in six)
        phone.reload()
        assert phone_choices(phone) == order  # stable pour l'étudiant et la question
        orders.append(tuple(order))
    assert len(set(orders)) > 1  # propre à chaque étudiant


@pytest.mark.spec("ETU-06")
def test_rotation_everyone_answers_everything_in_different_orders(
    teacher_page: Page, live_server, new_phone
):
    page = teacher_page
    session = make_live(4, shown=2)
    phones = started(page, live_server.url, new_phone, session, ["00123", "42", "7"])

    seen: list[list[str]] = [[] for _ in phones]
    for slot in range(4):
        if slot:
            rewind(session, 30)
        for index, phone in enumerate(phones):
            expect_slot(phone, slot)
            seen[index].append(question_of(phone_choices(phone)))
        # À chaque créneau, deux étudiants voisins ont deux questions différentes.
        assert seen[0][slot] != seen[1][slot]

    for order in seen:  # chacun répond à toutes les questions, une fois chacune
        assert sorted(order) == sorted(QUESTIONS)
        assert set(order[:2]) == set(list(QUESTIONS)[:2])  # groupe 1, puis groupe 2
    assert seen[0] != seen[1]  # pas dans le même ordre


@pytest.mark.spec("ETU-07")
def test_answer_can_change_until_deadline_then_refused(teacher_page: Page, live_server, new_phone):
    page = teacher_page
    session = make_live(1, shown=1)
    (phone,) = started(page, live_server.url, new_phone, session, ["00123"])
    expect(phone.get_by_role("group", name="Propositions")).to_be_visible(timeout=LIVE_MS)

    choose(phone, "Lyon")
    expect(save_status(phone)).to_have_text("Réponse enregistrée")
    choose(phone, "Paris")  # la dernière réponse compte
    expect(save_status(phone)).to_have_text("Réponse enregistrée")
    phone.reload()
    expect(phone.get_by_label("Paris", exact=True)).to_be_checked()
    expect(phone.get_by_label("Lyon", exact=True)).not_to_be_checked()

    # Le téléphone perd le réseau (il ne voit plus la fin du créneau) et répond trop tard.
    phone.route(re.compile(r".*/etat/$"), lambda route: route.abort())
    rewind(session, 30)
    choose(phone, "Nice")
    expect(save_status(phone)).to_have_text("Temps écoulé : réponse non enregistrée")
    answer = Answer.objects.get(participant__session=session)
    assert answer.choices == [0]  # Paris, la dernière réponse donnée à temps


@pytest.mark.spec("ETU-07")
def test_multiple_answer_changes_are_saved(teacher_page: Page, live_server, new_phone):
    page = teacher_page
    quiz = make_quiz(
        "M",
        [make_question("Lesquels sont pairs ?", QUESTIONS["Lesquels sont pairs ?"], multiple=True)],
    )
    session = make_session(quiz, make_group("TD1", STUDENTS), shown=1)
    (phone,) = started(page, live_server.url, new_phone, session, ["00123"])
    expect(phone.get_by_role("group", name="Propositions")).to_be_visible(timeout=LIVE_MS)

    for label in ("2", "7", "4"):
        choose(phone, label)
        expect(save_status(phone)).to_have_text("Réponse enregistrée")
    choose(phone, "7")  # décoché
    expect(save_status(phone)).to_have_text("Réponse enregistrée")
    phone.reload()
    for label, checked in (("2", True), ("4", True), ("7", False)):
        box = phone.get_by_label(label, exact=True)
        expect(box).to_be_checked() if checked else expect(box).not_to_be_checked()


@pytest.mark.spec("ETU-08")
def test_late_student_joins_and_missed_slots_are_unanswered(
    teacher_page: Page, live_server, new_phone
):
    page = teacher_page
    session = make_live(4, shown=2)
    started(page, live_server.url, new_phone, session, ["00123"])
    rewind(session, 30)  # le second créneau est en cours

    (late,) = phones_joined(new_phone, live_server.url, session.code, ["42"])
    expect(late.get_by_role("group", name="Propositions")).to_be_visible()
    question = question_of(phone_choices(late))
    assert question in list(QUESTIONS)[:2]  # une question du groupe en cours
    choose(late, phone_choices(late)[0])
    expect(save_status(late)).to_have_text("Réponse enregistrée")

    participant = session.participants.get(number="42")
    # Le créneau manqué n'a aucune réponse : il comptera comme non-réponse (v).
    assert participant.answers.count() == 1
    expect(connected_count(page)).to_have_count(0)  # le tableau est passé aux questions


@pytest.mark.spec("DER-03")
def test_board_shows_neither_correction_nor_statistics(teacher_page: Page, live_server, new_phone):
    page = teacher_page
    session = make_live(2, shown=2)
    phones = started(page, live_server.url, new_phone, session, ["00123", "42"])
    for phone in phones:
        expect(phone.get_by_role("group", name="Propositions")).to_be_visible(timeout=LIVE_MS)
        choose(phone, phone_choices(phone)[0])
        expect(save_status(phone)).to_have_text("Réponse enregistrée")
    with page.expect_response(re.compile(r"/etat/$")):  # le tableau a vu ces réponses
        pass

    board = page.get_by_role("main").inner_text()
    for forbidden in ("juste", "correct", "réponse", "%", "1 / 2", "2 / 2"):
        assert forbidden not in board.lower()
    expect(card(page, 1).get_by_role("listitem")).to_have_text(["Paris", "Lyon", "Nice"])
    styles = {background(item) for item in card(page, 1).get_by_role("listitem").all()}
    assert len(styles) == 1  # aucune proposition mise en valeur


@pytest.mark.spec("SES-04")
def test_teacher_releases_a_taken_number_before_start(teacher_page: Page, live_server, new_phone):
    page = teacher_page
    session = make_live(1, shown=1)
    impostor = new_phone()
    join(impostor, live_server.url, session.code, "00123")
    expect(impostor.get_by_text("Vous êtes DURAND Élise")).to_be_visible()
    real = new_phone()
    join(real, live_server.url, session.code, "00123")
    expect(real.get_by_role("alert")).to_contain_text("déjà utilisé")

    open_board(page, live_server.url, session)
    expect(connected_names(page)).to_have_text(["DURAND Élise"])
    manage_participants(page)
    row = page.get_by_role("row", name=re.compile("00123"))
    expect(row).to_contain_text("DURAND Élise")
    row.get_by_role("button", name="Libérer").click()
    expect(page.get_by_role("status")).to_contain_text("Numéro 00123 libéré")
    expect(page.get_by_role("row", name=re.compile("00123"))).to_have_count(0)

    impostor.reload()  # l'appareil qui occupait le numéro perd son identité
    expect(impostor.get_by_label("Numéro d'étudiant")).to_be_visible()
    real.get_by_label("Numéro d'étudiant").fill("00123")
    real.get_by_role("button", name="Valider").click()
    expect(real.get_by_text("Vous êtes DURAND Élise")).to_be_visible()

    # Après le démarrage, plus aucune libération.
    open_board(page, live_server.url, session)
    start(page)
    manage_participants(page)
    expect(page.get_by_role("button", name="Libérer")).to_have_count(0)
    expect(page.get_by_role("main")).to_contain_text("plus aucun numéro ne peut être libéré")


@pytest.mark.spec("ETU-07")
def test_phone_sends_answers_one_at_a_time(teacher_page: Page, live_server, new_phone):
    """Réseau lent : un second choix ne part qu'après le premier, avec l'état le plus récent ;
    la dernière réponse donnée est donc toujours la dernière enregistrée."""
    page = teacher_page
    pairs = QUESTIONS["Lesquels sont pairs ?"]
    quiz = make_quiz("M", [make_question("Lesquels sont pairs ?", pairs, multiple=True)])
    session = make_session(quiz, make_group("TD1", STUDENTS), shown=1)
    (phone,) = started(page, live_server.url, new_phone, session, ["00123"])
    expect(phone.get_by_role("group", name="Propositions")).to_be_visible(timeout=LIVE_MS)

    held = []  # envois retenus, comme sur un réseau très lent
    phone.route(re.compile(r".*/reponse/$"), lambda route: held.append(route))
    choose(phone, "2")
    choose(phone, "4")
    phone.wait_for_timeout(500)
    assert len(held) == 1  # le second envoi attend la fin du premier
    held.pop().continue_()
    for _ in range(20):  # le second envoi part une fois le premier terminé
        if held:
            break
        phone.wait_for_timeout(100)
    assert len(held) == 1
    with phone.expect_response(re.compile(r".*/reponse/$")):
        held.pop().continue_()
    expect(save_status(phone)).to_have_text("Réponse enregistrée")
    assert Answer.objects.get(participant__session=session).choices == [0, 1]  # 2 et 4
