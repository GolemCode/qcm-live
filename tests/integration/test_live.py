"""Sessions : accès enseignant, copies figées, et cas de concurrence (codes, numéros)."""

import json

import pytest
from django.urls import reverse

from live import forms as live_forms
from live.forms import IdentifyForm
from live.models import Participant, Session
from tests.factories import make_group, make_question, make_quiz, make_session

pytestmark = pytest.mark.django_db


@pytest.fixture
def session():
    q1 = make_question("Q1", [("a", False), ("b", True)])
    q2 = make_question("Q2", [("x", True), ("y", True), ("z", False)], multiple=True)
    quiz = make_quiz("QCM", [q2, q1], multiple_p="-1")
    return make_session(quiz, make_group("TD", [("1", "A"), ("2", "B")]), shown=2, seconds=20)


@pytest.mark.parametrize("method", ["get", "post"])
def test_teacher_pages_require_login(client, session, method):
    urls = [
        reverse("session-list"),
        reverse("session-launch"),
        reverse("board", args=[session.code]),
        reverse("board-state", args=[session.code]),
        reverse("session-start", args=[session.code]),
    ]
    for url in urls:
        response = getattr(client, method)(url)
        assert response.status_code == 302, url
        assert response["Location"].startswith(reverse("login")), url
    session.refresh_from_db()
    assert session.started_at is None


def test_start_requires_post_and_is_idempotent(admin_client, session):
    url = reverse("session-start", args=[session.code])
    assert admin_client.get(url).status_code == 405
    admin_client.post(url)
    session.refresh_from_db()
    first = session.started_at
    assert first is not None
    admin_client.post(url)
    session.refresh_from_db()
    assert session.started_at == first


def test_board_state_lists_names_in_join_order(admin_client, session):
    Participant.objects.create(session=session, number="2", name="B")
    Participant.objects.create(session=session, number="1", name="A")
    state = json.loads(admin_client.get(reverse("board-state", args=[session.code])).content)
    assert state == {"connected": ["B", "A"], "total": 2}


def test_snapshot_keeps_quiz_order_choices_and_scales(session):
    assert session.code.isdigit() and len(session.code) == 6
    questions = session.content["questions"]
    assert [q["text"] for q in questions] == ["Q2", "Q1"]
    assert questions[0]["multiple"] is True
    assert questions[0]["choices"] == [
        {"text": "x", "correct": True},
        {"text": "y", "correct": True},
        {"text": "z", "correct": False},
    ]
    assert questions[1]["ref"].startswith("Q")
    assert session.content["scales"]["multiple"]["p"] == "-1.00"
    assert session.content["scales"]["simple"]["p"] is None
    assert session.roster == [{"number": "1", "name": "A"}, {"number": "2", "name": "B"}]


def test_code_collision_draws_a_new_code(session, monkeypatch):
    codes = iter([session.code, "123456"])
    monkeypatch.setattr(live_forms, "random_code", lambda: next(codes))
    other = make_session(make_quiz("Q", [make_question("Qx")]), make_group("G", [("9", "Z")]))
    assert other.code == "123456"


def test_number_taken_concurrently_is_a_form_error(session, monkeypatch):
    form = IdentifyForm({"number": "1"}, session=session)
    assert form.is_valid()
    Participant.objects.create(session=session, number="1", name="A")  # l'autre téléphone
    assert form.save() is None
    assert "déjà utilisé" in form.errors["number"][0]
    assert session.participants.count() == 1


def test_unknown_session_page_is_404(client):
    assert client.get(reverse("student-session", args=["999999"])).status_code == 404


def test_one_device_keeps_one_identity_per_session(client, session):
    url = reverse("student-session", args=[session.code])
    client.post(url, {"number": "1"})
    client.post(url, {"number": "2"})  # le formulaire n'est plus proposé : rien ne change
    assert list(session.participants.values_list("number", flat=True)) == ["1"]
    assert Session.objects.count() == 1
