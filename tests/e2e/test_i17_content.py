"""Incrément 17 : formules, code et images dans les énoncés et les propositions (CNT-01 à
CNT-04), écrits en LaTeX léger dans le formulaire ou importés d'un fichier AMC-TXT, seul ou
dans une archive ZIP avec ses images (IMP-08).

Chaque écran est surveillé : aucune requête ne part vers un autre serveur que l'application
(la classe peut être sans Internet) et la CSP stricte ne refuse rien."""

from __future__ import annotations

import io
import zipfile

import pytest
from PIL import Image as PILImage
from playwright.sync_api import Locator, Page, expect

from bank.models import Question, Quiz
from tests.e2e.amc_ui import (
    expect_recap,
    import_amc,
    recap_items,
    upload_amc,
)
from tests.e2e.bank_ui import create_question, fill_question, open_bank, question_card
from tests.e2e.live_setup import expect_slot, started
from tests.e2e.live_ui import card
from tests.factories import make_group, make_quiz, make_session

STUDENTS = [("00123", "DURAND Élise")]
SKIPPED = "Questions écartées"


# --- Surveillance des écrans -------------------------------------------------------------------


def watch(screen: Page, base_url: str) -> list[str]:
    """Requêtes vers un autre serveur que l'application, et refus de la CSP, relevés sur cet
    écran à partir de maintenant : la liste doit rester vide."""
    problems: list[str] = []

    def request(r) -> None:
        if not r.url.startswith((base_url, "data:")):
            problems.append(f"requête : {r.url}")

    def console(message) -> None:
        if "Content Security Policy" in message.text:
            problems.append(f"CSP : {message.text}")

    screen.on("request", request)
    screen.on("console", console)
    return problems


def loaded(images: Locator) -> list[bool]:
    """Pour chaque image, vrai si elle est chargée et décodée."""
    return images.evaluate_all("els => els.map(e => e.complete && e.naturalWidth > 0)")


def font(locator: Locator) -> str:
    return locator.evaluate("e => getComputedStyle(e).fontFamily")


def rendered_text(locator: Locator) -> str:
    """Texte que l'œil voit des formules rendues (sans la MathML destinée aux lecteurs d'écran)."""
    return locator.evaluate(
        "e => [...e.querySelectorAll('.katex-html')].map(k => k.textContent).join(' ')"
    )


def article(page: Page, text: str) -> Locator:
    """Fiche d'une question de la banque, repérée par un morceau de son énoncé."""
    return page.get_by_role("article").filter(has_text=text)


def live(page: Page, base_url: str, new_phone, quiz: Quiz) -> Page:
    """Le QCM lancé pour un étudiant, démarré au tableau ; son téléphone, au premier créneau."""
    session = make_session(quiz, make_group("TD1", STUDENTS), shown=1, seconds=60)
    (phone,) = started(page, base_url, new_phone, session, ["00123"])
    expect_slot(phone, 0)
    return phone


def propositions(phone: Page) -> Locator:
    return phone.get_by_role("group", name="Propositions")


# --- CNT-01 : formules ------------------------------------------------------------------------

HALF = r"Que vaut $\frac{1}{2} + \frac{1}{2}$ ?"


@pytest.mark.spec("CNT-01")
def test_formulas_on_board_and_phone_without_internet(teacher_page: Page, live_server, new_phone):
    page = teacher_page
    problems = watch(page, live_server.url)
    create_question(page, HALF, choices=[("$1$", True), ("$x^2$", False)])
    bank_card = page.get_by_role("article")
    expect(bank_card.locator(".katex-html .mfrac")).to_have_count(2)
    expect(bank_card.get_by_role("listitem").locator(".katex-html .msupsub")).to_have_count(1)

    phone = live(page, live_server.url, new_phone, make_quiz("Formules", [Question.objects.get()]))
    phone_problems = watch(phone, live_server.url)
    phone.reload()
    expect_slot(phone, 0)

    statement = card(page, 1).get_by_role("heading")
    expect(statement.locator(".katex-html .mfrac")).to_have_count(2)
    expect(statement).to_contain_text("Que vaut")
    seen = rendered_text(statement)
    assert "\\" not in seen and "frac" not in seen, seen
    expect(statement).not_to_contain_text("$")

    # AFF-01 : le téléphone n'a que les propositions, rendues elles aussi.
    expect(propositions(phone).locator(".katex-html")).to_have_count(2)
    expect(propositions(phone).locator(".katex-html .msupsub")).to_have_count(1)
    assert "\\" not in rendered_text(propositions(phone))
    expect(phone.locator(".mfrac")).to_have_count(0)

    assert problems == [], problems
    assert phone_problems == [], phone_problems


@pytest.mark.spec("CNT-01")
def test_form_writes_light_latex(teacher_page: Page):
    """Hors formule et commande, le texte s'écrit tel quel ; seuls `$` et `\\` sont spéciaux."""
    page = teacher_page
    plain = r"Remise de 50 % sur A & B, pour x_1 : 3 \$ ?"
    create_question(page, plain, choices=[("~5 € {environ}", True), ("Non", False)])
    shown = question_card(page, "Remise de 50 % sur A & B, pour x_1 : 3 $ ?")
    expect(shown).to_be_visible()
    expect(shown.get_by_role("listitem").first).to_contain_text("~5 € {environ}")

    open_bank(page)
    page.get_by_role("link", name="Nouvelle question").click()
    fill_question(page, "Que vaut $x ?", multiple=False, choices=[("1", True), ("2", False)])
    expect(page.get_by_role("alert")).to_contain_text("Énoncé : formule non fermée")
    fill_question(
        page, r"Que vaut \hspace{1cm} x ?", multiple=False, choices=[("$1", True), ("2", False)]
    )
    alert = page.get_by_role("alert")
    expect(alert).to_contain_text(r"Énoncé : commande LaTeX non prise en charge : \hspace")
    expect(alert).to_contain_text("Proposition A : formule non fermée")
    assert Question.objects.count() == 1


IMPORTED_FORMULAS = r"""Title: Racines

* Que vaut [[$\sqrt{2}^2$]] ?
+ [[$2$]]
- [[$\sqrt{2}$]]
"""

LATEX_FILE = r"""Title: Indices
LaTeX: 1

* Que vaut $x_1$ si $x_1 = 50\%$ de 4 ?
+ $2$
- $1$
"""


@pytest.mark.spec("CNT-01")
def test_imported_formulas_are_kept(teacher_page: Page):
    page = teacher_page
    import_amc(page, IMPORTED_FORMULAS)
    open_bank(page)
    roots = article(page, "Que vaut")
    expect(roots.get_by_role("heading").locator(".katex-html .sqrt")).to_have_count(1)
    expect(roots.get_by_role("listitem").locator(".katex-html")).to_have_count(2)

    import_amc(page, LATEX_FILE, name="indices.txt")
    open_bank(page)
    indices = article(page, "si")
    expect(indices.get_by_role("heading").locator(".katex-html .msupsub")).to_have_count(2)
    assert "%" in rendered_text(indices.get_by_role("heading"))


# --- CNT-02 : code ----------------------------------------------------------------------------

CODE = "def f(x):\n    return x  # 50 %"
CODE_QUESTION = f"Que renvoie f(2) ?\n\\begin{{verbatim}}\n{CODE}\n\\end{{verbatim}}"


@pytest.mark.spec("CNT-02")
def test_code_keeps_spaces_and_line_breaks(teacher_page: Page, live_server, new_phone):
    page = teacher_page
    problems = watch(page, live_server.url)
    create_question(page, CODE_QUESTION, choices=[(r"\texttt{2}", True), ("Rien", False)])
    phone = live(page, live_server.url, new_phone, make_quiz("Code", [Question.objects.get()]))

    block = card(page, 1).get_by_role("heading").locator("code")
    expect(block).to_have_count(1)
    assert block.inner_text() == CODE
    assert font(block).startswith('"Atkinson Hyperlegible Mono"'), font(block)

    inline = propositions(phone).locator("code")
    expect(inline).to_have_text("2")
    assert font(inline).startswith('"Atkinson Hyperlegible Mono"'), font(inline)
    expect(propositions(phone)).not_to_contain_text("texttt")
    assert problems == [], problems


IMPORTED_CODE = """Title: Code importé

* Que renvoie f(2) ?
[verbatim]
def f(x):
    return x  # 50 %
[/verbatim]
+ [|2|]
- Rien
"""


@pytest.mark.spec("CNT-02")
def test_imported_code_keeps_spaces_and_line_breaks(teacher_page: Page):
    page = teacher_page
    import_amc(page, IMPORTED_CODE)
    open_bank(page)
    question = article(page, "Que renvoie f(2) ?")
    block = question.get_by_role("heading").locator("code")
    expect(block).to_have_count(1)
    assert block.inner_text() == CODE
    expect(question.get_by_role("listitem").locator("code")).to_have_text("2")


# --- CNT-03 et IMP-08 : images, archive ZIP ---------------------------------------------------


def picture(fmt: str, color: str = "red") -> bytes:
    buffer = io.BytesIO()
    PILImage.new("RGB", (40, 20), color).save(buffer, fmt)
    return buffer.getvalue()


SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="40" height="20">'
    b'<rect width="40" height="20" fill="blue"/></svg>'
)
PDF = b"%PDF-1.4\n%%EOF\n"


def archive(files: dict[str, bytes | str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zipped:
        for name, data in files.items():
            zipped.writestr(name, data)
    return buffer.getvalue()


IMAGES = """Title: Images

* Quelle figure ? !graphe.png!
+ !{center}[width=2cm]logo.svg!
- Aucune

* Quelle photo ? !photo.jpg!
+ Oui
- Non

* Quelle figure en PDF ? !figure.pdf!
+ Oui
- Non
"""


def images_zip() -> bytes:
    return archive(
        {
            "images.txt": IMAGES,
            "graphe.png": picture("PNG"),
            "logo.svg": SVG,
            "photo.jpg": picture("JPEG", "green"),
            "figure.pdf": PDF,
        }
    )


@pytest.mark.spec("CNT-03")
def test_images_on_board_and_phone(teacher_page: Page, live_server, new_phone):
    page = teacher_page
    problems = watch(page, live_server.url)
    upload_amc(page, images_zip(), name="images.zip")
    expect_recap(page)
    expect(page.get_by_role("main")).to_contain_text("2 questions à importer")
    skipped = recap_items(page, SKIPPED)
    expect(skipped).to_have_count(1)
    expect(skipped).to_contain_text("Ligne 11 : image PDF ou EPS")
    expect(skipped).to_contain_text("figure.pdf")
    page.get_by_role("button", name="Importer").click()
    expect(page.get_by_role("status")).to_contain_text("QCM importé : 2 questions")

    open_bank(page)
    images = page.get_by_role("main").locator("img")
    expect(images).to_have_count(3)
    page.wait_for_load_state("load")
    assert loaded(images) == [True] * 3

    phone = live(page, live_server.url, new_phone, Quiz.objects.get(title="Images"))
    board_images = card(page, 1).locator("img")
    expect(board_images).to_have_count(1)
    assert "graphe" in (board_images.get_attribute("src") or "")
    page.wait_for_load_state("load")
    assert loaded(board_images) == [True]
    # AFF-01 : l'image de l'énoncé n'est qu'au tableau, celle de la proposition qu'au téléphone.
    phone_images = phone.get_by_role("main").locator("img")
    expect(phone_images).to_have_count(1)
    assert "logo" in (phone_images.get_attribute("src") or "")
    phone.wait_for_load_state("load")
    assert loaded(phone_images) == [True]
    assert problems == [], problems


@pytest.mark.spec("CNT-03")
def test_form_keeps_imported_images_and_refuses_unknown_ones(teacher_page: Page):
    page = teacher_page
    import_amc(page, images_zip(), name="images.zip")
    open_bank(page)
    article(page, "Quelle photo ?").get_by_role("link", name="Modifier").click()
    statement = page.get_by_label("Énoncé")
    text = statement.input_value()
    assert text.startswith(r"Quelle photo ? \includegraphics{photo-") and text.endswith(".jpg}")
    statement.fill(text.replace("Quelle photo ?", "Quelle est cette photo ?"))
    page.get_by_role("button", name="Enregistrer").click()
    expect(page.get_by_role("status")).to_contain_text("Question enregistrée")
    edited = article(page, "Quelle est cette photo ?").locator("img")
    expect(edited).to_have_count(1)
    page.wait_for_load_state("load")
    assert loaded(edited) == [True]

    # I17 : une image ne s'ajoute que par l'import ; un nom inconnu est refusé.
    page.get_by_role("link", name="Nouvelle question").click()
    fill_question(
        page,
        r"Quelle courbe ? \includegraphics{inconnue.png}",
        multiple=False,
        choices=[("Oui", True), ("Non", False)],
    )
    expect(page.get_by_role("alert")).to_contain_text("Énoncé : image inconnue : inconnue.png")


@pytest.mark.spec("IMP-08")
def test_zip_archive_with_its_images(teacher_page: Page):
    """Le fichier AMC-TXT peut être dans un dossier de l'archive ; ses images se cherchent à
    partir de ce dossier. Les fichiers ajoutés par macOS sont ignorés."""
    page = teacher_page
    text = "Title: Archive\n\n* Quelle image ? !img/a.png!\n+ Oui\n- Non\n"
    zipped = archive(
        {
            "controle/controle.txt": text,
            "controle/img/a.png": picture("PNG"),
            "__MACOSX/controle/._controle.txt": b"\x00\x05\x16\x07",
        }
    )
    import_amc(page, zipped, name="controle.zip")
    open_bank(page)
    image = article(page, "Quelle image ?").locator("img")
    expect(image).to_have_count(1)
    page.wait_for_load_state("load")
    assert loaded(image) == [True]


@pytest.mark.spec("IMP-08")
def test_missing_image_refuses_the_file(teacher_page: Page):
    page = teacher_page
    text = "Title: Manque\n\n* Quelle image ? !img/b.png!\n+ Oui\n- Non\n"
    upload_amc(page, archive({"controle.txt": text, "img/a.png": picture("PNG")}), "c.zip")
    expect(page.get_by_role("alert")).to_contain_text("Ligne 3 : image absente : img/b.png")
    expect(page.get_by_role("heading", name="Récapitulatif de l'import")).to_have_count(0)

    # Le fichier seul ne contient aucune image : il est refusé de la même façon.
    upload_amc(page, text, name="manque.txt")
    expect(page.get_by_role("alert")).to_contain_text("Ligne 3 : image absente : img/b.png")

    upload_amc(page, archive({"img/a.png": picture("PNG")}), name="vide.zip")
    expect(page.get_by_role("alert")).to_contain_text("aucun fichier AMC-TXT (.txt)")
    upload_amc(page, archive({"a.txt": text, "b/b.txt": text}), name="deux.zip")
    expect(page.get_by_role("alert")).to_contain_text("plusieurs fichiers AMC-TXT (.txt)")
    assert not Quiz.objects.exists()


# --- CNT-04 : mise en forme -------------------------------------------------------------------

STYLED = """Title: Mise en forme

* [==Chimie==] Le mot [*important*] est-il [_penché_] ou [/souligné/] ?
+ [*Oui*]
- Non
"""


@pytest.mark.spec("CNT-04")
def test_imported_emphasis_on_board_and_phone(teacher_page: Page, live_server, new_phone):
    page = teacher_page
    import_amc(page, STYLED)
    open_bank(page)
    heading = article(page, "Le mot").get_by_role("heading")
    expect(heading.locator("strong")).to_have_text(["Chimie", "important"])
    expect(heading.locator("em")).to_have_text("penché")
    expect(heading.locator("u")).to_have_text("souligné")
    expect(heading).not_to_contain_text("[")

    phone = live(page, live_server.url, new_phone, Quiz.objects.get(title="Mise en forme"))
    statement = card(page, 1).get_by_role("heading")
    expect(statement.locator("strong")).to_have_text(["Chimie", "important"])
    expect(statement.locator("em")).to_have_text("penché")
    expect(statement.locator("u")).to_have_text("souligné")
    expect(propositions(phone).locator("strong")).to_have_text("Oui")


@pytest.mark.spec("CNT-04")
def test_disabled_emphasis_stays_text(teacher_page: Page):
    """`Disable: embf` laisse les marques en texte, comme dans AMC."""
    page = teacher_page
    import_amc(page, "Title: Brut\nDisable: embf\n\n* Le mot [*brut*] ?\n+ Oui\n- Non\n")
    open_bank(page)
    heading = article(page, "Le mot").get_by_role("heading")
    expect(heading).to_have_text("Le mot [*brut*] ?")
    expect(heading.locator("strong")).to_have_count(0)
