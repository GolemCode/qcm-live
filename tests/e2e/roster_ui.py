"""Parcours enseignant pour les groupes d'étudiants, par l'interface uniquement."""

from __future__ import annotations

from playwright.sync_api import Locator, Page, expect

from tests.e2e.conftest import teacher_nav


def open_groups(page: Page) -> None:
    teacher_nav(page).get_by_role("link", name="Groupes").click()
    expect(page.get_by_role("heading", name="Groupes", exact=True, level=1)).to_be_visible()


def submit_group(page: Page, name: str, content: bytes, year: str | None = None) -> None:
    """Remplit le formulaire d'import (déjà ouvert) et l'envoie ; sans `year`, l'année reste
    celle que propose le formulaire (GRP-04)."""
    page.get_by_label("Nom du groupe").fill(name)
    if year is not None:
        page.get_by_label("Année").fill(year)
    page.get_by_label("Fichier CSV").set_input_files(
        files=[{"name": "groupe.csv", "mimeType": "text/csv", "buffer": content}]
    )
    page.get_by_role("button", name="Importer").click()


def import_group(page: Page, name: str, content: bytes, year: str | None = None) -> None:
    open_groups(page)
    page.get_by_role("link", name="Importer un groupe").click()
    submit_group(page, name, content, year)
    expect(page.get_by_role("heading", name=name, level=1)).to_be_visible()


def student_rows(page: Page) -> Locator:
    """Lignes (n°, numéro étudiant, nom) du tableau des étudiants du groupe affiché, sans
    l'en-tête."""
    return page.get_by_role("table", name="Étudiants du groupe").locator("tbody tr")
