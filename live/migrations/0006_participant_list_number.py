"""I14 (MIG-01, ETU-13) : l'étudiant d'une session est désigné par son n° de liste.

La liste figée d'une session d'avant I14 (numéro, nom, dans l'ordre du fichier) reçoit le n°
de liste que la migration roster.0002 donne au groupe : le rang dans le fichier. Chaque
participant le reçoit par son ancien numéro, unique dans la session. Réponses et rangs de
rotation ne changent pas : les notes non plus.
"""

from django.db import migrations, models


def number_roster(apps, schema_editor):
    Session = apps.get_model("live", "Session")
    Participant = apps.get_model("live", "Participant")
    for session in Session.objects.all():
        if session.roster and "list_number" in session.roster[0]:
            continue
        session.roster = [
            {"list_number": rank, "student_number": s["number"], "name": s["name"]}
            for rank, s in enumerate(session.roster, start=1)
        ]
        session.save(update_fields=["roster"])
        by_number = {s["student_number"]: s["list_number"] for s in session.roster}
        for participant in Participant.objects.filter(session=session):
            participant.list_number = by_number[participant.student_number]
            participant.save(update_fields=["list_number"])


def unnumber_roster(apps, schema_editor):
    """Retour à l'état d'avant I14 : la liste figée reprend l'ordre des n°."""
    Session = apps.get_model("live", "Session")
    for session in Session.objects.all():
        students = sorted(session.roster, key=lambda s: s["list_number"])
        session.roster = [{"number": s["student_number"], "name": s["name"]} for s in students]
        session.save(update_fields=["roster"])


class Migration(migrations.Migration):
    dependencies = [
        ("live", "0005_frozen_question_scoring"),
        ("roster", "0002_student_list_number"),
    ]

    operations = [
        migrations.RemoveConstraint(model_name="participant", name="unique_participant_number"),
        migrations.RenameField(model_name="participant", old_name="number", new_name="student_number"),
        migrations.AlterField(
            model_name="participant",
            name="student_number",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="participant",
            name="list_number",
            field=models.PositiveSmallIntegerField(null=True),
        ),
        migrations.RunPython(number_roster, unnumber_roster),
        migrations.AlterField(
            model_name="participant",
            name="list_number",
            field=models.PositiveSmallIntegerField(),
        ),
        migrations.AddConstraint(
            model_name="participant",
            constraint=models.UniqueConstraint(
                fields=("session", "list_number"), name="unique_participant_list_number"
            ),
        ),
    ]
