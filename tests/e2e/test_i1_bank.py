"""Incrément 1 : banque de questions, QCM et barème, par l'interface enseignant."""

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.bank_ui import (
    MULTIPLE,
    SIMPLE,
    create_quiz,
    fill_question,
    fill_quiz,
    open_bank,
    open_quiz,
    open_quizzes,
    question_card,
    quiz_question_items,
    scale_input,
    scale_row,
)
from tests.factories import make_question, make_quiz

CAPITAL = "Quelle est la capitale de la France ?"
PRIMES = "Lesquels de ces nombres sont premiers ?"


def choices_of(page: Page, text: str):
    return question_card(page, text).get_by_role("listitem")


def alert(page: Page):
    return page.get_by_role("alert")


@pytest.mark.spec("BAN-01")
def test_create_simple_question(teacher_page: Page):
    page = teacher_page
    open_bank(page)
    expect(page.get_by_text("La banque est vide")).to_be_visible()
    page.get_by_role("link", name="Nouvelle question").click()

    # Énoncé vide : refusé.
    fill_question(page, "", multiple=False, choices=[("Paris", True), ("Lyon", False)])
    expect(alert(page)).to_contain_text("Énoncé")
    # Une seule proposition : refusé.
    fill_question(page, CAPITAL, multiple=False, choices=[("Paris", True)])
    expect(alert(page)).to_contain_text("au moins 2 propositions")
    # Deux bonnes réponses : refusé.
    fill_question(page, CAPITAL, multiple=False, choices=[("Paris", True), ("Lyon", True)])
    expect(alert(page)).to_contain_text("exactement une bonne réponse")
    # Aucune bonne réponse : refusé.
    fill_question(page, CAPITAL, multiple=False, choices=[("Paris", False), ("Lyon", False)])
    expect(alert(page)).to_contain_text("exactement une bonne réponse")
    # Case « juste » cochée sur une proposition vide : refusé.
    fill_question(page, CAPITAL, multiple=False, choices=[("Paris", True), ("", True)])
    expect(alert(page)).to_contain_text("vide")

    fill_question(
        page,
        CAPITAL,
        multiple=False,
        choices=[("Paris", True), ("Lyon", False), ("Marseille", False)],
    )
    expect(page.get_by_role("status")).to_contain_text("Question enregistrée")
    expect(page.get_by_role("heading", name="Banque de questions", level=1)).to_be_visible()
    card = question_card(page, CAPITAL)
    expect(card).to_contain_text("Choix simple")
    expect(choices_of(page, CAPITAL)).to_have_text(["Paris (juste)", "Lyon", "Marseille"])
    expect(page.get_by_role("article")).to_have_count(1)


@pytest.mark.spec("BAN-02")
def test_create_multiple_question_with_eight_choices(teacher_page: Page):
    page = teacher_page
    open_bank(page)
    page.get_by_role("link", name="Nouvelle question").click()
    numbers = [("2", True), ("4", False), ("5", True), ("9", False)]
    numbers += [("11", True), ("15", False), ("21", False), ("23", True)]

    # Aucune bonne réponse : refusé.
    fill_question(page, PRIMES, multiple=True, choices=[(n, False) for n, _ in numbers])
    expect(alert(page)).to_contain_text("au moins une bonne réponse")
    # Une seule proposition : refusé aussi en choix multiple.
    fill_question(page, PRIMES, multiple=True, choices=[("2", True)])
    expect(alert(page)).to_contain_text("au moins 2 propositions")

    fill_question(page, PRIMES, multiple=True, choices=numbers)
    expect(page.get_by_role("status")).to_contain_text("Question enregistrée")
    expect(question_card(page, PRIMES)).to_contain_text("Choix multiple")
    expect(choices_of(page, PRIMES)).to_have_text(
        [f"{n} (juste)" if ok else n for n, ok in numbers]
    )

    # Limite basse : une question multiple peut n'avoir qu'une seule bonne réponse.
    page.get_by_role("link", name="Nouvelle question").click()
    fill_question(page, "Lequel est pair ?", multiple=True, choices=[("2", True), ("3", False)])
    expect(page.get_by_role("status")).to_contain_text("Question enregistrée")
    expect(question_card(page, "Lequel est pair ?")).to_contain_text("Choix multiple")
    expect(choices_of(page, "Lequel est pair ?")).to_have_text(["2 (juste)", "3"])


@pytest.mark.spec("BAN-03")
def test_create_quiz_with_ordered_questions(teacher_page: Page):
    page = teacher_page
    for text in ("Q-alpha", "Q-beta", "Q-gamma", "Q-delta"):
        make_question(text)
    open_quizzes(page)
    page.get_by_role("link", name="Nouveau QCM").click()

    # Titre vide : refusé.
    fill_quiz(page, "", ["Q-alpha"])
    expect(alert(page)).to_contain_text("Titre")
    # Aucune question choisie : refusé.
    fill_quiz(page, "Contrôle 1", [])
    expect(alert(page)).to_contain_text("au moins une question")
    # Deux questions au même rang : refusé.
    page.get_by_label("Ordre de la question : Q-alpha", exact=True).fill("1")
    page.get_by_label("Ordre de la question : Q-gamma", exact=True).fill("1")
    page.get_by_role("button", name="Enregistrer").click()
    expect(alert(page)).to_contain_text("même rang")

    # Rangs non contigus, ordre sans rapport avec l'ordre de création :
    # gamma=1, alpha=7, delta=3, beta exclue → gamma, delta, alpha.
    page.get_by_label("Ordre de la question : Q-alpha", exact=True).fill("7")
    page.get_by_label("Ordre de la question : Q-beta", exact=True).fill("")
    page.get_by_label("Ordre de la question : Q-gamma", exact=True).fill("1")
    page.get_by_label("Ordre de la question : Q-delta", exact=True).fill("3")
    page.get_by_role("button", name="Enregistrer").click()

    expect(page.get_by_role("heading", name="Contrôle 1", level=1)).to_be_visible()
    expect(quiz_question_items(page)).to_have_count(3)
    expect(quiz_question_items(page)).to_contain_text(["Q-gamma", "Q-delta", "Q-alpha"])
    open_quizzes(page)
    expect(page.get_by_role("row", name="Contrôle 1")).to_contain_text("3 questions")


@pytest.mark.spec("BAN-04")
def test_question_reused_in_two_quizzes(teacher_page: Page):
    page = teacher_page
    make_question("Q-commune")
    make_question("Q-propre")
    create_quiz(page, "QCM A", ["Q-commune", "Q-propre"])
    create_quiz(page, "QCM B", ["Q-commune"])

    open_quiz(page, "QCM A")
    expect(quiz_question_items(page)).to_contain_text(["Q-commune", "Q-propre"])
    open_quiz(page, "QCM B")
    expect(quiz_question_items(page)).to_contain_text(["Q-commune"])
    expect(quiz_question_items(page)).to_have_count(1)
    open_bank(page)
    expect(question_card(page, "Q-commune")).to_contain_text("Utilisée dans : QCM A, QCM B")
    expect(question_card(page, "Q-propre")).to_contain_text("Utilisée dans : QCM A")


@pytest.mark.spec("BAR-01")
def test_quiz_scale_defaults_and_custom_values(teacher_page: Page):
    page = teacher_page
    make_question("Q-barème")
    open_quizzes(page)
    page.get_by_role("link", name="Nouveau QCM").click()

    # Valeurs par défaut d'AMC : b=1, m=0, v=0, plancher p vide.
    for group in (SIMPLE, MULTIPLE):
        for key, expected in (("b", 1), ("m", 0), ("v", 0)):
            assert float(scale_input(page, group, key).input_value()) == expected
    expect(scale_input(page, MULTIPLE, "p")).to_have_value("")
    expect(page.get_by_role("group", name=SIMPLE).get_by_label("p —")).to_have_count(0)

    # Défauts enregistrés tels quels : p vide signifie « pas de plancher » (pas 0).
    fill_quiz(page, "Défauts", ["Q-barème"])
    expect(page.get_by_role("heading", name="Défauts", level=1)).to_be_visible()
    expect(scale_row(page, SIMPLE)).to_have_text(["1", "0", "0", "—"])
    expect(scale_row(page, MULTIPLE)).to_have_text(["1", "0", "0", "—"])

    # Valeurs négatives et décimales.
    open_quizzes(page)
    page.get_by_role("link", name="Nouveau QCM").click()
    fill_quiz(
        page,
        "Examen",
        ["Q-barème"],
        {
            SIMPLE: {"b": "2", "m": "-0.5", "v": "0"},
            MULTIPLE: {"b": "0.5", "m": "-0.25", "v": "-1", "p": "-2"},
        },
    )
    expect(page.get_by_role("heading", name="Examen", level=1)).to_be_visible()
    expect(scale_row(page, SIMPLE)).to_have_text(["2", "-0,50", "0", "—"])
    expect(scale_row(page, MULTIPLE)).to_have_text(["0,50", "-0,25", "-1", "-2"])


@pytest.mark.spec("BAN-05")
def test_edit_question(teacher_page: Page):
    page = teacher_page
    make_question("Couleur du ciel ?", [("Bleu", True), ("Vert", False)])
    open_bank(page)
    question_card(page, "Couleur du ciel ?").get_by_role("link", name="Modifier").click()
    expect(page.get_by_label("Énoncé")).to_have_value("Couleur du ciel ?")
    expect(page.get_by_label("Proposition A", exact=True)).to_have_value("Bleu")
    expect(page.get_by_label("Proposition A juste", exact=True)).to_be_checked()

    # Mêmes règles qu'à la création.
    fill_question(page, "", multiple=False, choices=[("Bleu", True), ("Vert", False)])
    expect(alert(page)).to_contain_text("Énoncé")
    fill_question(page, "Couleurs du ciel ?", multiple=False, choices=[("Bleu", True)])
    expect(alert(page)).to_contain_text("au moins 2 propositions")
    fill_question(
        page, "Couleurs du ciel ?", multiple=False, choices=[("Bleu", True), ("Azur", True)]
    )
    expect(alert(page)).to_contain_text("exactement une bonne réponse")
    fill_question(
        page, "Couleurs du ciel ?", multiple=True, choices=[("Bleu", False), ("Vert", False)]
    )
    expect(alert(page)).to_contain_text("au moins une bonne réponse")
    open_bank(page)  # aucun refus n'a modifié la question
    expect(choices_of(page, "Couleur du ciel ?")).to_have_text(["Bleu (juste)", "Vert"])
    question_card(page, "Couleur du ciel ?").get_by_role("link", name="Modifier").click()

    fill_question(
        page,
        "Couleurs du ciel ?",
        multiple=True,
        choices=[("Bleu", True), ("Vert", False), ("Azur", True)],
    )
    expect(page.get_by_role("status")).to_contain_text("Question enregistrée")
    expect(page.get_by_role("article")).to_have_count(1)
    expect(question_card(page, "Couleurs du ciel ?")).to_contain_text("Choix multiple")
    expect(choices_of(page, "Couleurs du ciel ?")).to_have_text(
        ["Bleu (juste)", "Vert", "Azur (juste)"]
    )


@pytest.mark.spec("BAN-06")
def test_edit_quiz(teacher_page: Page):
    page = teacher_page
    q1, q2, _ = (make_question(text) for text in ("Q1", "Q2", "Q3"))
    make_quiz("Partiel", [q1, q2], multiple_p="-1")
    open_quiz(page, "Partiel")

    page.get_by_role("link", name="Modifier").click()
    expect(page.get_by_label("Titre")).to_have_value("Partiel")
    expect(page.get_by_label("Ordre de la question : Q1", exact=True)).to_have_value("1")
    expect(page.get_by_label("Ordre de la question : Q2", exact=True)).to_have_value("2")
    expect(scale_input(page, MULTIPLE, "p")).to_have_value("-1.00")
    fill_quiz(page, "Partiel v2", ["Q3", "Q1"], {SIMPLE: {"b": "3"}, MULTIPLE: {"p": ""}})

    expect(page.get_by_role("heading", name="Partiel v2", level=1)).to_be_visible()
    expect(quiz_question_items(page)).to_have_count(2)
    expect(quiz_question_items(page)).to_contain_text(["Q3", "Q1"])
    expect(scale_row(page, SIMPLE)).to_have_text(["3", "0", "0", "—"])
    expect(scale_row(page, MULTIPLE)).to_have_text(["1", "0", "0", "—"])  # plancher retiré
    open_quizzes(page)
    expect(page.get_by_role("link", name="Partiel", exact=True)).to_have_count(0)


@pytest.mark.spec("BAN-07")
def test_delete_question_after_confirmation(teacher_page: Page):
    page = teacher_page
    removed, kept = make_question("Q-supprimée"), make_question("Q-gardée")
    make_quiz("QCM A", [removed, kept])
    make_quiz("QCM B", [removed])

    # Annuler : rien ne change.
    open_bank(page)
    question_card(page, "Q-supprimée").get_by_role("link", name="Supprimer").click()
    expect(page.get_by_role("heading", name="Supprimer la question ?")).to_be_visible()
    expect(page.get_by_role("main")).to_contain_text("Q-supprimée")
    expect(page.get_by_role("main")).to_contain_text("QCM A, QCM B")
    page.get_by_role("link", name="Annuler").click()
    expect(question_card(page, "Q-supprimée")).to_be_visible()

    # Confirmer : la question disparaît de la banque et des QCM.
    question_card(page, "Q-supprimée").get_by_role("link", name="Supprimer").click()
    page.get_by_role("button", name="Supprimer").click()
    expect(page.get_by_role("status")).to_contain_text("Question supprimée")
    expect(question_card(page, "Q-supprimée")).to_have_count(0)
    expect(question_card(page, "Q-gardée")).to_be_visible()
    open_quiz(page, "QCM A")
    expect(quiz_question_items(page)).to_have_count(1)
    expect(quiz_question_items(page)).to_contain_text(["Q-gardée"])
    open_quiz(page, "QCM B")
    expect(quiz_question_items(page)).to_have_count(0)
    expect(page.get_by_text("Ce QCM ne contient aucune question")).to_be_visible()


@pytest.mark.spec("BAN-08")
def test_delete_quiz_after_confirmation(teacher_page: Page):
    page = teacher_page
    survivor = make_question("Q-survivante")
    make_quiz("QCM jetable", [survivor])
    make_quiz("QCM gardé", [survivor])

    open_quiz(page, "QCM jetable")
    page.get_by_role("link", name="Supprimer").click()
    expect(page.get_by_role("heading", name="Supprimer le QCM ?")).to_be_visible()
    page.get_by_role("link", name="Annuler").click()
    expect(page.get_by_role("heading", name="QCM jetable", level=1)).to_be_visible()

    page.get_by_role("link", name="Supprimer").click()
    page.get_by_role("button", name="Supprimer").click()
    expect(page.get_by_role("status")).to_contain_text("QCM supprimé")
    expect(page.get_by_role("link", name="QCM jetable", exact=True)).to_have_count(0)
    expect(page.get_by_role("link", name="QCM gardé", exact=True)).to_be_visible()
    open_bank(page)
    expect(question_card(page, "Q-survivante")).to_contain_text("Utilisée dans : QCM gardé")
