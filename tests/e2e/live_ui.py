"""Parcours d'une session en direct : l'enseignant sur le PC du tableau, les étudiants sur
leur téléphone. Uniquement par l'interface."""

from __future__ import annotations

import io
import re

import zxingcpp
from PIL import Image
from playwright.sync_api import Locator, Page, expect

CODE_RE = re.compile(r"\b(\d{6})\b")


def open_sessions(page: Page) -> None:
    page.get_by_role("navigation").get_by_role("link", name="Sessions").click()
    expect(page.get_by_role("heading", name="Sessions", exact=True, level=1)).to_be_visible()


def fill_launch(page: Page, quiz: str, group: str, shown: int | str, seconds: int | str) -> None:
    page.get_by_label("QCM").select_option(label=quiz)
    page.get_by_label("Groupe").select_option(label=group)
    page.get_by_label("Questions affichées en même temps").fill(str(shown))
    page.get_by_label("Temps par question (secondes)").fill(str(seconds))
    page.get_by_role("button", name="Lancer").click()


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
    return page.get_by_text(re.compile(r"^Connectés : \d+ / \d+$"))


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


def seconds_left(page: Page) -> int:
    text = timer(page).inner_text()
    match = re.fullmatch(r"(\d+) s", text.strip())
    assert match, text
    return int(match.group(1))


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
    values = "|".join(str(s) for s in range(low, high + 1))
    expect(timer(screen)).to_have_text(re.compile(rf"^({values}) s$"), timeout=timeout)


def join_hint(page: Page) -> Locator:
    """Consigne projetée au tableau : l'adresse à ouvrir et le code de session."""
    return page.get_by_text(re.compile(r"^Sur votre téléphone, ouvrez "))


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


def results_rows(page: Page) -> list[list[str]]:
    """Lignes du tableau des résultats (sans l'en-tête), cellule par cellule."""
    table = page.get_by_role("table", name="Résultats")
    expect(table).to_be_visible()
    return [
        [cell.inner_text().strip() for cell in row.get_by_role("cell").all()]
        for row in table.locator("tbody").get_by_role("row").all()
    ]
