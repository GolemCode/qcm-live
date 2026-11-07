"""Préconditions des tests du déroulement : un QCM de questions reconnaissables, un groupe,
une session lancée par les fabriques, puis démarrée au tableau."""

from __future__ import annotations

from playwright.sync_api import Page, expect

from live.models import Session
from tests.e2e.live_ui import LIVE_MS, phones_joined, start
from tests.factories import make_group, make_question, make_quiz, make_session

# Des propositions distinctes d'une question à l'autre : le téléphone, qui n'affiche jamais
# l'énoncé, se reconnaît à ses propositions.
QUESTIONS = {
    "Capitale de la France ?": [("Paris", True), ("Lyon", False), ("Nice", False)],
    "Couleur du ciel ?": [("Bleu", True), ("Vert", False), ("Rouge", False)],
    "Deux plus deux ?": [("Quatre", True), ("Trois", False), ("Cinq", False)],
    "Lesquels sont pairs ?": [("2", True), ("4", True), ("7", False)],
}
MULTIPLE = {"Lesquels sont pairs ?"}
STUDENTS = [("00123", "DURAND Élise"), ("42", "MARTIN Léo"), ("7", "Ng Anh")]


def question_of(choices: list[str]) -> str:
    """Énoncé de la question dont le téléphone affiche ces propositions (dans le désordre)."""
    for text, expected in QUESTIONS.items():
        if sorted(choices) == sorted(label for label, _ in expected):
            return text
    raise AssertionError(f"propositions inconnues : {choices}")


def expect_slot(phone: Page, slot: int, timeout: float = LIVE_MS) -> None:
    """Le téléphone affiche le créneau `slot` (jeton de page « running:<slot> »)."""
    expect(phone.locator("main")).to_have_attribute("data-page", f"running:{slot}", timeout=timeout)


def make_live(
    n_questions: int,
    shown: int,
    seconds: int = 30,
    *,
    students=STUDENTS,
    scale: dict[str, str] | None = None,
) -> Session:
    """Session lancée sur les `n_questions` premières questions, avec le barème `scale`."""
    questions = [
        make_question(text, choices, multiple=text in MULTIPLE)
        for text, choices in list(QUESTIONS.items())[:n_questions]
    ]
    group = make_group("TD1", students)
    quiz = make_quiz("Contrôle", questions, **(scale or {}))
    return make_session(quiz, group, shown=shown, seconds=seconds)


def open_board(page: Page, base_url: str, session: Session) -> None:
    page.goto(f"{base_url}/prof/sessions/{session.code}/")


def started(page: Page, base_url: str, new_phone, session: Session, numbers=()) -> list[Page]:
    """Les téléphones `numbers` rejoignent la session, puis l'enseignant la démarre."""
    phones = phones_joined(new_phone, base_url, session.code, numbers)
    open_board(page, base_url, session)
    start(page)
    return phones
