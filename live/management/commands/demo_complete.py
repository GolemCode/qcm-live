"""Démonstration complète (DEM-03 à DEM-07), préparée sur une base vide par `qcm-live demo`.

Tout passe par les formulaires et les fonctions de l'application, comme si l'enseignant
l'avait fait : import des trois fichiers de `demo-complet/` (DEM-04), deux groupes « L1
Sciences » (DEM-05), une session passée avec des réponses (DEM-06), un QCM composé et une
nouvelle version de question (DEM-07). Les réponses sont tirées avec une graine fixe : les
mêmes résultats à chaque lancement. Seuls l'heure de la session passée et le mot de passe
changent.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from itertools import product
from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.datastructures import MultiValueDict

from bank.forms import QuestionForm, QuizForm
from bank.importer import import_quiz
from bank.management.commands.demo import demo_account, folder_archive, write_account
from bank.models import Question, Quiz
from live.forms import AnswerForm, LaunchSessionForm
from live.models import Answer, Participant, Session
from live.results import none_index
from live.snapshot import FrozenQuestion
from roster.csv_import import HEADER
from roster.forms import GroupImportForm
from roster.models import StudentGroup
from roster.years import academic_year

# À part de demo/, que l'enseignant peut mettre en ZIP tel quel (DEM-01).
COMPLETE_DIR = Path(settings.BASE_DIR) / "demo-complet"
FILES = ("fonctions", "probabilites", "python")
GROUP_NAME = "L1 Sciences"
GROUP_SIZE, PREVIOUS_SIZE = 70, 24
COMPOSED = "Mathématiques : révisions"
COMPOSED_PER_FILE = 8  # premières questions hors groupe AMC de chaque fichier de mathématiques
SEED = 2026
ABSENT = 6
DAYS_AGO = 7
SHOWN, SECONDS = 1, 45
# La question posée lors de la session passée puis reformulée (DEM-07).
REVISED = "Quelle est la dérivée de $f(x) = x^3$ ?"
REVISION = "Soit $f(x) = x^3$. Que vaut sa dérivée $f'(x)$ ?"
# Noms fictifs, combinés deux à deux.
LAST_NAMES = (
    "ARNAUD",
    "BLANC",
    "BRUN",
    "CARON",
    "CHEVALIER",
    "COLIN",
    "DAVID",
    "DUBOIS",
    "FAURE",
    "FONTAINE",
    "GARNIER",
    "GIRARD",
    "GUERIN",
    "HENRY",
    "LAMBERT",
    "LEFEBVRE",
    "MARCHAND",
    "MERCIER",
    "MOREL",
    "NOEL",
    "PERRIN",
    "RENAUD",
    "ROBIN",
    "VIDAL",
)
FIRST_NAMES = (
    "Adam",
    "Alix",
    "Anaïs",
    "Arthur",
    "Bastien",
    "Camille",
    "Clara",
    "Elsa",
    "Ethan",
    "Gabin",
    "Hugo",
    "Inès",
    "Jules",
    "Léna",
    "Lucas",
    "Maël",
    "Manon",
    "Nina",
    "Noé",
    "Oscar",
    "Rose",
    "Sacha",
    "Théo",
    "Zoé",
)


class Command(BaseCommand):
    help = "Prépare la démonstration complète sur une base vide (qcm-live demo)."

    @transaction.atomic
    def handle(self, *args, **options) -> None:
        if Quiz.objects.exists() or StudentGroup.objects.exists() or Session.objects.exists():
            raise CommandError(
                "La base contient déjà des QCM, des groupes ou des sessions : la démonstration "
                "complète se prépare sur une base à part (qcm-live demo)."
            )
        now = timezone.now()
        quizzes = {name: import_file(name) for name in FILES}
        names = fictitious_names()
        year = academic_year(timezone.localdate())
        group = import_group(year, names[:GROUP_SIZE], first_number=1)
        previous = import_group(
            previous_year(year), names[GROUP_SIZE:][:PREVIOUS_SIZE], first_number=501
        )
        session = past_session(quizzes["fonctions"], group, now - timedelta(days=DAYS_AGO))
        composed = compose(quizzes["fonctions"], quizzes["probabilites"])
        revise(REVISED, REVISION)

        for quiz in [*quizzes.values(), composed]:
            self.stdout.write(f"QCM : {quiz.title} ({quiz.questions.count()} questions)")
        for each in (group, previous):
            self.stdout.write(f"Groupe : {each} ({each.students.count()} étudiants)")
        present = session.participants.count()
        self.stdout.write(f"Session passée : {session.quiz_title}, {present} présents")
        write_account(self.stdout, demo_account())
        self.stdout.write("Nouveau mot de passe, et données remises à neuf, à chaque lancement.")


def import_file(name: str) -> Quiz:
    folder = COMPLETE_DIR / name
    return import_quiz(folder_archive(folder), f"{name}.zip")


def previous_year(year: str) -> str:
    first = int(year[:4]) - 1
    return f"{first}-{first + 1}"


def fictitious_names() -> list[str]:
    """Noms « NOM Prénom » tous différents, dans un ordre tiré avec la graine fixe."""
    names = [f"{last} {first}" for last, first in product(LAST_NAMES, FIRST_NAMES)]
    random.Random(SEED).shuffle(names)  # noqa: S311 — données fictives reproductibles
    return names


def import_group(year: str, names: list[str], first_number: int) -> StudentGroup:
    """Groupe importé par le formulaire, d'un CSV au format d'I14 (n°, numéro, nom), par
    ordre alphabétique comme une liste de scolarité."""
    rows = [
        f"{n};2{first_number + n - 1:07d};{name}\n" for n, name in enumerate(sorted(names), start=1)
    ]
    content = "".join([";".join(HEADER) + "\n", *rows]).encode()
    upload = SimpleUploadedFile("l1-sciences.csv", content, content_type="text/csv")
    form = GroupImportForm({"name": GROUP_NAME, "year": year}, {"file": upload})
    if not form.is_valid():
        raise CommandError(f"Groupe de démonstration refusé : {form.errors.as_text()}")
    return form.save()


def past_session(quiz: Quiz, group: StudentGroup, started: datetime) -> Session:
    """Session lancée, rejointe et démarrée `started`, terminée depuis, avec des réponses."""
    form = LaunchSessionForm(
        {"quiz": quiz.pk, "group": group.pk, "shown": SHOWN, "seconds": SECONDS}
    )
    if not form.is_valid():
        raise CommandError(f"Session de démonstration refusée : {form.errors.as_text()}")
    session = form.save()
    rng = random.Random(SEED)  # noqa: S311 — réponses fictives reproductibles
    absent = set(rng.sample([s["list_number"] for s in session.students], ABSENT))
    answers: list[Answer] = []
    for student in session.students:
        if student["list_number"] not in absent:
            participant = session.enrol(student)
            if participant is None:  # pragma: no cover — base vide, liste sans doublon
                raise CommandError(f"N° {student['list_number']} déjà pris.")
            ability = rng.uniform(0.3, 0.95)
            answers += answer_all(participant, session.questions, ability=ability, rng=rng)
    Answer.objects.bulk_create(answers)
    session.start(started)
    # Les horodatages, dans le passé : le lancement, les arrivées, et chaque réponse pendant le
    # créneau de sa question (une question par créneau de SECONDS).
    Session.objects.filter(pk=session.pk).update(created_at=started - timedelta(minutes=4))
    session.participants.update(joined_at=started - timedelta(minutes=2))
    for index in range(len(session.questions)):
        Answer.objects.filter(participant__session=session, question=index).update(
            updated_at=started + timedelta(seconds=index * SECONDS + SECONDS // 2)
        )
    return session


def answer_all(
    participant: Participant,
    questions: list[FrozenQuestion],
    *,
    ability: float,
    rng: random.Random,
) -> list[Answer]:
    """Une réponse par question, validée comme celle d'un téléphone (AnswerForm), à enregistrer
    ensemble ; l'étudiant trouve chaque proposition avec la probabilité `ability`, et en laisse
    quelques-unes."""
    answers = []
    for index, question in enumerate(questions):
        if rng.random() < 0.04:
            continue  # sans réponse
        chosen = pick(question, ability, rng)
        form = AnswerForm(MultiValueDict({"choice": [str(c) for c in chosen]}), question=question)
        if not form.is_valid():
            raise CommandError(f"Réponse de démonstration refusée : {form.errors.as_text()}")
        if form.cleaned_data["choice"]:
            answers.append(
                Answer(participant=participant, question=index, choices=form.cleaned_data["choice"])
            )
    return answers


def pick(question: FrozenQuestion, ability: float, rng: random.Random) -> list[int]:
    choices = question["choices"]
    none = none_index(question)
    real = [i for i in range(len(choices)) if i != none]
    if not question["multiple"]:
        right = next(i for i in real if choices[i]["correct"])
        return [right if rng.random() < ability else rng.choice(real)]
    chosen = [i for i in real if (rng.random() < ability) == choices[i]["correct"]]
    if not chosen and none is not None and (rng.random() < ability) == choices[none]["correct"]:
        return [none]  # « Aucune de ces réponses », juste ou fausse selon `ability`
    return chosen


def compose(*sources: Quiz) -> Quiz:
    """QCM composé par le formulaire (CMP-04), des premières questions hors groupe AMC de
    chaque fichier."""
    chosen: list[Question] = []
    for quiz in sources:
        alone = [q for q in quiz.ordered_questions() if not q.amc_group]
        chosen.extend(alone[:COMPOSED_PER_FILE])
    data = {"title": COMPOSED} | {QuizForm.include_field(q): "on" for q in chosen}
    form = QuizForm(data)
    if not form.is_valid():
        raise CommandError(f"QCM composé refusé : {form.errors.as_text()}")
    return form.save()


def revise(text: str, new_text: str) -> Question:
    """Nouvelle version de la question, enregistrée par le formulaire de la banque (VER-01) :
    sa saisie actuelle, l'énoncé changé."""
    question = Question.objects.get(text=text, hidden=False)
    current = QuestionForm(instance=question)
    data: dict[str, str] = {}
    for name in current.fields:
        value = current[name].value()
        if value is True:
            data[name] = "on"
        elif value is not None and value is not False and value != "":  # 0 est une valeur
            data[name] = str(value)
    data["text"] = new_text
    form = QuestionForm(data, instance=question)
    if not form.is_valid():
        raise CommandError(f"Nouvelle version refusée : {form.errors.as_text()}")
    return form.save_version()
