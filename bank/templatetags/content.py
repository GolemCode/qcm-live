"""Filtres de gabarit du contenu (CNT-01 à CNT-04) : le LaTeX léger d'un énoncé ou d'une
proposition en HTML de phrase (`span`, `code`, `strong`, `em`, `u`, `img`, `br`), pour rester
dans un titre ou un libellé. Tout texte est échappé ; les formules sont rendues par
`static/js/math.js`, leur code restant en texte si le script ne s'exécute pas."""

from __future__ import annotations

from django import template
from django.urls import reverse
from django.utils.html import escape, format_html
from django.utils.safestring import SafeString, mark_safe

from bank import content as parser
from bank.content import Break, Code, ContentError, Image, Math, Node, Style, Text

register = template.Library()


def _html(node: Node, preview: bool) -> str:
    match node:
        case Text(text):
            return escape(text)
        case Math(tex, display):
            mode = "true" if display else "false"
            return format_html(
                '<span class="math" data-tex="{}" data-display="{}">{}</span>', tex, mode, tex
            )
        case Code(text, block):
            return format_html(
                '<code class="code-block">{}</code>' if block else "<code>{}</code>", text
            )
        case Image(name) if preview:  # pas encore enregistrée : son nom seul
            return format_html('<span class="image-name">[{}]</span>', parser.image_alt(name))
        case Image(name):
            return format_html(
                '<img src="{}" alt="{}">', reverse("image", args=[name]), parser.image_alt(name)
            )
        case Style(tag, children):
            return f"<{tag}>{''.join(_html(child, preview) for child in children)}</{tag}>"
        case Break():
            return "<br>"


def _render(text: str, preview: bool) -> SafeString:
    try:
        nodes = parser.parse(text)
    except ContentError:  # jamais enregistré ainsi (formulaire) : montré tel quel
        return escape(text)
    return mark_safe("".join(_html(node, preview) for node in nodes))  # noqa: S308 (échappé ci-dessus)


@register.filter
def content(text: str) -> SafeString:
    return _render(text, preview=False)


@register.filter
def content_preview(text: str) -> SafeString:
    """Récapitulatif d'un import : les images, pas encore enregistrées, par leur nom."""
    return _render(text, preview=True)


@register.filter
def plain(text: str) -> str:
    """Pour un attribut (`aria-label`, `title`) : le texte sans balisage."""
    return parser.plain(text)
