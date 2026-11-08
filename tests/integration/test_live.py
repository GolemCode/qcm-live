"""Sessions : accès enseignant, copies figées, et cas de concurrence (codes, numéros)."""

import json
from datetime import timedelta
from typing import cast

import pytest
from django.db import IntegrityError
from django.forms import ModelChoiceField
from django.template.loader import render_to_string
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from live import forms as live_forms
from live.forms import IdentifyForm
from live.models import Answer, Extension, Participant, Session
from live.schedule import Schedule
from live.views import CLEARED, SAVED, SLOT_OVER
from tests.factories import jump_to, make_group, make_question, make_quiz, make_session, rewind

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
        reverse("session-add-time", args=[session.code]),
        reverse("results", args=[session.code]),
        reverse("results-csv", args=[session.code]),
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
    Participant.objects.create(session=session, number="2", name="B", rank=0)
    Participant.objects.create(session=session, number="1", name="A", rank=1)
    state = json.loads(admin_client.get(reverse("board-state", args=[session.code])).content)
    assert state == {"page": "waiting", "remaining_ms": None, "slot": None, "connected": ["B", "A"]}


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
def running(client, admin_client, session):
    """Session démarrée, l'appareil `client` identifié comme l'étudiant n°1 (rang 0)."""
    client.post(reverse("student-session", args=[session.code]), {"number": "1"})
    admin_client.post(reverse("session-start", args=[session.code]))
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
    # Rang 0, créneau 1 : la question simple Q1 (2 propositions).
    rewind(running, 20)
    response = answer(client, running, *choices, slot="1")
    assert response.status_code == 400
    assert not Answer.objects.exists()


def test_unchecking_everything_means_no_answer(client, running):
    assert answer(client, running, 0, 1).status_code == 200  # Q2, multiple
    assert Answer.objects.get().choices == [0, 1]
    response = answer(client, running)
    assert response.status_code == 200
    assert response.json() == {"message": CLEARED}
    assert not Answer.objects.exists()


def test_clearing_a_single_answer_means_no_answer(client, running):
    """ETU-09 : « Effacer ma réponse » envoie une réponse vide."""
    rewind(running, 20)  # rang 0, créneau 1 : Q1, simple
    assert answer(client, running, 1, slot="1").json() == {"message": SAVED}
    assert answer(client, running, slot="1").json() == {"message": CLEARED}
    assert not Answer.objects.exists()
    assert answer(client, running, slot="1").json() == {"message": CLEARED}  # déjà vide


def test_answer_for_another_slot_is_too_late(client, running):
    response = answer(client, running, 0, slot="1")
    assert response.status_code == 409
    assert not Answer.objects.exists()


def test_release_only_before_start(admin_client, session):
    participant = Participant.objects.create(session=session, number="1", name="A")
    url = reverse("participant-release", args=[session.code, participant.pk])
    assert admin_client.get(url).status_code == 405
    admin_client.post(reverse("session-start", args=[session.code]))
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


def test_ranks_stay_distinct_after_a_release(admin_client, session):
    from django.test import Client

    for number in ("1", "2"):
        Client().post(reverse("student-session", args=[session.code]), {"number": number})
    first = session.participants.get(number="1")
    admin_client.post(reverse("participant-release", args=[session.code, first.pk]))
    Client().post(reverse("student-session", args=[session.code]), {"number": "1"})
    assert sorted(session.participants.values_list("rank", flat=True)) == [1, 2]


def test_rank_conflict_retries_with_the_next_rank(session, monkeypatch):
    Participant.objects.create(session=session, number="1", name="A", rank=0)
    form = IdentifyForm({"number": "2"}, session=session)
    assert form.is_valid()
    ranks = iter([0, 1])  # arrivée simultanée : le premier rang lu est déjà pris
    monkeypatch.setattr(IdentifyForm, "_next_rank", lambda self: next(ranks))
    participant = form.save()
    assert participant is not None and participant.rank == 1


def test_start_renumbers_ranks_in_arrival_order(admin_client, session):
    for rank, number in ((0, "1"), (3, "2")):  # un trou laissé par une libération
        Participant.objects.create(session=session, number=number, name=number, rank=rank)
    admin_client.post(reverse("session-start", args=[session.code]))
    assert list(session.participants.values_list("number", "rank")) == [("1", 0), ("2", 1)]


def test_simultaneous_first_answers_keep_the_last(client, running, monkeypatch):
    participant = running.participants.get()
    Answer.objects.create(participant=participant, question=0, choices=[0])

    def created_meanwhile(*args, **kwargs):
        raise IntegrityError

    monkeypatch.setattr(Answer.objects, "update_or_create", created_meanwhile)
    assert answer(client, running, 1, 2).status_code == 200
    assert Answer.objects.get().choices == [1, 2]


def test_answer_accepted_until_the_very_end_of_the_slot(client, running):
    jump_to(running, running.seconds - 0.5)
    assert answer(client, running, 0, slot="0").status_code == 200
    jump_to(running, running.seconds + 0.01)
    assert answer(client, running, 1, slot="0").status_code == 409
    assert Answer.objects.get().choices == [0]


# --- Temps additionnel (TPS-01) -----------------------------------------------------------


def _add_time(client, session, slot) -> list[str]:
    response = client.post(
        reverse("session-add-time", args=[session.code]), {"slot": slot}, follow=True
    )
    assert response.redirect_chain[-1][0] == reverse("board", args=[session.code])
    return [str(m) for m in response.context["messages"]]


def test_add_time_requires_post(admin_client, session):
    url = reverse("session-add-time", args=[session.code])
    assert admin_client.get(url).status_code == 405


def test_add_time_to_current_slot(admin_client, session):
    session.start(timezone.now())
    jump_to(session, 25)  # créneau 1 (t = 20 s)
    assert _add_time(admin_client, session, "1") == []
    assert _add_time(admin_client, session, "1") == []
    session = Session.objects.get(pk=session.pk)
    assert session.schedule.deadlines == [20, 60]
    state = json.loads(admin_client.get(reverse("board-state", args=[session.code])).content)
    assert state["slot"] == 1
    assert 34_000 < state["remaining_ms"] <= 35_000


@pytest.mark.parametrize("slot", ["0", "2", "", "x", "-1", "1.0", "01"])
def test_add_time_refused_for_another_slot(admin_client, session, slot):
    """Un clic parti avant le changement de créneau, ou une valeur invalide : rien n'est ajouté."""
    session.start(timezone.now())
    jump_to(session, 25)
    assert _add_time(admin_client, session, slot) == [SLOT_OVER]
    assert not Extension.objects.exists()


def test_add_time_refused_before_start_and_after_end(admin_client, session):
    assert _add_time(admin_client, session, "0") == [SLOT_OVER]
    session.start(timezone.now())
    jump_to(session, 40.5)
    assert _add_time(admin_client, session, "1") == [SLOT_OVER]
    assert not Extension.objects.exists()


def test_add_time_arriving_at_the_deadline_does_not_reopen_the_slot(session):
    """Le créneau se termine entre la vérification et l'écriture : l'ajout est annulé."""
    start = timezone.now()
    session.start(start)
    times = iter([start + timedelta(seconds=19.99)])  # vérification : encore dans le créneau 0
    late = start + timedelta(seconds=20)  # écriture : le créneau 0 vient de finir
    assert not session.add_time("0", clock=lambda: next(times, late))
    assert not Extension.objects.exists()


def test_add_time_reads_the_clock_when_called(session, monkeypatch):
    """L'horloge n'est pas figée à la définition de la méthode : l'horloge stable des tests
    doit s'appliquer ici comme ailleurs, sinon le créneau serait jugé sur une autre heure."""
    start = timezone.now()
    session.start(start)
    monkeypatch.setattr(timezone, "now", lambda: start + timedelta(hours=1))
    assert not session.add_time("0")


def test_concurrent_click_near_the_deadline_is_not_lost(session):
    """Deux clics à 0,01 s de l'échéance : le second vérifie l'échéance avant que le premier
    ne soit validé, puis écrit après elle. Il tient compte du premier ajout et passe."""
    start = timezone.now()
    session.start(start)

    calls = []

    def clock():
        calls.append(None)
        if len(calls) == 1:  # vérification du second clic, avant l'échéance
            return start + timedelta(seconds=19.99)
        return start + timedelta(seconds=20.5)  # écriture, après l'échéance d'origine

    Extension.objects.create(session=session, slot=0)  # le premier clic, validé entre-temps
    session = Session.objects.get(pk=session.pk)
    session.schedule = Schedule(2, 2, 20)  # mais la vérification ne l'avait pas vu
    assert session.add_time("0", clock=clock)
    assert Extension.objects.filter(slot=0).count() == 2
    assert Session.objects.get(pk=session.pk).schedule.deadlines == [40, 60]


def test_board_state_has_no_slot_once_ended(admin_client, session):
    session.start(timezone.now())
    rewind(session, 40)
    state = json.loads(admin_client.get(reverse("board-state", args=[session.code])).content)
    assert state == {"page": "ended", "remaining_ms": None, "slot": None}


# --- Fin de session et résultats (RES-01, RES-02) ---------------------------------


def test_results_only_once_the_session_is_over(admin_client, running):
    page = reverse("results", args=[running.code])
    export = reverse("results-csv", args=[running.code])
    for moment in ("waiting", "running"):
        if moment == "running":
            rewind(running, 1)
        assert admin_client.get(export).status_code == 404, moment
        assert "<table" not in admin_client.get(page).content.decode(), moment
    rewind(running, running.schedule.duration)
    assert "<table" in admin_client.get(page).content.decode()
    response = admin_client.get(export)
    assert response.status_code == 200
    assert response["Content-Type"] == "text/csv; charset=utf-8"
    assert response["Content-Disposition"] == f'attachment; filename="resultats-{running.code}.csv"'


def test_results_of_unknown_session_are_404(admin_client):
    assert admin_client.get(reverse("results", args=["000000"])).status_code == 404
    assert admin_client.get(reverse("results-csv", args=["000000"])).status_code == 404


def test_added_time_keeps_the_rotation(client, running):
    """TPS-01 : un « +10 s » ne change pas la question attribuée à l'étudiant, à aucun créneau.
    Le test du reçu (FIN-01, retiré) était le seul à le vérifier au niveau du participant."""
    participant = running.participants.get()
    slots = running.schedule.slots
    before = [participant.question_at(slot)[0] for slot in slots]
    Extension.objects.create(session=running, slot=0)
    again = Participant.objects.get(pk=participant.pk)
    assert [again.question_at(slot)[0] for slot in slots] == before


def test_board_projects_the_join_url_of_class_mode(admin_client, session, settings):
    """CLA-01 : le PC ouvre le tableau en local, mais le tableau projette l'adresse du
    réseau local ; sans mode classe, l'adresse par laquelle le tableau a été ouvert."""
    board = reverse("board", args=[session.code])
    assert "http://testserver/" in admin_client.get(board).content.decode()
    settings.JOIN_URL = "http://192.168.1.23:8000/"
    html = admin_client.get(board).content.decode()
    assert "http://192.168.1.23:8000/" in html and "testserver" not in html


@pytest.mark.parametrize("remote", ["192.168.1.50", "10.0.0.7", "fe80::1"])
def test_class_mode_keeps_the_teacher_area_on_the_teacher_pc(client, settings, remote):
    """Mode classe : l'espace enseignant, connexion comprise, refuse toute requête qui ne vient
    pas du PC lui-même ; les pages des étudiants restent ouvertes au réseau local."""
    settings.TEACHER_LOCAL_ONLY = True
    for path in ("/prof/", "/prof/connexion/", "/prof/sessions/"):
        for send in (client.get, client.post):
            response = send(path, REMOTE_ADDR=remote)
            assert response.status_code == 403, (send, path)
            assert "réservé au PC de l'enseignant" in response.content.decode()
    assert client.get("/", REMOTE_ADDR=remote).status_code == 200


@pytest.mark.parametrize("remote", ["127.0.0.1", "::1"])
def test_class_mode_opens_the_teacher_area_on_the_teacher_pc(client, settings, remote):
    settings.TEACHER_LOCAL_ONLY = True
    assert client.get("/prof/connexion/", REMOTE_ADDR=remote).status_code == 200
    assert client.get("/prof/", REMOTE_ADDR=remote).status_code == 302  # vers la connexion


def test_teacher_area_is_open_to_the_network_outside_class_mode(client):
    assert client.get("/prof/connexion/", REMOTE_ADDR="192.168.1.50").status_code == 200


def test_error_pages_are_in_french(client, session):
    """Hors mode debug (mode classe), les pages d'erreur suivent l'interface : en français."""
    missing = client.get("/page-inexistante/")
    assert missing.status_code == 404 and "<h1>Page introuvable</h1>" in missing.content.decode()
    csrf_client = Client(enforce_csrf_checks=True)
    expired = csrf_client.post(reverse("student-session", args=[session.code]), {"number": "1"})
    assert expired.status_code == 403 and "<h1>Formulaire expiré</h1>" in expired.content.decode()
    assert "<h1>Erreur du serveur</h1>" in render_to_string("500.html")
    unknown_host = client.get("/", headers={"host": "inconnu.example"})
    assert unknown_host.status_code == 400
    assert "<h1>Requête refusée</h1>" in unknown_host.content.decode()
