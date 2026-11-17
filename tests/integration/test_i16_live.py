"""I16 côté serveur : terminer le créneau (TPS-02), « k / n ont répondu » (DER-04), retour au
formulaire de lancement (CMP-03)."""

import json
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from bank.models import Quiz
from live.models import Answer, Extension, Session
from live.views import SLOT_ALREADY_OVER
from roster.models import StudentGroup
from tests.factories import (
    jump_to,
    make_group,
    make_participant,
    make_question,
    make_quiz,
    make_session,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def session():
    quiz = make_quiz("QCM", [make_question("Q1"), make_question("Q2")])
    return make_session(quiz, make_group("TD", [("1", "A"), ("2", "B")]), shown=1, seconds=20)


def _end_slot(client, session, slot) -> list[str]:
    response = client.post(
        reverse("session-end-slot", args=[session.code]), {"slot": slot}, follow=True
    )
    assert response.redirect_chain[-1][0] == reverse("board", args=[session.code])
    return [str(m) for m in response.context["messages"]]


def test_end_slot_requires_post(admin_client, session):
    assert admin_client.get(reverse("session-end-slot", args=[session.code])).status_code == 405


def test_end_slot_leaves_5_s_then_nothing_more(admin_client, session):
    session.start(timezone.now())
    jump_to(session, 5)  # 15 s restantes au créneau 0
    assert _end_slot(admin_client, session, "0") == []
    assert list(Extension.objects.values_list("slot", "seconds")) == [(0, -10)]
    session = Session.objects.get(pk=session.pk)
    assert session.schedule.deadlines == [10, 30]
    assert _end_slot(admin_client, session, "0") == []  # 5 s restantes : rien de plus
    assert Extension.objects.count() == 1


@pytest.mark.parametrize("slot", ["1", "", "x", "-1", "00"])
def test_end_slot_refused_for_another_slot(admin_client, session, slot):
    session.start(timezone.now())
    jump_to(session, 5)
    assert _end_slot(admin_client, session, slot) == [SLOT_ALREADY_OVER]
    assert not Extension.objects.exists()


def test_end_slot_refused_before_start_and_after_end(admin_client, session):
    assert _end_slot(admin_client, session, "0") == [SLOT_ALREADY_OVER]
    session.start(timezone.now())
    jump_to(session, 40.5)
    assert _end_slot(admin_client, session, "1") == [SLOT_ALREADY_OVER]
    assert not Extension.objects.exists()


def test_end_slot_arriving_at_the_deadline_changes_nothing(session):
    start = timezone.now()
    session.start(start)
    times = iter([start + timedelta(seconds=19.99)])
    late = start + timedelta(seconds=20)
    assert not session.end_slot("0", clock=lambda: next(times, late))
    assert not Extension.objects.exists()


def test_two_simultaneous_ends_remove_time_once(session):
    """Le second retrait se calcule avec le premier, déjà validé : il ne retire plus rien."""
    start = timezone.now()
    session.start(start)
    at = start + timedelta(seconds=5)
    assert session.end_slot("0", clock=lambda: at)
    assert Session.objects.get(pk=session.pk).end_slot("0", clock=lambda: at)
    assert list(Extension.objects.values_list("seconds", flat=True)) == [-10]


def test_board_state_counts_answers_with_numbers_only(admin_client, session):
    """DER-04 : deux nombres de plus dans le JSON du tableau, aucun texte (AFF-01)."""
    first = make_participant(session, 1)
    make_participant(session, 2)
    url = reverse("board-state", args=[session.code])
    waiting = json.loads(admin_client.get(url).content)
    assert "answered" not in waiting
    session.start(timezone.now())
    session = Session.objects.get(pk=session.pk)
    question = session.schedule.question_for(session.schedule.slots[0], first.rank)
    Answer.objects.create(participant=first, question=question, choices=[0])
    state = json.loads(admin_client.get(url).content)
    assert (state["answered"], state["present"]) == (1, 2)
    assert set(state) == {"page", "remaining_ms", "slot", "slot_ms", "answered", "present"}
    jump_to(session, 40.5)
    assert "answered" not in json.loads(admin_client.get(url).content)


def test_back_returns_to_the_filled_launch_form(admin_client, session):
    """CMP-03, « Revenir » : rien n'est créé, le formulaire garde la saisie."""
    data = {"quiz": Quiz.objects.get().pk, "group": StudentGroup.objects.get().pk}
    data |= {"shown": 2, "seconds": 45, "back": "1"}
    count = Session.objects.count()
    response = admin_client.post(reverse("session-launch"), data)
    assert response.templates[0].name == "live/session_launch.html"
    assert response.context["form"]["seconds"].value() == "45"
    assert Session.objects.count() == count
