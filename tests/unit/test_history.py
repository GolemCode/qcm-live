"""Questions déjà posées (CMP-03) : reconnaissance des étudiants et familles de versions."""

import pytest

from live.history import Person, family_root, posed_counts, same_student


@pytest.mark.parametrize(
    ("student", "participant", "same"),
    [
        (Person("00123", "DURAND Élise-Marie"), Person("00123", "DURAND Élise"), True),
        (Person("99", "Ng Anh"), Person("7", "Ng Anh"), False),  # deux numéros : ils décident
        (Person("", "MARTIN Léo"), Person("42", "MARTIN Léo"), True),  # un seul : le nom
        (Person("42", "MARTIN Léo"), Person("", "MARTIN Léo"), True),
        (Person("", "MARTIN Léo"), Person("", "MARTIN Leo"), False),  # nom exact
        (Person("", "MARTIN Léo"), Person("", "martin léo"), False),
        (Person("", "MARTIN Léo"), Person("", "MARTIN Léo"), True),
    ],
)
def test_same_student_by_number_then_by_exact_name(student, participant, same):
    assert same_student(student, participant) is same
    # posed_counts applique la même règle par ses index.
    assert posed_counts([student], [(1, participant)]) == ({1: 1} if same else {})


def test_family_root_follows_previous_versions():
    previous = {1: None, 2: 1, 3: 2, 4: 1, 5: None}
    assert [family_root(pk, previous) for pk in (1, 2, 3, 4, 5)] == [1, 1, 1, 1, 5]
    assert family_root(9, previous) == 9  # inconnue : sa propre famille


def test_family_root_stops_on_a_cycle():
    assert family_root(1, {1: 2, 2: 1}) in {1, 2}


def test_posed_counts_counts_each_student_once():
    durand, martin, petit = Person("1", "DURAND"), Person("", "MARTIN"), Person("3", "PETIT")
    played = [
        (10, Person("1", "DURAND")),
        (10, Person("1", "DURAND autre nom")),  # deuxième séance : toujours une étudiante
        (10, Person("8", "MARTIN")),
        (20, Person("4", "PETIT")),  # autre numéro : personne
        (30, Person("3", "PETIT")),
    ]
    assert posed_counts([durand, martin, petit], played) == {10: 2, 30: 1}


def test_posed_counts_without_history():
    assert posed_counts([Person("1", "A")], []) == {}


def test_posed_counts_keeps_homonyms_without_number_apart():
    """Deux étudiants du groupe, même nom, sans numéro : le nom les désigne tous deux."""
    students = [Person("", "NGUYEN An"), Person("", "NGUYEN An"), Person("5", "NGUYEN An")]
    assert posed_counts(students, [(10, Person("", "NGUYEN An"))]) == {10: 3}
    assert posed_counts(students, [(10, Person("6", "NGUYEN An"))]) == {10: 2}
    assert posed_counts(students, [(10, Person("5", "autre"))]) == {10: 1}
