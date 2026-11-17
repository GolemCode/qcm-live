"""Lien des sessions vers les questions de la banque copiées au lancement (VER-01).

Une session lancée avant I15 n'a que sa copie figée : elle est rattachée aux questions de la
banque dont le contenu est encore celui de la copie (énoncé, type, barème, options,
propositions dans l'ordre). Une question modifiée depuis n'est pas rattachée : elle n'a jamais
servi sous sa forme actuelle.
"""

from decimal import Decimal

from django.db import migrations, models


def frozen_key(frozen):
    choices = tuple(
        (c["text"], c["correct"], None if c["points"] is None else Decimal(c["points"]))
        for c in frozen["choices"]
        if not c["none"]
    )
    has_none = any(c["none"] for c in frozen["choices"])
    return (
        frozen["text"],
        frozen["multiple"],
        frozen["ordered"],
        frozen["scoring"],
        has_none,
        choices,
    )


def bank_key(question):
    choices = tuple(
        (c.text, c.correct, c.points)
        for c in sorted(question.choices.all(), key=lambda c: c.position)
    )
    multiple = question.kind == "multiple"
    return (
        question.text,
        multiple,
        question.ordered,
        question.scoring,
        question.none_of_these,
        choices,
    )


def link_old_sessions(apps, schema_editor):
    Session = apps.get_model("live", "Session")
    Question = apps.get_model("bank", "Question")
    for session in Session.objects.all():
        frozen = session.content["questions"]
        keys = {frozen_key(question) for question in frozen}
        texts = {question["text"] for question in frozen}
        candidates = Question.objects.filter(text__in=texts).prefetch_related("choices")
        session.source_questions.set(q for q in candidates if bank_key(q) in keys)


class Migration(migrations.Migration):
    dependencies = [
        ("bank", "0004_question_versions_origins"),
        ("live", "0006_participant_list_number"),
    ]

    operations = [
        migrations.AddField(
            model_name="session",
            name="source_questions",
            field=models.ManyToManyField(blank=True, related_name="sessions", to="bank.question"),
        ),
        migrations.RunPython(link_old_sessions, migrations.RunPython.noop),
    ]
