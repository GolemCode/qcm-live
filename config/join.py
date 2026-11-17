"""Adresse que les téléphones ouvrent (SES-01, CLA-02) et essai d'un téléphone (CLA-04).

L'adresse projetée est, dans l'ordre :
1. celle que l'enseignant a choisie parmi les adresses du PC (page « Réseau et téléphones »),
   gardée en mémoire jusqu'à l'arrêt de l'application ;
2. celle du mode classe (`JOIN_URL`, la plus probable des adresses du PC, ou `--adresse`) ;
3. à défaut, l'adresse par laquelle la page a été ouverte.

Le choix vit dans le cache de Django, en mémoire du processus : le mode classe n'en a qu'un
(waitress, plusieurs fils). Il ne survit pas à un redémarrage, et n'accepte qu'une adresse
trouvée au démarrage (`LAN_ADDRESSES`), donc déjà acceptée par `ALLOWED_HOSTS`.
"""

from __future__ import annotations

import secrets
from urllib.parse import urlsplit, urlunsplit

import segno
from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest

CHOICE_KEY = "qcm-live:join-host"
TRIAL_PREFIX = "qcm-live:trial:"
TRIAL_S = 3600


def offered() -> set[str]:
    return {item["address"] for item in addresses()}


def addresses() -> list[dict]:
    """Adresses proposées à l'enseignant : celles du PC, plus l'adresse imposée au lancement
    (`--adresse`) si elle n'en fait pas partie."""
    found = list(settings.LAN_ADDRESSES)
    host = urlsplit(settings.JOIN_URL).hostname
    if host and host not in {item["address"] for item in found}:
        found.insert(0, {"address": host, "interface": "choisie au lancement", "virtual": False})
    return found


def choose(address: str) -> bool:
    """Projette `address`, si c'est l'une des adresses proposées."""
    if address not in offered():
        return False
    cache.set(CHOICE_KEY, address, timeout=None)
    return True


def with_host(url: str, host: str) -> str:
    parts = urlsplit(url)
    netloc = f"{host}:{parts.port}" if parts.port else host
    return urlunsplit((parts.scheme, netloc, parts.path, "", ""))


def join_url(request: HttpRequest) -> str:
    """Adresse projetée, avec « / » final."""
    base = settings.JOIN_URL or request.build_absolute_uri("/")
    chosen = cache.get(CHOICE_KEY)
    if chosen and chosen in offered():
        return with_host(base, chosen)
    return base


def qr_data_uri(url: str) -> str:
    """QR code de `url`, en image intégrée à la page (CSP : `img-src data:`)."""
    return segno.make_qr(url).svg_data_uri(omitsize=True)


def new_trial() -> str:
    """Jeton d'un essai de téléphone : imprévisible, valable une heure."""
    token = secrets.token_urlsafe(16)
    cache.set(TRIAL_PREFIX + token, False, timeout=TRIAL_S)
    return token


def trial_state(token: str) -> bool | None:
    """None : jeton inconnu ou expiré ; sinon, un téléphone l'a-t-il ouvert ?"""
    return cache.get(TRIAL_PREFIX + token)


def trial_reached(token: str) -> bool:
    """Un téléphone ouvre l'adresse d'essai. False si le jeton est inconnu."""
    if trial_state(token) is None:
        return False
    cache.set(TRIAL_PREFIX + token, True, timeout=TRIAL_S)
    return True
