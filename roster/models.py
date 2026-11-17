"""Groupes d'étudiants importés depuis un CSV (n°, numéro étudiant, nom : GRP-05)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import models

from roster.csv_import import MAX_NAME_LENGTH, MAX_STUDENT_NUMBER_LENGTH

if TYPE_CHECKING:
    from django.db.models.fields.related_descriptors import RelatedManager


GROUP_NAME_MAX_LENGTH = 100


class StudentGroup(models.Model):
    name = models.CharField("nom du groupe", max_length=GROUP_NAME_MAX_LENGTH, unique=True)

    if TYPE_CHECKING:
        students: RelatedManager[Student]

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Student(models.Model):
    """Un étudiant d'un groupe, désigné par son n° de liste (GRP-05)."""

    group = models.ForeignKey(StudentGroup, on_delete=models.CASCADE, related_name="students")
    list_number = models.PositiveSmallIntegerField("n°")
    student_number = models.CharField(
        "numéro étudiant", max_length=MAX_STUDENT_NUMBER_LENGTH, blank=True
    )
    name = models.CharField("nom", max_length=MAX_NAME_LENGTH)

    class Meta:
        ordering = ["list_number"]
        constraints = [
            models.UniqueConstraint(fields=["group", "list_number"], name="unique_list_number"),
            models.UniqueConstraint(
                fields=["group", "student_number"],
                condition=~models.Q(student_number=""),
                name="unique_student_number",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.list_number} {self.name}"
