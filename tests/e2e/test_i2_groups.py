"""Incrément 2 : groupes d'étudiants importés depuis un CSV."""

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.roster_ui import import_group, open_groups, student_rows, submit_group
from tests.factories import make_group

# Export d'Excel en français : point-virgule, en-tête, Windows-1252, zéro de tête.
TD1_CSV = "numéro;nom\r\n00123;DURAND Élise\r\n\r\n42;MARTIN Léo;;\r\n7;Ng Anh\r\n".encode("cp1252")
# Export UTF-8 avec BOM, virgule, sans en-tête, nom entre guillemets contenant une virgule.
TD2_CSV = '﻿9001,"DUPONT, Jeanne"\n9002,ROUX Paul\n'.encode()


def alert(page: Page):
    return page.get_by_role("alert")


@pytest.mark.spec("GRP-01")
def test_import_group_from_csv(teacher_page: Page):
    page = teacher_page
    open_groups(page)
    expect(page.get_by_text("Aucun groupe")).to_be_visible()

    import_group(page, "TD1", TD1_CSV)
    expect(page.get_by_role("status")).to_contain_text("Groupe importé : 3 étudiants")
    expect(student_rows(page)).to_have_count(3)
    expect(student_rows(page).nth(0).get_by_role("cell")).to_have_text(["00123", "DURAND Élise"])
    expect(student_rows(page).nth(1).get_by_role("cell")).to_have_text(["42", "MARTIN Léo"])
    expect(student_rows(page).nth(2).get_by_role("cell")).to_have_text(["7", "Ng Anh"])

    import_group(page, "TD2", TD2_CSV)
    expect(student_rows(page).nth(0).get_by_role("cell")).to_have_text(["9001", "DUPONT, Jeanne"])
    expect(student_rows(page)).to_have_count(2)

    open_groups(page)
    expect(page.get_by_role("row", name="TD1")).to_contain_text("3 étudiants")
    expect(page.get_by_role("row", name="TD2")).to_contain_text("2 étudiants")


INVALID_FILES = [
    # (contenu, extraits attendus du message)
    (b"1;A\n2\n", ["Ligne 2", "format incorrect"]),
    (b"1;A;B\n", ["Ligne 1", "format incorrect"]),
    (b"numero;nom\n1;A\n2;B\n1;C\n", ["Ligne 4", "numéro 1 en double", "ligne 2"]),
    (b"1;A\n;B\n", ["Ligne 2", "numéro vide"]),
    (b"1;A\n2;\n", ["Ligne 2", "nom vide"]),
    (b"1;A\n12a;B\n", ["Ligne 2", "chiffres"]),
    (b"1;A\n2\n3;\n", ["Ligne 2", "Ligne 3"]),  # toutes les lignes fautives sont désignées
    (b"numero;nom\n\n", ["aucun étudiant"]),
]


@pytest.mark.spec("GRP-02")
def test_invalid_csv_is_refused_entirely(teacher_page: Page):
    page = teacher_page
    make_group("Existant", [("1", "A")])
    open_groups(page)
    page.get_by_role("link", name="Importer un groupe").click()

    for content, fragments in INVALID_FILES:
        submit_group(page, "TD3", content)
        for fragment in fragments:
            expect(alert(page)).to_contain_text(fragment)
    # Nom de groupe vide, puis déjà pris.
    submit_group(page, "", b"1;A\n2;B\n")
    expect(alert(page)).to_contain_text("Nom du groupe")
    submit_group(page, "Existant", b"1;A\n2;B\n")
    expect(alert(page)).to_contain_text("existe déjà")

    # Rien n'a été créé : seul le groupe préexistant reste.
    open_groups(page)
    expect(page.get_by_role("link", name="TD3")).to_have_count(0)
    expect(page.locator("tbody tr")).to_have_count(1)


@pytest.mark.spec("GRP-03")
def test_delete_group_after_confirmation(teacher_page: Page):
    page = teacher_page
    make_group("TD jetable", [("1", "A"), ("2", "B")])
    make_group("TD gardé", [("3", "C")])
    open_groups(page)
    page.get_by_role("link", name="TD jetable").click()

    page.get_by_role("link", name="Supprimer").click()
    expect(page.get_by_role("heading", name="Supprimer le groupe ?")).to_be_visible()
    expect(page.get_by_role("main")).to_contain_text("2 étudiants")
    page.get_by_role("link", name="Annuler").click()
    expect(page.get_by_role("heading", name="TD jetable", level=1)).to_be_visible()

    page.get_by_role("link", name="Supprimer").click()
    page.get_by_role("button", name="Supprimer").click()
    expect(page.get_by_role("status")).to_contain_text("Groupe supprimé")
    expect(page.get_by_role("link", name="TD jetable")).to_have_count(0)
    expect(page.get_by_role("link", name="TD gardé")).to_be_visible()
