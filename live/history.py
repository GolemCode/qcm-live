"""Questions déjà posées à un groupe (CMP-03), étudiant par étudiant.

Une question est posée à un étudiant du groupe s'il s'est identifié dans une session démarrée
qui la contenait, elle ou une autre de ses versions, et dont le groupe figé porte le même nom
et la même année. L'étudiant d'alors est reconnu par son numéro étudiant quand les deux en ont
un, sinon par son nom exact : un groupe réimporté garde ainsi son historique."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import NamedTuple

from bank.models import Question
from live.models import Participant, Session
from roster.models import StudentGroup


class Person(NamedTuple):
    student_number: str  # vide : reconnu par son nom seulement
    name: str


def same_student(student: Person, participant: Person) -> bool:
    if student.student_number and participant.student_number:
        return student.student_number == participant.student_number
    return student.name == participant.name


def family_root(pk: int, previous: Mapping[int, int | None]) -> int:
    """Première version de la question `pk` : toutes ses versions la partagent (VER-01)."""
    seen = {pk}
    while (parent := previous.get(pk)) is not None and parent not in seen:
        seen.add(parent)
        pk = parent
    return pk


def posed_counts(
    students: Iterable[Person], played: Iterable[tuple[int, Person]]
) -> dict[int, int]:
    """{famille de questions : nombre d'étudiants de `students` à qui elle a été posée}, d'après
    `played`, les couples (famille, participant) des sessions passées du groupe."""
    # Index de same_student : chaque participant ne parcourt que ses candidats.
    by_number: dict[str, set[int]] = defaultdict(set)
    by_name: dict[str, set[int]] = defaultdict(set)  # tous les étudiants de ce nom
    unnumbered: dict[str, set[int]] = defaultdict(set)  # ceux de ce nom sans numéro
    for i, student in enumerate(students):  # indices : deux homonymes restent deux
        by_name[student.name].add(i)
        if student.student_number:
            by_number[student.student_number].add(i)
        else:
            unnumbered[student.name].add(i)
    reached: dict[int, set[int]] = defaultdict(set)
    for family, participant in played:
        if participant.student_number:
            found = by_number[participant.student_number] | unnumbered[participant.name]
        else:
            found = by_name[participant.name]
        reached[family] |= found
    return {family: len(found) for family, found in reached.items() if found}


def posed_to(group: StudentGroup, questions: Iterable[Question]) -> dict[Question, int]:
    """{question : nombre d'étudiants de `group` à qui elle a déjà été posée}, pour celles de
    `questions` qui l'ont été au moins une fois."""
    sessions = Session.objects.filter(
        group_name=group.name, group_year=group.year, started_at__isnull=False
    )
    links = Session.source_questions.through.objects.filter(session__in=sessions)
    families_by_session: dict[int, set[int]] = defaultdict(set)
    previous = dict(Question.objects.values_list("pk", "previous"))
    for session_id, question_id in links.values_list("session_id", "question_id"):
        families_by_session[session_id].add(family_root(question_id, previous))
    if not families_by_session:
        return {}
    participants = Participant.objects.filter(session__in=families_by_session)
    played = (
        (family, Person(number, name))
        for session_id, number, name in participants.values_list(
            "session_id", "student_number", "name"
        )
        for family in families_by_session[session_id]
    )
    students = (Person(*row) for row in group.students.values_list("student_number", "name"))
    counts = posed_counts(students, played)
    found = {q: counts.get(family_root(q.pk, previous), 0) for q in questions}
    return {q: n for q, n in found.items() if n}
