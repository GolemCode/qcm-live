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
from bank.models import AMC_DEFAULTS, Question, Quiz
from live.forms import IdentifyForm, LaunchSessionForm
from live.models import Participant, Session
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


def make_quiz(title: str, questions: Sequence[Question], **scale: str) -> Quiz:
    defaults = {"b": AMC_DEFAULTS.b, "m": AMC_DEFAULTS.m, "v": AMC_DEFAULTS.v}
    data = {
        f"{kind}_{key}": value for kind in ("simple", "multiple") for key, value in defaults.items()
    }
    data |= {"title": title, **scale}
    data |= {QuizForm.order_field(q): position for position, q in enumerate(questions, start=1)}
    return _saved(QuizForm(data))


def make_group(name: str, students: Sequence[tuple[str, str]]) -> StudentGroup:
    """Groupe importé par le formulaire d'import, à partir d'un CSV construit ici."""
    content = "".join(f"{number};{student}\n" for number, student in students).encode()
    upload = SimpleUploadedFile("groupe.csv", content, content_type="text/csv")
    return _saved(GroupImportForm({"name": name}, {"file": upload}))


def make_session(quiz: Quiz, group: StudentGroup, *, shown: int = 1, seconds: int = 30) -> Session:
    """Session lancée par le formulaire de lancement."""
    data = {"quiz": quiz.pk, "group": group.pk, "shown": shown, "seconds": seconds}
    return _saved(LaunchSessionForm(data))


def make_participant(session: Session, number: str) -> Participant:
    """Étudiant identifié dans la session, comme s'il avait saisi son numéro sur un téléphone :
    pour remplir une salle sans ouvrir un navigateur par étudiant."""
    form = IdentifyForm({"number": number}, session=session)
    participant = _saved(form)
    assert participant is not None, form.errors
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
