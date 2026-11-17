"""Incrément 12 : barème AMC par question, « Aucune de ces réponses n'est correcte », ordre fixe.

Les notes attendues sont calculées à la main d'après le §3 de SPEC.md (calcul d'AMC).
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from bank.models import Question, Quiz
from tests.e2e.amc_ui import NONE_OF_THESE, open_question_form
from tests.e2e.bank_ui import LETTERS, open_bank, open_quizzes, question_card
from tests.e2e.live_setup import expect_slot, started, wait_answer
from tests.e2e.live_ui import (
    LIVE_MS,
    choose,
    csv_rows,
    download_csv,
    open_results,
    phone_choices,
    results_rows,
    save_status,
)
from tests.factories import jump_to, make_group, make_question, make_quiz, make_session

SCORING = "Barème"
KEEP_ORDER = "Ne pas mélanger les propositions"


def new_question_form(page: Page) -> None:
    open_bank(page)
    page.get_by_role("link", name="Nouvelle question").click()


def fill_choices(page: Page, choices: list[tuple[str, bool]]) -> None:
    for index, letter in enumerate(LETTERS):
        label, correct = choices[index] if index < len(choices) else ("", False)
        page.get_by_label(f"Proposition {letter}", exact=True).fill(label)
        page.get_by_label(f"Proposition {letter} juste", exact=True).set_checked(correct)


def points(page: Page, letter: str):
    return page.get_by_label(f"Points de la proposition {letter}", exact=True)


def save(page: Page) -> None:
    page.get_by_role("button", name="Enregistrer").click()


# --- BAR-01 : le barème au formulaire -------------------------------------------------------


@pytest.mark.spec("BAR-01")
def test_question_scoring_in_form(teacher_page: Page):
    page = teacher_page
    new_question_form(page)
    page.get_by_label("Énoncé").fill("Capitale de l'Italie ?")
    page.get_by_label("Choix simple").check()
    fill_choices(page, [("Rome", True), ("Milan", False), ("Turin", False)])

    # Directive non prise en charge, puis valeur non numérique : refusées, avec la raison.
    page.get_by_label(SCORING, exact=True).fill("b=2,P=3")
    save(page)
    expect(page.get_by_role("alert")).to_contain_text("directive « P » non prise en charge")
    page.get_by_label(SCORING, exact=True).fill("b=deux")
    save(page)
    expect(page.get_by_role("alert")).to_contain_text("valeur non numérique")
    assert Question.objects.count() == 0

    # Barème accepté, avec la valeur propre d'une proposition (question simple).
    page.get_by_label(SCORING, exact=True).fill("b=2,m=-0.5")
    points(page, "B").fill("-1")
    save(page)
    expect(page.get_by_role("status")).to_contain_text("Question enregistrée")
    card = question_card(page, "Capitale de l'Italie ?")
    expect(card).to_contain_text("Barème : b=2,m=-0.5")

    # Modifier la question montre le barème et les points tels qu'enregistrés.
    open_question_form(page, "Capitale de l'Italie ?")
    expect(page.get_by_label(SCORING, exact=True)).to_have_value("b=2,m=-0.5")
    expect(points(page, "B")).to_have_value("-1")
    expect(points(page, "A")).to_have_value("")

    # Des points sur une proposition d'une question multiple : refusés.
    page.get_by_label("Choix multiple").check()
    save(page)
    expect(page.get_by_role("alert")).to_contain_text("question simple")

    # Le QCM n'a plus de barème : il est porté par chaque question.
    open_quizzes(page)
    page.get_by_role("link", name="Nouveau QCM").click()
    expect(page.get_by_role("group", name="Questions simples")).to_have_count(0)
    expect(page.get_by_label(SCORING, exact=True)).to_have_count(0)


# --- BAR-01 : les notes d'une session --------------------------------------------------------

# Q1 simple b=2,m=-1,MAX=3, B porte -3 ; Q2 multiple haut=2 ; Q3 multiple mz=3,v=-1, avec
# « Aucune… », fausse puisque 3 est juste ; Q4 multiple sans barème, aucune proposition
# juste : « Aucune… » est la bonne réponse.
GRADED = [
    ("Capitale de l'Italie ?", [("Rome", True), ("Milan", False, "-3"), ("Turin", False)], False),
    ("Lesquels sont pairs ?", [("2", True), ("4", True), ("7", False), ("9", False)], True),
    ("Lesquels sont premiers ?", [("3", True), ("8", False), ("10", False)], True),
    ("Lesquels sont négatifs ?", [("5", False), ("6", False)], True),
]
GRADED_SCORING = ["b=2,m=-1,MAX=3", "haut=2", "mz=3,v=-1", ""]
NONE_QUESTIONS = {"Lesquels sont premiers ?", "Lesquels sont négatifs ?"}
# Réponses par question : texte des propositions cochées, et leurs indices dans la banque.
GRADED_ANSWERS = {
    "00123": [["Milan"], ["2"], ["3"], [NONE_OF_THESE]],
    "42": [["Turin"], ["7"], [], ["5"]],
}
INDEXES = {
    "00123": [[1], [0], [0], [2]],
    "42": [[2], [2], [], [0]],
}
MAX_TOTAL = "10"  # MAX=3 ; haut=2 : 2 ; mz=3 : 3 ; 2 cases bien traitées : 2


@pytest.mark.spec("BAR-01")
def test_grades_follow_the_amc_scoring_of_each_question(teacher_page: Page, live_server, new_phone):
    page = teacher_page
    questions = [
        make_question(
            text,
            choices,
            multiple=multiple,
            scoring=scoring,
            none_of_these=text in NONE_QUESTIONS,
        )
        for (text, choices, multiple), scoring in zip(GRADED, GRADED_SCORING, strict=True)
    ]
    group = make_group("TD1", [("00123", "DURAND Élise"), ("42", "MARTIN Léo")])
    session = make_session(make_quiz("Barèmes", questions), group, shown=1, seconds=30)
    numbers = list(GRADED_ANSWERS)
    screens = started(page, live_server.url, new_phone, session, numbers)
    phones = dict(zip(numbers, screens, strict=True))
    for slot in range(4):
        jump_to(session, slot * 30 + 1)
        for number, phone in phones.items():
            expect_slot(phone, slot)
            for text in GRADED_ANSWERS[number][slot]:
                choose(phone, text)
                expect(save_status(phone)).to_have_text("Réponse enregistrée")
            if INDEXES[number][slot]:
                wait_answer(phone, session, number, slot, INDEXES[number][slot])
    jump_to(session, 121)
    expect(page.get_by_role("main")).to_contain_text("Session terminée", timeout=LIVE_MS)

    # Le barème est figé au lancement : le changer ensuite ne change pas les notes (SES-03).
    Question.objects.update(scoring="b=100")

    open_results(page)
    assert results_rows(page) == [
        ["1", "00123", "DURAND Élise", "3", MAX_TOTAL, "6"],  # -3 + 1 + 3 + 2 ; 3 / 10 x 20
        ["2", "42", "MARTIN Léo", "-1", MAX_TOTAL, "0"],  # -1 + 0 - 1 + 1, bornée à 0
    ]
    _, content = download_csv(page)
    rows = csv_rows(content)
    # « Aucune… » a la lettre qui suit la dernière proposition : C pour Q4.
    assert rows[1][6:] == ["B", "-3", "A", "1", "A", "3", "C", "2"]
    # Q2 : 3 cases mal traitées, 1 + d = -1, plancher p = 0 ; Q3 : rien coché, v = -1.
    assert rows[2][6:] == ["C", "-1", "C", "0", "-", "-1", "A", "1"]


# --- BAN-09 : « Aucune de ces réponses n'est correcte » --------------------------------------


@pytest.mark.spec("BAN-09")
def test_none_of_these_in_question_form(teacher_page: Page):
    page = teacher_page
    new_question_form(page)
    page.get_by_label("Énoncé").fill("Lesquels sont négatifs ?")
    page.get_by_label("Choix multiple").check()
    fill_choices(page, [("5", False), ("6", False)])
    save(page)
    expect(page.get_by_role("alert")).to_contain_text("au moins une bonne réponse")

    # Avec « Aucune… », zéro proposition juste est permis : c'est elle, la bonne réponse.
    page.get_by_label(NONE_OF_THESE, exact=True).check()
    save(page)
    expect(page.get_by_role("status")).to_contain_text("Question enregistrée")
    choices = question_card(page, "Lesquels sont négatifs ?").get_by_role("listitem")
    expect(choices).to_have_text(["5", "6", f"{NONE_OF_THESE} (juste)"])

    # Avec une proposition juste, « Aucune… » est fausse ; elle ne compte pas parmi les 8.
    new_question_form(page)
    page.get_by_label("Énoncé").fill("Lesquelles sont des voyelles ?")
    page.get_by_label("Choix multiple").check()
    fill_choices(page, [("A", True), *[(letter, False) for letter in "BCDFGHJ"]])
    page.get_by_label(NONE_OF_THESE, exact=True).check()
    save(page)
    expect(page.get_by_role("status")).to_contain_text("Question enregistrée")
    choices = question_card(page, "Lesquelles sont des voyelles ?").get_by_role("listitem")
    expect(choices).to_have_count(9)
    expect(choices.last).to_have_text(NONE_OF_THESE)

    # Réservée aux questions multiples.
    new_question_form(page)
    page.get_by_label("Énoncé").fill("Oui ou non ?")
    page.get_by_label("Choix simple").check()
    fill_choices(page, [("Oui", True), ("Non", False)])
    page.get_by_label(NONE_OF_THESE, exact=True).check()
    save(page)
    expect(page.get_by_role("alert")).to_contain_text("question multiple")


# --- BAN-10 : ordre fixe ----------------------------------------------------------------------


@pytest.mark.spec("BAN-10")
@pytest.mark.usefixtures("reversed_choices")
def test_fixed_order_is_not_shuffled_on_phones(teacher_page: Page, live_server, new_phone):
    page = teacher_page
    new_question_form(page)
    page.get_by_label("Énoncé").fill("Rangez du plus petit au plus grand.")
    page.get_by_label("Choix simple").check()
    fill_choices(page, [("Un", False), ("Deux", True), ("Trois", False), ("Quatre", False)])
    page.get_by_label(KEEP_ORDER, exact=True).check()
    save(page)
    expect(page.get_by_role("status")).to_contain_text("Question enregistrée")
    expect(question_card(page, "Rangez du plus petit au plus grand.")).to_contain_text("Ordre fixe")
    open_question_form(page, "Rangez du plus petit au plus grand.")
    expect(page.get_by_label(KEEP_ORDER, exact=True)).to_be_checked()

    fixed = Question.objects.get(text="Rangez du plus petit au plus grand.")
    free = make_question("Couleur du ciel ?", [("Bleu", True), ("Vert", False), ("Gris", False)])
    group = make_group("TD1", [("1", "UN Alice"), ("2", "DEUX Bob")])
    session = make_session(make_quiz("Ordre", [fixed, free]), group, shown=1, seconds=30)
    phones = started(page, live_server.url, new_phone, session, ["1", "2"])
    for phone in phones:  # ordre de la banque, sur chaque téléphone
        expect_slot(phone, 0)
        assert phone_choices(phone) == ["Un", "Deux", "Trois", "Quatre"]
    jump_to(session, 31)
    for phone in phones:  # témoin : une question ordinaire reste mélangée
        expect_slot(phone, 1)
        assert phone_choices(phone) == ["Gris", "Vert", "Bleu"]
    assert Quiz.objects.count() == 1


# --- ETU-12 : « Aucune… » sur le téléphone ----------------------------------------------------

POST_ANSWER = """async (choices) => {
  const form = document.getElementById("answer-form");
  const data = new FormData(form);
  data.delete("choice");
  for (const choice of choices) data.append("choice", String(choice));
  const response = await fetch(form.action, { method: "POST", body: data });
  return [response.status, (await response.json()).message];
}"""


@pytest.mark.spec("ETU-12")
@pytest.mark.usefixtures("reversed_choices")
def test_none_of_these_on_the_phone(teacher_page: Page, live_server, new_phone):
    page = teacher_page
    question = make_question(
        "Lesquels sont pairs ?",
        [("2", True), ("4", True), ("7", False)],
        multiple=True,
        none_of_these=True,
    )
    group = make_group("TD1", [("00123", "DURAND Élise")])
    session = make_session(make_quiz("Aucune", [question]), group, shown=1, seconds=60)
    (phone,) = started(page, live_server.url, new_phone, session, ["00123"])
    expect_slot(phone, 0)

    # Les autres propositions sont mélangées (ici, inversées) ; « Aucune… » reste en dernier.
    assert phone_choices(phone) == ["7", "4", "2", NONE_OF_THESE]
    group_box = phone.get_by_role("group", name="Propositions")
    none = group_box.get_by_role("checkbox", name=NONE_OF_THESE)
    two = group_box.get_by_role("checkbox", name="2", exact=True)

    # La cocher décoche les autres ; c'est une réponse, enregistrée et confirmée.
    choose(phone, "2")
    expect(save_status(phone)).to_have_text("Réponse enregistrée")
    choose(phone, NONE_OF_THESE)
    expect(two).not_to_be_checked()
    expect(none).to_be_checked()
    expect(save_status(phone)).to_have_text("Réponse enregistrée")
    wait_answer(phone, session, "00123", 0, [3])

    # Cocher une autre case la décoche.
    choose(phone, "7")
    expect(none).not_to_be_checked()
    expect(save_status(phone)).to_have_text("Réponse enregistrée")
    wait_answer(phone, session, "00123", 0, [2])

    # Le serveur refuse une réponse qui la combine avec une autre proposition.
    status, message = phone.evaluate(POST_ANSWER, [0, 3])
    assert status == 400
    assert "ne se combine pas" in message
    wait_answer(phone, session, "00123", 0, [2])  # la réponse enregistrée n'a pas changé
    status, _ = phone.evaluate(POST_ANSWER, [3])
    assert status == 200
    wait_answer(phone, session, "00123", 0, [3])

    # Une question simple n'a jamais « Aucune… ».
    simple = make_question("Oui ?", [("Oui", True), ("Non", False)])
    other = make_session(make_quiz("Simple", [simple]), group, shown=1, seconds=60)
    (phone2,) = started(page, live_server.url, new_phone, other, ["00123"])
    expect_slot(phone2, 0)
    assert NONE_OF_THESE not in phone_choices(phone2)
