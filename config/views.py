"""Vues transverses : espace enseignant, réseau et essai d'un téléphone (l'accueil des
étudiants est dans live.views)."""

from __future__ import annotations

from urllib.parse import urljoin, urlsplit

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET
from django.views.generic import TemplateView

from config import firewall, join
from config.classroom import GUIDE_URL
from live.models import Session

teacher_home = login_required(
    TemplateView.as_view(template_name="teacher/home.html", extra_context={"guide": GUIDE_URL})
)


def _board_url(code: str) -> str | None:
    """Tableau d'où vient l'enseignant, pour l'y renvoyer (session existante seulement)."""
    if code and Session.objects.filter(code=code).exists():
        return reverse("board", args=[code])
    return None


@login_required
def network(request: HttpRequest) -> HttpResponse:
    """CLA-02 à CLA-04 : adresse projetée, pare-feu et essai d'un téléphone."""
    code = request.POST.get("session") or request.GET.get("session") or ""
    board = _board_url(code)
    refused = False
    if request.method == "POST":
        if join.choose(request.POST.get("address", "")):
            return redirect(board or "network")
        refused = True  # adresse absente de la liste : forgée, ou d'un lancement précédent
    url = join.join_url(request)
    projected = urlsplit(url)
    token = join.new_trial()
    trial_url = urljoin(url, reverse("trial", args=[token]))
    context = {
        "join_url": url,
        "projected": projected.hostname or "",
        "addresses": join.addresses(),
        "refused": refused,
        "session_code": code if board else "",
        "board": board,
        "trial_url": trial_url,
        "trial_qr": join.qr_data_uri(trial_url),
        "trial_state_url": reverse("trial-state", args=[token]),
        "advices": firewall.advices(projected.port or int(request.get_port())),
    }
    return render(request, "teacher/network.html", context, status=400 if refused else 200)


@login_required
@require_GET
def trial_state(request: HttpRequest, token: str) -> JsonResponse:
    reached = join.trial_state(token)
    if reached is None:
        raise Http404
    return JsonResponse({"connected": reached})


@require_GET
def trial(request: HttpRequest, token: str) -> HttpResponse:
    """CLA-04 : un téléphone ouvre l'adresse d'essai ; un jeton inconnu ne mène nulle part."""
    if not join.trial_reached(token):
        raise Http404
    return render(request, "trial.html")
