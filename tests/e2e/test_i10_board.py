"""Incrément 10 : socle de la refonte visuelle (direction « Signalétique ») et tableau.

- VIS-01 : police servie par l'application, aucune ressource venue d'ailleurs ; énoncés en
  graisse normale, numéros en gras.
- VIS-02 : au tableau en déroulement, bandeau (code, position dans le QCM, temps restant,
  « +10 s ») et barre du temps restant ; de 1 à 6 questions sans défilement.
- VIS-03 : tableau en attente pour une classe de 40, sans défilement ; tableau terminé.
- ACC-01 : axe-core, contraste et clavier sur les pages communes et le tableau.

La barre du temps se mesure sur une capture de l'écran, comme un œil la voit.
"""

from __future__ import annotations

import io
import re

import pytest
from PIL import Image, ImageColor
from playwright.sync_api import Browser, Locator, Page, ViewportSize, expect

from tests.e2e.a11y import PAGE_JS, axe_violations, keyboard_problems, low_contrasts
from tests.e2e.live_setup import STUDENTS, make_live, open_board, started
from tests.e2e.live_ui import (
    LIVE_MS,
    add_time,
    assert_fits,
    card,
    connected_count,
    connected_names,
    join_qr,
    join_region,
    join_url,
    seconds_left,
    start,
    timer,
    timer_shows,
)
from tests.factories import (
    jump_to,
    make_group,
    make_participant,
    make_question,
    make_quiz,
    make_session,
)

FONT = "Atkinson Hyperlegible Next"
DASH = "\N{EN DASH}"  # entre deux numéros de question

LONG_TEXT = (
    "Dans un arbre binaire de recherche équilibré contenant un million de clés distinctes, "
    "quelles affirmations sur la hauteur de l'arbre et sur le coût d'une recherche sont "
    "exactes, en moyenne comme dans le pire des cas, sans autre hypothèse sur les données"
)


def statement(number: int, length: int) -> str:
    """Énoncé réaliste d'environ `length` caractères, coupé entre deux mots."""
    text = f"{number}. {LONG_TEXT}"
    cut = text[: length - 2].rsplit(" ", 1)[0] + " ?"
    assert length - 12 <= len(cut) <= length, (len(cut), cut)
    return cut


# --- VIS-01 : police servie par l'application -------------------------------------------

FONT_PROBLEMS = (
    "async (family) => {"
    + PAGE_JS
    + """
  await document.fonts.ready;
  const clean = s => s.replaceAll('"', "").trim();
  const problems = [];
  const loaded = [...document.fonts].some(f => clean(f.family) === family && f.status === "loaded");
  if (!loaded) problems.push("police non chargée");
  for (const el of textElements()) {
    if (el.closest("code, pre, kbd, samp")) continue;
    const first = clean(getComputedStyle(el).fontFamily.split(",")[0]);
    if (first !== family) problems.push(`${el.tagName} « ${name(el)} » : ${first}`);
  }
  return problems.slice(0, 10);
}"""
)


def font_problems(screen: Page) -> list[str]:
    """Textes visibles qui ne sont pas dans la police de l'application, ou police non chargée."""
    screen.wait_for_load_state("load")
    return screen.evaluate(FONT_PROBLEMS, FONT)


def weight(locator: Locator) -> int:
    return int(locator.evaluate("element => getComputedStyle(element).fontWeight"))


@pytest.mark.spec("VIS-01")
def test_font_is_served_by_the_application(teacher_page: Page, live_server, new_phone):
    page = teacher_page
    requested: list[str] = []
    page.context.on("request", lambda request: requested.append(request.url))
    phone = new_phone()
    phone.context.on("request", lambda request: requested.append(request.url))

    phone.goto(f"{live_server.url}/")
    assert font_problems(phone) == [], "accueil, téléphone"
    for path in ("/", "/prof/connexion/", "/page-introuvable/"):
        page.goto(f"{live_server.url}{path}")
        assert font_problems(page) == [], path

    session = make_live(4, shown=4)  # la quatrième question est multiple
    open_board(page, live_server.url, session)
    assert font_problems(page) == [], "tableau en attente"
    start(page)
    expect(card(page, 4)).to_be_visible()
    assert font_problems(page) == [], "tableau en déroulement"
    # Énoncés en graisse normale ; numéros et mentions en gras.
    for color in range(1, 5):
        assert weight(card(page, color).get_by_role("heading")) == 400, color
        assert weight(card(page, color).locator(".badge")) >= 700, color
    assert weight(card(page, 4).get_by_text("Plusieurs réponses possibles")) >= 700
    jump_to(session, 4 * 30 + 1)
    expect(page.get_by_role("main")).to_contain_text("Session terminée", timeout=LIVE_MS)
    assert font_problems(page) == [], "tableau terminé"

    # Rien n'a été demandé à un autre serveur que l'application : ni police, ni feuille de style.
    foreign = [url for url in requested if not url.startswith((live_server.url, "data:"))]
    assert requested and foreign == []


# --- VIS-02 : bandeau et barre du temps au tableau --------------------------------------


SIGNAL = ImageColor.getrgb("#f0e442")  # valeur de la barre du temps : le jaune signal
INK = ImageColor.getrgb("#111111")  # valeur de la barre des connectés : l'encre


def bar_fill(bar: Locator, value) -> float:
    """Part remplie d'une barre, lue sur une capture : longueur, depuis la gauche, de la plage
    de la couleur `value`, sur la ligne du milieu. Une barre vide mesure 0. Une barre placée à
    une position fractionnaire déborde d'un pixel sur le fond, de chaque côté : on les écarte."""
    image = Image.open(io.BytesIO(bar.screenshot())).convert("RGB")
    y = image.height // 2
    row = [image.getpixel((x, y)) for x in range(1, image.width - 1)]

    def near(pixel) -> bool:
        return sum(abs(a - b) for a, b in zip(pixel, value, strict=True)) <= 90

    run = next((x for x, pixel in enumerate(row) if not near(pixel)), len(row))
    return run / len(row)


def assert_visible_bar(bar: Locator) -> None:
    expect(bar).to_be_visible()
    box = bar.bounding_box()
    assert box and box["height"] >= 6, box  # visible de loin, pas un simple filet


def expect_fill(bar: Locator, value, expected: float, tolerance: float = 0.03) -> None:
    """La barre atteint, dans le délai du direct, la part `expected` (à `tolerance` près)."""
    assert_visible_bar(bar)
    seen = []
    for _ in range(LIVE_MS // 100):
        seen.append(round(bar_fill(bar, value), 3))
        if abs(seen[-1] - expected) <= tolerance:
            return
        bar.page.wait_for_timeout(100)
    raise AssertionError(f"barre à {seen[-5:]}, attendu {expected:.2f}")


def time_bar(page: Page) -> Locator:
    return page.get_by_role("progressbar", name="Part du créneau restante")


def expect_time_bar(page: Page, duration: int) -> None:
    """La barre du temps montre la part restante d'un créneau de `duration` secondes, mesurée
    au même instant que le minuteur : le temps restant, arrondi à la seconde supérieure, est
    lu juste avant et juste après la capture. Comme les deux baissent ensemble, attendre ne
    rapproche pas une barre fausse de la valeur juste ; on n'attend que le recalage de la page,
    dans le délai du direct."""
    bar = time_bar(page)
    assert_visible_bar(bar)
    seen = []
    for _ in range(LIVE_MS // 100):
        before = seconds_left(page)
        fill = bar_fill(bar, SIGNAL)
        after = seconds_left(page)
        low, high = (min(before, after) - 1) / duration, max(before, after) / duration
        seen.append((before, round(fill, 3)))
        if low - 0.02 <= fill <= high + 0.02:
            return
        page.wait_for_timeout(100)
    raise AssertionError(f"(secondes, barre) : {seen[-5:]}, pour un créneau de {duration} s")


@pytest.mark.spec("VIS-02")
def test_running_board_band_and_time_bar(teacher_page: Page, live_server, new_phone):
    page = teacher_page
    quiz = make_quiz("Cinq", [make_question(f"ÉNONCÉ {i} ?") for i in range(1, 6)])
    session = make_session(quiz, make_group("TD1", STUDENTS), shown=4, seconds=30)
    started(page, live_server.url, new_phone, session)

    band = page.get_by_role("banner")
    expect(band.get_by_role("heading", name=f"Session {session.code}", level=1)).to_be_visible()
    expect(band).to_contain_text(f"Questions 1{DASH}4 sur 5")
    expect(band.get_by_role("timer", name="Temps restant")).to_have_text(
        re.compile(r"^0:(2\d|30)$")
    )
    expect(band.get_by_role("button", name="+10 s")).to_be_visible()
    # La barre est juste sous le bandeau, sur toute la largeur.
    band_box, bar_box = band.bounding_box(), time_bar(page).bounding_box()
    assert band_box and bar_box
    assert abs(bar_box["y"] - (band_box["y"] + band_box["height"])) <= 2, (band_box, bar_box)
    assert bar_box["width"] >= 0.99 * band_box["width"], (band_box, bar_box)

    # La barre se vide avec le temps.
    jump_to(session, 15)
    expect(timer(page)).to_have_text(re.compile(r"^0:1[3-5]$"), timeout=LIVE_MS)
    expect_time_bar(page, 30)
    # Elle tient compte du temps ajouté : 25 s restantes sur 40.
    add_time(page)
    expect(timer(page)).to_have_text(re.compile(r"^0:2[3-5]$"), timeout=LIVE_MS)
    expect_time_bar(page, 40)
    # Créneau suivant, dans le même groupe : la page ne se recharge pas, et la barre se recale
    # pourtant sur sa durée, 30 s et non plus 40.
    jump_to(session, 40 + 5)
    expect(timer(page)).to_have_text(re.compile(r"^0:2[3-5]$"), timeout=LIVE_MS)
    expect(page.locator("body")).to_have_attribute("data-page", "running:0")
    expect_time_bar(page, 30)

    # Dernier groupe, d'une seule question : 40 s pour le premier créneau, 30 s pour les trois
    # suivants, puis le cinquième.
    jump_to(session, 40 + 3 * 30 + 3)
    expect(band).to_contain_text("Question 5 sur 5", timeout=LIVE_MS)
    expect(band).not_to_contain_text("Questions")
    expect_time_bar(page, 30)


@pytest.mark.spec("VIS-02")
def test_time_left_in_minutes_and_seconds(teacher_page: Page, live_server, new_phone):
    """Au-delà d'une minute, le temps restant s'écrit « 1:30 », au tableau comme sur le
    téléphone, puis passe à « 0:59 »."""
    page = teacher_page
    quiz = make_quiz("Deux", [make_question(f"ÉNONCÉ {i} ?") for i in range(1, 3)])
    session = make_session(quiz, make_group("TD1", STUDENTS), shown=1, seconds=90)
    (phone,) = started(page, live_server.url, new_phone, session, ["00123"])
    for screen in (page, phone):
        timer_shows(screen, 87, 90)  # « 1:27 » à « 1:30 »
    jump_to(session, 31)
    for screen in (page, phone):
        timer_shows(screen, 56, 59)  # « 0:56 » à « 0:59 »
    expect_time_bar(page, 90)
    # Près de l'échéance, la barre est presque vide : elle se vide jusqu'au bout. Dix secondes
    # de marge, pour mesurer avant le créneau suivant.
    jump_to(session, 80)
    timer_shows(page, 8, 10)
    expect_time_bar(page, 90)


def statement_size(page: Page) -> float:
    """Taille du texte du premier énoncé, en part de la hauteur de l'écran."""
    return (
        card(page, 1)
        .get_by_role("heading")
        .evaluate("h => parseFloat(getComputedStyle(h).fontSize) / window.innerHeight")
    )


@pytest.mark.spec("VIS-02")
@pytest.mark.spec("SES-06")  # 4 et 6 questions tiennent à l'écran
@pytest.mark.parametrize("shown", range(1, 7))
def test_board_fits_from_one_to_six_questions(
    teacher_page: Page, live_server, new_phone, shown: int
):
    page = teacher_page
    length = 200 if shown <= 4 else 135
    quiz = make_quiz("Long", [make_question(statement(i, length)) for i in range(1, shown + 1)])
    session = make_session(quiz, make_group("TD1", STUDENTS), shown=shown)
    started(page, live_server.url, new_phone, session)
    expect(page.get_by_role("article")).to_have_count(shown)

    def large_enough(size: ViewportSize) -> None:
        assert statement_size(page) >= 0.025, (size, statement_size(page))

    assert_fits(page, large_enough)


# --- VIS-03 : tableau en attente, pour une classe de 40 ---------------------------------

LAST = [
    "BELKACEM", "MARTIN", "NGUYEN", "HADDAD", "ROUSSEAU", "LE GALL", "BENALI", "LEFÈVRE",
    "MOREAU", "GIRARD", "FAURE", "PERRIN", "LAMBERT", "ROUX", "CHEVALIER", "GARNIER",
    "FONTAINE", "DUBOIS", "LAURENT", "SIMON", "MICHEL", "LEROY", "DAVID", "BERTRAND",
    "MOREL", "FOURNIER", "GIRAUD", "BONNET", "DUPONT", "LAMBERT-RICHARD",
    "DE LA FONTAINE-MARCHAND", "MERCIER", "BLANC", "GUÉRIN", "BOYER", "ANDRÉ", "CHAMPION",
    "MULLER", "HENRY", "ROBIN",
]  # fmt: skip
FIRST = ["Inès", "Hugo", "Chloé", "Yanis", "Léa", "Malo", "Sarah", "Tom", "Jade", "Noé"]
CLASS = [
    (f"2190{i:04d}", f"{last} {'Marie-Charlotte' if i == 30 else FIRST[i % len(FIRST)]}")
    for i, last in enumerate(LAST)
]


def people_bar(page: Page) -> Locator:
    return page.get_by_role("progressbar", name="Part des étudiants connectés")


@pytest.mark.spec("VIS-03")
def test_waiting_board_holds_a_class_of_forty(teacher_page: Page, live_server):
    page = teacher_page
    quiz = make_quiz("Algorithmique — Partiel 2", [make_question(f"Q{i} ?") for i in range(1, 25)])
    session = make_session(quiz, make_group("TC-3A G2", CLASS), shown=4, seconds=30)
    for number, _ in CLASS[:10]:
        make_participant(session, number)
    open_board(page, live_server.url, session)

    # L'adresse, puis le code en deux groupes de trois chiffres, bien séparés.
    expect(join_url(page)).to_have_text(f"{live_server.url}/")
    groups = join_region(page).get_by_text(re.compile(r"^\d{3}$"))
    expect(groups).to_have_text([session.code[:3], session.code[3:]])
    left, right = groups.nth(0).bounding_box(), groups.nth(1).bounding_box()
    assert left and right
    assert right["x"] - (left["x"] + left["width"]) >= 0.2 * left["height"], (left, right)
    for text in ("Algorithmique — Partiel 2", "TC-3A G2", "4 questions à la fois", "30 s par"):
        expect(join_region(page)).to_contain_text(text)
    expect(page.get_by_text("ou scannez", exact=True)).to_be_visible()

    # Le décompte et sa barre, mis à jour en direct.
    expect(connected_count(page)).to_have_text("10 / 40")
    expect_fill(people_bar(page), INK, 10 / 40)
    for number, _ in CLASS[10:]:
        make_participant(session, number)
    expect(connected_names(page)).to_have_count(40, timeout=LIVE_MS)
    expect(connected_count(page)).to_have_text("40 / 40")
    expect_fill(people_bar(page), INK, 1.0)

    # Tout tient à l'écran, sans défilement : noms, QR code et « Démarrer ».
    def all_in_view(size: ViewportSize) -> None:
        code_size = groups.nth(0).evaluate(
            "e => parseFloat(getComputedStyle(e).fontSize) / window.innerHeight"
        )
        assert code_size >= 0.08, (size, code_size)  # en grands chiffres
        expect(page.get_by_role("button", name="Démarrer")).to_be_in_viewport(ratio=1)
        expect(join_qr(page)).to_be_in_viewport(ratio=1)
        names = page.get_by_role("list", name="Étudiants connectés")
        expect(names).to_be_in_viewport(ratio=1)

    assert_fits(page, all_in_view)

    assert_no_teacher_navigation(page)

    # À la fin : « Session terminée. » et le lien vers les résultats ; « Gérer les connectés »
    # reste dans le bandeau.
    start(page)
    jump_to(session, 24 * 30 + 1)
    main = page.get_by_role("main")
    expect(main.get_by_text("Session terminée.", exact=True)).to_be_visible(timeout=LIVE_MS)
    expect(main.get_by_role("link", name="Résultats")).to_be_visible()
    band = page.get_by_role("banner")
    expect(band.get_by_role("link", name="Gérer les connectés")).to_be_visible()
    assert_no_teacher_navigation(page)


def assert_no_teacher_navigation(page: Page) -> None:
    """Le tableau, projeté, n'a ni la navigation de l'enseignant ni la déconnexion (VIS-02)."""
    expect(page.get_by_role("navigation")).to_have_count(0)
    expect(page.get_by_role("button", name=re.compile("Se déconnecter"))).to_have_count(0)


# --- ACC-01 : accessibilité des pages communes et du tableau ----------------------------


def assert_accessible(screen: Page, where: str) -> None:
    assert axe_violations(screen) == [], where
    assert low_contrasts(screen) == [], where
    assert keyboard_problems(screen) == [], where


@pytest.mark.spec("ACC-01")
def test_shared_pages_and_board_are_accessible(
    teacher_page: Page, live_server, new_phone, browser: Browser
):
    visitor = browser.new_page(viewport=ViewportSize(width=1920, height=1080), locale="fr-FR")
    base = live_server.url

    visitor.goto(f"{base}/")
    assert_accessible(visitor, "accueil")
    visitor.get_by_label("Code de session").fill("000000")
    visitor.get_by_role("button", name="Rejoindre").click()
    expect(visitor.get_by_role("alert")).to_be_visible()
    assert_accessible(visitor, "accueil, code refusé")

    phone = new_phone()
    phone.goto(f"{base}/")
    assert_accessible(phone, "accueil, téléphone")

    visitor.goto(f"{base}/prof/connexion/")
    assert_accessible(visitor, "connexion")
    visitor.get_by_label("Identifiant").fill("prof")
    visitor.get_by_label("Mot de passe").fill("faux")
    visitor.get_by_role("button", name="Se connecter").click()
    expect(visitor.get_by_role("alert")).to_be_visible()
    assert_accessible(visitor, "connexion refusée")

    visitor.goto(f"{base}/page-introuvable/")
    expect(visitor.get_by_role("heading", name="Page introuvable")).to_be_visible()
    assert_accessible(visitor, "page introuvable")

    visitor.goto(f"{base}/prof/connexion/")
    visitor.context.clear_cookies()  # plus de jeton CSRF : le formulaire a expiré
    visitor.get_by_label("Identifiant").fill("prof")
    visitor.get_by_label("Mot de passe").fill("faux")
    visitor.get_by_role("button", name="Se connecter").click()
    expect(visitor.get_by_role("heading", name="Formulaire expiré")).to_be_visible()
    assert_accessible(visitor, "formulaire expiré")
    visitor.context.close()

    # Le tableau, dans ses trois phases, avec les six couleurs (texte blanc sur le bleu) et des
    # questions multiples.
    page = teacher_page
    questions = [make_question(statement(i, 135), multiple=i in (2, 6)) for i in range(1, 7)]
    session = make_session(
        make_quiz("Six", questions), make_group("TD6", STUDENTS), shown=6, seconds=30
    )
    make_participant(session, STUDENTS[0][0])
    open_board(page, base, session)
    expect(connected_names(page)).to_have_count(1)
    assert_accessible(page, "tableau en attente")
    start(page)
    expect(card(page, 6)).to_be_visible()
    assert_accessible(page, "tableau en déroulement")
    jump_to(session, 6 * 30 + 1)
    expect(page.get_by_role("main")).to_contain_text("Session terminée", timeout=LIVE_MS)
    assert_accessible(page, "tableau terminé")
