"""Navigation de l'espace enseignant : rubriques du bandeau et rubrique en cours (VIS-05)."""

from __future__ import annotations

from django import template
from django.http import HttpRequest
from django.urls import reverse

register = template.Library()

# (libellé, adresse de la rubrique, préfixes des noms d'adresse qui en relèvent)
SECTIONS = (
    ("Accueil", "teacher-home", ()),
    ("Banque de questions", "question-list", ("question-",)),
    ("QCM", "quiz-list", ("quiz-",)),
    ("Groupes", "group-list", ("group-",)),
    ("Sessions", "session-list", ("session-", "board", "results", "participant")),
)


def section_of(url_name: str | None) -> str:
    """Rubrique d'une page, d'après le nom de son adresse ; l'accueil par défaut (réseau)."""
    for label, _, prefixes in SECTIONS:
        if url_name and url_name.startswith(prefixes):
            return label
    return SECTIONS[0][0]


@register.simple_tag
def teacher_sections(request: HttpRequest) -> list[tuple[str, str, bool]]:
    """(libellé, adresse, rubrique en cours ?) pour chaque rubrique du bandeau."""
    match = request.resolver_match
    current = section_of(match.url_name if match else None)
    return [(label, reverse(name), label == current) for label, name, _ in SECTIONS]
