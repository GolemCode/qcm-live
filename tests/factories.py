"""Données de test fictives créées en base, en passant par les formulaires de l'application.

Passer par les formulaires garantit que les préconditions respectent les mêmes règles que
l'interface : une fabrique ne peut pas produire une donnée que l'enseignant ne pourrait pas
créer. À réserver aux *préconditions* : quand un test vérifie la création elle-même, il passe
par l'interface (tests/e2e/bank_ui.py).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import F
from django.utils import timezone

from bank.forms import LETTERS, QuestionForm, QuizForm
from bank.models import Question, Quiz
from live.forms import LaunchSessionForm
from live.models import Participant, Session
from roster.csv_import import HEADER
from roster.forms import GroupImportForm
from roster.models import StudentGroup

YES_NO = (("oui", True), ("non", False))


def _saved(form):
    assert form.is_valid(), form.errors
    return form.save()


def make_question(
    text: str,
    choices: Sequence[tuple[str, bool] | tuple[str, bool, str]] = YES_NO,
    *,
    multiple: bool = False,
    scoring: str = "",
    none_of_these: bool = False,
    ordered: bool = False,
) -> Question:
    """Question enregistrée par le formulaire. Une proposition peut porter ses propres points
    (troisième élément, questions simples : BAR-01) ; `scoring` : directives AMC du barème."""
    data = {"text": text, "kind": Question.Kind.MULTIPLE if multiple else Question.Kind.SIMPLE}
    data["scoring"] = scoring
    if none_of_these:
        data["none_of_these"] = "on"
    if ordered:
        data["ordered"] = "on"
    for letter, (label, correct, *points) in zip(LETTERS, choices, strict=False):
        data[f"choice_{letter}"] = label
        if correct:
            data[f"correct_{letter}"] = "on"
        if points:
            data[f"points_{letter}"] = points[0]
    return _saved(QuestionForm(data))


def make_quiz(title: str, questions: Sequence[Question]) -> Quiz:
    data: dict[str, object] = {"title": title}
    data |= {QuizForm.order_field(q): position for position, q in enumerate(questions, start=1)}
    return _saved(QuizForm(data))


def make_group(
    name: str, students: Sequence[tuple[str, str]] | Sequence[tuple[int, str, str]]
) -> StudentGroup:
    """Groupe importé par le formulaire d'import, à partir d'un CSV construit ici : à l'ancien
    format pour des couples (numéro étudiant, nom), dont le n° est alors le rang ; au format
    d'I14 pour des triplets (n°, numéro étudiant, nom) (GRP-05)."""
    lines = [";".join(map(str, student)) + "\n" for student in students]
    if students and len(students[0]) == 3:
        lines.insert(0, ";".join(HEADER) + "\n")
    content = "".join(lines).encode()
    upload = SimpleUploadedFile("groupe.csv", content, content_type="text/csv")
    return _saved(GroupImportForm({"name": name}, {"file": upload}))


def make_session(quiz: Quiz, group: StudentGroup, *, shown: int = 1, seconds: int = 30) -> Session:
    """Session lancée par le formulaire de lancement."""
    data = {"quiz": quiz.pk, "group": group.pk, "shown": shown, "seconds": seconds}
    return _saved(LaunchSessionForm(data))


def make_participant(session: Session, list_number: int) -> Participant:
    """Étudiant identifié dans la session, par le même chemin que la confirmation de son nom
    sur un téléphone (`Session.enrol`) : pour remplir une salle sans ouvrir un navigateur par
    étudiant."""
    student = session.student(list_number)
    assert student is not None, f"n° {list_number} hors de la liste"
    participant = session.enrol(student)
    assert participant is not None, f"n° {list_number} déjà pris"
    return participant


def rewind(session: Session, seconds: float) -> None:
    """Fait comme si la session avait démarré `seconds` plus tôt : avance le déroulement
    sans attendre (les tests à temps réel restent ceux de DER-02)."""
    Session.objects.filter(pk=session.pk).update(
        started_at=F("started_at") - timedelta(seconds=seconds)
    )


def jump_to(session: Session, elapsed: float) -> None:
    """Place le déroulement `elapsed` secondes après le démarrage, à partir de maintenant :
    pour tester une échéance à la demi-seconde près, quel que soit le temps déjà écoulé."""
    Session.objects.filter(pk=session.pk).update(
        started_at=timezone.now() - timedelta(seconds=elapsed)
    )
