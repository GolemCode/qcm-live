"""Groupes d'étudiants importés depuis un CSV (n°, numéro étudiant, nom : GRP-05)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.core.exceptions import ValidationError
from django.db import models

from roster.csv_import import MAX_NAME_LENGTH, MAX_STUDENT_NUMBER_LENGTH
from roster.years import YEAR_ERROR, YEAR_LENGTH, group_label, valid_year

if TYPE_CHECKING:
    from django.db.models.fields.related_descriptors import RelatedManager


GROUP_NAME_MAX_LENGTH = 100
SAME_YEAR = "Un groupe porte déjà ce nom cette année-là."


def validate_year(value: str) -> None:
    if not valid_year(value):
        raise ValidationError(YEAR_ERROR)


class StudentGroup(models.Model):
    """Un groupe d'une année universitaire : le même nom peut revenir une autre année (GRP-04)."""

    name = models.CharField("nom du groupe", max_length=GROUP_NAME_MAX_LENGTH)
    year = models.CharField("année", max_length=YEAR_LENGTH, validators=[validate_year])

    if TYPE_CHECKING:
        students: RelatedManager[Student]

    class Meta:
        ordering = ["name", "-year"]  # homonymes : l'année la plus récente d'abord
        constraints = [
            models.UniqueConstraint(
                fields=["name", "year"],
                name="unique_group_name_year",
                violation_error_message=SAME_YEAR,
            )
        ]

    def __str__(self) -> str:
        return group_label(self.name, self.year)  # GRP-04 : au choix du groupe, au lancement


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
