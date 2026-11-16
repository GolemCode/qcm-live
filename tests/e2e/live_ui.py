"""Parcours d'une session en direct : l'enseignant sur le PC du tableau, les étudiants sur
leur téléphone. Uniquement par l'interface."""

from __future__ import annotations

import csv
import io
import re
from collections.abc import Callable

import zxingcpp
from PIL import Image, ImageColor
from playwright.sync_api import Locator, Page, ViewportSize, expect

CODE_RE = re.compile(r"\b(\d{6})\b")


def open_sessions(page: Page) -> None:
    """Liste des sessions, par la navigation de l'espace enseignant."""
    page.get_by_role("navigation").get_by_role("link", name="Sessions").click()
    expect(page.get_by_role("heading", name="Sessions", exact=True, level=1)).to_be_visible()


def fill_launch(page: Page, quiz: str, group: str, shown: int | str, seconds: int | str) -> None:
    page.get_by_label("QCM").select_option(label=quiz)
    page.get_by_label("Groupe").select_option(label=group)
    page.get_by_label("Questions affichées en même temps").fill(str(shown))
    page.get_by_label("Temps par question (secondes)").fill(str(seconds))
    page.get_by_role("button", name="Lancer").click()


def leave_board(page: Page) -> None:
    """Retour du tableau, qui n'a pas la navigation de l'enseignant, à la liste des sessions,
    par le logo du bandeau."""
    page.get_by_role("banner").get_by_role("link", name="QCM Live : sessions").click()
    expect(page.get_by_role("heading", name="Sessions", exact=True, level=1)).to_be_visible()


def board_code(page: Page) -> str:
    """Identifiant de la session affichée au tableau."""
    heading = page.get_by_role("heading", name=re.compile(r"^Session \d{6}$"), level=1)
    expect(heading).to_be_visible()
    match = CODE_RE.search(heading.inner_text())
    assert match
    return match.group(1)


def launch_session(page: Page, quiz: str, group: str, shown: int = 1, seconds: int = 30) -> str:
    open_sessions(page)
    page.get_by_role("link", name="Lancer une session").click()
    fill_launch(page, quiz, group, shown, seconds)
    return board_code(page)


def connected_names(page: Page) -> Locator:
    return page.get_by_role("list", name="Étudiants connectés").get_by_role("listitem")


def connected_count(page: Page) -> Locator:
    """Décompte « k / n » affiché sous le titre « Connectés » du tableau en attente."""
    return page.get_by_role("region", name="Connectés").get_by_text(re.compile(r"^\d+ / \d+$"))


def enter_code(phone: Page, base_url: str, code: str) -> None:
    phone.goto(f"{base_url}/")
    phone.get_by_label("Code de session").fill(code)
    phone.get_by_role("button", name="Rejoindre").click()


def identify(phone: Page, number: str) -> None:
    """Sur l'écran de la session, l'étudiant saisit son numéro."""
    phone.get_by_label("Numéro d'étudiant").fill(number)
    phone.get_by_role("button", name="Valider").click()


def join(phone: Page, base_url: str, code: str, number: str) -> None:
    """L'étudiant ouvre l'adresse projetée, saisit le code puis son numéro."""
    enter_code(phone, base_url, code)
    identify(phone, number)


LIVE_MS = 2_000  # « en direct » : 2 s au plus (SPEC SES-02, DER-02)


def start(page: Page) -> None:
    page.get_by_role("button", name="Démarrer").click()
    expect(page.get_by_role("button", name="Démarrer")).to_have_count(0)


def card(page: Page, color: int) -> Locator:
    """Question affichée au tableau sous la couleur `color`."""
    return page.get_by_role("article", name=f"Couleur {color}", exact=True)


def timer(page: Page) -> Locator:
    return page.get_by_role("timer", name="Temps restant")


def clock(seconds: int) -> str:
    """Temps restant tel qu'affiché, en minutes et secondes : 18 s s'écrit « 0:18 » (VIS-02)."""
    return f"{seconds // 60}:{seconds % 60:02d}"


def seconds_left(page: Page) -> int:
    text = timer(page).inner_text()
    match = re.fullmatch(r"(\d+):(\d{2})", text.strip())
    assert match, text
    return int(match.group(1)) * 60 + int(match.group(2))


def background(locator: Locator) -> str:
    return locator.evaluate("element => getComputedStyle(element).backgroundColor")


def phone_color(phone: Page) -> int:
    badge = phone.get_by_text(re.compile(r"^Couleur \d$"))
    expect(badge).to_be_visible()
    return int(badge.inner_text().split()[-1])


def phone_choices(phone: Page) -> list[str]:
    """Propositions affichées sur le téléphone, dans l'ordre de l'écran."""
    group = phone.get_by_role("group", name="Propositions")
    expect(group).to_be_visible()
    return [label.inner_text().strip() for label in group.locator("label").all()]


def choose(phone: Page, text: str) -> None:
    phone.get_by_role("group", name="Propositions").get_by_text(text, exact=True).click()


def save_status(phone: Page) -> Locator:
    return phone.get_by_role("status")


def manage_participants(page: Page) -> None:
    page.get_by_role("link", name="Gérer les connectés").click()
    expect(page.get_by_role("heading", name="Connectés", level=1)).to_be_visible()


def identity(phone: Page) -> Locator:
    """Confirmation d'identité affichée sur le téléphone (« Vous êtes … »)."""
    return phone.get_by_text(re.compile(r"^Vous êtes "))


def phones_joined(new_phone, base_url: str, code: str, numbers) -> list[Page]:
    """Un nouveau téléphone par numéro, identifié dans la session `code`."""
    phones = []
    for number in numbers:
        phone = new_phone()
        join(phone, base_url, code, number)
        expect(identity(phone)).to_be_visible()
        phones.append(phone)
    return phones


def add_time_button(page: Page) -> Locator:
    """Bouton du tableau qui ajoute 10 secondes au créneau en cours (TPS-01)."""
    return page.get_by_role("button", name="+10 s")


def add_time(page: Page) -> None:
    add_time_button(page).click()


def clear_button(phone: Page) -> Locator:
    """Bouton du téléphone qui efface la réponse à une question simple (ETU-09)."""
    return phone.get_by_role("button", name="Effacer ma réponse")


def clear_answer(phone: Page) -> None:
    clear_button(phone).click()


def timer_shows(screen: Page, low: int, high: int, timeout: float = LIVE_MS) -> None:
    """Le temps restant affiché atteint, dans le délai, une valeur entre `low` et `high` s."""
    values = "|".join(clock(s) for s in range(low, high + 1))
    expect(timer(screen)).to_have_text(re.compile(rf"^({values})$"), timeout=timeout)


def join_region(page: Page) -> Locator:
    """Consigne projetée au tableau : l'adresse à ouvrir et le code de session."""
    return page.get_by_role("region", name="Rejoindre la session")


def join_url(page: Page) -> Locator:
    """Adresse à ouvrir, seule dans son élément, au tableau en attente."""
    return join_region(page).get_by_text(re.compile(r"^https?://"))


def join_qr(page: Page) -> Locator:
    """QR code affiché au tableau pour rejoindre la session (SES-05)."""
    return page.get_by_role("img", name="QR code pour rejoindre la session")


def qr_text(qr: Locator) -> str:
    """Contenu du QR code, décodé depuis une capture de l'écran, comme le ferait le lecteur
    d'un téléphone."""
    expect(qr).to_be_visible()
    image = Image.open(io.BytesIO(qr.screenshot()))
    codes = zxingcpp.read_barcodes(image)
    assert [code.format for code in codes] == [zxingcpp.BarcodeFormat.QRCode], codes
    return codes[0].text


def open_results(page: Page) -> None:
    page.get_by_role("link", name="Résultats").click()
    expect(page.get_by_role("heading", name="Résultats", level=1)).to_be_visible()


def download_csv(page: Page) -> tuple[str, bytes]:
    """Nom proposé et contenu brut du CSV des résultats (RES-02)."""
    with page.expect_download() as info:
        page.get_by_role("link", name="Télécharger le CSV").click()
    download = info.value
    with open(download.path(), "rb") as file:
        return download.suggested_filename, file.read()


def csv_rows(content: bytes) -> list[list[str]]:
    """Lignes du CSV des résultats : UTF-8 avec BOM, séparateur point-virgule."""
    return list(csv.reader(io.StringIO(content.decode("utf-8-sig")), delimiter=";"))


def results_table(page: Page) -> Locator:
    return page.get_by_role("table", name="Résultats")


def show_grades(page: Page) -> None:
    """La page des résultats s'ouvre notes masquées : l'écran est projeté (RES-04)."""
    page.get_by_text("Afficher les notes", exact=True).click()
    expect(results_table(page)).to_be_visible()


def results_rows(page: Page) -> list[list[str]]:
    """Lignes du tableau des résultats (sans l'en-tête), cellule par cellule. Affiche d'abord
    les notes, si elles sont encore masquées."""
    table = results_table(page)
    if not table.is_visible():
        show_grades(page)
    return [
        [cell.inner_text().strip() for cell in row.get_by_role("cell").all()]
        for row in table.locator("tbody").get_by_role("row").all()
    ]


BOARD_SIZES = (ViewportSize(width=1920, height=1080), ViewportSize(width=1280, height=720))


def assert_fits(page: Page, check: Callable[[ViewportSize], None] | None = None) -> None:
    """Le tableau tient sans défilement en 1920x1080 et en 1280x720. `check`, s'il est donné,
    fait ses propres vérifications à chacune de ces tailles."""
    # Après le démarrage, la page se charge à nouveau : mesurer avant sa feuille de style
    # donnerait n'importe quoi (des formes SVG sans taille occupent toute la largeur).
    page.wait_for_load_state("load")
    for size in BOARD_SIZES:
        page.set_viewport_size(size)
        overflow = page.evaluate(
            "() => document.documentElement.scrollHeight - document.documentElement.clientHeight"
        )
        assert overflow <= 0, (size, overflow)
        if check:
            check(size)


# --- Barres, mesurées sur une capture de l'écran, comme un œil les voit (VIS-02, VIS-04) ---

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
