"""`make demo` (DEM-02) : compte enseignant `demo`, groupe « Démo » et QCM de démonstration.

Relancée, la commande réutilise le groupe et le QCM, et tire un nouveau mot de passe : aucun
mot de passe fixe n'est écrit dans le dépôt.

`--sans-compte` (installation, INS-01) : le groupe et le QCM seulement, l'enseignant ayant
déjà son propre compte.
"""

from __future__ import annotations

import secrets
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from bank.importer import AlreadyImported, import_quiz
from roster.forms import GroupImportForm
from roster.models import StudentGroup

DEMO_FILE = Path(settings.BASE_DIR) / "demo" / "qcm-demo.txt"
USERNAME = "demo"
GROUP_NAME = "Démo"
STUDENTS = [  # fictifs
    ("10001", "BERNARD Alice"),
    ("10002", "DUPONT Basile"),
    ("10003", "LEROY Chloé"),
    ("10004", "MARTIN David"),
    ("10005", "PETIT Emma"),
    ("10006", "ROUX Félix"),
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
        try:
            quiz = import_quiz(DEMO_FILE.read_bytes(), DEMO_FILE.name)
        except AlreadyImported as already:
            quiz = already.quiz

        self.stdout.write(f"QCM : {quiz.title} ({quiz.questions.count()} questions)")
        self.stdout.write(f"Groupe : {group.name} ({group.students.count()} étudiants)")
        if options["no_account"]:
            return
        password = secrets.token_urlsafe(12)
        user, _ = get_user_model().objects.get_or_create(username=USERNAME)
        user.set_password(password)
        user.is_active = True
        user.save()
        self.stdout.write(f"Identifiant : {USERNAME}")
        self.stdout.write(f"Mot de passe : {password}")
        self.stdout.write("Nouveau mot de passe à chaque lancement de make demo.")

    def import_group(self) -> StudentGroup:
        content = "".join(f"{number};{name}\n" for number, name in STUDENTS).encode()
        upload = SimpleUploadedFile("demo.csv", content, content_type="text/csv")
        form = GroupImportForm({"name": GROUP_NAME}, {"file": upload})
        if not form.is_valid():
            raise CommandError(f"Groupe de démonstration refusé : {form.errors.as_text()}")
        return form.save()
