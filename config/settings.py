"""Réglages Django, lus depuis l'environnement.

Aucun secret n'est écrit ici : `DJANGO_SECRET_KEY` vient de l'environnement
(fichier `.env` local généré par `make setup`, jamais versionné).
"""

import os
from pathlib import Path
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured
from django.utils.csp import CSP

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str) -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY est absent : lancez `make setup` (ou "
        "`uv run --no-project python scripts/gen_env.py`) puis utilisez `uv run --env-file .env …`."
    )

DEBUG = env_bool("DJANGO_DEBUG")
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

# Adresse que les téléphones ouvrent, projetée au tableau (SES-01). Le mode classe
# (config/classroom.py) y met celle du PC sur le réseau local ; à défaut, le tableau
# affiche l'adresse par laquelle il a lui-même été ouvert. Son hôte est toujours accepté.
JOIN_URL = os.environ.get("QCM_JOIN_URL", "")
if join_host := urlsplit(JOIN_URL).hostname:
    ALLOWED_HOSTS.append(join_host)
# Mode classe : l'application est ouverte au réseau de l'école, mais l'espace enseignant
# (connexion, notes, pilotage) ne répond qu'au PC lui-même (config/middleware.py).
TEACHER_LOCAL_ONLY = env_bool("QCM_TEACHER_LOCAL_ONLY")

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "bank",
    "roster",
    "live",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Fichiers statiques servis par l'application elle-même, hors mode debug (mode classe).
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
    "config.middleware.teacher_local_only",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        # Changer de base sert aux tests du mode classe, lancé dans un autre processus.
        "NAME": os.environ.get("DJANGO_DB_PATH") or BASE_DIR / "db.sqlite3",
        # Base de test dans un fichier, pas en mémoire : en mémoire partagée, SQLite refuse
        # aussitôt (« table is locked ») un accès concurrent entre le test et le serveur de
        # test, au lieu d'attendre. En fichier, il attend la fin de l'écriture, comme en usage.
        "TEST": {"NAME": BASE_DIR / ".test-db.sqlite3"},
        # Toute une classe écrit au même instant (CLA-01). Une transaction ordinaire lit
        # d'abord, puis demande le verrou d'écriture : si une autre écrit déjà, SQLite
        # refuse aussitôt (« database is locked »). IMMEDIATE prend le verrou dès le début,
        # et les suivantes attendent leur tour (jusqu'à `timeout` secondes).
        "OPTIONS": {"transaction_mode": "IMMEDIATE", "timeout": 20},
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "teacher-home"
LOGOUT_REDIRECT_URL = "home"

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
# whitenoise sert les fichiers là où ils sont, sans étape `collectstatic` : une poignée de
# fichiers, lus une fois au démarrage.
WHITENOISE_USE_FINDERS = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Politique de sécurité du contenu stricte : aucun script ni style inline.
SECURE_CSP = {
    "default-src": [CSP.SELF],
    "img-src": [CSP.SELF, "data:"],
    "object-src": [CSP.NONE],
    "base-uri": [CSP.NONE],
    "form-action": [CSP.SELF],
    "frame-ancestors": [CSP.NONE],
}

# Hors mode debug, Django ne montre pas les erreurs des requêtes : en mode classe, elles
# s'affichent dans le terminal. Les alertes de file d'attente de waitress, normales quand
# toute la classe envoie au même instant, n'y figurent pas.
if not DEBUG:
    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "handlers": {"console": {"class": "logging.StreamHandler"}},
        "loggers": {
            "django.request": {"handlers": ["console"], "level": "ERROR"},
            "waitress.queue": {"level": "ERROR"},
        },
    }
