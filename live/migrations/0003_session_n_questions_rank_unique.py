"""Nombre de questions stocké à part (états interrogés chaque seconde) ; rangs uniques."""

from django.db import migrations, models


def fill(apps, schema_editor):
    Session = apps.get_model("live", "Session")
    Participant = apps.get_model("live", "Participant")
    for session in Session.objects.all():
        session.n_questions = len(session.content["questions"])
        session.save(update_fields=["n_questions"])
        # Anciennes sessions : rangs éventuellement en double, renumérotés dans l'ordre d'arrivée.
        participants = list(Participant.objects.filter(session=session).order_by("rank", "pk"))
        for rank, participant in enumerate(participants):
            participant.rank = rank + len(participants)
        Participant.objects.bulk_update(participants, ["rank"])
        for rank, participant in enumerate(participants):
            participant.rank = rank
        Participant.objects.bulk_update(participants, ["rank"])


class Migration(migrations.Migration):
    dependencies = [("live", "0002_participant_rank_answer")]

    operations = [
        migrations.AddField(
            model_name="session",
            name="n_questions",
            field=models.PositiveSmallIntegerField(default=0),
            preserve_default=False,
        ),
        migrations.RunPython(fill, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="participant",
            constraint=models.UniqueConstraint(
                fields=("session", "rank"), name="unique_participant_rank"
            ),
        ),
    ]
