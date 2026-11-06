"""Groupes d'étudiants importés depuis un CSV (numéro, nom)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import models

from roster.csv_import import MAX_NAME_LENGTH

if TYPE_CHECKING:
    from django.db.models.fields.related_descriptors import RelatedManager


class StudentGroup(models.Model):
    name = models.CharField("nom du groupe", max_length=100, unique=True)

    if TYPE_CHECKING:
        students: RelatedManager[Student]

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Student(models.Model):
    """Un étudiant d'un groupe ; `position` garde l'ordre du fichier importé."""

    group = models.ForeignKey(StudentGroup, on_delete=models.CASCADE, related_name="students")
    number = models.CharField("numéro", max_length=20)
    name = models.CharField("nom", max_length=MAX_NAME_LENGTH)
    position = models.PositiveIntegerField()

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["group", "number"], name="unique_student_number"),
        ]

    def __str__(self) -> str:
        return f"{self.number} {self.name}"
