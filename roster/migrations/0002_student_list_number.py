"""I14 (GRP-05, MIG-01) : chaque étudiant reçoit un n° de liste, son rang dans le fichier
importé ; son numéro devient le numéro étudiant, facultatif."""

from django.db import migrations, models


def number_by_rank(apps, schema_editor):
    Student = apps.get_model("roster", "Student")
    students = Student.objects.order_by("group_id", "position", "pk")
    group, rank = None, 0
    for student in students:
        rank = rank + 1 if student.group_id == group else 1
        group = student.group_id
        student.list_number = rank
        student.save(update_fields=["list_number"])


def position_from_number(apps, schema_editor):
    Student = apps.get_model("roster", "Student")
    Student.objects.update(position=models.F("list_number") - 1)


class Migration(migrations.Migration):
    dependencies = [("roster", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="student",
            name="list_number",
            field=models.PositiveSmallIntegerField(null=True, verbose_name="n°"),
        ),
        migrations.RunPython(number_by_rank, position_from_number),
        migrations.AlterField(
            model_name="student",
            name="list_number",
            field=models.PositiveSmallIntegerField(verbose_name="n°"),
        ),
        migrations.AlterField(  # l'ancien rang reste, pour une migration à rebours
            model_name="student",
            name="position",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.RemoveConstraint(model_name="student", name="unique_student_number"),
        migrations.RenameField(model_name="student", old_name="number", new_name="student_number"),
        migrations.AlterField(
            model_name="student",
            name="student_number",
            field=models.CharField(blank=True, max_length=20, verbose_name="numéro étudiant"),
        ),
        migrations.RemoveField(model_name="student", name="position"),
        migrations.AlterModelOptions(name="student", options={"ordering": ["list_number"]}),
        migrations.AddConstraint(
            model_name="student",
            constraint=models.UniqueConstraint(
                fields=("group", "list_number"), name="unique_list_number"
            ),
        ),
        migrations.AddConstraint(
            model_name="student",
            constraint=models.UniqueConstraint(
                condition=models.Q(("student_number", ""), _negated=True),
                fields=("group", "student_number"),
                name="unique_student_number",
            ),
        ),
    ]
