"""I16 (GRP-04, MIG-02) : chaque groupe reçoit une année universitaire, celle de la première
session lancée avec son nom, sinon celle en cours ; le nom n'est plus unique que dans une
année."""

from django.db import migrations, models
from django.utils import timezone

import roster.models


def academic_year(day):
    """Copie de roster.years.academic_year à la date d'I16 : une migration ne suit pas le code."""
    first = day.year if day.month >= 9 else day.year - 1
    return f"{first}-{first + 1}"


def year_from_sessions(apps, schema_editor):
    StudentGroup = apps.get_model("roster", "StudentGroup")
    Session = apps.get_model("live", "Session")
    current = academic_year(timezone.localdate())
    for group in StudentGroup.objects.all():
        launches = Session.objects.filter(group_name=group.name).only("created_at")
        first = launches.order_by("created_at").first()  # sans les QCM figés (JSON)
        launched = timezone.localdate(first.created_at) if first else None
        group.year = academic_year(launched) if launched else current
        group.save(update_fields=["year"])


class Migration(migrations.Migration):
    dependencies = [
        ("live", "0007_session_source_questions"),
        ("roster", "0002_student_list_number"),
    ]

    operations = [
        migrations.AddField(
            model_name="studentgroup",
            name="year",
            field=models.CharField(default="", max_length=9, verbose_name="année"),
            preserve_default=False,
        ),
        migrations.RunPython(year_from_sessions, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="studentgroup",
            name="year",
            field=models.CharField(
                max_length=9,
                validators=[roster.models.validate_year],
                verbose_name="année",
            ),
        ),
        migrations.AlterField(
            model_name="studentgroup",
            name="name",
            field=models.CharField(max_length=100, verbose_name="nom du groupe"),
        ),
        migrations.AlterModelOptions(
            name="studentgroup",
            options={"ordering": ["name", "-year"]},
        ),
        migrations.AddConstraint(
            model_name="studentgroup",
            constraint=models.UniqueConstraint(
                fields=("name", "year"),
                name="unique_group_name_year",
                violation_error_message="Un groupe porte déjà ce nom cette année-là.",
            ),
        ),
    ]
