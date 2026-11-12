"""Incrément 9 : le tableau n'affiche que les énoncés, le téléphone que les propositions
(AFF-01), et 4 questions s'affichent à la fois par défaut (SES-06). Les questions multiples
sont signalées au tableau (AFF-02). Chaque couleur a sa forme (AFF-03) et la palette reste
lisible pour les daltoniens (AFF-04). L'ordre des propositions est propre à l'étudiant (ETU-05).

Les textes sont des marqueurs uniques : les chercher dans le code de la page ne donne aucun
faux positif, et couvre aussi ce qui serait envoyé sans être visible.
"""

from __future__ import annotations

import csv
import io

import pytest
from PIL import Image
from playwright.sync_api import Locator, Page, ViewportSize, expect

from bank.scoring import LETTERS
from live.models import Answer
from tests.e2e.live_setup import STUDENTS, expect_slot, open_board
from tests.e2e.live_ui import (
    LIVE_MS,
    background,
    board_code,
    card,
    choose,
    enter_code,
    launch_session,
    open_results,
    open_sessions,
    phone_choices,
    phone_color,
    phones_joined,
    results_rows,
    save_status,
    start,
)
from tests.factories import jump_to, make_group, make_question, make_quiz, make_session

CHOICES = {f"ÉNONCÉ-{q} ?": [(f"RÉPONSE-{q}-{c}", c == 1) for c in (1, 2, 3)] for q in (1, 2, 3)}
STATEMENTS = list(CHOICES)
ALL_CHOICES = [label for choices in CHOICES.values() for label, _ in choices]


def make_marked_session(shown: int = 2):
    """Trois questions, dont la dernière multiple : un groupe de 2, puis un groupe de 1."""
    questions = [
        make_question(text, choices, multiple=text == STATEMENTS[2])
        for text, choices in CHOICES.items()
    ]
    return make_session(
        make_quiz("Contrôle", questions), make_group("TD1", STUDENTS), shown=shown, seconds=30
    )


def assert_shows_none(content: str, *forbidden: str) -> None:
    present = [text for text in forbidden if text in content]
    assert present == [], present


def state(page: Page, url: str) -> str:
    response = page.request.get(url)
    assert response.ok, url
    return response.text()


@pytest.mark.spec("AFF-01")
def test_board_has_only_statements_and_phone_only_choices(
    teacher_page: Page, live_server, new_phone
):
    page = teacher_page
    session = make_marked_session()
    code = session.code
    phones = phones_joined(new_phone, live_server.url, code, ["00123", "42"])
    board_state = f"{live_server.url}/prof/sessions/{code}/etat/"
    phone_state = f"{live_server.url}/s/{code}/etat/"
    everything = (*STATEMENTS, *ALL_CHOICES)

    # En attente : ni énoncé ni proposition, nulle part.
    open_board(page, live_server.url, session)
    assert_shows_none(page.content(), *everything)
    for phone in phones:
        assert_shows_none(phone.content(), *everything)

    start(page)
    # Créneaux 0 et 1, puis créneau 2 : (énoncés du groupe au tableau, questions de chaque rang).
    plan = [
        (STATEMENTS[:2], [STATEMENTS[0], STATEMENTS[1]]),
        (STATEMENTS[:2], [STATEMENTS[1], STATEMENTS[0]]),
        (STATEMENTS[2:], [STATEMENTS[2], STATEMENTS[2]]),
    ]
    for slot, (on_board, on_phones) in enumerate(plan):
        jump_to(session, slot * 30 + 1)
        expect(card(page, 1).get_by_role("heading")).to_have_text(on_board[0], timeout=LIVE_MS)
        for color, statement in enumerate(on_board, start=1):
            expect(card(page, color).get_by_role("heading")).to_have_text(statement)
        expect(card(page, len(on_board) + 1)).to_have_count(0)

        # Le tableau : les énoncés de son groupe, aucune proposition, même invisible.
        board_html = page.content()
        assert_shows_none(board_html, *ALL_CHOICES)
        assert_shows_none(board_html, *(s for s in STATEMENTS if s not in on_board))
        assert_shows_none(state(page, board_state), *everything)

        for phone, statement in zip(phones, on_phones, strict=True):
            expect_slot(phone, slot)
            # Le téléphone : les propositions de sa question, aucun énoncé, même invisible.
            own = [label for label, _ in CHOICES[statement]]
            assert sorted(phone_choices(phone)) == sorted(own)
            phone_html = phone.content()
            assert_shows_none(phone_html, *STATEMENTS)
            assert_shows_none(phone_html, *(c for c in ALL_CHOICES if c not in own))
            assert_shows_none(state(phone, phone_state), *everything)

    # Terminée : plus rien, ni au tableau, ni sur le téléphone, ni dans les résultats.
    jump_to(session, 91)
    expect(page.get_by_role("main")).to_contain_text("Session terminée", timeout=LIVE_MS)
    assert_shows_none(page.content(), *everything)
    for phone in phones:
        expect(phone.get_by_role("main")).to_contain_text("Session terminée", timeout=LIVE_MS)
        assert_shows_none(phone.content(), *everything)

    open_results(page)
    assert_shows_none(page.content(), *everything)
    with page.expect_download() as info:
        page.get_by_role("link", name="Télécharger le CSV").click()
    assert_shows_none(info.value.path().read_text(encoding="utf-8-sig"), *everything)


@pytest.mark.spec("SES-06")
def test_four_questions_at_once_by_default(teacher_page: Page, live_server, new_phone):
    page = teacher_page
    long_text = "Quelle est la proposition exacte parmi celles de votre téléphone ? " * 3
    statements = [f"{i} : {long_text}" for i in range(1, 6)]
    quiz = make_quiz("Cinq", [make_question(text) for text in statements])
    make_group("TD1", STUDENTS)

    open_sessions(page)
    page.get_by_role("link", name="Lancer une session").click()
    page.get_by_label("QCM").select_option(label=quiz.title)
    page.get_by_label("Groupe").select_option(label="TD1")
    # Sans toucher au champ : la valeur par défaut.
    expect(page.get_by_label("Questions affichées en même temps")).to_have_value("4")
    page.get_by_role("button", name="Lancer").click()
    code = board_code(page)
    expect(page.get_by_role("main")).to_contain_text("4 questions à la fois")

    (phone,) = phones_joined(new_phone, live_server.url, code, ["00123"])
    start(page)
    for color in range(1, 5):
        expect(card(page, color).get_by_role("heading")).to_contain_text(f"{color} : ")
    expect(card(page, 5)).to_have_count(0)
    assert phone_color(phone) == 1
    # Les 4 énoncés tiennent à l'écran, sans défilement, même assez longs, y compris sur un
    # projecteur de 720 lignes.
    for width, height in ((1920, 1080), (1280, 720)):
        size = ViewportSize(width=width, height=height)
        page.set_viewport_size(size)
        overflow = page.evaluate(
            "() => document.documentElement.scrollHeight - document.documentElement.clientHeight"
        )
        assert overflow <= 0, (size, overflow)


@pytest.mark.spec("SES-06")
def test_another_value_can_be_chosen_at_launch(teacher_page: Page):
    page = teacher_page
    make_quiz("Trois", [make_question(text) for text in STATEMENTS])
    make_group("TD1", STUDENTS)
    launch_session(page, "Trois", "TD1", shown=2)
    expect(page.get_by_role("main")).to_contain_text("2 questions à la fois")
    start(page)
    expect(card(page, 2).get_by_role("heading")).to_have_text(STATEMENTS[1])
    expect(card(page, 3)).to_have_count(0)


MULTIPLE_HINT = "Plusieurs réponses possibles"


@pytest.mark.spec("AFF-02")
def test_board_flags_multiple_answer_questions(teacher_page: Page, live_server, new_phone):
    page = teacher_page
    session = make_marked_session(shown=3)  # la troisième question est multiple
    phones_joined(new_phone, live_server.url, session.code, ["00123"])
    open_board(page, live_server.url, session)
    start(page)

    hint = card(page, 3).get_by_text(MULTIPLE_HINT, exact=True)
    expect(hint).to_be_visible()
    # Sous son énoncé.
    heading = card(page, 3).get_by_role("heading")
    heading_box, hint_box = heading.bounding_box(), hint.bounding_box()
    assert heading_box and hint_box
    assert hint_box["y"] >= heading_box["y"] + heading_box["height"] - 1
    # Une question simple n'a aucune mention, et la mention n'apparaît qu'une fois.
    for color in (1, 2):
        expect(card(page, color)).not_to_contain_text("réponses possibles")
    expect(page.get_by_text(MULTIPLE_HINT)).to_have_count(1)

    # Seule dans son groupe, elle garde sa mention ; une question simple seule n'en a pas.
    alone = make_marked_session(shown=2)
    phones_joined(new_phone, live_server.url, alone.code, ["42"])
    open_board(page, live_server.url, alone)
    start(page)
    expect(card(page, 1)).not_to_contain_text("réponses possibles")
    jump_to(alone, 61)
    expect(card(page, 1).get_by_role("heading")).to_have_text(STATEMENTS[2], timeout=LIVE_MS)
    expect(card(page, 1).get_by_text(MULTIPLE_HINT, exact=True)).to_be_visible()


# Formes (AFF-03) et palette d'Okabe et Ito (AFF-04), dans l'ordre des couleurs 1 à 6.
SHAPES = ["rond", "triangle", "carré", "losange", "étoile", "croix"]
PALETTE = ["#F0E442", "#0072B2", "#009E73", "#56B4E9", "#CC79A7", "#E69F00"]
SIX_STUDENTS = [(f"{n}", f"ÉTUDIANT {n}") for n in range(101, 107)]


def rgb(hex_color: str) -> str:
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
    return f"rgb({r}, {g}, {b})"


def make_six_session():
    """Six questions affichées à la fois, la dernière multiple, et six téléphones : au premier
    créneau, l'étudiant de rang r a la couleur r + 1."""
    questions = [
        make_question(f"ÉNONCÉ-{q} ?", [(f"R{q}-{c}", c == 1) for c in (1, 2, 3)], multiple=q == 6)
        for q in range(1, 7)
    ]
    quiz = make_quiz("Six", questions)
    return make_session(quiz, make_group("TD6", SIX_STUDENTS), shown=6, seconds=60)


def shape(screen: Page | Locator, color: int) -> Locator:
    return screen.get_by_role("img", name=SHAPES[color - 1], exact=True)


def silhouette(image: Locator) -> Image.Image:
    """Silhouette de la forme, lue sur une capture de l'écran : les pixels plus proches de la
    couleur de la forme que du fond, recadrés puis ramenés à 32x32."""
    image.scroll_into_view_if_needed()
    capture = Image.open(io.BytesIO(image.screenshot())).convert("RGB")
    ink = parse_rgb(image.evaluate("element => getComputedStyle(element).color"))
    paper = capture.getpixel((0, 0))  # coin hors de la forme : le fond
    assert isinstance(paper, tuple)

    def near_ink(pixel) -> bool:
        to_ink = sum((a - b) ** 2 for a, b in zip(pixel, ink, strict=True))
        to_paper = sum((a - b) ** 2 for a, b in zip(pixel, paper, strict=True))
        return to_ink < to_paper

    mask = Image.new("1", capture.size)
    mask.putdata([near_ink(pixel) for pixel in capture.getdata()])
    box = mask.getbbox()
    assert box, "forme invisible"
    return mask.crop(box).resize((32, 32))


def overlap(a: Image.Image, b: Image.Image) -> float:
    """Part commune de deux silhouettes (1 : identiques)."""
    pa, pb = a.convert("L").tobytes(), b.convert("L").tobytes()
    both = sum(1 for x, y in zip(pa, pb, strict=True) if x and y)
    either = sum(1 for x, y in zip(pa, pb, strict=True) if x or y)
    return both / either


def parse_rgb(css: str) -> tuple[int, int, int]:
    parts = css[css.index("(") + 1 : css.index(")")].replace(",", " ").split()
    r, g, b = (round(float(p)) for p in parts[:3])
    return r, g, b


def luminance(color) -> float:
    def channel(c: float) -> float:
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in color)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b) -> float:
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


# Pour chaque élément visible qui porte du texte, ou pour chaque forme : couleur du texte et
# fond effectif, composé à travers les fonds semi-transparents des ancêtres.
READ_COLORS = """() => {
  const parse = s => s.match(/[\\d.]+/g).map(Number);
  const backdrop = el => {
    const layers = [];
    for (let e = el; e; e = e.parentElement) {
      const [r, g, b, a = 1] = parse(getComputedStyle(e).backgroundColor);
      if (a > 0) layers.push([r, g, b, a]);
      if (a >= 1) break;
    }
    let out = [255, 255, 255];
    for (const [r, g, b, a] of layers.reverse()) {
      out = out.map((v, i) => v * (1 - a) + [r, g, b][i] * a);
    }
    return out;
  };
  const found = [];
  for (const el of document.body.querySelectorAll("*")) {
    const text = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
    if (!(text || el.matches("svg[role=img]")) || !el.checkVisibility()) continue;
    const box = el.getBoundingClientRect();
    if (box.width < 2 || box.height < 2) continue;
    const label = el.getAttribute("aria-label") || el.textContent.trim();
    const fg = parse(getComputedStyle(el).color);
    found.push({label: label.slice(0, 40), fg, bg: backdrop(el)});
  }
  return found;
}"""


def low_contrasts(screen: Page) -> list[tuple[str, float]]:
    """Textes et formes de l'écran dont le contraste avec leur fond est sous 4,5:1."""
    found = screen.evaluate(READ_COLORS)
    assert found
    measured = [(item["label"], contrast(item["fg"][:3], item["bg"])) for item in found]
    return [(label, round(ratio, 2)) for label, ratio in measured if ratio < 4.5]


@pytest.mark.spec("AFF-03")
def test_each_color_has_its_own_shape(teacher_page: Page, live_server, new_phone):
    page = teacher_page
    session = make_six_session()
    phones = phones_joined(new_phone, live_server.url, session.code, [n for n, _ in SIX_STUDENTS])
    open_board(page, live_server.url, session)
    start(page)

    # Au tableau : chaque carte porte son numéro et sa forme, et les six formes se distinguent
    # à l'œil, et non seulement par leur nom.
    board = {}
    for color in range(1, 7):
        expect(card(page, color).locator(".badge")).to_contain_text(str(color))
        image = shape(card(page, color), color)
        expect(image).to_be_visible()
        expect(card(page, color).get_by_role("img")).to_have_count(1)
        board[color] = silhouette(image)
    for a in range(1, 7):
        for b in range(a + 1, 7):
            assert overlap(board[a], board[b]) < 0.85, (SHAPES[a - 1], SHAPES[b - 1])

    # Sur le téléphone : le numéro et la même forme qu'au tableau.
    for rank, phone in enumerate(phones):
        color = rank + 1
        assert phone_color(phone) == color
        image = shape(phone, color)
        expect(image).to_be_visible()
        expect(phone.get_by_role("img")).to_have_count(1)
        seen = silhouette(image)
        closest = max(board, key=lambda c: overlap(seen, board[c]))
        assert closest == color, (SHAPES[color - 1], SHAPES[closest - 1])


@pytest.mark.spec("AFF-04")
def test_color_blind_safe_palette_and_readable_text(teacher_page: Page, live_server, new_phone):
    page = teacher_page
    session = make_six_session()
    phones = phones_joined(new_phone, live_server.url, session.code, [n for n, _ in SIX_STUDENTS])
    open_board(page, live_server.url, session)
    start(page)

    for color, hex_color in enumerate(PALETTE, start=1):
        assert background(card(page, color)) == rgb(hex_color), color
    expect(card(page, 6).get_by_text(MULTIPLE_HINT)).to_be_visible()
    assert low_contrasts(page) == []

    for rank, phone in enumerate(phones):
        color = rank + 1
        assert phone_color(phone) == color
        assert background(phone.locator("body")) == rgb(PALETTE[rank])
        # Une réponse choisie : le bouton d'effacement est actif et la confirmation s'affiche.
        choose(phone, f"R{color}-2")
        expect(save_status(phone)).to_have_text("Réponse enregistrée")
        assert low_contrasts(phone) == [], color


ORDER_CHOICES = [(f"CHOIX-{i}", i == 1) for i in range(1, 9)]  # huit propositions, A juste


def wait_saved(page: Page, session, number: str, index: int) -> None:
    """La réponse de `number` est enregistrée : la proposition d'indice `index` de la banque."""
    saved = Answer.objects.filter(participant__session=session, participant__number=number)
    for _ in range(40):
        if list(saved.values_list("choices", flat=True)) == [[index]]:
            return
        page.wait_for_timeout(50)
    raise AssertionError(f"{number} : réponse non enregistrée")


@pytest.mark.spec("ETU-05")
def test_choice_order_survives_coming_back(teacher_page: Page, live_server, new_phone):
    page = teacher_page
    quiz = make_quiz("Ordre", [make_question("Huit propositions", ORDER_CHOICES)])
    session = make_session(quiz, make_group("TD1", STUDENTS), shown=1, seconds=60)
    phones = phones_joined(new_phone, live_server.url, session.code, ["00123", "42"])
    open_board(page, live_server.url, session)
    start(page)

    orders = []
    for phone in phones:
        expect_slot(phone, 0)
        order = phone_choices(phone)
        # L'étudiant revient sur la session en ressaisissant le code…
        enter_code(phone, live_server.url, session.code)
        expect_slot(phone, 0)
        assert phone_choices(phone) == order
        # … ou dans un nouvel onglet du même navigateur.
        tab = phone.context.new_page()
        tab.goto(f"{live_server.url}/s/{session.code}/")
        expect_slot(tab, 0)
        assert phone_choices(tab) == order
        orders.append(order)
    assert orders[0] != orders[1]


@pytest.mark.spec("ETU-05")
def test_marks_do_not_depend_on_displayed_order(teacher_page: Page, live_server, new_phone):
    """Chaque étudiant choisit une proposition affichée ailleurs qu'à sa place dans la banque :
    la note et la lettre du CSV sont celles de la proposition, pas de sa place à l'écran."""
    page = teacher_page
    labels = [label for label, _ in ORDER_CHOICES]
    quiz = make_quiz("Ordre", [make_question("Huit propositions", ORDER_CHOICES)])
    session = make_session(quiz, make_group("TD1", STUDENTS), shown=1, seconds=60)
    numbers = ["00123", "42", "7"]
    phones = phones_joined(new_phone, live_server.url, session.code, numbers)
    open_board(page, live_server.url, session)
    start(page)

    # 00123 et 7 choisissent la bonne réponse (A). 42 choisit une mauvaise réponse affichée
    # ailleurs qu'à sa place dans la banque : sa lettre dans le CSV distingue à coup sûr la
    # proposition de sa place à l'écran.
    picked = {}
    for number, phone in zip(numbers, phones, strict=True):
        expect_slot(phone, 0)
        shown = phone_choices(phone)
        wrong = (t for t in labels[1:] if shown.index(t) != labels.index(t))
        picked[number] = next(wrong) if number == "42" else labels[0]
        choose(phone, picked[number])
        expect(save_status(phone)).to_have_text("Réponse enregistrée")
        wait_saved(page, session, number, labels.index(picked[number]))

    jump_to(session, 61)
    expect(page.get_by_role("main")).to_contain_text("Session terminée", timeout=LIVE_MS)
    open_results(page)
    marks = {row[0]: row[2] for row in results_rows(page)}
    assert marks == {"00123": "1", "42": "0", "7": "1"}
    with page.expect_download() as info:
        page.get_by_role("link", name="Télécharger le CSV").click()
    rows = list(csv.reader(io.StringIO(info.value.path().read_text("utf-8-sig")), delimiter=";"))
    answers = {row[0]: (row[4], row[5]) for row in rows[1:]}
    assert answers == {
        "00123": ("A", "1"),
        "42": (LETTERS[labels.index(picked["42"])], "0"),
        "7": ("A", "1"),
    }
