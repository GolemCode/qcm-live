"""BAR-01 (I12) : la copie figée d'une session porte le barème de chaque question.

Avant I12, elle portait un barème par type de question (`scales`, b, m, v et le plancher p
des multiples). Chaque question figée reçoit l'équivalent (bank.migrations._legacy_scoring) : les
notes et la note maximale d'une session déjà lancée ne changent pas.
"""

from decimal import Decimal

from django.db import migrations

from bank.migrations._legacy_scoring import legacy_scoring


def freeze_scoring(content):
    scales = content.pop("scales")
    for question in content["questions"]:
        kind = "multiple" if question["multiple"] else "simple"
        scale = scales[kind]  # valeurs enregistrées en texte ; p vaut None pour une simple
        question["scoring"] = legacy_scoring(
            multiple=question["multiple"],
            n_choices=len(question["choices"]),
            b=Decimal(scale["b"]),
            m=Decimal(scale["m"]),
            v=Decimal(scale["v"]),
            p=Decimal(scale["p"]) if question["multiple"] and scale["p"] is not None else None,
        )
        question["ordered"] = False
        for choice in question["choices"]:
            choice["points"] = None
            choice["none"] = False
    return content


def forwards(apps, schema_editor):
    Session = apps.get_model("live", "Session")
    for session in Session.objects.all():
        if "scales" in session.content:
            session.content = freeze_scoring(session.content)
            session.save(update_fields=["content"])


class Migration(migrations.Migration):
    dependencies = [
        ("live", "0004_extension"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
