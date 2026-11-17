"""Incrément 14 : identification par la liste du groupe.

Le n° de liste désigne l'étudiant (GRP-05) ; l'étudiant choisit son nom sur son téléphone
(ETU-13) ; les résultats commencent par le n°, le numéro étudiant et le nom (RES-05) ; les
groupes et sessions d'avant I14 passent la mise à jour (MIG-01).
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.conf import settings
from django.contrib.sessions.backends.db import SessionStore
from django.utils import timezone
from playwright.sync_api import Browser, Page, Playwright, expect

from tests.e2e.a11y import axe_violations, keyboard_problems, low_contrasts
from tests.e2e.live_setup import expect_slot, make_live, open_board
from tests.e2e.live_ui import (
    LIVE_MS,
    choose,
    connected_names,
    csv_rows,
    download_csv,
    enter_code,
    group_list,
    identify,
    identity,
    join,
    launch_session,
    leave_board,
    list_entry,
    open_results,
    phones_joined,
    results_rows,
    results_table,
    save_status,
    search,
    show_grades,
    start,
)
from tests.e2e.roster_ui import import_group, open_groups, student_rows, submit_group
from tests.factories import jump_to, make_group, make_question, make_quiz
from tests.migrations import leaves, migrate

# --- GRP-05 : fichier à en-tête n°, numéro étudiant, nom -------------------------------------

# Export d'Excel en français, en Windows-1252 : n° qui ne se suivent pas et pas dans l'ordre,
# un numéro étudiant vide, un autre avec des lettres.
TD_CSV = (
    "N°;Numéro étudiant;Nom\r\n12;21904567;DUPONT Jeanne\r\n3;;LEFÈVRE Zoé\r\n"
    "7;INE-0042b;MARTIN Paul\r\n"
).encode("cp1252")
HEADER = b"n\xc2\xb0;num\xc3\xa9ro \xc3\xa9tudiant;nom\n"


def students(count: int) -> bytes:
    return HEADER + "".join(f"{n};;ÉTUDIANT {n}\n" for n in range(1, count + 1)).encode()


@pytest.mark.spec("GRP-05")
def test_import_group_with_list_numbers(teacher_page: Page):
    page = teacher_page
    import_group(page, "TD1", TD_CSV)
    expect(page.get_by_role("status")).to_contain_text("Groupe importé : 3 étudiants")
    expect(page.get_by_role("status")).not_to_contain_text("en-tête")  # en-tête attendu
    table = page.get_by_role("table", name="Étudiants du groupe")
    expect(table.get_by_role("columnheader")).to_have_text(["N°", "Numéro étudiant", "Nom"])
    # Par n° croissant, le numéro étudiant tel quel, vide s'il manque.
    expect(student_rows(page)).to_have_count(3)
    expect(student_rows(page).nth(0).get_by_role("cell")).to_have_text(["3", "", "LEFÈVRE Zoé"])
    expect(student_rows(page).nth(1).get_by_role("cell")).to_have_text(
        ["7", "INE-0042b", "MARTIN Paul"]
    )
    expect(student_rows(page).nth(2).get_by_role("cell")).to_have_text(
        ["12", "21904567", "DUPONT Jeanne"]
    )

    # 70 étudiants : accepté, la limite tout juste ; 999, le plus grand n°.
    import_group(page, "Amphi", students(69) + b"999;;DERNIER Max\n")
    expect(page.get_by_role("status")).to_contain_text("Groupe importé : 70 étudiants")
    expect(student_rows(page).last.get_by_role("cell")).to_have_text(["999", "", "DERNIER Max"])

    # Refus, sans rien créer.
    open_groups(page)
    page.get_by_role("link", name="Importer un groupe").click()
    refused = [
        (students(71), ["71 étudiants : 70 au plus"]),
        (HEADER + b"12;A;X\n5;B;Y\n12;C;Z\n", ["Ligne 4", "n° 12 en double", "ligne 2"]),
        (HEADER + b"1000;;X\n", ["Ligne 2", "le n° « 1000 » doit être un entier de 1 à 999"]),
        (HEADER + b"0;;X\n", ["Ligne 2", "de 1 à 999"]),
        (HEADER + b";1;X\n", ["Ligne 2", "n° vide"]),
        (HEADER + b"1;" + b"9" * 21 + b";X\n", ["Ligne 2", "20 caractères au plus"]),
        (HEADER + b"1;A1;X\n2;A1;Y\n", ["Ligne 3", "numéro étudiant « A1 » en double"]),
        (HEADER + b"1;X\n", ["Ligne 2", "3 colonnes attendues"]),
        # Trois colonnes sans l'en-tête : l'erreur dit lequel est attendu.
        (b"1;00123;X\n", ["Ligne 1", "n°;numéro étudiant;nom"]),
    ]
    for content, fragments in refused:
        submit_group(page, "TD refusé", content)
        for fragment in fragments:
            expect(page.get_by_role("alert")).to_contain_text(fragment)
    open_groups(page)
    expect(page.get_by_role("link", name="TD refusé")).to_have_count(0)

    # L'ancien format reste accepté : le n° est le rang dans le fichier.
    import_group(page, "Ancien", b"numero;nom\n00123;DURAND Elise\n42;MARTIN Leo\n")
    expect(student_rows(page).nth(1).get_by_role("cell")).to_have_text(["2", "42", "MARTIN Leo"])


# --- ETU-13 : l'étudiant choisit son nom dans la liste ----------------------------------------

TD = [(12, "21904567", "DUPONT Jeanne"), (3, "", "LEFÈVRE Zoé"), (7, "INE-0042b", "MARTIN Paul")]


@pytest.fixture
def td_session(transactional_db):
    group = make_group("TD1", TD)
    quiz = make_quiz("Contrôle", [make_question("Q1")])
    return group, quiz


def check_a11y(phone: Page, where: str) -> None:
    assert axe_violations(phone) == [], where
    assert low_contrasts(phone) == [], where
    assert keyboard_problems(phone) == [], where


@pytest.mark.spec("ETU-13")
def test_student_picks_name_in_the_group_list(
    teacher_page: Page, live_server, new_phone, td_session
):
    code = launch_session(teacher_page, "Contrôle", "TD1")
    phone = new_phone()
    enter_code(phone, live_server.url, code)

    # Toute la liste, par n° croissant, avec le n° et le nom ; aucun numéro à taper ni affiché.
    entries = group_list(phone).get_by_role("listitem")
    expect(entries).to_have_count(3)
    for entry, (number, name) in zip(
        entries.all(), [(3, "LEFÈVRE Zoé"), (7, "MARTIN Paul"), (12, "DUPONT Jeanne")], strict=True
    ):
        expect(entry).to_contain_text(str(number))
        expect(entry).to_contain_text(name)
    expect(phone.locator("input[inputmode=numeric]")).to_have_count(0)
    expect(phone.locator("body")).not_to_contain_text("21904567")
    expect(phone.locator("body")).not_to_contain_text("INE-0042b")
    expect(teacher_page.get_by_role("main")).not_to_contain_text("21904567")
    for link in group_list(phone).get_by_role("link").all():
        box = link.bounding_box()
        assert box and box["height"] >= 48, box  # cible tactile (VIS-04)
    check_a11y(phone, "liste")

    # Recherche sans majuscules ni accents, pendant la saisie.
    search(phone).fill("lefevre")
    expect(entries.filter(visible=True)).to_have_count(1)
    expect(list_entry(phone, "LEFÈVRE Zoé")).to_be_visible()
    search(phone).fill("ZOE")
    expect(list_entry(phone, "LEFÈVRE Zoé")).to_be_visible()
    expect(list_entry(phone, "DUPONT Jeanne")).to_be_hidden()
    search(phone).fill("xyz")
    expect(entries.filter(visible=True)).to_have_count(0)
    expect(phone.get_by_text("Aucun nom ne correspond.")).to_be_visible()
    check_a11y(phone, "recherche sans résultat")
    search(phone).fill("")
    expect(entries.filter(visible=True)).to_have_count(3)

    # Toucher son nom ouvre une confirmation ; « Non » revient à la liste sans identifier.
    list_entry(phone, "MARTIN Paul").get_by_role("link").click()
    expect(phone.get_by_text("Vous êtes MARTIN Paul ?")).to_be_visible()
    expect(phone.get_by_role("main")).to_contain_text("N° 7")
    expect(phone.locator("body")).not_to_contain_text("INE-0042b")
    check_a11y(phone, "confirmation")
    phone.get_by_role("link", name="Non, revenir à la liste").click()
    expect(group_list(phone)).to_be_visible()
    expect(identity(phone)).to_have_count(0)
    expect(connected_names(teacher_page)).to_have_count(0)

    # « Oui, c'est moi » identifie : nom et n°, jamais le numéro étudiant.
    identify(phone, "MARTIN Paul")
    expect(identity(phone)).to_have_text("Vous êtes MARTIN Paul")
    expect(phone.get_by_role("main")).to_contain_text("N° 7")
    expect(phone.locator("body")).not_to_contain_text("INE-0042b")
    expect(connected_names(teacher_page)).to_have_text(["MARTIN Paul"], timeout=LIVE_MS)

    # Sur un autre téléphone, le nom pris est grisé, « déjà connecté », et ne se choisit pas.
    other = new_phone()
    enter_code(other, live_server.url, code)
    taken, free = list_entry(other, "MARTIN Paul"), list_entry(other, "DUPONT Jeanne")
    expect(taken).to_contain_text("déjà connecté")
    expect(taken.get_by_role("link")).to_have_count(0)
    expect(free).not_to_contain_text("déjà connecté")
    grey = taken.get_by_text("MARTIN Paul", exact=True)
    ink = free.get_by_text("DUPONT Jeanne", exact=True)
    assert grey.evaluate("e => getComputedStyle(e).color") != ink.evaluate(
        "e => getComputedStyle(e).color"
    )
    check_a11y(other, "liste avec un nom pris")

    # Pris pendant la confirmation : refusé, avec un message, et la liste revient.
    list_entry(other, "DUPONT Jeanne").get_by_role("link").click()
    join(new_phone(), live_server.url, code, "DUPONT Jeanne")
    other.get_by_role("button", name="Oui, c'est moi").click()
    expect(other.get_by_role("status")).to_contain_text("déjà connecté")
    expect(list_entry(other, "DUPONT Jeanne")).to_contain_text("déjà connecté")
    expect(identity(other)).to_have_count(0)
    identify(other, "LEFÈVRE Zoé")
    expect(identity(other)).to_have_text("Vous êtes LEFÈVRE Zoé")


@pytest.mark.spec("ETU-13")
def test_group_list_works_without_javascript(
    teacher_page: Page, live_server, browser: Browser, playwright: Playwright, td_session
):
    code = launch_session(teacher_page, "Contrôle", "TD1")
    context = browser.new_context(
        **playwright.devices["Pixel 7"], locale="fr-FR", java_script_enabled=False
    )
    try:
        phone = context.new_page()
        enter_code(phone, live_server.url, code)
        expect(search(phone)).to_be_hidden()  # inutile sans script : pas affiché
        expect(group_list(phone).get_by_role("listitem")).to_have_count(3)
        list_entry(phone, "DUPONT Jeanne").get_by_role("link").click()
        phone.get_by_role("button", name="Oui, c'est moi").click()
        expect(identity(phone)).to_have_text("Vous êtes DUPONT Jeanne")
    finally:
        context.close()


# --- RES-05 : n°, numéro étudiant, nom dans les résultats -------------------------------------


@pytest.mark.spec("RES-05")
def test_results_start_with_list_number(teacher_page: Page, live_server, new_phone):
    page = teacher_page
    session = make_live(
        1,
        shown=1,
        students=[(12, "=1+1", "DUPONT Jeanne"), (3, "", "LEFÈVRE Zoé"), (7, "7", "+MARTIN")],
    )
    phones_joined(new_phone, live_server.url, session.code, ["LEFÈVRE Zoé"])
    open_board(page, live_server.url, session)
    start(page)
    jump_to(session, 31)
    expect(page.get_by_role("main")).to_contain_text("Session terminée", timeout=LIVE_MS)
    open_results(page)

    show_grades(page)
    expect(results_table(page).get_by_role("columnheader")).to_have_text(
        ["N°", "Numéro étudiant", "Nom", "Note", "Note maximale", "Note /20"]
    )
    # Par n° croissant ; le numéro étudiant vide reste une cellule vide.
    assert results_rows(page) == [
        ["3", "", "LEFÈVRE Zoé", "0", "1", "0"],
        ["7", "7", "+MARTIN", "Absent", "1", ""],
        ["12", "=1+1", "DUPONT Jeanne", "Absent", "1", ""],
    ]

    _, content = download_csv(page)
    rows = csv_rows(content)
    assert rows[0][:3] == ["n°", "numéro étudiant", "nom"]
    # Numéro étudiant et nom, texte libre, neutralisés pour le tableur.
    assert [row[:4] for row in rows[1:]] == [
        ["3", "", "LEFÈVRE Zoé", "0"],
        ["7", "7", "'+MARTIN", "Absent"],
        ["12", "'=1+1", "DUPONT Jeanne", "Absent"],
    ]


# --- MIG-01 : groupes et sessions d'avant I14 -------------------------------------------------

BEFORE = [("roster", "0001_initial"), ("live", "0005_frozen_question_scoring")]
OLD_ROSTER = [
    {"number": "00123", "name": "DURAND Élise"},
    {"number": "42", "name": "MARTIN Léo"},
    {"number": "7", "name": "Ng Anh"},
]


@pytest.fixture
def old_apps(transactional_db):
    """Base ramenée à l'état d'avant I14 ; remise à jour à la fin, même en cas d'échec."""
    apps = migrate(BEFORE)
    yield apps
    migrate(leaves())


def choice(text: str, correct: bool) -> dict:
    return {"text": text, "correct": correct, "points": None, "none": False}


CONTENT = {
    "questions": [
        {
            "text": "Capitale de la France ?",
            "multiple": False,
            "ordered": False,
            "scoring": "b=2,m=-1",
            "choices": [choice("Paris", True), choice("Lyon", False), choice("Nice", False)],
        }
    ]
}


def make_old_data(apps) -> int:
    """Données créées avec les modèles d'avant I14 : un groupe, une session terminée et une
    session en attente. Renvoie l'id du participant connecté à la session en attente."""
    group = apps.get_model("roster", "StudentGroup").objects.create(name="TD ancien")
    for position, student in enumerate(OLD_ROSTER):
        group.students.create(position=position, **student)
    Session = apps.get_model("live", "Session")
    common = {"quiz_title": "Contrôle", "group_name": "TD ancien", "content": CONTENT}
    common |= {"roster": OLD_ROSTER, "n_questions": 1, "shown": 1, "seconds": 30}
    ended = Session.objects.create(
        code="111111", started_at=timezone.now() - timedelta(hours=1), **common
    )
    for rank, (number, name, chosen) in enumerate(
        [("42", "MARTIN Léo", [0]), ("00123", "DURAND Élise", [1])]
    ):
        participant = ended.participants.create(number=number, name=name, rank=rank)
        participant.answers.create(question=0, choices=chosen)
    waiting = Session.objects.create(code="222222", **common)
    return waiting.participants.create(number="42", name="MARTIN Léo", rank=0).pk


@pytest.mark.spec("MIG-01")
def test_groups_and_sessions_from_before_i14(teacher_page: Page, live_server, new_phone, old_apps):
    page = teacher_page
    participant_id = make_old_data(old_apps)
    # Le téléphone de MARTIN Léo, identifié avant la mise à jour : son cookie de session.
    store = SessionStore()
    store["live_participants"] = {"222222": participant_id}
    store.save()
    leo = new_phone()
    leo.context.add_cookies(
        [{"name": settings.SESSION_COOKIE_NAME, "value": store.session_key, "url": live_server.url}]
    )

    migrate(leaves())

    # Le groupe : n° = rang dans le fichier, l'ancien numéro devient le numéro étudiant.
    open_groups(page)
    page.get_by_role("link", name="TD ancien").click()
    expect(student_rows(page)).to_have_count(3)
    for row, cells in zip(
        student_rows(page).all(),
        [["1", "00123", "DURAND Élise"], ["2", "42", "MARTIN Léo"], ["3", "7", "Ng Anh"]],
        strict=True,
    ):
        expect(row.get_by_role("cell")).to_have_text(cells)

    # La session terminée : mêmes notes, nouvelles colonnes.
    page.goto(f"{live_server.url}/prof/sessions/111111/")
    open_results(page)
    assert [row[:5] for row in results_rows(page)] == [
        ["1", "00123", "DURAND Élise", "-1", "2"],
        ["2", "42", "MARTIN Léo", "2", "2"],
        ["3", "7", "Ng Anh", "Absent", "2"],
    ]
    _, content = download_csv(page)
    assert [row[:4] for row in csv_rows(content)] == [
        ["n°", "numéro étudiant", "nom", "note"],
        ["1", "00123", "DURAND Élise", "-1"],
        ["2", "42", "MARTIN Léo", "2"],
        ["3", "7", "Ng Anh", "Absent"],
    ]

    # La session en attente : MARTIN Léo reste connecté, son nom est pris pour les autres.
    leo.goto(f"{live_server.url}/s/222222/")
    expect(identity(leo)).to_have_text("Vous êtes MARTIN Léo")
    expect(leo.get_by_role("main")).to_contain_text("N° 2")
    other = new_phone()
    enter_code(other, live_server.url, "222222")
    expect(list_entry(other, "MARTIN Léo")).to_contain_text("déjà connecté")
    page.goto(f"{live_server.url}/prof/sessions/222222/")
    expect(connected_names(page)).to_have_text(["MARTIN Léo"])
    start(page)
    expect_slot(leo, 0)
    choose(leo, "Paris")
    expect(save_status(leo)).to_have_text("Réponse enregistrée")

    # Une nouvelle session sur le groupe repris : la liste porte les n°.
    make_quiz("Nouveau", [make_question("Q1")])
    leave_board(page)
    code = launch_session(page, "Nouveau", "TD ancien")
    phone = new_phone()
    join(phone, live_server.url, code, "Ng Anh")
    expect(identity(phone)).to_have_text("Vous êtes Ng Anh")
    expect(phone.get_by_role("main")).to_contain_text("N° 3")
