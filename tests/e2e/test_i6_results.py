"""Incrément 6 : résultats et export CSV.

Préconditions communes : quatre questions, N = 2 (deux groupes de deux), t = 30 s, et un
barème qui distingue chaque cas (v et m négatifs et distincts, plancher p = 0 au-dessus du v
des multiples : appliqué à tort à v, il se verrait). Les propositions sont
affichées en ordre inverse sur les téléphones (`reversed_choices`) : une lettre calculée sur
la position à l'écran, et non sur l'ordre du tableau, serait fausse.

Questions, dans l'ordre du QCM (lettres du tableau) :
- Q1 « Capitale de la France ? » : A Paris (juste), B Lyon, C Nice ;
- Q2 « Couleur du ciel ? » : A Bleu (juste), B Vert, C Rouge ;
- Q3 « Deux plus deux ? » : A Quatre (juste), B Trois, C Cinq ;
- Q4 « Lesquels sont pairs ? » (multiple) : A 2 (juste), B 4 (juste), C 7.

Rotation (rang + étape) mod 2 : rang 0 (00123) a Q1, Q2, Q3, Q4 ; rang 1 (42) a Q2, Q1, Q4,
Q3 ; le retardataire (7), arrivé au troisième créneau, a le rang 2 : Q1, Q2 (manquées), Q3, Q4 ;
555, arrivé au dernier créneau et qui ne répond jamais, a le rang 3 : Q2, Q1, Q4, Q3.

L'ordre du fichier du groupe (7, 00123, 0999, 42, 555) diffère de l'ordre d'arrivée
(00123, 42, 7, 555), et l'absent (0999) est au milieu.
"""

from __future__ import annotations

import csv
import io

import pytest
from playwright.sync_api import Page, expect

from bank.models import Quiz
from live.models import Answer, Session
from roster.models import StudentGroup
from tests.e2e.live_setup import (
    QUESTIONS,
    expect_slot,
    make_live,
    open_board,
    question_of,
    started,
)
from tests.e2e.live_ui import (
    LIVE_MS,
    choose,
    open_results,
    open_sessions,
    phone_choices,
    phones_joined,
    results_rows,
    save_status,
    start,
)
from tests.factories import jump_to, make_group, make_question, make_quiz, make_session

SCALE = {
    "simple_b": "2",
    "simple_m": "-0.5",
    "simple_v": "-0.25",
    "multiple_b": "1",
    "multiple_m": "-1",
    "multiple_v": "-0.5",
    "multiple_p": "0",
}
MAX_TOTAL = "9"  # 3 questions simples à 2 points, une multiple de 3 propositions à 1 point
STUDENTS = [
    ("7", "Ng Anh"),
    ("00123", "DURAND Élise"),
    ("0999", "ABSENT Zoé"),  # jamais connecté
    ("42", "MARTIN Léo"),
    ("555", "SILENCIEUX Paul"),  # connecté, sans aucune réponse : noté, pas absent
]

# Réponses de chaque étudiant, créneau par créneau : (question attendue, propositions choisies).
ANSWERS = {
    "00123": [
        ("Capitale de la France ?", ["Lyon"]),  # B : faux, -0,5
        ("Couleur du ciel ?", []),  # pas de réponse : v = -0,25
        ("Deux plus deux ?", ["Quatre"]),  # A : juste, 2
        ("Lesquels sont pairs ?", ["2", "7"]),  # AC : 1 - 1 - 1 = -1, plancher 0
    ],
    "42": [
        ("Couleur du ciel ?", ["Rouge"]),  # C : faux, -0,5
        ("Capitale de la France ?", ["Paris"]),  # A : juste, 2
        ("Lesquels sont pairs ?", ["4"]),  # B : -1 + 1 + 1 = 1
        ("Deux plus deux ?", []),  # pas de réponse : -0,25
    ],
    "7": [  # arrivé au troisième créneau
        None,
        None,
        ("Deux plus deux ?", ["Quatre"]),  # A : juste, 2
        ("Lesquels sont pairs ?", []),  # pas de réponse : v = -0,5, sans plancher
    ],
}


def make_results_session() -> Session:
    return make_live(4, shown=2, students=STUDENTS, scale=SCALE)


def answer_slot(phones: dict, slot: int, session: Session) -> None:
    """Chaque téléphone présent répond (ou non) au créneau `slot`, comme prévu par ANSWERS."""
    jump_to(session, slot * 30 + 1)
    for number, phone in phones.items():
        planned = ANSWERS[number][slot]
        assert planned is not None
        expected_question, chosen = planned
        expect_slot(phone, slot)
        assert question_of(phone_choices(phone)) == expected_question
        for text in chosen:
            choose(phone, text)
            expect(save_status(phone)).to_have_text("Réponse enregistrée")
        if chosen:
            wait_saved(phone, session, number, expected_question, chosen)


def wait_saved(phone: Page, session: Session, number: str, question: str, chosen: list[str]):
    """Le dernier choix est enregistré avant de passer au créneau suivant."""
    index = list(QUESTIONS).index(question)
    labels = [label for label, _ in QUESTIONS[question]]
    expected = sorted(labels.index(text) for text in chosen)
    answers = Answer.objects.filter(
        participant__session=session, participant__number=number, question=index
    )
    for _ in range(40):
        if sorted(answers.values_list("choices", flat=True).first() or []) == expected:
            return
        phone.wait_for_timeout(50)
    raise AssertionError(f"{number} : réponse {chosen} non enregistrée")


def play_session(page: Page, base_url: str, new_phone) -> Session:
    """Session jouée jusqu'au bout : 00123 et 42 dès le départ, 7 au troisième créneau, 555 au
    dernier sans répondre, 0999 jamais connecté."""
    session = make_results_session()
    numbers = ["00123", "42"]
    phones = dict(zip(numbers, started(page, base_url, new_phone, session, numbers), strict=True))
    answer_slot(phones, 0, session)
    answer_slot(phones, 1, session)
    jump_to(session, 61)
    (phones["7"],) = phones_joined(new_phone, base_url, session.code, ["7"])
    answer_slot(phones, 2, session)
    answer_slot(phones, 3, session)
    phones_joined(new_phone, base_url, session.code, ["555"])
    jump_to(session, 121)
    return session


@pytest.mark.spec("RES-01")
@pytest.mark.usefixtures("reversed_choices")
def test_teacher_sees_results_with_amc_scale(teacher_page: Page, live_server, new_phone):
    page = teacher_page
    session = play_session(page, live_server.url, new_phone)
    expect(page.get_by_role("main")).to_contain_text("Session terminée", timeout=LIVE_MS)
    # Le tableau projeté n'affiche aucune note.
    expect(page.get_by_role("main")).not_to_contain_text("1,25")
    expect(page.get_by_role("table")).to_have_count(0)

    # Le contenu figé fait foi (SES-03) : changer le barème ou supprimer le groupe après le
    # lancement ne change rien aux résultats.
    Quiz.objects.update(simple_b=10, simple_v=0, multiple_p=None)
    StudentGroup.objects.all().delete()

    open_results(page)
    expect(page.get_by_role("main")).to_contain_text("Contrôle")
    expect(page.get_by_role("main")).to_contain_text("TD1")
    headers = page.get_by_role("table", name="Résultats").get_by_role("columnheader")
    expect(headers).to_have_text(["Numéro", "Nom", "Note", "Note maximale"])
    assert results_rows(page) == [  # ordre du fichier du groupe, pas celui d'arrivée
        ["7", "Ng Anh", "1", MAX_TOTAL],  # -0,25 - 0,25 + 2 - 0,5
        ["00123", "DURAND Élise", "1,25", MAX_TOTAL],  # -0,5 - 0,25 + 2 + 0
        ["0999", "ABSENT Zoé", "Absent", MAX_TOTAL],
        ["42", "MARTIN Léo", "2,25", MAX_TOTAL],  # -0,5 + 2 + 1 - 0,25
        ["555", "SILENCIEUX Paul", "-1,25", MAX_TOTAL],  # 3 x -0,25 - 0,5
    ]

    # Les résultats sont aussi accessibles depuis la liste des sessions.
    open_sessions(page)
    row = page.get_by_role("row").filter(has_text=session.code)
    expect(row).to_contain_text("Terminée")
    row.get_by_role("link", name="Résultats").click()
    expect(page.get_by_role("heading", name="Résultats", level=1)).to_be_visible()
    assert results_rows(page)[1] == ["00123", "DURAND Élise", "1,25", MAX_TOTAL]


@pytest.mark.spec("RES-01")
def test_no_results_before_the_end(teacher_page: Page, live_server, new_phone):
    page = teacher_page
    session = make_results_session()
    (phone,) = phones_joined(new_phone, live_server.url, session.code, ["00123"])
    page.goto(f"{live_server.url}/prof/sessions/")
    row = page.get_by_role("row").filter(has_text=session.code)
    expect(row).to_contain_text("En attente")
    expect(row.get_by_role("link", name="Résultats")).to_have_count(0)

    open_board(page, live_server.url, session)
    start(page)
    expect_slot(phone, 0)
    choose(phone, "Paris")  # une note provisoire existe : 2 points
    expect(save_status(phone)).to_have_text("Réponse enregistrée")
    page.goto(f"{live_server.url}/prof/sessions/")
    expect(row).to_contain_text("En cours")
    expect(row.get_by_role("link", name="Résultats")).to_have_count(0)
    # Même par son adresse, la page n'affiche ni étudiant ni note avant la fin.
    page.goto(f"{live_server.url}/prof/sessions/{session.code}/resultats/")
    main = page.get_by_role("main")
    expect(main).to_contain_text("à la fin de la session")
    for hidden in ("DURAND", "Élise", "Absent", "Note"):  # le code de session a des chiffres
        expect(main).not_to_contain_text(hidden)
    expect(page.get_by_role("link", name="Télécharger le CSV")).to_have_count(0)


def download_csv(page: Page) -> tuple[str, bytes]:
    with page.expect_download() as info:
        page.get_by_role("link", name="Télécharger le CSV").click()
    download = info.value
    path = download.path()
    with open(path, "rb") as file:
        return download.suggested_filename, file.read()


@pytest.mark.spec("RES-02")
@pytest.mark.usefixtures("reversed_choices")
def test_results_csv(teacher_page: Page, live_server, new_phone):
    page = teacher_page
    session = play_session(page, live_server.url, new_phone)
    open_board(page, live_server.url, session)
    open_results(page)
    filename, content = download_csv(page)

    assert filename == f"resultats-{session.code}.csv"
    assert content.startswith(b"\xef\xbb\xbf")  # UTF-8 avec BOM, pour Excel
    rows = list(csv.reader(io.StringIO(content.decode("utf-8-sig")), delimiter=";"))
    questions = [f"Q{i} {kind}" for i in range(1, 5) for kind in ("réponse", "points")]
    assert rows == [
        ["numéro", "nom", "note", "note max", *questions],
        # Une colonne par question, dans l'ordre du QCM ; `-` : pas de réponse.
        # Les nombres ne sont pas neutralisés, même négatifs.
        ["7", "Ng Anh", "1", "9", "-", "-0,25", "-", "-0,25", "A", "2", "-", "-0,5"],
        ["00123", "DURAND Élise", "1,25", "9", "B", "-0,5", "-", "-0,25", "A", "2", "AC", "0"],
        ["0999", "ABSENT Zoé", "Absent", "9", "", "", "", "", "", "", "", ""],
        ["42", "MARTIN Léo", "2,25", "9", "A", "2", "C", "-0,5", "-", "-0,25", "B", "1"],
        ["555", "SILENCIEUX Paul", "-1,25", "9", *["-", "-0,25"] * 3, "-", "-0,5"],
    ]


@pytest.mark.spec("RES-02")
def test_results_csv_neutralises_formulas(teacher_page: Page, live_server, new_phone):
    """Les noms viennent d'un fichier extérieur : un tableur ne doit exécuter aucune formule."""
    page = teacher_page
    names = ["=1+1", "+33 6", "-2", "@SOMME(A1)", "Nom=normal"]
    group = make_group("TD2", [(str(i), name) for i, name in enumerate(names, start=1)])
    quiz = make_quiz("Court", [make_question("Oui ?")])
    session = make_session(quiz, group, seconds=5)
    started(page, live_server.url, new_phone, session)
    jump_to(session, 6)
    expect(page.get_by_role("main")).to_contain_text("Session terminée", timeout=LIVE_MS)
    open_results(page)
    _, content = download_csv(page)
    rows = list(csv.reader(io.StringIO(content.decode("utf-8-sig")), delimiter=";"))
    assert [row[1] for row in rows[1:]] == ["'=1+1", "'+33 6", "'-2", "'@SOMME(A1)", "Nom=normal"]
    # Le tableau de la page, lui, affiche les noms tels quels.
    assert [row[1] for row in results_rows(page)] == names
