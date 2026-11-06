"""Sessions : accès enseignant, copies figées, et cas de concurrence (codes, numéros)."""

import json
from typing import cast

import pytest
from django.forms import ModelChoiceField
from django.urls import reverse
from django.utils import timezone

from live import forms as live_forms
from live.forms import IdentifyForm
from live.models import Answer, Participant, Session
from tests.factories import make_group, make_question, make_quiz, make_session, rewind

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
    assert state == {"phase": "waiting", "connected": ["B", "A"]}


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


def test_code_space_exhaustion_fails_loudly(session, monkeypatch):
    monkeypatch.setattr(live_forms, "random_code", lambda: session.code)
    with pytest.raises(RuntimeError):
        make_session(make_quiz("Q", [make_question("Qx")]), make_group("G", [("9", "Z")]))


def test_quiz_emptied_before_launch_is_refused():
    quiz = make_quiz("Q", [make_question("Qx")])
    group = make_group("G", [("9", "Z")])
    form = live_forms.LaunchSessionForm(
        {"quiz": quiz.pk, "group": group.pk, "shown": 1, "seconds": 30}
    )
    quiz.questions.all().delete()  # entre l'affichage du formulaire et l'envoi
    # Le choix était encore proposé quand le formulaire a été affiché.
    cast(ModelChoiceField, form.fields["quiz"]).queryset = live_forms.Quiz.objects.all()
    assert not form.is_valid()
    assert "plus aucune question" in str(form.errors)


def test_stray_query_parameters_do_not_show_errors(client):
    response = client.get("/?utm_source=qr")
    assert response.status_code == 200
    assert not response.context["form"].is_bound


def test_code_typed_with_spaces_is_accepted(client, session):
    spaced = f"{session.code[:3]} {session.code[3:]}"
    response = client.get("/", {"code": spaced})
    assert response["Location"] == reverse("student-session", args=[session.code])


def test_digit_inputs_have_no_maxlength(client):
    assert "maxlength" not in client.get("/").content.decode()


def test_board_polls_until_the_session_ends(admin_client, session):
    board = reverse("board", args=[session.code])
    assert "data-state-url" in admin_client.get(board).content.decode()
    admin_client.post(reverse("session-start", args=[session.code]))
    assert "data-state-url" in admin_client.get(board).content.decode()  # déroulement
    rewind(session, session.schedule.duration)
    assert "data-state-url" not in admin_client.get(board).content.decode()  # terminée


# --- Réponses (ETU-07) et libération (SES-04) -------------------------------------------


@pytest.fixture
def running(client, session):
    """Session démarrée, l'appareil `client` identifié comme l'étudiant n°1 (rang 0)."""
    client.post(reverse("student-session", args=[session.code]), {"number": "1"})
    Session.objects.filter(pk=session.pk).update(started_at=timezone.now())
    session.refresh_from_db()
    return session


def answer(client, session, *choices, slot="0"):
    url = reverse("student-answer", args=[session.code])
    return client.post(url, {"slot": slot, "choice": [str(c) for c in choices]})


def test_answer_requires_identity(running):
    from django.test import Client

    response = answer(Client(), running, 0)
    assert response.status_code == 403
    assert not Answer.objects.exists()


@pytest.mark.parametrize(
    "choices",
    [("x",), (9,), (-1,), (0, 1)],  # non entier, hors bornes, deux choix en simple
)
def test_invalid_answers_are_refused(client, running, choices):
    # Rang 0, créneau 0 : la question multiple Q2 (3 propositions) — on vise la simple Q1.
    rewind(running, 20)
    response = answer(client, running, *choices, slot="1")
    assert response.status_code == 400
    assert not Answer.objects.exists()


def test_unchecking_everything_means_no_answer(client, running):
    assert answer(client, running, 0, 1).status_code == 200  # Q2, multiple
    assert Answer.objects.get().choices == [0, 1]
    assert answer(client, running).status_code == 200
    assert not Answer.objects.exists()


def test_answer_for_another_slot_is_too_late(client, running):
    response = answer(client, running, 0, slot="1")
    assert response.status_code == 409
    assert not Answer.objects.exists()


def test_release_only_before_start(admin_client, session):
    participant = Participant.objects.create(session=session, number="1", name="A")
    url = reverse("participant-release", args=[session.code, participant.pk])
    assert admin_client.get(url).status_code == 405
    Session.objects.filter(pk=session.pk).update(started_at=timezone.now())
    admin_client.post(url)
    assert Participant.objects.filter(pk=participant.pk).exists()
    session.started_at = None
    session.save()
    admin_client.post(url)
    assert not Participant.objects.filter(pk=participant.pk).exists()


def test_release_requires_login(client, session):
    participant = Participant.objects.create(session=session, number="1", name="A")
    url = reverse("participant-release", args=[session.code, participant.pk])
    assert client.post(url)["Location"].startswith(reverse("login"))
    assert client.get(reverse("participants", args=[session.code]))["Location"].startswith(
        reverse("login")
    )
    assert Participant.objects.filter(pk=participant.pk).exists()
