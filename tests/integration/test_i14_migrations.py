"""Migrations d'I14 (MIG-01) : les groupes et les sessions d'avant I14 passent au n° de liste.

Chaque test ramène la base à l'état d'avant I14, y crée des données au format ancien (numéro,
nom ; `position` dans le groupe ; `number` du participant), puis applique les migrations
jusqu'au bout et relit le résultat avec les modèles de l'application.
"""

from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from live.models import Participant, Session
from live.results import ABSENT, csv_rows, grade
from live.snapshot import FrozenChoice, FrozenQuiz
from roster.models import Student, StudentGroup
from tests.migrations import leaves, migrate

BEFORE = [("roster", "0001_initial"), ("live", "0005_frozen_question_scoring")]

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def old_apps():
    apps = migrate(BEFORE)
    yield apps
    migrate(leaves())


def choice(text, correct) -> FrozenChoice:
    return {"text": text, "correct": correct, "points": None, "none": False}


CONTENT: FrozenQuiz = {
    "questions": [
        {
            "text": "S",
            "multiple": False,
            "ordered": False,
            "scoring": "b=2,m=-1",
            "choices": [choice("a", True), choice("b", False)],
        },
        {
            "text": "M",
            "multiple": True,
            "ordered": False,
            "scoring": "",
            "choices": [choice("x", True), choice("y", True), choice("z", False)],
        },
    ]
}
# Liste figée d'avant I14 : dans l'ordre du fichier, numéro et nom.
OLD_ROSTER = [
    {"number": "00123", "name": "DURAND Élise"},
    {"number": "42", "name": "MARTIN Léo"},
    {"number": "7", "name": "Ng Anh"},
]
NEW_ROSTER = [
    {"list_number": 1, "student_number": "00123", "name": "DURAND Élise"},
    {"list_number": 2, "student_number": "42", "name": "MARTIN Léo"},
    {"list_number": 3, "student_number": "7", "name": "Ng Anh"},
]


def test_students_get_their_rank_in_the_file_as_list_number(old_apps):
    Group = old_apps.get_model("roster", "StudentGroup")
    OldStudent = old_apps.get_model("roster", "Student")
    td1, td2 = Group.objects.create(name="TD1"), Group.objects.create(name="TD2")
    # Créés dans le désordre : seul `position` donne l'ordre du fichier.
    for position, number, name in [(2, "7", "Ng Anh"), (0, "00123", "DURAND Élise")]:
        OldStudent.objects.create(group=td1, position=position, number=number, name=name)
    OldStudent.objects.create(group=td1, position=1, number="42", name="MARTIN Léo")
    OldStudent.objects.create(group=td2, position=0, number="42", name="ROUX Paul")

    migrate(leaves())

    rows = Student.objects.filter(group__name="TD1").values_list(
        "list_number", "student_number", "name"
    )
    assert list(rows) == [(1, "00123", "DURAND Élise"), (2, "42", "MARTIN Léo"), (3, "7", "Ng Anh")]
    assert list(StudentGroup.objects.get(name="TD2").students.values_list("list_number")) == [(1,)]
    # Le n° est désormais unique dans le groupe.
    with pytest.raises(IntegrityError), transaction.atomic():
        Student.objects.create(group=StudentGroup.objects.get(name="TD2"), list_number=1, name="X")


def old_session(apps, code, *, started_minutes_ago=None):
    started = None
    if started_minutes_ago is not None:
        started = timezone.now() - timedelta(minutes=started_minutes_ago)
    return apps.get_model("live", "Session").objects.create(
        code=code,
        quiz_title="Contrôle",
        group_name="TD1",
        content=CONTENT,
        roster=OLD_ROSTER,
        n_questions=2,
        shown=1,
        seconds=10,
        started_at=started,
    )


def old_participant(apps, session, number, rank, answers=None):
    name = next(s["name"] for s in OLD_ROSTER if s["number"] == number)
    participant = apps.get_model("live", "Participant").objects.create(
        session=session, number=number, name=name, rank=rank
    )
    for question, choices in (answers or {}).items():
        participant.answers.create(question=question, choices=choices)
    return participant


def test_ended_session_keeps_participants_answers_and_marks(old_apps):
    ended = old_session(old_apps, "111111", started_minutes_ago=60)
    leo = old_participant(old_apps, ended, "42", 0, {0: [0], 1: [0, 1]})
    elise = old_participant(old_apps, ended, "00123", 1, {0: [1]})

    migrate(leaves())

    session = Session.objects.get(code="111111")
    assert session.state(timezone.now()).phase == "ended"
    assert session.roster == NEW_ROSTER
    participants = session.participants.order_by("list_number")
    assert [(p.pk, p.list_number, p.student_number, p.name, p.rank) for p in participants] == [
        (elise.pk, 1, "00123", "DURAND Élise", 1),
        (leo.pk, 2, "42", "MARTIN Léo", 0),
    ]
    assert Participant.objects.get(pk=leo.pk).answer_map() == {0: [0], 1: [0, 1]}

    # Mêmes notes qu'avant ; seules les colonnes d'identité changent (RES-05).
    rows = session.results()
    assert [(r.list_number, r.student_number, r.name) for r in rows] == [
        (1, "00123", "DURAND Élise"),
        (2, "42", "MARTIN Léo"),
        (3, "7", "Ng Anh"),
    ]
    expected = [grade(CONTENT, {0: [1]}), grade(CONTENT, {0: [0], 1: [0, 1]})]
    assert [r.marks for r in rows[:2]] == expected
    assert rows[2].marks is None
    table = csv_rows(session.content, rows)
    assert table[0][:4] == ["n°", "numéro étudiant", "nom", "note"]
    assert [row[:4] for row in table[1:]] == [
        ["1", "00123", "DURAND Élise", "-1"],
        ["2", "42", "MARTIN Léo", "5"],
        ["3", "7", "Ng Anh", ABSENT],
    ]


def test_waiting_and_running_sessions_keep_their_connected_students(old_apps):
    waiting = old_session(old_apps, "222222")
    old_participant(old_apps, waiting, "7", 0)
    running = old_session(old_apps, "333333", started_minutes_ago=0)
    old_participant(old_apps, running, "00123", 0, {0: [0]})
    old_participant(old_apps, running, "7", 1)

    migrate(leaves())

    session = Session.objects.get(code="222222")
    assert session.state(timezone.now()).phase == "waiting"
    assert session.roster == NEW_ROSTER
    assert list(session.participants.values_list("list_number", "student_number")) == [(3, "7")]
    assert session.student(3) == NEW_ROSTER[2]
    assert session.student(4) is None

    session = Session.objects.get(code="333333")
    assert session.state(timezone.now()).phase == "running"
    participants = session.participants.order_by("rank")
    assert [(p.list_number, p.rank, p.answer_map()) for p in participants] == [
        (1, 0, {0: [0]}),
        (3, 1, {}),
    ]
    # Le n° est désormais unique dans la session : le même étudiant ne s'identifie pas deux
    # fois.
    with pytest.raises(IntegrityError), transaction.atomic():
        Participant.objects.create(session=session, list_number=1, name="X", rank=5)
