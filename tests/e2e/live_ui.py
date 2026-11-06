"""Parcours d'une session en direct : l'enseignant sur le PC du tableau, les étudiants sur
leur téléphone. Uniquement par l'interface."""

from __future__ import annotations

import re

from playwright.sync_api import Locator, Page, expect

CODE_RE = re.compile(r"\b(\d{6})\b")


def open_sessions(page: Page) -> None:
    page.get_by_role("navigation").get_by_role("link", name="Sessions").click()
    expect(page.get_by_role("heading", name="Sessions", exact=True, level=1)).to_be_visible()


def fill_launch(page: Page, quiz: str, group: str, shown: int | str, seconds: int | str) -> None:
    page.get_by_label("QCM").select_option(label=quiz)
    page.get_by_label("Groupe").select_option(label=group)
    page.get_by_label("Questions affichées en même temps").fill(str(shown))
    page.get_by_label("Temps par question (secondes)").fill(str(seconds))
    page.get_by_role("button", name="Lancer").click()


def board_code(page: Page) -> str:
    """Identifiant de la session affichée au tableau."""
    heading = page.get_by_role("heading", name=re.compile(r"^Session \d{6}$"), level=1)
    expect(heading).to_be_visible()
    match = CODE_RE.search(heading.inner_text())
    assert match
    return match.group(1)


def launch_session(page: Page, quiz: str, group: str, shown: int = 1, seconds: int = 30) -> str:
    open_sessions(page)
    page.get_by_role("link", name="Lancer une session").click()
    fill_launch(page, quiz, group, shown, seconds)
    return board_code(page)


def connected_names(page: Page) -> Locator:
    return page.get_by_role("list", name="Étudiants connectés").get_by_role("listitem")


def connected_count(page: Page) -> Locator:
    return page.get_by_text(re.compile(r"^Connectés : \d+ / \d+$"))


def enter_code(phone: Page, base_url: str, code: str) -> None:
    phone.goto(f"{base_url}/")
    phone.get_by_label("Code de session").fill(code)
    phone.get_by_role("button", name="Rejoindre").click()


def join(phone: Page, base_url: str, code: str, number: str) -> None:
    """L'étudiant ouvre l'adresse projetée, saisit le code puis son numéro."""
    enter_code(phone, base_url, code)
    phone.get_by_label("Numéro d'étudiant").fill(number)
    phone.get_by_role("button", name="Valider").click()
