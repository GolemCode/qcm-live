"""Import d'un groupe : nom + fichier CSV, refusé en entier à la moindre ligne fautive."""

from __future__ import annotations

from django import forms
from django.db import transaction
from django.utils import timezone

from config.forms import TeacherForm
from roster.csv_import import MAX_BYTES, RosterError, parse_roster
from roster.models import Student, StudentGroup
from roster.years import YEAR_ERROR, academic_year, valid_year


class GroupImportForm(TeacherForm):
    # GRP-04. Sans longueur maximale : « 2025-2026-2027 » n'est pas tronqué en une année valide
    # par le navigateur (maxlength), il est refusé avec le message du format.
    year = forms.CharField(label="Année")
    file = forms.FileField(label="Fichier CSV")

    class Meta:
        model = StudentGroup
        fields = ["name", "year"]
        labels = {"name": "Nom du groupe"}

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # GRP-04 : l'année universitaire du jour de l'import, à corriger s'il le faut.
        self.fields["year"].initial = academic_year(timezone.localdate())

    def clean_year(self) -> str:
        year = self.cleaned_data["year"]
        if not valid_year(year):
            raise forms.ValidationError(YEAR_ERROR)
        return year

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
