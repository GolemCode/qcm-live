"""Import d'un groupe : nom + fichier CSV, refusé en entier à la moindre ligne fautive."""

from __future__ import annotations

from django import forms
from django.db import transaction

from config.forms import TeacherForm
from roster.csv_import import MAX_BYTES, RosterError, parse_roster
from roster.models import Student, StudentGroup


class GroupImportForm(TeacherForm):
    file = forms.FileField(label="Fichier CSV")

    class Meta:
        model = StudentGroup
        fields = ["name"]
        labels = {"name": "Nom du groupe"}

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
                Student(group=group, number=entry.number, name=entry.name, position=position)
                for position, entry in enumerate(self.cleaned_data["file"].entries)
            )
        return group
