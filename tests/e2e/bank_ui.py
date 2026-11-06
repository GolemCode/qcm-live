"""Parcours enseignant dans la banque de questions et les QCM, par l'interface uniquement.

Réutilisables par les tests des incréments suivants (il faut un QCM pour lancer une session).
"""

from __future__ import annotations

import re

from playwright.sync_api import Locator, Page, expect

LETTERS = "ABCDEFGH"
SIMPLE = "Questions simples"
MULTIPLE = "Questions multiples"


def open_bank(page: Page) -> None:
    page.get_by_role("navigation").get_by_role("link", name="Banque de questions").click()
    expect(page.get_by_role("heading", name="Banque de questions", level=1)).to_be_visible()


def open_quizzes(page: Page) -> None:
    page.get_by_role("navigation").get_by_role("link", name="QCM", exact=True).click()
    expect(page.get_by_role("heading", name="QCM", exact=True, level=1)).to_be_visible()


def question_card(page: Page, text: str) -> Locator:
    """La fiche d'une question dans la banque (repérée par son énoncé)."""
    return page.get_by_role("article").filter(
        has=page.get_by_role("heading", name=text, exact=True)
    )


def fill_question(
    page: Page, text: str, *, multiple: bool, choices: list[tuple[str, bool]]
) -> None:
    """Remplit le formulaire de question (création ou modification) puis enregistre.

    Les emplacements non fournis sont vidés : `choices` décrit la question complète.
    """
    page.get_by_label("Énoncé").fill(text)
    page.get_by_label("Choix multiple" if multiple else "Choix simple").check()
    for index, letter in enumerate(LETTERS):
        label, correct = choices[index] if index < len(choices) else ("", False)
        page.get_by_label(f"Proposition {letter}", exact=True).fill(label)
        page.get_by_label(f"Proposition {letter} juste", exact=True).set_checked(correct)
    page.get_by_role("button", name="Enregistrer").click()


def create_question(
    page: Page, text: str, *, multiple: bool = False, choices: list[tuple[str, bool]]
) -> None:
    open_bank(page)
    page.get_by_role("link", name="Nouvelle question").click()
    fill_question(page, text, multiple=multiple, choices=choices)
    expect(page.get_by_role("status")).to_contain_text("Question enregistrée")


def scale_input(page: Page, group: str, key: str) -> Locator:
    """Champ du barème : `group` = SIMPLE ou MULTIPLE, `key` = b, m, v ou p."""
    return page.get_by_role("group", name=group).get_by_label(re.compile(rf"^{key} —"))


def fill_quiz(
    page: Page,
    title: str,
    questions: list[str],
    scales: dict[str, dict[str, str]] | None = None,
) -> None:
    """Remplit le formulaire de QCM (titre, questions dans l'ordre voulu, barème) et enregistre."""
    page.get_by_label("Titre").fill(title)
    for order_input in page.get_by_label(re.compile(r"^Ordre de la question")).all():
        order_input.fill("")
    for position, text in enumerate(questions, start=1):
        page.get_by_label(f"Ordre de la question : {text}", exact=True).fill(str(position))
    for group, values in (scales or {}).items():
        for key, value in values.items():
            scale_input(page, group, key).fill(value)
    page.get_by_role("button", name="Enregistrer").click()


def create_quiz(
    page: Page,
    title: str,
    questions: list[str],
    scales: dict[str, dict[str, str]] | None = None,
) -> None:
    open_quizzes(page)
    page.get_by_role("link", name="Nouveau QCM").click()
    fill_quiz(page, title, questions, scales)
    expect(page.get_by_role("heading", name=title, level=1)).to_be_visible()


def open_quiz(page: Page, title: str) -> None:
    open_quizzes(page)
    page.get_by_role("link", name=title, exact=True).click()
    expect(page.get_by_role("heading", name=title, level=1)).to_be_visible()


def quiz_question_items(page: Page) -> Locator:
    """Les questions du QCM affiché, dans l'ordre."""
    return page.get_by_role("list", name="Questions du QCM").get_by_role("listitem")


def scale_row(page: Page, group: str) -> Locator:
    """Cellules b, m, v, p d'une ligne du barème affiché sur la fiche du QCM."""
    return (
        page.get_by_role("table", name="Barème").get_by_role("row", name=group).get_by_role("cell")
    )
