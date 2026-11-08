"""Sessions en direct : le tableau de l'enseignant et l'écran des étudiants.

Une session passe par trois phases (Session.state) : attente, déroulement, terminée. Le
créneau en cours se calcule à partir de l'heure de démarrage (live.schedule), sans tâche de
fond : chaque page et chaque état JSON le recalculent.

Chaque page qui suit le direct porte un « jeton de page » (data-page) : la phase, et le groupe
(tableau) ou le créneau (téléphone) affiché. static/js/poll.js recharge la page dès que l'état
JSON annonce un autre jeton.
"""

from __future__ import annotations

import csv
from urllib.parse import urljoin

import segno
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from live.forms import AnswerForm, IdentifyForm, JoinForm, LaunchSessionForm
from live.models import PHASE_LABELS, Answer, Participant, Session, State
from live.results import csv_rows, decimal_fr, max_total

# Identité des étudiants : {code de session: id du participant}, dans la session Django
# (cookie). Un rechargement ou une sortie de veille la retrouve (ETU-03).
IDENTITIES = "live_participants"
SAVED = "Réponse enregistrée"
CLEARED = "Réponse effacée"
TOO_LATE = "Temps écoulé : réponse non enregistrée"
RELEASE_CLOSED = "La session a démarré : plus aucun numéro ne peut être libéré."
SLOT_OVER = "Créneau terminé : aucun temps ajouté."


def _ms(seconds: float) -> int:
    return int(seconds * 1000)


def _page(state: State, *, board: bool) -> str:
    """Jeton de la page à afficher : il change quand le tableau change de groupe, ou quand le
    téléphone change de créneau."""
    if state.position is None:
        return state.phase
    slot = state.position.slot
    return f"running:{slot.group if board else slot.index}"


def _live_json(state: State, *, board: bool, **extra) -> JsonResponse:
    """État d'une page en direct : son jeton, le temps restant et le rang du créneau en cours
    (visé par « +10 s », car le tableau ne se recharge qu'au changement de groupe)."""
    position = state.position
    return JsonResponse(
        {
            "page": _page(state, board=board),
            "remaining_ms": _ms(position.remaining) if position else None,
            "slot": position.slot.index if position else None,
            **extra,
        }
    )


# --- Enseignant ---------------------------------------------------------------------------


@login_required
def session_list(request: HttpRequest) -> HttpResponse:
    now = timezone.now()
    # `content` et `roster` sont inutiles à la liste. La phase d'une session démarrée coûte une
    # petite requête (ses ajouts de temps) : acceptable sur cette page de l'enseignant.
    sessions = Session.objects.defer("content", "roster")
    rows = []
    for session in sessions:
        phase = session.state(now).phase
        rows.append((session, PHASE_LABELS[phase], phase == "ended"))
    return render(request, "live/session_list.html", {"rows": rows})


@login_required
def session_launch(request: HttpRequest) -> HttpResponse:
    form = LaunchSessionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        session = form.save()
        return redirect("board", code=session.code)
    return render(request, "live/session_launch.html", {"form": form})


def _connected(session: Session) -> list[str]:
    return list(session.participants.values_list("name", flat=True))


def _join_qr(url: str) -> str:
    """SES-05 : QR code qui ouvre cette adresse sur le téléphone (image SVG en data URI)."""
    return segno.make(url, micro=False).svg_data_uri(scale=1, border=4)


@login_required
def board(request: HttpRequest, code: str) -> HttpResponse:
    session = get_object_or_404(Session, code=code)
    state = session.state(timezone.now())
    context: dict = {"session": session, "state": state, "page": _page(state, board=True)}
    if state.phase == "waiting":
        join_url = settings.JOIN_URL or request.build_absolute_uri("/")  # CLA-01 : réseau local
        context |= {
            "join_url": join_url,
            "join_qr": _join_qr(urljoin(join_url, reverse("student-session", args=[code]))),
            "connected": _connected(session),
        }
    elif state.position is not None:
        group = session.schedule.groups[state.position.slot.group]
        context |= {  # DER-01 : les questions du groupe, avec leur couleur (1 à n)
            "cards": [
                {"color": color, "question": session.questions[index]}
                for color, index in enumerate(group, start=1)
            ],
            "remaining_ms": _ms(state.position.remaining),
        }
    return render(request, "live/board.html", context)


@login_required
def board_state(request: HttpRequest, code: str) -> JsonResponse:
    """État du tableau, interrogé chaque seconde par static/js/board.js."""
    session = get_object_or_404(Session.objects.defer("content", "roster"), code=code)
    state = session.state(timezone.now())
    if state.phase == "waiting":
        return _live_json(state, board=True, connected=_connected(session))
    return _live_json(state, board=True)


@login_required
@require_POST
def session_start(request: HttpRequest, code: str) -> HttpResponse:
    session = get_object_or_404(Session.objects.only("pk", "started_at"), code=code)
    if session.start(timezone.now()):
        messages.success(request, "Session démarrée.")
    return redirect("board", code=code)


@login_required
@require_POST
def session_add_time(request: HttpRequest, code: str) -> HttpResponse:
    """TPS-01 : +10 s au créneau affiché au tableau, s'il est toujours en cours."""
    session = get_object_or_404(Session.objects.defer("content", "roster"), code=code)
    if not session.add_time(request.POST.get("slot")):
        messages.error(request, SLOT_OVER)
    return redirect("board", code=code)


@login_required
def participants(request: HttpRequest, code: str) -> HttpResponse:
    """Connectés avec leur numéro (page non projetée) : libération avant le démarrage."""
    session = get_object_or_404(Session.objects.defer("content", "roster"), code=code)
    return render(
        request,
        "live/participants.html",
        {
            "session": session,
            "participants": session.participants.all(),
            "can_release": session.started_at is None,
            "release_closed": RELEASE_CLOSED,
        },
    )


@login_required
@require_POST
def participant_release(request: HttpRequest, code: str, pk: int) -> HttpResponse:
    """SES-04 : avant le démarrage, libérer un numéro pris (par erreur ou par usurpation)."""
    participant = get_object_or_404(Participant, pk=pk, session__code=code)
    # Suppression conditionnelle et atomique : rien ne part si « Démarrer » est passé entre-temps.
    released = Participant.objects.filter(pk=pk, session__started_at__isnull=True).delete()[0]
    if released:
        messages.success(request, f"Numéro {participant.number} libéré.")
    else:
        messages.error(request, RELEASE_CLOSED)
    return redirect("participants", code=code)


def _is_over(session: Session) -> bool:
    return session.state(timezone.now()).phase == "ended"


@login_required
def results(request: HttpRequest, code: str) -> HttpResponse:
    """RES-01 : notes de la session, sur une page non projetée, une fois la session terminée."""
    session = get_object_or_404(Session, code=code)
    over = _is_over(session)
    context: dict = {"session": session, "over": over}
    if over:
        context |= {
            "rows": session.results(),
            "maximum": decimal_fr(max_total(session.content)),
        }
    return render(request, "live/results.html", context)


@login_required
def results_csv(request: HttpRequest, code: str) -> HttpResponse:
    """RES-02 : export pour Excel en français (« ; », virgule décimale, UTF-8 avec BOM)."""
    session = get_object_or_404(Session, code=code)
    if not _is_over(session):
        raise Http404("Session non terminée")
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="resultats-{session.code}.csv"'
    response.write("\ufeff")
    csv.writer(response, delimiter=";").writerows(csv_rows(session.content, session.results()))
    return response


# --- Étudiant -----------------------------------------------------------------------------


def home(request: HttpRequest) -> HttpResponse:
    """Page d'accueil : l'étudiant saisit le code de session projeté au tableau."""
    form = JoinForm(request.GET if "code" in request.GET else None)
    if form.is_valid():
        return redirect("student-session", code=form.cleaned_data["code"])
    return render(request, "home.html", {"form": form})


def _identity(request: HttpRequest, session: Session) -> Participant | None:
    participant_id = request.session.get(IDENTITIES, {}).get(session.code)
    if participant_id is None:
        return None
    return session.participants.filter(pk=participant_id).first()


def student_session(request: HttpRequest, code: str) -> HttpResponse:
    session = get_object_or_404(Session, code=code)
    state = session.state(timezone.now())
    participant = _identity(request, session)
    context: dict = {
        "session": session,
        "state": state,
        "participant": participant,
        "page": _page(state, board=False),
        "follow": participant is not None and state.phase != "ended",
    }
    if participant is None and state.phase != "ended":
        form = IdentifyForm(request.POST or None, session=session)
        if request.method == "POST" and form.is_valid() and (participant := form.save()):
            request.session[IDENTITIES] = {
                **request.session.get(IDENTITIES, {}),
                session.code: participant.pk,
            }
            return redirect("student-session", code=code)
        context["form"] = form
    elif participant is not None and state.position is not None:
        # ETU-04, ETU-05 : couleur et propositions mélangées pour l'étudiant, jamais l'énoncé.
        slot = state.position.slot
        index, question = participant.question_at(slot)
        saved = participant.answers.filter(question=index).values_list("choices", flat=True)
        context |= {
            "slot": slot,
            "color": slot.color(participant.rank),
            "multiple": question["multiple"],
            "choices": [
                (i, question["choices"][i]["text"]) for i in participant.choice_order(index)
            ],
            "saved": saved.first() or [],
            "remaining_ms": _ms(state.position.remaining),
        }
    return render(request, "live/student.html", context)


def student_state(request: HttpRequest, code: str) -> JsonResponse:
    """Phase et créneau en cours, interrogés chaque seconde par static/js/phone.js."""
    session = get_object_or_404(Session.objects.defer("content", "roster"), code=code)
    return _live_json(session.state(timezone.now()), board=False)


@require_POST
def student_answer(request: HttpRequest, code: str) -> JsonResponse:
    """Enregistre la réponse au créneau en cours (ETU-07) ; refusée hors délai."""
    session = get_object_or_404(Session.objects.defer("roster"), code=code)
    participant = _identity(request, session)
    if participant is None:
        return JsonResponse({"message": "Identifiez-vous d'abord."}, status=403)
    position = session.state(timezone.now()).position
    if position is None or request.POST.get("slot") != str(position.slot.index):
        return JsonResponse({"message": TOO_LATE}, status=409)
    index, question = participant.question_at(position.slot)
    form = AnswerForm(request.POST, question=question)
    if not form.is_valid():
        return JsonResponse({"message": "Réponse invalide."}, status=400)
    if chosen := form.cleaned_data["choice"]:
        try:
            with transaction.atomic():
                Answer.objects.update_or_create(
                    participant=participant, question=index, defaults={"choices": chosen}
                )
        except IntegrityError:  # deux envois simultanés : la ligne vient d'être créée
            Answer.objects.filter(participant=participant, question=index).update(choices=chosen)
    else:  # tout décoché, ou « Effacer ma réponse » (ETU-09) : pas de réponse (v)
        Answer.objects.filter(participant=participant, question=index).delete()
        return JsonResponse({"message": CLEARED})
    return JsonResponse({"message": SAVED})
