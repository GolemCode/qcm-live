"""I17 : les énoncés et les propositions s'écrivent en LaTeX léger (CNT-01 à CNT-04). Un texte
d'avant I17 y est réécrit pour s'afficher à l'identique, et comme l'écrirait l'import d'AMC-TXT
(IMP-07 : la même question n'est pas dupliquée) : `\\` devient `\\textbackslash{}`, `$` devient
`\\$`, `{` et `}` deviennent `\\{` et `\\}`. Les copies figées des sessions (`live.snapshot`) le sont aussi.

Les réécritures sont écrites ici, sans appel à `bank.content` : une migration ne suit pas le
code qui évolue. Le retour en arrière défait ces réécritures, y compris dans un texte écrit après I17.
"""

import re

from django.db import migrations

FORWARD = {"\\": "\\textbackslash{}", "$": "\\$", "{": "\\{", "}": "\\}"}
BACKWARD = {value: key for key, value in FORWARD.items()}
FORWARD_RE = re.compile(r"[\\${}]")
BACKWARD_RE = re.compile(r"\\textbackslash\{\}|\\[${}]")


def _forward(text: str) -> str:
    return FORWARD_RE.sub(lambda match: FORWARD[match.group()], text)


def _backward(text: str) -> str:
    return BACKWARD_RE.sub(lambda match: BACKWARD[match.group()], text)


def _rewrite(apps, convert) -> None:
    for model in ("Question", "Choice"):
        for row in apps.get_model("bank", model).objects.filter(text__regex=r"[\\${}]"):
            row.text = convert(row.text)
            row.save(update_fields=["text"])
    for session in apps.get_model("live", "Session").objects.all():
        for question in session.content["questions"]:
            question["text"] = convert(question["text"])
            for choice in question["choices"]:
                choice["text"] = convert(choice["text"])
        session.save(update_fields=["content"])


def forward(apps, schema_editor) -> None:
    _rewrite(apps, _forward)


def backward(apps, schema_editor) -> None:
    _rewrite(apps, _backward)


class Migration(migrations.Migration):
    dependencies = [
        ("bank", "0006_image"),
        ("live", "0008_extension_seconds_session_group_year"),
    ]

    operations = [migrations.RunPython(forward, backward)]
