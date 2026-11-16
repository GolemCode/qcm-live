"""Incrément 12 : import de questions AMC-TXT (IMP-01 à IMP-07).

Les fichiers sont écrits ici, aux questions fictives. Les numéros de ligne cités dans les
messages sont ceux de ces fichiers, en commençant à 1.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from bank.models import Question, Quiz
from tests.e2e.amc_ui import (
    NONE_OF_THESE,
    confirm_import,
    expect_recap,
    import_amc,
    open_question_form,
    recap_items,
    upload_amc,
)
from tests.e2e.bank_ui import open_bank, open_quiz, question_card, quiz_question_items

SKIPPED = "Questions écartées"
IGNORED = "Textes ignorés"

FILE_OK = """# QCM fictif, pour les tests
Title: Contrôle d'essai

* Capitale de l'Italie ?
+ Rome
- Milan
- Turin

*[ordered]{b=2} Combien font deux et deux ?
Une seule réponse.

Réfléchissez bien.
- Trois
+ Quatre
- Cinq

** Lesquels sont des nombres pairs ?
+ Deux
+ Quatre
- Sept
"""
PARAGRAPHS = "Combien font deux et deux ? Une seule réponse.\n\nRéfléchissez bien."
TITLES = ["Capitale de l'Italie ?", PARAGRAPHS, "Lesquels sont des nombres pairs ?"]


@pytest.mark.spec("IMP-01")
def test_import_shows_a_recap_then_creates_the_quiz(teacher_page: Page):
    page = teacher_page
    upload_amc(page, FILE_OK)
    expect_recap(page)
    main = page.get_by_role("main")
    expect(main).to_contain_text("Contrôle d'essai")
    expect(main).to_contain_text("3 questions à importer")
    expect(main).to_contain_text("dont 0 déjà dans la banque")
    expect(page.get_by_role("region", name=SKIPPED)).to_contain_text("Aucune")

    # Annuler : rien n'est créé.
    page.get_by_role("button", name="Annuler").click()
    expect(page.get_by_role("status")).to_contain_text("Import annulé")
    assert (Quiz.objects.count(), Question.objects.count()) == (0, 0)

    # Confirmer : un QCM, ses questions dans l'ordre du fichier, entrées dans la banque.
    upload_amc(page, FILE_OK)
    expect_recap(page)
    assert (Quiz.objects.count(), Question.objects.count()) == (0, 0)
    confirm_import(page)
    expect(page.get_by_role("status")).to_contain_text("QCM importé : 3 questions")
    expect(page.get_by_role("heading", name="Contrôle d'essai", level=1)).to_be_visible()
    items = quiz_question_items(page)
    expect(items).to_have_count(3)
    for item, title in zip(items.all(), TITLES, strict=True):
        expect(item).to_contain_text(title.split("\n")[0])

    # Les lignes d'un paragraphe sont jointes par une espace ; les paragraphes restent séparés.
    assert Question.objects.get(text__startswith="Combien").text == PARAGRAPHS
    open_bank(page)
    heading = question_card(page, PARAGRAPHS).get_by_role("heading")
    assert re.fullmatch(
        r"Combien font deux et deux \? Une seule réponse\.\n+Réfléchissez bien\.",
        heading.inner_text(),
    )


@pytest.mark.spec("IMP-01")
def test_import_title_from_file_name_and_size_limit(teacher_page: Page):
    page = teacher_page
    without_title = FILE_OK.replace("Title: Contrôle d'essai\n", "")
    import_amc(page, without_title, name="partiel-2024.txt")
    expect(page.get_by_role("heading", name="partiel-2024", level=1)).to_be_visible()

    upload_amc(page, b"# " + b"x" * 1_000_000 + b"\n", name="gros.txt")
    expect(page.get_by_role("alert")).to_contain_text("trop volumineux")
    assert Quiz.objects.count() == 1


SYNTAX_ERRORS = """Title: Erreurs
Couleur: bleu
- orpheline

* Une seule proposition ?
+ Oui

* Deux bonnes réponses ?
+ Oui
+ Bien sûr
- Non
"""


@pytest.mark.spec("IMP-02")
def test_syntax_error_refuses_the_whole_file(teacher_page: Page):
    page = teacher_page
    upload_amc(page, SYNTAX_ERRORS)
    alert = page.get_by_role("alert")
    expect(alert).to_contain_text("Ligne 2 : option inconnue « Couleur »")
    expect(alert).to_contain_text("Ligne 3 : proposition hors d'une question")
    expect(alert).to_contain_text("Ligne 5 : question avec moins de 2 propositions")
    expect(alert).to_contain_text("Ligne 8 : question simple avec 2 bonnes réponses")
    expect(page.get_by_role("heading", name="Récapitulatif de l'import")).to_have_count(0)
    assert (Quiz.objects.count(), Question.objects.count()) == (0, 0)

    # Au-delà de 20 erreurs : les 20 premières, puis le nombre des autres.
    upload_amc(page, "- orpheline\n" * 25)
    expect(page.get_by_role("alert")).to_contain_text("Ligne 20 : proposition hors")
    expect(page.get_by_role("alert")).not_to_contain_text("Ligne 21 ")
    expect(page.get_by_role("alert")).to_contain_text("… et 5 autres erreurs.")

    # Fichier qui n'est pas en UTF-8.
    upload_amc(page, "* Été ?\n+ Oui\n- Non\n".encode("cp1252"))
    expect(page.get_by_role("alert")).to_contain_text("UTF-8")
    assert Question.objects.count() == 0


SOME_SKIPPED = """Title: Écartées

* Capitale de l'Italie ?
+ Rome
- Milan

*<lines=3> Expliquez votre démarche.

* Que vaut [[x^2]] pour x = 2 ?
+ 4
- 2

*{b=2,P=4} Barème avec plafond ?
+ Oui
- Non

* Capitale de l'Italie ?
+ Rome
- Milan
"""


@pytest.mark.spec("IMP-03")
def test_unsupported_questions_are_listed_before_confirmation(teacher_page: Page):
    page = teacher_page
    upload_amc(page, SOME_SKIPPED)
    expect_recap(page)
    expect(page.get_by_role("main")).to_contain_text("1 question à importer")
    skipped = recap_items(page, SKIPPED)
    expect(skipped).to_have_count(4)
    expect(skipped.nth(0)).to_contain_text(re.compile(r"Ligne 7 : question ouverte"))
    expect(skipped.nth(1)).to_contain_text(re.compile(r"Ligne 9 : .*formule"))
    expect(skipped.nth(2)).to_contain_text(re.compile(r"Ligne 13 : .*directive « P »"))
    expect(skipped.nth(3)).to_contain_text(re.compile(r"Ligne 17 : .*doublon.*ligne 3"))
    assert Question.objects.count() == 0

    confirm_import(page)
    expect(page.get_by_role("status")).to_contain_text("QCM importé : 1 question")
    expect(quiz_question_items(page)).to_have_count(1)
    assert Question.objects.count() == 1

    # Un fichier dont toutes les questions sont écartées ne peut pas être importé.
    upload_amc(page, "*<lines=3> Racontez.\n\n* Que vaut [[x]] ?\n+ 1\n- 2\n", name="vide.txt")
    expect_recap(page)
    expect(page.get_by_role("main")).to_contain_text("ne peut pas être importé")
    expect(page.get_by_role("button", name="Importer")).to_have_count(0)


SCORED = """Title: Barèmes
DefaultScoringS: b=3

* Simple, barème du fichier ?
+ Oui
- Non

*{b=2,m=-1} Simple, son propre barème ?
+ Oui
- Non

** Multiple, sans barème ?
+ Oui
+ Si
- Non

* Simple, valeur d'une proposition ?
+ Oui
-{-2} Non
"""
SCORED_M = """Title: Barèmes multiples
DefaultScoringM: b=1,m=-0.5

** Multiple, barème par défaut du fichier ?
+ Oui
- Non
"""


def scoring_of(page: Page, text: str) -> str:
    open_question_form(page, text)
    return page.get_by_label("Barème", exact=True).input_value()


@pytest.mark.spec("IMP-04")
def test_scoring_comes_from_the_file(teacher_page: Page):
    page = teacher_page
    import_amc(page, SCORED)
    import_amc(page, SCORED_M, name="multiples.txt")
    # Le barème de la question remplace celui par défaut du fichier, sans s'y ajouter.
    assert scoring_of(page, "Simple, barème du fichier ?") == "b=3"
    assert scoring_of(page, "Simple, son propre barème ?") == "b=2,m=-1"
    # Sans DefaultScoringM : le défaut implicite d'AMC pour une multiple.
    assert scoring_of(page, "Multiple, sans barème ?") == "haut=2"
    assert scoring_of(page, "Multiple, barème par défaut du fichier ?") == "b=1,m=-0.5"
    assert scoring_of(page, "Simple, valeur d'une proposition ?") == "b=3"
    expect(page.get_by_label("Points de la proposition B", exact=True)).to_have_value("-2")


@pytest.mark.spec("IMP-05")
def test_complete_multi(teacher_page: Page):
    page = teacher_page
    import_amc(page, "** Lesquels ?\n+ Oui\n- Non\n\n** Aucun de justes ?\n- A\n- B\n")
    # Par défaut, comme AMC : « Aucune… » ajoutée à chaque multiple, juste si rien d'autre.
    first = question_card(page, "Lesquels ?").get_by_role("listitem")
    expect(first).to_have_text(["Oui (juste)", "Non", NONE_OF_THESE])
    second = question_card(page, "Aucun de justes ?").get_by_role("listitem")
    expect(second).to_have_text(["A", "B", f"{NONE_OF_THESE} (juste)"])

    upload_amc(
        page,
        "Title: Sans complétion\nCompleteMulti: 0\n\n** Lesquelles ?\n+ Ah\n- Bé\n\n"
        "** Rien de juste ?\n- C\n- D\n",
    )
    expect_recap(page)
    expect(recap_items(page, SKIPPED)).to_have_count(1)
    expect(recap_items(page, SKIPPED)).to_contain_text("Ligne 8 : ")
    confirm_import(page)
    open_bank(page)
    expect(question_card(page, "Lesquelles ?").get_by_role("listitem")).to_have_text(
        ["Ah (juste)", "Bé"]
    )


GROUPS = """Title: Groupes

*([group=geo,shuffle=1,numquestions=1] Répondez aux questions de géographie.
* Capitale de l'Espagne ?
+ Madrid
- Séville

* Capitale du Portugal ?
+ Lisbonne
- Porto
*)

* Hors groupe ?
+ Oui
- Non
"""


@pytest.mark.spec("IMP-06")
def test_groups_are_imported_whole_with_their_label(teacher_page: Page):
    page = teacher_page
    upload_amc(page, GROUPS)
    expect_recap(page)
    # Tirage ignoré : toutes les questions, dans l'ordre du fichier.
    expect(page.get_by_role("main")).to_contain_text("3 questions à importer")
    ignored = recap_items(page, IGNORED)
    expect(ignored).to_have_count(1)
    expect(ignored).to_contain_text("Ligne 3 : ")
    expect(ignored).to_contain_text("Répondez aux questions de géographie.")
    confirm_import(page)
    items = quiz_question_items(page)
    expect(items).to_have_text(
        [
            re.compile(r"Capitale de l'Espagne \?.*geo"),
            re.compile(r"Capitale du Portugal \?.*geo"),
            re.compile(r"Hors groupe \?"),
        ]
    )
    expect(items.nth(2)).not_to_contain_text("geo")
    open_bank(page)
    expect(question_card(page, "Capitale de l'Espagne ?")).to_contain_text("Étiquette : geo")


@pytest.mark.spec("IMP-07")
def test_identical_questions_are_shared_and_reimport_is_refused(teacher_page: Page):
    page = teacher_page
    import_amc(page, FILE_OK)
    open_quiz(page, "Contrôle d'essai")

    # Un autre fichier qui reprend une question identique : partagée, pas recopiée.
    other = "Title: Reprise\n\n* Capitale de l'Italie ?\n+ Rome\n- Milan\n- Turin\n\n"
    other += "* Capitale de l'Italie ?\n+ Rome\n- Milan\n"  # même énoncé, autres propositions
    upload_amc(page, other, name="reprise.txt")
    expect_recap(page)
    expect(page.get_by_role("main")).to_contain_text("2 questions à importer")
    expect(page.get_by_role("main")).to_contain_text("dont 1 déjà dans la banque")
    confirm_import(page)
    assert Question.objects.filter(text="Capitale de l'Italie ?").count() == 2
    shared = Question.objects.get(text="Capitale de l'Italie ?", choices__text="Turin")
    assert sorted(shared.quizzes.values_list("title", flat=True)) == ["Contrôle d'essai", "Reprise"]

    # Réimporter le même fichier, octet pour octet, est refusé avec le nom du QCM existant.
    upload_amc(page, FILE_OK, name="autre-nom.txt")
    expect(page.get_by_role("alert")).to_contain_text("déjà importé")
    expect(page.get_by_role("alert")).to_contain_text("Contrôle d'essai")
    assert Quiz.objects.count() == 2
    # Une fois ce QCM supprimé, le fichier peut de nouveau être importé.
    Quiz.objects.filter(title="Contrôle d'essai").delete()
    import_amc(page, FILE_OK)
    assert Quiz.objects.count() == 2
