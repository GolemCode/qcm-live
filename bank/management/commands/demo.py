"""`make demo` (DEM-02) : compte enseignant `demo`, groupe « Démo » et QCM de démonstration.

Relancée, la commande réutilise le groupe et le QCM, et tire un nouveau mot de passe : aucun
mot de passe fixe n'est écrit dans le dépôt.

`--sans-compte` (installation, INS-01) : le groupe et le QCM seulement, l'enseignant ayant
déjà son propre compte.
"""

from __future__ import annotations

import io
import secrets
import zipfile
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from bank.importer import import_quiz
from roster.csv_import import HEADER
from roster.forms import GroupImportForm
from roster.models import StudentGroup
from roster.years import academic_year

DEMO_DIR = Path(settings.BASE_DIR) / "demo"  # qcm-demo.txt et ses images (DEM-01)
USERNAME = "demo"
GROUP_NAME = "Démo"
# Fictifs, au format d'I14 (GRP-05) : n° de liste avec des trous, un numéro étudiant manquant.
STUDENTS = [
    (1, "10001", "BERNARD Alice"),
    (2, "10002", "DUPONT Basile"),
    (4, "10004", "LEROY Chloé"),
    (5, "", "MARTIN David"),
    (7, "10007", "PETIT Emma"),
    (8, "10008", "ROUX Félix"),
]


class Command(BaseCommand):
    help = "Prépare la démonstration : compte « demo », groupe « Démo » et QCM de démonstration."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--sans-compte",
            action="store_true",
            dest="no_account",
            help="ne pas créer le compte « demo »",
        )

    @transaction.atomic
    def handle(self, *args, **options) -> None:
        group = StudentGroup.objects.filter(name=GROUP_NAME).first() or self.import_group()
        # Relancée, elle complète le même QCM au lieu d'en créer un autre (IMP-10).
        quiz = import_quiz(demo_archive(), "qcm-demo.zip")

        self.stdout.write(f"QCM : {quiz.title} ({quiz.questions.count()} questions)")
        self.stdout.write(f"Groupe : {group.name} ({group.students.count()} étudiants)")
        if options["no_account"]:
            return
        write_account(self.stdout, demo_account())
        self.stdout.write("Nouveau mot de passe à chaque lancement de make demo.")

    def import_group(self) -> StudentGroup:
        lines = [f"{n};{number};{name}\n" for n, number, name in STUDENTS]
        content = "".join([";".join(HEADER) + "\n", *lines]).encode()
        upload = SimpleUploadedFile("demo.csv", content, content_type="text/csv")
        year = academic_year(timezone.localdate())  # GRP-04 : l'année en cours
        form = GroupImportForm({"name": GROUP_NAME, "year": year}, {"file": upload})
        if not form.is_valid():
            raise CommandError(f"Groupe de démonstration refusé : {form.errors.as_text()}")
        return form.save()


def demo_account() -> str:
    """Le compte `demo`, créé ou réactivé, avec un nouveau mot de passe, rendu."""
    password = secrets.token_urlsafe(12)
    user, _ = get_user_model().objects.get_or_create(username=USERNAME)
    user.set_password(password)
    user.is_active = True
    user.save()
    return password


def write_account(stdout, password: str) -> None:
    stdout.write(f"Identifiant : {USERNAME}")
    stdout.write(f"Mot de passe : {password}")


def folder_archive(folder: Path) -> bytes:
    """Un dossier en archive ZIP (IMP-08) : son fichier AMC-TXT et ses images."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(folder).as_posix())
    return buffer.getvalue()


def demo_archive() -> bytes:
    """Le dossier `demo/` en archive ZIP (IMP-08) : le fichier AMC-TXT et son image."""
    return folder_archive(DEMO_DIR)
