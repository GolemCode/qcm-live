"""Mode classe : l'espace enseignant reste sur le PC de l'enseignant."""

from collections.abc import Callable
from ipaddress import ip_address

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

TEACHER_PREFIX = "/prof/"


def _is_local(remote: str) -> bool:
    try:
        return ip_address(remote).is_loopback
    except ValueError:
        return False


def teacher_local_only(get_response: Callable[[HttpRequest], HttpResponse]):
    """En mode classe, tout l'espace enseignant (connexion comprise) refuse une requête qui
    ne vient pas du PC lui-même : un étudiant sur le Wi-Fi de l'école ne peut ni essayer des
    mots de passe ni intercepter une connexion. Le serveur (waitress) n'est derrière aucun
    mandataire : REMOTE_ADDR est bien l'appareil qui envoie la requête."""

    def middleware(request: HttpRequest) -> HttpResponse:
        if (
            settings.TEACHER_LOCAL_ONLY
            and request.path.startswith(TEACHER_PREFIX)
            and not _is_local(request.META.get("REMOTE_ADDR", ""))
        ):
            return render(request, "teacher_local_only.html", status=403)
        return get_response(request)

    return middleware
