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

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from config.join import join_url, qr_data_uri
from live.forms import AnswerForm, JoinForm, LaunchSessionForm
from live.models import PHASE_LABELS, Answer, Participant, Session, State
from live.results import csv_rows, decimal_fr, grade_20_text, max_total

# Identité des étudiants : {code de session: id du participant}, dans la session Django
# (cookie). Un rechargement ou une sortie de veille la retrouve (ETU-03).
IDENTITIES = "live_participants"
SAVED = "Réponse enregistrée"
CLEARED = "Réponse effacée"
TOO_LATE = "Temps écoulé : réponse non enregistrée"
IDENTIFY_FIRST = "Identifiez-vous d'abord."
# Espace insécable avant « : », pour que le deux-points ne commence pas une ligne.
TAKEN = (
    "Ce nom est déjà connecté sur un autre appareil\u00a0: si c'est le vôtre,"
    " prévenez l'enseignant."
)
RELEASE_CLOSED = "La session a démarré : plus aucun numéro ne peut être libéré."  # n° de liste
SLOT_OVER = "Créneau terminé : aucun temps ajouté."
SLOT_ALREADY_OVER = "Créneau terminé : rien n'est changé."  # TPS-02, clic après la fin


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
    """État d'une page en direct : son jeton, le temps restant, le rang du créneau en cours
    (visé par « +10 s », car le tableau ne se recharge qu'au changement de groupe) et sa durée.
    La barre du temps se recale ainsi sans recharger la page, sur un créneau allongé par
    « +10 s » comme, au tableau, sur le créneau suivant du même groupe (VIS-02, VIS-04)."""
    position = state.position
    data = {
        "page": _page(state, board=board),
        "remaining_ms": _ms(position.remaining) if position else None,
        "slot": position.slot.index if position else None,
        "slot_ms": _ms(position.length) if position else None,
    }
    return JsonResponse(data | extra)


def _position_label(group: list[int], total: int) -> str:
    """VIS-02 : place du groupe affiché dans le QCM. Pour les questions 5 à 8 sur 24, le libellé
    est « Questions 5 », tiret demi-cadratin, « 8 sur 24 » ; pour une seule question, il est
    « Question 5 sur 24 »."""
    first, last = group[0] + 1, group[-1] + 1
    if first == last:
        return f"Question {first} sur {total}"
    return f"Questions {first}\N{EN DASH}{last} sur {total}"


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


@login_required
def board(request: HttpRequest, code: str) -> HttpResponse:
    session = get_object_or_404(Session, code=code)
    state = session.state(timezone.now())
    context: dict = {"session": session, "state": state, "page": _page(state, board=True)}
    if state.phase == "waiting":
        url = join_url(request)  # CLA-01, CLA-02 : adresse du PC sur le réseau local
        context |= {
            "join_url": url,
            # SES-05 : QR code qui ouvre l'écran de la session sur le téléphone.
            "join_qr": qr_data_uri(urljoin(url, reverse("student-session", args=[code]))),
            "connected": _connected(session),
        }
    elif state.position is not None:
        group = session.schedule.groups[state.position.slot.group]
        # DER-01, AFF-01 : les énoncés du groupe et leur couleur, sans proposition ;
        # AFF-02 : la mention des questions à réponses multiples.
        questions = [session.questions[index] for index in group]
        answered, present = session.answered(state.position.slot)
        context |= {
            "answered": answered,  # DER-04
            "present": present,
            "cards": [
                {"color": color, "text": question["text"], "multiple": question["multiple"]}
                for color, question in enumerate(questions, start=1)
            ],
            "position_label": _position_label(group, session.n_questions),
            "remaining_ms": _ms(state.position.remaining),
            "slot_ms": _ms(state.position.length),
        }
    return render(request, "live/board.html", context)


@login_required
def board_state(request: HttpRequest, code: str) -> JsonResponse:
    """État du tableau, interrogé chaque seconde par static/js/board.js."""
    session = get_object_or_404(Session.objects.defer("content", "roster"), code=code)
    state = session.state(timezone.now())
    if state.phase == "waiting":
        return _live_json(state, board=True, connected=_connected(session))
    if state.position is not None:  # DER-04 : des nombres seulement, aucun texte (AFF-01)
        answered, present = session.answered(state.position.slot)
        return _live_json(state, board=True, answered=answered, present=present)
    return _live_json(state, board=True)


@login_required
@require_POST
def session_start(request: HttpRequest, code: str) -> HttpResponse:
    session = get_object_or_404(Session.objects.only("pk", "started_at"), code=code)
    session.start(timezone.now())  # déjà démarrée (double clic) : rien ne change
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
@require_POST
def session_end_slot(request: HttpRequest, code: str) -> HttpResponse:
    """TPS-02 : ramène à 5 s le créneau affiché au tableau, s'il est toujours en cours."""
    session = get_object_or_404(Session.objects.defer("content", "roster"), code=code)
    if not session.end_slot(request.POST.get("slot")):
        messages.error(request, SLOT_ALREADY_OVER)
    return redirect("board", code=code)


@login_required
def participants(request: HttpRequest, code: str) -> HttpResponse:
    """Connectés avec leur n° et leur numéro étudiant (page non projetée) : libération avant
    le démarrage."""
    session = get_object_or_404(Session.objects.defer("content", "roster"), code=code)
    return render(
        request,
        "live/participants.html",
        {
            "session": session,
            "participants": session.participants.order_by("list_number"),
            "can_release": session.started_at is None,
            "release_closed": RELEASE_CLOSED,
        },
    )


@login_required
@require_POST
def participant_release(request: HttpRequest, code: str, pk: int) -> HttpResponse:
    """SES-04 : avant le démarrage, libérer un nom pris (par erreur ou par usurpation)."""
    participant = get_object_or_404(Participant, pk=pk, session__code=code)
    # Suppression conditionnelle et atomique : rien ne part si « Démarrer » est passé entre-temps.
    released = Participant.objects.filter(pk=pk, session__started_at__isnull=True).delete()[0]
    if released:
        messages.success(
            request,
            f"N° {participant.list_number} libéré : {participant.name} peut de nouveau choisir"
            " son nom.",
        )
    else:
        messages.error(request, RELEASE_CLOSED)
    return redirect("participants", code=code)


def _is_over(session: Session) -> bool:
    return session.state(timezone.now()).phase == "ended"


@login_required
def results(request: HttpRequest, code: str) -> HttpResponse:
    """RES-01 : notes de la session, une fois la session terminée. L'écran du PC peut être
    dupliqué au projecteur : le tableau s'ouvre masqué (RES-04)."""
    session = get_object_or_404(Session, code=code)
    over = _is_over(session)
    context: dict = {"session": session, "over": over}
    if over:
        top = max_total(session.content)
        context |= {
            "rows": [(row, grade_20_text(row.total, top)) for row in session.results()],
            "maximum": decimal_fr(top),
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
        # ETU-13 : la liste du groupe figé, par n° ; un nom déjà pris ne se choisit pas.
        taken = set(session.participants.values_list("list_number", flat=True))
        context["students"] = [
            (s["list_number"], s["name"], s["list_number"] in taken) for s in session.students
        ]
    elif participant is not None and state.position is not None:
        # ETU-04, ETU-05 : couleur et propositions mélangées pour l'étudiant, jamais l'énoncé.
        slot = state.position.slot
        index, question = participant.question_at(slot)
        saved = participant.answers.filter(question=index).values_list("choices", flat=True)
        context |= {
            "slot": slot,
            "color": slot.color(participant.rank),
            "multiple": question["multiple"],
            "choices": [  # (indice canonique, texte, « Aucune… », ETU-12)
                (i, question["choices"][i]["text"], question["choices"][i]["none"])
                for i in participant.choice_order(index)
            ],
            "saved": saved.first() or [],
            "remaining_ms": _ms(state.position.remaining),
            "slot_ms": _ms(state.position.length),
            # Messages que le téléphone affiche aussi de lui-même (static/js/phone.js).
            "texts": {"saved": SAVED, "cleared": CLEARED, "too_late": TOO_LATE},
        }
    return render(request, "live/student.html", context)


def student_confirm(request: HttpRequest, code: str, list_number: int) -> HttpResponse:
    """ETU-13 : « Vous êtes … ? ». La confirmation identifie le téléphone ; un nom pris
    entre-temps est refusé, et la liste revient avec le message."""
    session = get_object_or_404(Session.objects.defer("content"), code=code)
    student = session.student(list_number)
    if student is None:
        raise Http404("Étudiant inconnu")
    if _identity(request, session) is not None or _is_over(session):
        return redirect("student-session", code=code)
    if session.participants.filter(list_number=list_number).exists():
        messages.error(request, TAKEN)  # nom pris : adresse saisie, liste périmée
        return redirect("student-session", code=code)
    if request.method == "POST":
        participant = session.enrol(student)
        if participant is None:
            messages.error(request, TAKEN)
        else:
            request.session[IDENTITIES] = {
                **request.session.get(IDENTITIES, {}),
                session.code: participant.pk,
            }
        return redirect("student-session", code=code)
    # La session Django existe avant « Oui, c'est moi » : l'identité s'y écrit côté serveur,
    # et un second envoi la retrouve même si la réponse au premier (son cookie) s'est perdue.
    request.session.setdefault(IDENTITIES, {})
    # Le n° et le nom seulement : le numéro étudiant n'atteint jamais le gabarit du téléphone.
    shown = {"list_number": student["list_number"], "name": student["name"]}
    return render(request, "live/student_confirm.html", {"session": session, "student": shown})


def student_state(request: HttpRequest, code: str) -> JsonResponse:
    """Phase et créneau en cours, interrogés chaque seconde par static/js/phone.js."""
    session = get_object_or_404(Session.objects.defer("content", "roster"), code=code)
    return _live_json(session.state(timezone.now()), board=False)


def student_answers(request: HttpRequest, code: str) -> JsonResponse:
    """ETU-10, FIN-02 : réponses enregistrées pour ce téléphone, par rang de créneau. Le
    téléphone les compare à la trace de ses envois : une réponse arrivée à temps compte comme
    transmise, même s'il n'en a pas vu la confirmation. Ni énoncé ni proposition (AFF-01) :
    seulement les indices des propositions choisies."""
    session = get_object_or_404(Session.objects.defer("content", "roster"), code=code)
    participant = _identity(request, session)
    if participant is None:
        return JsonResponse({"message": IDENTIFY_FIRST}, status=403)
    answers = participant.answers_by_slot()
    return JsonResponse({"answers": {str(slot): choices for slot, choices in answers.items()}})


@require_POST
def student_answer(request: HttpRequest, code: str) -> JsonResponse:
    """Enregistre la réponse au créneau en cours (ETU-07) ; refusée hors délai."""
    session = get_object_or_404(Session.objects.defer("roster"), code=code)
    participant = _identity(request, session)
    if participant is None:
        return JsonResponse({"message": IDENTIFY_FIRST}, status=403)
    position = session.state(timezone.now()).position
    if position is None or request.POST.get("slot") != str(position.slot.index):
        return JsonResponse({"message": TOO_LATE}, status=409)
    index, question = participant.question_at(position.slot)
    form = AnswerForm(request.POST, question=question)
    if not form.is_valid():
        return JsonResponse({"message": form.errors["choice"][0]}, status=400)
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
