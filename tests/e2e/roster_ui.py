"""Parcours enseignant pour les groupes d'étudiants, par l'interface uniquement."""

from __future__ import annotations

from playwright.sync_api import Locator, Page, expect


def open_groups(page: Page) -> None:
    page.get_by_role("navigation").get_by_role("link", name="Groupes").click()
    expect(page.get_by_role("heading", name="Groupes", exact=True, level=1)).to_be_visible()


def submit_group(page: Page, name: str, content: bytes) -> None:
    """Remplit le formulaire d'import (déjà ouvert) et l'envoie."""
    page.get_by_label("Nom du groupe").fill(name)
    page.get_by_label("Fichier CSV").set_input_files(
        files=[{"name": "groupe.csv", "mimeType": "text/csv", "buffer": content}]
    )
    page.get_by_role("button", name="Importer").click()


def import_group(page: Page, name: str, content: bytes) -> None:
    open_groups(page)
    page.get_by_role("link", name="Importer un groupe").click()
    submit_group(page, name, content)
    expect(page.get_by_role("heading", name=name, level=1)).to_be_visible()


def student_rows(page: Page) -> Locator:
    """Lignes (numéro, nom) du tableau des étudiants du groupe affiché, sans l'en-tête."""
    return page.get_by_role("table", name="Étudiants du groupe").locator("tbody tr")
