"""Sessions en direct : le tableau de l'enseignant et l'écran des étudiants."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from live.forms import IdentifyForm, JoinForm, LaunchSessionForm
from live.models import Participant, Session

# Identité des étudiants : {code de session: id du participant}, dans la session Django
# (cookie). Un rechargement ou une sortie de veille la retrouve (ETU-03).
IDENTITIES = "live_participants"


# --- Enseignant ---------------------------------------------------------------------------


@login_required
def session_list(request: HttpRequest) -> HttpResponse:
    return render(request, "live/session_list.html", {"sessions": Session.objects.all()})


@login_required
def session_launch(request: HttpRequest) -> HttpResponse:
    form = LaunchSessionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        session = form.save()
        return redirect("board", code=session.code)
    return render(request, "live/session_launch.html", {"form": form})


def _connected(session: Session) -> list[str]:
    return list(session.participants.values_list("name", flat=True))


@login_required
def board(request: HttpRequest, code: str) -> HttpResponse:
    session = get_object_or_404(Session, code=code)
    return render(
        request,
        "live/board.html",
        {
            "session": session,
            "join_url": request.build_absolute_uri("/"),
            "connected": _connected(session),
        },
    )


@login_required
def board_state(request: HttpRequest, code: str) -> JsonResponse:
    """État du tableau, interrogé chaque seconde par static/js/board.js."""
    session = get_object_or_404(Session, code=code)
    return JsonResponse({"connected": _connected(session), "total": len(session.roster)})


@login_required
@require_POST
def session_start(request: HttpRequest, code: str) -> HttpResponse:
    session = get_object_or_404(Session, code=code)
    if session.started_at is None:
        session.started_at = timezone.now()
        session.save(update_fields=["started_at"])
        messages.success(request, "Session démarrée.")
    return redirect("board", code=code)


# --- Étudiant -----------------------------------------------------------------------------


def home(request: HttpRequest) -> HttpResponse:
    """Page d'accueil : l'étudiant saisit le code de session projeté au tableau."""
    form = JoinForm(request.GET or None)
    if form.is_valid():
        return redirect("student-session", code=form.cleaned_data["code"].code)
    return render(request, "home.html", {"form": form})


def _identity(request: HttpRequest, session: Session) -> Participant | None:
    participant_id = request.session.get(IDENTITIES, {}).get(session.code)
    if participant_id is None:
        return None
    return session.participants.filter(pk=participant_id).first()


def student_session(request: HttpRequest, code: str) -> HttpResponse:
    session = get_object_or_404(Session, code=code)
    participant = _identity(request, session)
    form = None
    if participant is None:
        form = IdentifyForm(request.POST or None, session=session)
        if request.method == "POST" and form.is_valid() and (participant := form.save()):
            request.session[IDENTITIES] = {
                **request.session.get(IDENTITIES, {}),
                session.code: participant.pk,
            }
            return redirect("student-session", code=code)
    return render(
        request,
        "live/student.html",
        {"session": session, "participant": participant, "form": form},
    )
