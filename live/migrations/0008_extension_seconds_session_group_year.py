"""I16 : temps signé par clic (TPS-02 : un retrait est négatif ; les clics d'avant valent
+10 s) et année figée du groupe ; une session d'avant I16 reçoit l'année universitaire de son
lancement (MIG-02)."""

from django.db import migrations, models
from django.utils import timezone


def academic_year(day):
    """Copie de roster.years.academic_year à la date d'I16 : une migration ne suit pas le code."""
    first = day.year if day.month >= 9 else day.year - 1
    return f"{first}-{first + 1}"


def year_of_launch(apps, schema_editor):
    Session = apps.get_model("live", "Session")
    sessions = list(Session.objects.only("pk", "created_at"))  # sans les QCM figés (JSON)
    for session in sessions:
        session.group_year = academic_year(timezone.localdate(session.created_at))
    Session.objects.bulk_update(sessions, ["group_year"])


class Migration(migrations.Migration):
    dependencies = [
        ("live", "0007_session_source_questions"),
    ]

    operations = [
        migrations.AddField(
            model_name="extension",
            name="seconds",
            field=models.SmallIntegerField(default=10),
        ),
        migrations.AddField(
            model_name="session",
            name="group_year",
            field=models.CharField(default="", max_length=9),
            preserve_default=False,
        ),
        migrations.RunPython(year_of_launch, migrations.RunPython.noop),
    ]
