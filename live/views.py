"""Sessions en direct : le tableau de l'enseignant et l'écran des étudiants.

Une session passe par trois phases (Session.phase) : attente, déroulement, terminée. Le
créneau en cours se calcule à partir de l'heure de démarrage (live.schedule), sans tâche de
fond : chaque page et chaque état JSON le recalculent.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from live.forms import IdentifyForm, JoinForm, LaunchSessionForm
from live.models import Answer, Participant, Session
from live.schedule import Position

# Identité des étudiants : {code de session: id du participant}, dans la session Django
# (cookie). Un rechargement ou une sortie de veille la retrouve (ETU-03).
IDENTITIES = "live_participants"
SAVED = "Réponse enregistrée"
TOO_LATE = "Temps écoulé : réponse non enregistrée"


def _ms(seconds: float) -> int:
    return int(seconds * 1000)


# --- Enseignant ---------------------------------------------------------------------------


@login_required
def session_list(request: HttpRequest) -> HttpResponse:
    sessions = Session.objects.defer("content", "roster")  # inutiles à la liste
    return render(request, "live/session_list.html", {"sessions": sessions})


@login_required
def session_launch(request: HttpRequest) -> HttpResponse:
    form = LaunchSessionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        session = form.save()
        return redirect("board", code=session.code)
    return render(request, "live/session_launch.html", {"form": form})


def _connected(session: Session) -> list[str]:
    return list(session.participants.values_list("name", flat=True))


def _cards(session: Session, position: Position) -> list[dict]:
    """Questions du groupe en cours, avec leur couleur (1 à n) : DER-01."""
    group = session.schedule.groups[position.slot.group]
    return [
        {"color": color, "question": session.questions[index]}
        for color, index in enumerate(group, start=1)
    ]


@login_required
def board(request: HttpRequest, code: str) -> HttpResponse:
    session = get_object_or_404(Session, code=code)
    now = timezone.now()
    context = {"session": session, "phase": session.phase(now)}
    if context["phase"] == "waiting":
        context |= {"join_url": request.build_absolute_uri("/"), "connected": _connected(session)}
    elif (position := session.position(now)) is not None:
        context |= {
            "slot": position.slot,
            "cards": _cards(session, position),
            "remaining_ms": _ms(position.remaining),
        }
    return render(request, "live/board.html", context)


@login_required
def board_state(request: HttpRequest, code: str) -> JsonResponse:
    """État du tableau, interrogé chaque seconde par static/js/board.js."""
    session = get_object_or_404(Session.objects.defer("roster"), code=code)
    now = timezone.now()
    phase = session.phase(now)
    if phase == "waiting":
        return JsonResponse({"phase": phase, "connected": _connected(session)})
    position = session.position(now)
    if position is None:
        return JsonResponse({"phase": "ended"})
    return JsonResponse(
        {"phase": phase, "group": position.slot.group, "remaining_ms": _ms(position.remaining)}
    )


@login_required
@require_POST
def session_start(request: HttpRequest, code: str) -> HttpResponse:
    get_object_or_404(Session.objects.only("pk"), code=code)
    # Mise à jour conditionnelle et atomique : un double clic ne déplace pas l'heure de départ.
    if Session.objects.filter(code=code, started_at__isnull=True).update(started_at=timezone.now()):
        messages.success(request, "Session démarrée.")
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
        },
    )


@login_required
@require_POST
def participant_release(request: HttpRequest, code: str, pk: int) -> HttpResponse:
    """SES-04 : avant le démarrage, libérer un numéro pris (par erreur ou par usurpation)."""
    participant = get_object_or_404(
        Participant.objects.select_related("session"), pk=pk, session__code=code
    )
    if participant.session.started_at is not None:
        messages.error(request, "La session a démarré : plus aucun numéro ne peut être libéré.")
    else:
        participant.delete()
        messages.success(request, f"Numéro {participant.number} libéré.")
    return redirect("participants", code=code)


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


def _question_screen(session: Session, participant: Participant, position: Position) -> dict:
    """Ce que voit l'étudiant pendant un créneau (ETU-04, ETU-05) : couleur et propositions
    mélangées pour lui, jamais l'énoncé."""
    slot = position.slot
    index = session.schedule.question_for(slot, participant.rank)
    question = session.questions[index]
    saved = participant.answers.filter(question=index).values_list("choices", flat=True).first()
    return {
        "slot": slot,
        "color": session.schedule.color_for(slot, participant.rank),
        "multiple": question["multiple"],
        "choices": [(i, question["choices"][i]["text"]) for i in participant.choice_order(index)],
        "saved": saved or [],
        "remaining_ms": _ms(position.remaining),
    }


def student_session(request: HttpRequest, code: str) -> HttpResponse:
    session = get_object_or_404(Session, code=code)
    now = timezone.now()
    phase = session.phase(now)
    participant = _identity(request, session)
    context: dict = {"session": session, "participant": participant, "phase": phase}
    if participant is None and phase != "ended":
        form = IdentifyForm(request.POST or None, session=session)
        if request.method == "POST" and form.is_valid() and (participant := form.save()):
            request.session[IDENTITIES] = {
                **request.session.get(IDENTITIES, {}),
                session.code: participant.pk,
            }
            return redirect("student-session", code=code)
        context["form"] = form
    elif participant is not None and (position := session.position(now)) is not None:
        context |= _question_screen(session, participant, position)
    return render(request, "live/student.html", context)


def student_state(request: HttpRequest, code: str) -> JsonResponse:
    """Phase et créneau en cours, interrogés chaque seconde par static/js/phone.js."""
    session = get_object_or_404(Session.objects.defer("roster"), code=code)
    now = timezone.now()
    position = session.position(now)
    return JsonResponse(
        {
            "phase": session.phase(now),
            "slot": position.slot.index if position else None,
            "remaining_ms": _ms(position.remaining) if position else None,
        }
    )


@require_POST
def student_answer(request: HttpRequest, code: str) -> JsonResponse:
    """Enregistre la réponse au créneau en cours (ETU-07) ; refusée hors délai."""
    session = get_object_or_404(Session, code=code)
    participant = _identity(request, session)
    if participant is None:
        return JsonResponse({"message": "Identifiez-vous d'abord."}, status=403)
    position = session.position(timezone.now())
    if position is None or request.POST.get("slot") != str(position.slot.index):
        return JsonResponse({"message": TOO_LATE}, status=409)
    index = session.schedule.question_for(position.slot, participant.rank)
    question = session.questions[index]
    try:
        chosen = sorted({int(value) for value in request.POST.getlist("choice")})
    except ValueError:
        chosen = [-1]
    if any(not 0 <= c < len(question["choices"]) for c in chosen) or (
        not question["multiple"] and len(chosen) > 1
    ):
        return JsonResponse({"message": "Réponse invalide."}, status=400)
    if chosen:
        Answer.objects.update_or_create(
            participant=participant, question=index, defaults={"choices": chosen}
        )
    else:  # tout décoché : pas de réponse
        Answer.objects.filter(participant=participant, question=index).delete()
    return JsonResponse({"message": SAVED})
