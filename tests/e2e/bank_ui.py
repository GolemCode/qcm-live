"""Parcours enseignant dans la banque de questions et les QCM, par l'interface uniquement.

Réutilisables par les tests des incréments suivants (il faut un QCM pour lancer une session).
"""

from __future__ import annotations

import re

from playwright.sync_api import Locator, Page, expect

from tests.e2e.conftest import teacher_nav

LETTERS = "ABCDEFGH"


def open_bank(page: Page) -> None:
    teacher_nav(page).get_by_role("link", name="Banque de questions").click()
    expect(page.get_by_role("heading", name="Banque de questions", level=1)).to_be_visible()


def open_quizzes(page: Page) -> None:
    teacher_nav(page).get_by_role("link", name="QCM", exact=True).click()
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


INCLUDE = "Inclure la question : "


def include_box(page: Page, text: str) -> Locator:
    """Case à cocher d'une question dans le formulaire de QCM (CMP-04)."""
    return page.get_by_label(INCLUDE + text, exact=True)


def fill_quiz(page: Page, title: str, questions: list[str]) -> None:
    """Remplit le formulaire de QCM (titre, questions cochées, les autres décochées) et
    enregistre. L'ordre ne se choisit plus (CMP-04) : il suit le fichier ou la banque."""
    page.get_by_label("Titre").fill(title)
    for box in page.get_by_label(re.compile("^" + INCLUDE)).all():
        box.uncheck()
    for text in questions:
        include_box(page, text).check()
    page.get_by_role("button", name="Enregistrer").click()


def create_quiz(page: Page, title: str, questions: list[str]) -> None:
    open_quizzes(page)
    page.get_by_role("link", name="Nouveau QCM").click()
    fill_quiz(page, title, questions)
    expect(page.get_by_role("heading", name=title, level=1)).to_be_visible()


def open_quiz(page: Page, title: str) -> None:
    open_quizzes(page)
    page.get_by_role("link", name=title, exact=True).click()
    expect(page.get_by_role("heading", name=title, level=1)).to_be_visible()


def quiz_question_items(page: Page) -> Locator:
    """Les questions du QCM affiché, dans l'ordre."""
    return page.get_by_role("list", name="Questions du QCM").get_by_role("listitem")


def quiz_item(page: Page, text: str) -> Locator:
    """La ligne d'une question sur la fiche du QCM affiché."""
    return quiz_question_items(page).filter(has_text=text)
