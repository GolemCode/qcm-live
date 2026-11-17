"""Parcours enseignant de l'import AMC-TXT (I12), par l'interface uniquement."""

from __future__ import annotations

from playwright.sync_api import Locator, Page, expect

from tests.e2e.bank_ui import open_bank, open_quizzes, question_card

NONE_OF_THESE = "Aucune de ces réponses n'est correcte"
IMPORT_HEADING = "Importer un fichier AMC"
RECAP_HEADING = "Récapitulatif de l'import"
ZIP = "application/zip"


def upload_amc(page: Page, content: str | bytes, name: str = "controle.txt") -> None:
    """Depuis la liste des QCM, envoie un fichier AMC-TXT, ou une archive ZIP s'il porte ce
    nom (IMP-08), à l'analyse (rien n'est encore créé)."""
    open_quizzes(page)
    page.get_by_role("link", name=IMPORT_HEADING).click()
    expect(page.get_by_role("heading", name=IMPORT_HEADING, level=1)).to_be_visible()
    data = content.encode() if isinstance(content, str) else content
    page.get_by_label("Fichier AMC-TXT").set_input_files(
        files=[
            {
                "name": name,
                "mimeType": ZIP if name.endswith(".zip") else "text/plain",
                "buffer": data,
            }
        ]
    )
    page.get_by_role("button", name="Analyser").click()


def expect_recap(page: Page) -> None:
    expect(page.get_by_role("heading", name=RECAP_HEADING, level=1)).to_be_visible()


def recap_items(page: Page, region: str) -> Locator:
    """Lignes d'une liste du récapitulatif : « Questions écartées » ou « Textes ignorés »."""
    return page.get_by_role("region", name=region).get_by_role("listitem")


def confirm_import(page: Page) -> None:
    page.get_by_role("button", name="Importer").click()


def import_amc(page: Page, content: str | bytes, name: str = "controle.txt") -> None:
    """Import complet : envoi, récapitulatif, confirmation, fiche du QCM créé."""
    upload_amc(page, content, name)
    expect_recap(page)
    confirm_import(page)
    expect(page.get_by_role("status")).to_contain_text("QCM importé")


def open_question_form(page: Page, text: str) -> None:
    """Formulaire de modification de la question d'énoncé `text`, depuis la banque."""
    open_bank(page)
    question_card(page, text).get_by_role("link", name="Modifier").click()
    expect(page.get_by_role("heading", name="Modifier la question", level=1)).to_be_visible()
