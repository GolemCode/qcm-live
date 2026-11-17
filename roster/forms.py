"""Import d'un groupe : nom + fichier CSV, refusé en entier à la moindre ligne fautive."""

from __future__ import annotations

from django import forms
from django.db import transaction
from django.utils import timezone

from config.forms import TeacherForm
from roster.csv_import import MAX_BYTES, RosterError, parse_roster
from roster.models import Student, StudentGroup, validate_year
from roster.years import academic_year


class GroupImportForm(TeacherForm):
    # GRP-04. Sans longueur maximale : « 2025-2026-2027 » n'est pas tronqué en une année valide
    # par le navigateur (maxlength), il est refusé avec le message du format.
    # Validé ici plutôt que par le modèle : un seul message, sans celui de la longueur.
    year = forms.CharField(label="Année", validators=[validate_year])
    file = forms.FileField(label="Fichier CSV")

    class Meta:
        model = StudentGroup
        fields = ["name", "year"]
        labels = {"name": "Nom du groupe"}

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # GRP-04 : l'année universitaire du jour de l'import, à corriger s'il le faut.
        self.fields["year"].initial = academic_year(timezone.localdate())

    def clean_file(self):
        """Le fichier validé devient un Roster (lecture bornée à MAX_BYTES + 1 octets)."""
        try:
            return parse_roster(self.cleaned_data["file"].read(MAX_BYTES + 1))
        except RosterError as error:
            raise forms.ValidationError(error.messages) from None

    @transaction.atomic
    def save(self, commit: bool = True) -> StudentGroup:
        group = super().save(commit=commit)
        if commit:
            Student.objects.bulk_create(
                Student(
                    group=group,
                    list_number=entry.list_number,
                    student_number=entry.student_number,
                    name=entry.name,
                )
                for entry in self.cleaned_data["file"].entries
            )
        return group
