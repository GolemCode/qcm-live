"""Incrément 19 : espace enseignant en « Signalétique », recherche et filtres de la banque,
envoi d'une image depuis le formulaire d'une question.

- BAN-11 : texte (énoncé et propositions, sans majuscules ni accents), type, utilisation,
  tri, 20 questions par page, critères dans l'adresse.
- BAN-12 : QCM d'origine (questions venues du fichier, même retirées du QCM).
- BAN-13 : « déjà posée » ou « jamais posée » à un groupe (calcul de CMP-03).
- CNT-06 : image envoyée depuis le formulaire, ajoutée en fin d'énoncé.
- VIS-05 : bandeau, rubrique en cours, filets, étiquettes, images bornées, largeur.
- ACC-03 : axe-core, contraste et clavier sur les pages de l'espace enseignant.
"""

from __future__ import annotations

import io
import re

import pytest
from django.utils import timezone
from PIL import Image as PILImage
from playwright.sync_api import Locator, Page, ViewportSize, expect

from bank.forms import QuizCopyForm
from bank.importer import import_quiz
from bank.models import Image, Question
from tests.e2e.a11y import axe_violations, keyboard_problems, low_contrasts
from tests.e2e.amc_ui import upload_amc
from tests.e2e.bank_ui import fill_question, open_bank
from tests.e2e.conftest import TEACHER_USERNAME, assert_fits_width
from tests.e2e.live_ui import fill_launch, open_sessions
from tests.e2e.test_i16_posed import CAPITAL, OCEAN, SKY, SUM, history
from tests.e2e.test_i17_content import PDF, SVG, archive, picture
from tests.factories import (
    current_year,
    make_group,
    make_participant,
    make_question,
    make_quiz,
    make_session,
    new_version,
    rewind,
)

INK = "rgb(17, 17, 17)"
STUDENTS = [(1, "001", "DURAND Élise"), (2, "002", "MARTIN Léo")]


# --- Aides -----------------------------------------------------------------------------------


def search_form(page: Page) -> Locator:
    return page.get_by_role("search", name="Rechercher dans la banque")


def search(page: Page, **criteria: str) -> None:
    """Remplit les critères donnés (les autres restent tels quels), puis « Filtrer »."""
    form = search_form(page)
    labels = {
        "text": "Rechercher",
        "kind": "Type",
        "use": "Utilisation",
        "origin": "QCM d'origine",
        "posed": "Posée à un groupe",
        "sort": "Tri",
    }
    for key, value in criteria.items():
        field = form.get_by_label(labels[key], exact=True)
        if key == "text":
            field.fill(value)
        else:
            field.select_option(label=value)
    form.get_by_role("button", name="Filtrer").click()


def titles(page: Page) -> list[str]:
    """Énoncés des questions affichées, dans l'ordre."""
    page.wait_for_load_state("load")
    return [t.strip() for t in page.get_by_role("article").locator("h2").all_inner_texts()]


def count(page: Page) -> Locator:
    return page.get_by_role("main").get_by_text(re.compile(r"^\d+ questions? sur \d+$"))


def options(page: Page, label: str) -> list[str]:
    return search_form(page).get_by_label(label, exact=True).locator("option").all_inner_texts()


def article(page: Page, text: str) -> Locator:
    return page.get_by_role("article").filter(has_text=text)


def tall_picture() -> bytes:
    buffer = io.BytesIO()
    PILImage.new("RGB", (400, 1600), "red").save(buffer, "PNG")
    return buffer.getvalue()


def loaded(images: Locator) -> list[bool]:
    return images.evaluate_all("els => els.map(e => e.complete && e.naturalWidth > 0)")


def heights(images: Locator) -> list[float]:
    return images.evaluate_all("els => els.map(e => e.getBoundingClientRect().height)")


# --- BAN-11 : texte, type, utilisation ------------------------------------------------------

ECOLE = "Où est l'École normale ?"
RHONE = "Capitale du Rhône ?"
VILLES = "Villes de France ?"
CIEL = "Couleur du ciel ?"


def four_questions() -> None:
    ecole = make_question(ECOLE, [("Paris", True), ("Rome", False)])
    make_question(RHONE, [("LYON", True), ("Marseille", False)])
    make_question(VILLES, [("Paris", True), ("Lyon", True), ("Rome", False)], multiple=True)
    ciel = make_question(CIEL, [("Bleu", True), ("Vert", False)])
    make_quiz("Géographie", [ecole, ciel])


@pytest.mark.spec("BAN-11")
def test_search_by_text_kind_and_use(teacher_page: Page):
    page = teacher_page
    four_questions()
    open_bank(page)
    assert titles(page) == [CIEL, VILLES, RHONE, ECOLE]  # plus récentes d'abord
    expect(count(page)).to_have_text("4 questions sur 4")

    search(page, text="ecole")  # énoncé, sans accent ni majuscule
    assert titles(page) == [ECOLE]
    expect(count(page)).to_have_text("1 question sur 4")
    search(page, text="lyon")  # propositions, sans majuscule ; « Lyon » n'est dans aucun énoncé
    assert titles(page) == [VILLES, RHONE]
    search(page, kind="Choix multiple")  # les critères se combinent
    assert titles(page) == [VILLES]
    search(page, text="", kind="Choix simple")
    assert titles(page) == [CIEL, RHONE, ECOLE]
    search(page, kind="Tous les types", use="Dans au moins un QCM")
    assert titles(page) == [CIEL, ECOLE]
    search(page, use="Dans aucun QCM", text="PARIS")
    assert titles(page) == [VILLES]

    search(page, use="Toutes", text="zzz")
    assert titles(page) == []
    expect(page.get_by_role("main")).to_contain_text("Aucune question ne correspond.")
    page.get_by_role("link", name="Effacer les critères").click()
    assert titles(page) == [CIEL, VILLES, RHONE, ECOLE]
    expect(search_form(page).get_by_label("Rechercher", exact=True)).to_have_value("")


@pytest.mark.spec("BAN-11")
def test_sort_and_twenty_questions_per_page(teacher_page: Page):
    page = teacher_page
    for k in range(1, 26):
        make_question(f"Question {k:02d} ?")
    for k in range(1, 23):
        make_question(f"Multiple {k:02d} ?", [("a", True), ("b", True)], multiple=True)
    open_bank(page)
    expect(count(page)).to_have_text("47 questions sur 47")
    assert titles(page) == [f"Multiple {k:02d} ?" for k in range(22, 2, -1)]
    pages = page.get_by_role("navigation", name="Pages")
    expect(pages).to_contain_text("Page 1 sur 3")
    expect(pages.get_by_role("link", name="Page précédente")).to_have_count(0)

    # Changer de page garde les critères et le tri.
    search(page, kind="Choix multiple", sort="Plus anciennes d'abord")
    assert titles(page) == [f"Multiple {k:02d} ?" for k in range(1, 21)]
    expect(count(page)).to_have_text("22 questions sur 47")
    pages.get_by_role("link", name="Page suivante").click()
    assert titles(page) == ["Multiple 21 ?", "Multiple 22 ?"]
    expect(pages).to_contain_text("Page 2 sur 2")
    expect(pages.get_by_role("link", name="Page suivante")).to_have_count(0)
    form = search_form(page)
    expect(form.get_by_label("Type", exact=True).locator("option:checked")).to_have_text(
        "Choix multiple"
    )
    expect(form.get_by_label("Tri", exact=True).locator("option:checked")).to_have_text(
        "Plus anciennes d'abord"
    )
    pages.get_by_role("link", name="Page précédente").click()
    assert titles(page)[0] == "Multiple 01 ?"


@pytest.mark.spec("BAN-11")
def test_sort_by_statement_ignores_case_and_accents(teacher_page: Page):
    page = teacher_page
    for text in ("Zèbre ?", "été ?", "Eau ?", "arbre ?", "Ecole ?"):
        make_question(text)
    open_bank(page)
    search(page, sort="Énoncé de A à Z")
    assert titles(page) == ["arbre ?", "Eau ?", "Ecole ?", "été ?", "Zèbre ?"]


@pytest.mark.spec("BAN-11")
def test_criteria_live_in_the_address(teacher_page: Page):
    """Un retour en arrière, ou le retour après « Modifier », retrouve les critères."""
    page = teacher_page
    four_questions()
    open_bank(page)
    search(page, text="lyon", kind="Choix multiple")
    assert titles(page) == [VILLES]
    filtered = page.url
    assert "lyon" in filtered

    article(page, VILLES).get_by_role("link", name="Modifier").click()
    page.get_by_label("Énoncé").fill("Villes de France, au choix ?")
    page.get_by_role("button", name="Enregistrer").click()
    expect(page.get_by_role("status")).to_contain_text("Question enregistrée")
    assert titles(page) == ["Villes de France, au choix ?"]
    expect(search_form(page).get_by_label("Rechercher", exact=True)).to_have_value("lyon")

    page.get_by_role("navigation", name="Espace enseignant").get_by_role("link", name="QCM").click()
    page.go_back()
    assert titles(page) == ["Villes de France, au choix ?"]
    page.goto(filtered)
    expect(
        search_form(page).get_by_label("Type", exact=True).locator("option:checked")
    ).to_have_text("Choix multiple")

    # « Annuler » ramène aussi aux critères.
    article(page, "Villes de France, au choix ?").get_by_role("link", name="Modifier").click()
    page.get_by_role("link", name="Annuler").click()
    assert titles(page) == ["Villes de France, au choix ?"]


# --- BAN-12 : QCM d'origine -----------------------------------------------------------------

FILE_1 = "Title: Contrôle 1\n\n* Question A1 ?\n+ Oui\n- Non\n\n* Question A2 ?\n+ Oui\n- Non\n"
FILE_2 = "Title: Contrôle 2\n\n* Question A2 ?\n+ Oui\n- Non\n\n* Question B1 ?\n+ Oui\n- Non\n"
FILE_3 = "Title: bilan\n\n* Question C1 ?\n+ Oui\n- Non\n"
A2_NEW = "Question A2, nouvelle version ?"


@pytest.mark.spec("BAN-12")
def test_filter_by_origin_quiz(teacher_page: Page):
    page = teacher_page
    first = import_quiz(FILE_1.encode(), "controle1.txt")
    import_quiz(FILE_2.encode(), "controle2.txt")  # Question A2 partagée (IMP-07)
    import_quiz(FILE_3.encode(), "bilan.txt")
    manual = make_question("Question manuelle ?")
    make_quiz("Composé à la main", [manual])
    copy = QuizCopyForm({"title": "Copie du contrôle 1"}, source=first)
    assert copy.is_valid(), copy.errors
    copy.save()  # CMP-01 : ne vient d'aucun fichier
    _a1, a2 = first.ordered_questions()
    first.set_questions([a2.pk])  # « Retirer du QCM » (CMP-05)
    make_session(first, make_group("TD", STUDENTS))  # A2 utilisée : sa modification la versionne
    new_version(a2, A2_NEW)

    open_bank(page)
    assert options(page, "QCM d'origine") == ["Tous les QCM", "bilan", "Contrôle 1", "Contrôle 2"]
    search(page, origin="Contrôle 1")
    assert titles(page) == [A2_NEW, "Question A1 ?"]  # A1, retirée du QCM, en vient toujours
    search(page, origin="Contrôle 2")
    assert titles(page) == [A2_NEW, "Question B1 ?"]
    search(page, origin="bilan", text="question")
    assert titles(page) == ["Question C1 ?"]
    search(page, origin="Contrôle 1", text="B1")
    assert titles(page) == []
    search(page, origin="Tous les QCM", text="")
    assert len(titles(page)) == 5


# --- BAN-13 : déjà posée ou jamais posée à un groupe ----------------------------------------


@pytest.mark.spec("BAN-13")
def test_filter_posed_or_never_posed_to_a_group(teacher_page: Page):
    page = teacher_page
    history()
    open_bank(page)
    assert options(page, "Posée à un groupe") == [
        "Sans filtre",
        "Déjà posée à ITI4 — 2025-2026",
        "Jamais posée à ITI4 — 2025-2026",
        "Déjà posée à ITI4 — 2024-2025",
        "Jamais posée à ITI4 — 2024-2025",
        "Déjà posée à ITI5 — 2025-2026",
        "Jamais posée à ITI5 — 2025-2026",
        f"Déjà posée à TD vierge — {current_year()}",
        f"Jamais posée à TD vierge — {current_year()}",
    ]
    search(page, posed="Déjà posée à ITI4 — 2025-2026")
    assert titles(page) == [CAPITAL, SKY]
    expect(article(page, CAPITAL)).to_contain_text("posée à 2 étudiants sur 5")
    expect(article(page, SKY)).to_contain_text("posée à 1 étudiant sur 5")
    search(page, posed="Jamais posée à ITI4 — 2025-2026")
    assert titles(page) == [OCEAN, SUM]
    expect(page.get_by_role("main")).not_to_contain_text("posée à")
    search(page, posed="Déjà posée à ITI4 — 2024-2025")  # même nom, autre année
    assert titles(page) == [OCEAN]
    expect(article(page, OCEAN)).to_contain_text("posée à 4 étudiants sur 4")
    search(page, posed=f"Jamais posée à TD vierge — {current_year()}", text="océan")
    assert titles(page) == [OCEAN]
    search(page, posed=f"Déjà posée à TD vierge — {current_year()}", text="")
    assert titles(page) == []


# --- CNT-06 : envoi d'une image depuis le formulaire ----------------------------------------


def attach(page: Page, name: str, data: bytes, mime: str = "image/png") -> None:
    page.get_by_label("Image", exact=True).set_input_files(
        files=[{"name": name, "mimeType": mime, "buffer": data}]
    )


YES = [("Oui", True), ("Non", False)]


@pytest.mark.spec("CNT-06")
def test_image_sent_from_the_form(teacher_page: Page):
    page = teacher_page
    open_bank(page)
    page.get_by_role("link", name="Nouvelle question").click()
    attach(page, "Courbe été.png", picture("PNG"))
    fill_question(page, "Quelle courbe ?", multiple=False, choices=YES)
    expect(page.get_by_role("status")).to_contain_text("Question enregistrée")
    stored = Image.objects.get()
    assert re.fullmatch(r"Courbe_ete-[0-9a-f]{8}\.png", stored.name), stored.name
    assert Question.objects.get().text == f"Quelle courbe ?\n\n\\includegraphics{{{stored.name}}}"
    shown = article(page, "Quelle courbe ?").locator("h2 img")
    expect(shown).to_have_count(1)
    page.wait_for_load_state("load")
    assert loaded(shown) == [True]

    # La référence se déplace ensuite dans une proposition : le formulaire la connaît.
    article(page, "Quelle courbe ?").get_by_role("link", name="Modifier").click()
    reference = f"\\includegraphics{{{stored.name}}}"
    fill_question(
        page, "Quelle courbe ?", multiple=False, choices=[(reference, True), ("Non", False)]
    )
    expect(page.get_by_role("status")).to_contain_text("Question enregistrée")
    expect(article(page, "Quelle courbe ?").locator("li img")).to_have_count(1)

    # La même image, envoyée pour une autre question, est partagée ; un SVG est accepté.
    page.get_by_role("link", name="Nouvelle question").click()
    attach(page, "autre-nom.png", picture("PNG"))
    fill_question(page, "Même courbe ?", multiple=False, choices=YES)
    expect(page.get_by_role("status")).to_contain_text("Question enregistrée")
    assert Image.objects.count() == 1
    assert Question.objects.get(text__startswith="Même courbe").text.endswith(reference)
    page.get_by_role("link", name="Nouvelle question").click()
    attach(page, "logo.svg", SVG, "image/svg+xml")
    fill_question(page, "Quel logo ?", multiple=False, choices=YES)
    expect(page.get_by_role("status")).to_contain_text("Question enregistrée")
    assert Image.objects.count() == 2


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


@pytest.mark.spec("CNT-06")
def test_refused_image_saves_nothing(teacher_page: Page):
    page = teacher_page
    open_bank(page)
    refused = [
        ("figure.pdf", PDF, "application/pdf", "image PDF ou EPS, à convertir en PNG, JPEG ou SVG"),
        ("photo.gif", b"GIF89a", "image/gif", "format d'image non pris en charge"),
        ("grand.png", PNG_SIGNATURE.ljust(2_000_001, b"\0"), "image/png", "image de plus de 2 Mo"),
        ("piege.svg", b'<!DOCTYPE svg [<!ENTITY a "b">]><svg/>', "image/svg+xml", "illisible"),
    ]
    page.get_by_role("link", name="Nouvelle question").click()
    for name, data, mime, reason in refused:
        attach(page, name, data, mime)
        fill_question(page, "Quelle figure ?", multiple=False, choices=YES)
        expect(page.get_by_role("alert")).to_contain_text(f"Image : {reason}")
        expect(page.get_by_label("Énoncé")).to_have_value("Quelle figure ?")
        assert (Question.objects.count(), Image.objects.count()) == (0, 0), name

    # Tout juste à la limite : 2 Mo exactement.
    attach(page, "limite.png", PNG_SIGNATURE.ljust(2_000_000, b"\0"))
    fill_question(page, "Quelle figure ?", multiple=False, choices=YES)
    expect(page.get_by_role("status")).to_contain_text("Question enregistrée")
    assert (Question.objects.count(), Image.objects.count()) == (1, 1)


@pytest.mark.spec("CNT-06")
def test_image_is_not_kept_when_the_form_has_another_error(teacher_page: Page):
    page = teacher_page
    open_bank(page)
    page.get_by_role("link", name="Nouvelle question").click()
    attach(page, "graphe.png", picture("PNG"))
    fill_question(page, "Quel graphe ?", multiple=False, choices=[("Oui", False), ("Non", False)])
    alert = page.get_by_role("alert")
    expect(alert).to_contain_text("Une question à choix simple a exactement une bonne réponse.")
    expect(alert).to_contain_text("L'image n'a pas été gardée : choisissez-la de nouveau.")
    assert (Question.objects.count(), Image.objects.count()) == (0, 0)
    expect(page.get_by_label("Énoncé")).to_have_value("Quel graphe ?")

    attach(page, "graphe.png", picture("PNG"))
    fill_question(page, "Quel graphe ?", multiple=False, choices=YES)
    expect(page.get_by_role("status")).to_contain_text("Question enregistrée")
    assert (Question.objects.count(), Image.objects.count()) == (1, 1)


@pytest.mark.spec("CNT-06")
def test_image_added_to_a_used_question_makes_a_new_version(teacher_page: Page):
    page = teacher_page
    question = make_question("Quel schéma ?")
    make_session(make_quiz("Séance", [question]), make_group("TD", STUDENTS))
    open_bank(page)
    article(page, "Quel schéma ?").get_by_role("link", name="Modifier").click()
    attach(page, "schema.png", picture("PNG", "blue"))
    page.get_by_role("button", name="Enregistrer").click()
    expect(page.get_by_role("status")).to_contain_text("Nouvelle version enregistrée")
    question.refresh_from_db()
    assert question.text == "Quel schéma ?"
    new = Question.objects.get(previous=question)
    assert new.text == f"Quel schéma ?\n\n\\includegraphics{{{Image.objects.get().name}}}"


# --- VIS-05 : présentation de l'espace enseignant -------------------------------------------

SECTIONS = ["Accueil", "Banque de questions", "QCM", "Groupes", "Sessions"]


def assert_band(page: Page, current: str | None) -> None:
    """Bandeau noir : logo, navigation (rubrique en cours marquée), déconnexion."""
    band = page.get_by_role("banner")
    expect(band).to_have_css("background-color", INK)
    expect(band.get_by_role("link", name="QCM Live")).to_be_visible()
    nav = band.get_by_role("navigation", name="Espace enseignant")
    for section in SECTIONS:
        link = nav.get_by_role("link", name=section, exact=True)
        expect(link).to_be_visible()
        if section == current:
            expect(link).to_have_attribute("aria-current", "page")
        else:
            expect(link).not_to_have_attribute("aria-current", "page")
    expect(band.get_by_role("button", name=f"Se déconnecter ({TEACHER_USERNAME})")).to_be_visible()


def assert_title_rule(page: Page) -> None:
    title = page.get_by_role("heading", level=1)
    width = title.evaluate("e => parseFloat(getComputedStyle(e).borderBottomWidth)")
    assert width >= 3, width
    expect(title).to_have_css("border-bottom-color", INK)


@pytest.mark.spec("VIS-05")
def test_teacher_band_marks_the_current_section(teacher_page: Page, live_server):
    page = teacher_page
    quiz = make_quiz("Contrôle", [make_question("Deux plus deux ?")])
    group = make_group("TD", STUDENTS)
    session = make_session(quiz, group)
    base = live_server.url
    assert_band(page, "Accueil")
    for section in SECTIONS:
        page.get_by_role("banner").get_by_role("link", name=section, exact=True).click()
        assert_band(page, section)
        assert_title_rule(page)
    # Pages de second niveau : la rubrique dont elles relèvent.
    for path, current in [
        ("/prof/questions/nouvelle/", "Banque de questions"),
        (f"/prof/qcm/{quiz.pk}/", "QCM"),
        ("/prof/qcm/importer/", "QCM"),
        (f"/prof/groupes/{group.pk}/", "Groupes"),
        ("/prof/sessions/lancer/", "Sessions"),
        (f"/prof/sessions/{session.code}/connectes/", "Sessions"),
        ("/prof/reseau/", "Accueil"),
    ]:
        page.goto(base + path)
        assert_band(page, current)
        assert_title_rule(page)
    page.get_by_role("banner").get_by_role("link", name="QCM Live").click()
    expect(page.get_by_role("heading", name="Espace enseignant", level=1)).to_be_visible()


@pytest.mark.spec("VIS-05")
def test_cards_and_labels(teacher_page: Page):
    page = teacher_page
    question = make_question("Deux plus deux ?", [("4", True), ("5", False)], scoring="b=2")
    make_quiz("Contrôle", [question])
    open_bank(page)
    card = article(page, "Deux plus deux ?")
    width = card.evaluate("e => parseFloat(getComputedStyle(e).borderTopWidth)")
    assert width >= 2, width
    expect(card).to_have_css("border-top-color", INK)
    label = card.get_by_text("Choix simple", exact=True)
    expect(label).to_have_css("text-transform", "uppercase")
    spacing = label.evaluate("e => parseFloat(getComputedStyle(e).letterSpacing)")
    assert spacing > 0, spacing
    expect(card).to_contain_text("b=2")
    expect(card).to_contain_text("Contrôle")


@pytest.mark.spec("VIS-05")
def test_images_keep_a_text_height_on_every_teacher_page(teacher_page: Page, live_server):
    """Point hérité d'I17 : la liste de confirmation du lancement montrait l'image en grand."""
    page = teacher_page
    text = "Title: Figures\n\n* Quelle figure ? !grand.png!\n+ Oui\n- Non\n"
    quiz = import_quiz(archive({"f.txt": text, "grand.png": tall_picture()}), "f.zip")
    group = make_group("TD", STUDENTS)
    played = make_session(quiz, group)
    make_participant(played, 1)
    played.start(timezone.now())
    question = quiz.ordered_questions().get()
    base = live_server.url

    def assert_bounded(where: str) -> None:
        images = page.get_by_role("main").locator("img")
        expect(images.first).to_be_visible()
        page.wait_for_load_state("load")
        found = heights(images)
        assert found and all(0 < h < 200 for h in found), (where, found)  # loin de 1600 px

    open_bank(page)
    assert_bounded("banque")
    page.goto(f"{base}/prof/qcm/{quiz.pk}/")
    assert_bounded("fiche du QCM")
    page.goto(f"{base}/prof/qcm/{quiz.pk}/modifier/")
    assert_bounded("composition")
    page.goto(f"{base}/prof/questions/{question.pk}/supprimer/")
    assert_bounded("confirmation de suppression")
    open_sessions(page)
    page.get_by_role("link", name="Lancer une session").click()
    fill_launch(page, "Figures", f"TD — {current_year()}", 1, 30)
    expect(page.get_by_role("heading", name="Questions déjà posées")).to_be_visible()
    assert_bounded("confirmation du lancement")


def teacher_paths(base: str) -> list[str]:
    """Pages de l'espace enseignant, avec des contenus longs : tableaux, mots sans espace."""
    long = "Anticonstitutionnellement" * 3
    question = make_question(f"{long} ?", [(long, True), ("Non", False)], scoring="b=2,m=-0.5")
    quiz = make_quiz(f"Contrôle {long}", [question])
    group = make_group("TD", [(1, "001", long), (2, "002", "MARTIN Léo")])
    session = make_session(quiz, group)
    make_participant(session, 1)
    session.start(timezone.now())
    rewind(session, 600)
    return [
        "/prof/",
        "/prof/questions/",
        "/prof/questions/nouvelle/",
        f"/prof/questions/{question.pk}/modifier/",
        "/prof/qcm/",
        f"/prof/qcm/{quiz.pk}/",
        f"/prof/qcm/{quiz.pk}/modifier/",
        "/prof/qcm/importer/",
        "/prof/groupes/",
        f"/prof/groupes/{group.pk}/",
        "/prof/groupes/importer/",
        "/prof/sessions/",
        "/prof/sessions/lancer/",
        f"/prof/sessions/{session.code}/resultats/",
        "/prof/reseau/",
    ]


@pytest.mark.spec("VIS-05")
@pytest.mark.parametrize("width,height", [(1280, 720), (360, 740)])
def test_teacher_pages_never_scroll_sideways(teacher_page: Page, live_server, width, height):
    page = teacher_page
    page.set_viewport_size(ViewportSize(width=width, height=height))
    for path in teacher_paths(live_server.url):
        page.goto(live_server.url + path)
        try:
            assert_fits_width(page)
        except AssertionError as error:
            raise AssertionError(f"{path} : {error}") from None


# --- ACC-03 : accessibilité de l'espace enseignant ------------------------------------------


@pytest.mark.spec("ACC-03")
def test_teacher_pages_are_accessible(teacher_page: Page, live_server):
    page = teacher_page
    base = live_server.url
    paths = teacher_paths(base)
    four_questions()
    history_quiz = history()
    import_quiz(FILE_1.encode(), "controle1.txt")
    problems: dict[str, list[str]] = {}

    def check(where: str) -> None:
        found = axe_violations(page) + [f"contraste {c}" for c in low_contrasts(page)]
        found += keyboard_problems(page)
        if found:
            problems[where] = found

    for path in paths:
        page.goto(base + path)
        check(path)

    # Banque filtrée (déjà posée, avec la mention), pagination, récapitulatif d'import, erreurs.
    open_bank(page)
    search(page, posed="Déjà posée à ITI4 — 2025-2026")
    check("banque filtrée")
    for k in range(21):
        make_question(f"Remplissage {k} ?")
    open_bank(page)
    check("banque, pagination")
    page.get_by_role("link", name="Nouvelle question").click()
    page.get_by_role("button", name="Enregistrer").click()
    check("formulaire de question, erreurs")
    upload_amc(page, FILE_2, "c.txt")
    expect(page.get_by_role("heading", name="Récapitulatif de l'import")).to_be_visible()
    check("récapitulatif d'import")
    open_sessions(page)
    page.get_by_role("link", name="Lancer une session").click()
    fill_launch(page, history_quiz.title, "ITI4 — 2025-2026", 1, 30)
    expect(page.get_by_role("heading", name="Questions déjà posées")).to_be_visible()
    check("confirmation du lancement")
    assert problems == {}
