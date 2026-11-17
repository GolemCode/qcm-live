"""Incrément 15 : composition des QCM, versions des questions, réimport d'un fichier AMC.

Tout passe par l'interface enseignant ; une session lancée (précondition de VER-01) vient de
`make_session`, qui suit le formulaire de lancement.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from bank.models import Question, Quiz
from live.models import Session
from tests.e2e.amc_ui import confirm_import, expect_recap, import_amc, upload_amc
from tests.e2e.bank_ui import (
    fill_question,
    fill_quiz,
    include_box,
    open_bank,
    open_quiz,
    question_card,
    quiz_item,
    quiz_question_items,
)
from tests.factories import make_group, make_question, make_quiz, make_session

FILE = """Title: Contrôle fichier

* Fichier Q1 ?
+ Un
- Deux

* Fichier Q2 ?
+ Trois
- Quatre

* Fichier Q3 ?
+ Cinq
- Six
"""
FILE_QUESTIONS = ["Fichier Q1 ?", "Fichier Q2 ?", "Fichier Q3 ?"]
FILE_CHOICES = [("Un", "Deux"), ("Trois", "Quatre"), ("Cinq", "Six")]


def starts(*texts: str) -> list[re.Pattern[str]]:
    return [re.compile("^" + re.escape(text)) for text in texts]


def alert(page: Page):
    return page.get_by_role("alert")


def status(page: Page):
    return page.get_by_role("status")


def edit_from_quiz(page: Page, quiz: str, text: str) -> None:
    """Formulaire de la question `text`, ouvert depuis la fiche du QCM `quiz` (VER-02)."""
    open_quiz(page, quiz)
    quiz_item(page, text).get_by_role("link", name="Modifier").click()
    expect(page.get_by_role("heading", name="Modifier la question", level=1)).to_be_visible()


def edit_from_bank(page: Page, text: str) -> None:
    open_bank(page)
    question_card(page, text).get_by_role("link", name="Modifier").click()
    expect(page.get_by_role("heading", name="Modifier la question", level=1)).to_be_visible()


def launch(quiz: Quiz) -> Session:
    """Session lancée, jamais démarrée : la question compte déjà comme utilisée (VER-01)."""
    return make_session(quiz, make_group(f"Groupe {quiz.pk}", [("1", "Alice Fictive")]))


def previous_versions(page: Page, text: str):
    """Ouvre « Versions précédentes » sur la fiche de la question `text` de la banque."""
    card = question_card(page, text)
    card.get_by_text("Versions précédentes").click()
    return card


# --- CMP-01 : reprendre un ancien QCM ----------------------------------------------------------


@pytest.mark.spec("CMP-01")
def test_new_quiz_takes_an_old_quiz_whole(teacher_page: Page):
    page = teacher_page
    # Déjà dans la banque, créées à rebours : l'ordre du QCM n'est pas celui de leur création.
    for text, (right, wrong) in reversed(list(zip(FILE_QUESTIONS, FILE_CHOICES, strict=True))):
        make_question(text, [(right, True), (wrong, False)])
    import_amc(page, FILE, name="fichier.txt")
    make_question("Banque seule ?")

    open_quiz(page, "Contrôle fichier")
    page.get_by_role("link", name="Reprendre dans un nouveau QCM").click()
    expect(
        page.get_by_role("heading", name="Reprendre dans un nouveau QCM", level=1)
    ).to_be_visible()
    expect(page.get_by_role("main")).to_contain_text("Contrôle fichier")
    # Titre obligatoire.
    page.get_by_label("Titre").fill("")
    page.get_by_role("button", name="Créer le QCM").click()
    expect(alert(page)).to_contain_text("Titre")
    assert Quiz.objects.count() == 1

    page.get_by_label("Titre").fill("Contrôle 2027")
    page.get_by_role("button", name="Créer le QCM").click()
    expect(page.get_by_role("heading", name="Contrôle 2027", level=1)).to_be_visible()
    expect(quiz_question_items(page)).to_have_text(starts(*FILE_QUESTIONS))

    # Même questions (partagées, pas recopiées), même ordre ; l'ancien QCM est intact.
    assert Question.objects.count() == 4
    copy, old = Quiz.objects.get(title="Contrôle 2027"), Quiz.objects.get(title="Contrôle fichier")
    assert list(copy.ordered_questions()) == list(old.ordered_questions())
    open_quiz(page, "Contrôle fichier")
    expect(quiz_question_items(page)).to_have_text(starts(*FILE_QUESTIONS))


# --- CMP-02 et CMP-04 : ajouter, retirer, cases à cocher, ordre ---------------------------------


@pytest.mark.spec("CMP-02")
@pytest.mark.spec("CMP-04")
def test_add_and_remove_questions_with_checkboxes(teacher_page: Page):
    page = teacher_page
    import_amc(page, FILE, name="fichier.txt")
    import_amc(page, "Title: Autre\n\n* Autre A ?\n+ x\n- y\n\n* Autre B ?\n+ x\n- z\n")
    make_question("Banque seule ?")

    open_quiz(page, "Contrôle fichier")
    page.get_by_role("link", name="Modifier le QCM").click()
    # Plus de rang à saisir : une case par question de la banque, cochée si elle est dans le QCM.
    expect(page.get_by_label(re.compile("^Ordre de la question"))).to_have_count(0)
    for text in FILE_QUESTIONS:
        expect(include_box(page, text)).to_be_checked()
    for text in ("Autre A ?", "Autre B ?", "Banque seule ?"):
        expect(include_box(page, text)).not_to_be_checked()

    # Aucune case : refusé, rien ne change.
    fill_quiz(page, "Contrôle fichier", [])
    expect(alert(page)).to_contain_text("au moins une question")
    open_quiz(page, "Contrôle fichier")
    expect(quiz_question_items(page)).to_have_count(3)

    # Retirer Q2, ajouter deux questions venues d'ailleurs (cochées dans le désordre).
    page.get_by_role("link", name="Modifier le QCM").click()
    fill_quiz(
        page, "Contrôle fichier", ["Banque seule ?", "Fichier Q3 ?", "Autre B ?", "Fichier Q1 ?"]
    )
    expect(status(page)).to_contain_text("QCM enregistré")
    # Questions du fichier dans leur ordre, les autres à la suite, dans l'ordre de la banque.
    expect(quiz_question_items(page)).to_have_text(
        starts("Fichier Q1 ?", "Fichier Q3 ?", "Autre B ?", "Banque seule ?")
    )

    # Q2 remise : elle retrouve sa place du fichier, avant les ajouts.
    page.get_by_role("link", name="Modifier le QCM").click()
    include_box(page, "Fichier Q2 ?").check()
    page.get_by_role("button", name="Enregistrer").click()
    expect(quiz_question_items(page)).to_have_text(
        starts(*FILE_QUESTIONS, "Autre B ?", "Banque seule ?")
    )
    # L'autre QCM n'a pas bougé.
    open_quiz(page, "Autre")
    expect(quiz_question_items(page)).to_have_text(starts("Autre A ?", "Autre B ?"))


@pytest.mark.spec("CMP-04")
def test_quiz_without_file_keeps_its_order_and_appends(teacher_page: Page):
    page = teacher_page
    import_amc(page, FILE, name="fichier.txt")
    make_question("Banque X ?")
    make_question("Banque Y ?")

    # Copie d'un QCM importé (CMP-01) : elle ne vient d'aucun fichier.
    open_quiz(page, "Contrôle fichier")
    page.get_by_role("link", name="Reprendre dans un nouveau QCM").click()
    page.get_by_label("Titre").fill("Copie")
    page.get_by_role("button", name="Créer le QCM").click()

    page.get_by_role("link", name="Modifier le QCM").click()
    fill_quiz(page, "Copie", ["Banque Y ?", "Fichier Q3 ?", "Fichier Q2 ?", "Banque X ?"])
    # Ordre gardé (Q2, Q3), ajouts à la fin dans l'ordre de la banque.
    expect(quiz_question_items(page)).to_have_text(
        starts("Fichier Q2 ?", "Fichier Q3 ?", "Banque X ?", "Banque Y ?")
    )
    # Q1 remise dans une copie : à la fin, la copie n'a pas de fichier.
    page.get_by_role("link", name="Modifier le QCM").click()
    include_box(page, "Fichier Q1 ?").check()
    page.get_by_role("button", name="Enregistrer").click()
    expect(quiz_question_items(page)).to_have_text(
        starts("Fichier Q2 ?", "Fichier Q3 ?", "Banque X ?", "Banque Y ?", "Fichier Q1 ?")
    )


# --- CMP-05 : retirer du QCM, distinct de supprimer de la banque ---------------------------------


@pytest.mark.spec("CMP-05")
def test_remove_from_quiz_keeps_the_question_in_the_bank(teacher_page: Page):
    page = teacher_page
    q1, q2 = make_question("Commune ?"), make_question("Propre ?")
    make_quiz("QCM A", [q1, q2])
    make_quiz("QCM B", [q1])

    open_quiz(page, "QCM A")
    quiz_item(page, "Commune ?").get_by_role("button", name="Retirer du QCM").click()
    expect(status(page)).to_contain_text("retirée du QCM")
    expect(page.get_by_role("heading", name="QCM A", level=1)).to_be_visible()
    expect(quiz_question_items(page)).to_have_text(starts("Propre ?"))

    # Toujours dans la banque et dans l'autre QCM.
    open_bank(page)
    expect(question_card(page, "Commune ?")).to_contain_text("Utilisée dans : QCM B")
    open_quiz(page, "QCM B")
    expect(quiz_question_items(page)).to_have_text(starts("Commune ?"))

    # Retirer la dernière question : le QCM reste, vide.
    open_quiz(page, "QCM A")
    quiz_item(page, "Propre ?").get_by_role("button", name="Retirer du QCM").click()
    expect(page.get_by_role("main")).to_contain_text("Ce QCM ne contient aucune question.")
    assert Question.objects.count() == 2


# --- VER-01 : une question utilisée ne se modifie plus -----------------------------------------


@pytest.mark.spec("VER-01")
def test_used_question_gets_a_new_version(teacher_page: Page):
    page = teacher_page
    used = make_question("Capitale ?", [("Paris", True), ("Lyon", False)])
    unused = make_question("Libre ?")
    quiz = make_quiz("Contrôle", [used])
    make_quiz("Jamais lancé", [unused])
    other = make_quiz("Rattrapage", [used])
    session = launch(quiz)  # lancée, jamais démarrée

    # Une question jamais utilisée se modifie sur place, sans avertissement ni version.
    edit_from_bank(page, "Libre ?")
    expect(page.get_by_role("main")).not_to_contain_text("nouvelle version")
    fill_question(
        page, "Libre, modifiée ?", multiple=False, choices=[("oui", True), ("non", False)]
    )
    expect(status(page)).to_contain_text("Question enregistrée")
    assert Question.objects.filter(pk=unused.pk, text="Libre, modifiée ?").exists()

    # La question utilisée : avertissement, puis nouvelle version.
    edit_from_bank(page, "Capitale ?")
    expect(page.get_by_role("main")).to_contain_text("a déjà servi dans une session")
    fill_question(
        page, "Capitale de la France ?", multiple=False, choices=[("Lyon", False), ("Paris", True)]
    )
    expect(status(page)).to_contain_text("Nouvelle version enregistrée")

    # L'ancienne est inchangée, toujours celle de la session ; la nouvelle la remplace dans
    # les QCM.
    old = Question.objects.get(pk=used.pk)
    assert old.text == "Capitale ?"
    assert list(old.choices.values_list("text", "correct")) == [("Paris", True), ("Lyon", False)]
    assert list(session.source_questions.all()) == [old]
    new = Question.objects.get(text="Capitale de la France ?")
    assert new.pk != old.pk
    for title in ("Contrôle", "Rattrapage"):
        open_quiz(page, title)
        expect(quiz_item(page, "Capitale de la France ?")).to_have_count(1)
        expect(quiz_item(page, "Capitale ?")).to_have_count(0)
    assert list(other.ordered_questions()) == [new]
    assert Session.objects.get(pk=session.pk).questions[0]["text"] == "Capitale ?"

    # Enregistrer sans rien changer ne crée pas de version.
    count = Question.objects.count()
    launch(Quiz.objects.get(pk=other.pk))
    edit_from_bank(page, "Capitale de la France ?")
    page.get_by_role("button", name="Enregistrer").click()
    expect(status(page)).to_contain_text("Aucun changement")
    assert Question.objects.count() == count

    # Changer la seule bonne réponse, énoncé intact : c'est un changement, donc une version.
    edit_from_bank(page, "Capitale de la France ?")
    fill_question(
        page, "Capitale de la France ?", multiple=False, choices=[("Lyon", True), ("Paris", False)]
    )
    expect(status(page)).to_contain_text("Nouvelle version enregistrée")
    assert Question.objects.count() == count + 1
    assert list(new.choices.values_list("text", "correct")) == [("Lyon", False), ("Paris", True)]
    latest = Question.objects.get(previous=new)
    assert list(latest.choices.values_list("text", "correct")) == [("Lyon", True), ("Paris", False)]


# --- VER-02 : QCM touchés, limiter au QCM courant ----------------------------------------------


@pytest.mark.spec("VER-02")
def test_new_version_lists_quizzes_and_can_stay_in_one(teacher_page: Page):
    page = teacher_page
    used = make_question("Partagée ?")
    quiz_a = make_quiz("QCM A", [used])
    make_quiz("QCM B", [used])
    launch(quiz_a)

    # Depuis la fiche de QCM A : liste des QCM touchés et choix de la portée.
    edit_from_quiz(page, "QCM A", "Partagée ?")
    touched = page.get_by_role("list", name="QCM touchés")
    expect(touched.get_by_role("listitem")).to_have_text(["QCM A", "QCM B"])
    expect(page.get_by_label("Dans tous ces QCM")).to_be_checked()
    page.get_by_label("Seulement dans « QCM A »").check()
    fill_question(page, "Partagée, v2 ?", multiple=False, choices=[("oui", True), ("non", False)])
    expect(status(page)).to_contain_text("Nouvelle version enregistrée")

    open_quiz(page, "QCM A")
    expect(quiz_question_items(page)).to_have_text(starts("Partagée, v2 ?"))
    open_quiz(page, "QCM B")
    expect(quiz_question_items(page)).to_have_text(starts("Partagée ?"))

    # Depuis la banque, pas de choix : tous les QCM de l'ancienne version sont touchés.
    edit_from_bank(page, "Partagée ?")
    expect(page.get_by_role("list", name="QCM touchés").get_by_role("listitem")).to_have_text(
        ["QCM B"]
    )
    expect(page.get_by_label("Seulement dans « QCM B »")).to_have_count(0)
    fill_question(page, "Partagée, v3 ?", multiple=False, choices=[("oui", True), ("non", False)])
    open_quiz(page, "QCM B")
    expect(quiz_question_items(page)).to_have_text(starts("Partagée, v3 ?"))
    open_quiz(page, "QCM A")
    expect(quiz_question_items(page)).to_have_text(starts("Partagée, v2 ?"))


# --- VER-03 : ancienne version masquée, consultable ---------------------------------------------


@pytest.mark.spec("VER-03")
def test_old_version_leaves_the_bank_but_stays_visible(teacher_page: Page):
    page = teacher_page
    used = make_question("Capitale ?", [("Paris", True), ("Lyon", False)])
    kept = make_quiz("Gardé", [used])
    make_quiz("Changé", [used])
    launch(kept)

    # Limitée à « Changé » : l'ancienne version reste dans la banque, « Gardé » l'utilise.
    edit_from_quiz(page, "Changé", "Capitale ?")
    page.get_by_label("Seulement dans « Changé »").check()
    fill_question(page, "Capitale v2 ?", multiple=False, choices=[("Lyon", False), ("Paris", True)])
    open_bank(page)
    expect(question_card(page, "Capitale ?")).to_be_visible()
    expect(question_card(page, "Capitale v2 ?")).to_be_visible()

    # Remplacée partout : l'ancienne quitte la banque et la composition des QCM.
    edit_from_quiz(page, "Gardé", "Capitale ?")
    page.get_by_label("Dans tous ces QCM").check()
    fill_question(
        page, "Capitale v3 ?", multiple=False, choices=[("Paris", True), ("Lille", False)]
    )
    open_bank(page)
    expect(question_card(page, "Capitale ?")).to_have_count(0)
    open_quiz(page, "Changé")
    page.get_by_role("link", name="Modifier le QCM").click()
    expect(include_box(page, "Capitale ?")).to_have_count(0)
    expect(include_box(page, "Capitale v2 ?")).to_be_checked()

    # Consultable depuis la nouvelle version, propositions dans l'ordre d'alors (lettres du CSV).
    open_bank(page)
    card = previous_versions(page, "Capitale v3 ?")
    expect(
        card.get_by_role("list", name="Propositions : Capitale ?").get_by_role("listitem")
    ).to_have_text(["A. Paris (juste)", "B. Lyon"])

    # Un import ne partage pas une ancienne version : la question est recréée.
    count = Question.objects.count()
    import_amc(page, "Title: Ancienne\n\n* Capitale ?\n+ Paris\n- Lyon\n")
    assert Question.objects.count() == count + 1
    open_bank(page)
    expect(question_card(page, "Capitale ?")).to_have_count(1)


# --- IMP-10 : réimport d'un fichier AMC ---------------------------------------------------------


@pytest.mark.spec("IMP-10")
def test_reimport_completes_the_quiz(teacher_page: Page):
    page = teacher_page
    with_skipped = FILE + "\n* Fichier Q2 ?\n+ Trois\n- Quatre\n"  # doublon : écarté (IMP-03)
    import_amc(page, with_skipped, name="fichier.txt")
    quiz = Quiz.objects.get()

    # L'enseignant renomme le QCM, modifie Q1, retire Q2 du QCM, supprime Q3 de la banque.
    open_quiz(page, "Contrôle fichier")
    page.get_by_role("link", name="Modifier le QCM").click()
    fill_quiz(page, "Contrôle renommé", FILE_QUESTIONS)
    edit_from_quiz(page, "Contrôle renommé", "Fichier Q1 ?")
    fill_question(
        page, "Fichier Q1, corrigée ?", multiple=False, choices=[("Un", True), ("Deux", False)]
    )
    open_quiz(page, "Contrôle renommé")
    quiz_item(page, "Fichier Q2 ?").get_by_role("button", name="Retirer du QCM").click()
    Question.objects.get(text="Fichier Q3 ?").delete()  # BAN-07, testé en I1
    count = Question.objects.count()

    upload_amc(page, with_skipped, name="autre-nom.txt")
    expect_recap(page)
    main = page.get_by_role("main")
    expect(main).to_contain_text("complète le QCM « Contrôle renommé »")
    expect(main).to_contain_text("1 déjà là, 2 ajoutées")
    rows = page.get_by_role("region", name="Questions du fichier").get_by_role("listitem")
    expect(rows).to_have_text(
        [
            re.compile(r"^Fichier Q1 \?.*déjà là"),
            re.compile(r"^Fichier Q2 \?.*ajoutée"),
            re.compile(r"^Fichier Q3 \?.*ajoutée"),
        ]
    )
    expect(
        page.get_by_role("region", name="Questions écartées").get_by_role("listitem")
    ).to_have_count(1)
    confirm_import(page)
    expect(status(page)).to_contain_text("QCM complété : 2 questions ajoutées")

    # Même QCM, titre gardé, modification gardée, Q2 remise, Q3 recréée, à leur place.
    expect(page.get_by_role("heading", name="Contrôle renommé", level=1)).to_be_visible()
    expect(quiz_question_items(page)).to_have_text(
        starts("Fichier Q1, corrigée ?", "Fichier Q2 ?", "Fichier Q3 ?")
    )
    assert Quiz.objects.get().pk == quiz.pk
    assert Question.objects.count() == count + 1

    # Rien à compléter : tout est « déjà là ».
    upload_amc(page, with_skipped)
    expect(page.get_by_role("main")).to_contain_text("3 déjà là, 0 ajoutée")


@pytest.mark.spec("IMP-10")
def test_reimport_recognises_a_new_version(teacher_page: Page):
    page = teacher_page
    import_amc(page, FILE, name="fichier.txt")
    launch(Quiz.objects.get())
    edit_from_bank(page, "Fichier Q1 ?")
    fill_question(page, "Fichier Q1 v2 ?", multiple=False, choices=[("Un", True), ("Deux", False)])
    expect(status(page)).to_contain_text("Nouvelle version enregistrée")

    upload_amc(page, FILE)
    expect(page.get_by_role("main")).to_contain_text("3 déjà là, 0 ajoutée")


@pytest.mark.spec("IMP-10")
def test_corrected_file_or_deleted_quiz_gives_a_new_quiz(teacher_page: Page):
    page = teacher_page
    import_amc(page, FILE, name="fichier.txt")
    edit_from_bank(page, "Fichier Q1 ?")
    fill_question(
        page, "Fichier Q1, corrigée ?", multiple=False, choices=[("Un", True), ("Deux", False)]
    )

    # Fichier corrigé : un autre contenu, un nouveau QCM.
    corrected = FILE.replace("Title: Contrôle fichier", "Title: Contrôle corrigé")
    upload_amc(page, corrected)
    expect_recap(page)
    expect(page.get_by_role("main")).not_to_contain_text("complète le QCM")
    confirm_import(page)
    assert Quiz.objects.count() == 2

    # QCM d'origine supprimé : le réimport crée un QCM, questions reconnues par leur origine.
    open_quiz(page, "Contrôle fichier")
    page.get_by_role("link", name="Supprimer").click()
    page.get_by_role("button", name="Supprimer").click()
    count = Question.objects.count()
    upload_amc(page, FILE)
    expect(page.get_by_role("main")).not_to_contain_text("complète le QCM")
    confirm_import(page)
    expect(quiz_question_items(page)).to_have_text(
        starts("Fichier Q1, corrigée ?", "Fichier Q2 ?", "Fichier Q3 ?")
    )
    assert Question.objects.count() == count


@pytest.mark.spec("IMP-10")
def test_file_imported_before_i15_is_recognised_by_identity_then_place(teacher_page: Page):
    from bank.models import QuestionOrigin

    page = teacher_page
    import_amc(page, FILE, name="fichier.txt")
    open_quiz(page, "Contrôle fichier")
    edit_from_quiz(page, "Contrôle fichier", "Fichier Q2 ?")
    fill_question(
        page, "Fichier Q2, corrigée ?", multiple=False, choices=[("Trois", True), ("Quatre", False)]
    )
    QuestionOrigin.objects.all().delete()  # comme un import d'avant I15
    count = Question.objects.count()

    upload_amc(page, FILE)
    expect(page.get_by_role("main")).to_contain_text("3 déjà là, 0 ajoutée")
    confirm_import(page)
    open_quiz(page, "Contrôle fichier")
    expect(quiz_question_items(page)).to_have_text(
        starts("Fichier Q1 ?", "Fichier Q2, corrigée ?", "Fichier Q3 ?")
    )
    assert Question.objects.count() == count
    # Les origines sont désormais enregistrées : la place n'est plus nécessaire.
    assert QuestionOrigin.objects.count() == 3


@pytest.mark.spec("IMP-10")
def test_before_i15_identity_comes_before_place(teacher_page: Page):
    # QCM d'avant I15 : Q1 modifiée sur place, Q2 retirée ; il reste [Q1 modifiée, Q3].
    # Q3 est reconnue par identité (rang 3) ; Q1 modifiée par sa place (rang 1) ; la place 2,
    # occupée par Q3, n'est pas libre : Q2, toujours dans la banque, est remise à son rang.
    from bank.models import QuestionOrigin

    page = teacher_page
    import_amc(page, FILE, name="fichier.txt")
    open_quiz(page, "Contrôle fichier")
    quiz_item(page, "Fichier Q2 ?").get_by_role("button", name="Retirer du QCM").click()
    expect(status(page)).to_contain_text("retirée du QCM")
    edit_from_quiz(page, "Contrôle fichier", "Fichier Q1 ?")
    fill_question(
        page, "Fichier Q1, corrigée ?", multiple=False, choices=[("Un", True), ("Deux", False)]
    )
    QuestionOrigin.objects.all().delete()  # comme un import d'avant I15
    count = Question.objects.count()

    upload_amc(page, FILE)
    expect(page.get_by_role("main")).to_contain_text("2 déjà là, 1 ajoutée")
    confirm_import(page)
    open_quiz(page, "Contrôle fichier")
    expect(quiz_question_items(page)).to_have_text(
        starts("Fichier Q1, corrigée ?", "Fichier Q2 ?", "Fichier Q3 ?")
    )
    assert Question.objects.count() == count
