"""Résultats d'une session (RES-01, RES-02) : notation sur la copie figée et export CSV."""

from decimal import Decimal as D

import pytest

from live.results import (
    ABSENT,
    Mark,
    StudentResult,
    csv_rows,
    decimal_fr,
    grade,
    letters,
    max_total,
    neutralised,
    results,
)
from live.snapshot import FrozenQuestion, FrozenQuiz, FrozenStudent

SIMPLE = "b=2,m=-0.5,v=0.25"
MULTIPLE = "m=-1,v=0.5,p=0"


def question(
    multiple: bool, *correct: bool, scoring: str = "", points=(), none: bool = False
) -> FrozenQuestion:
    """Question figée ; `points` : valeur propre de chaque proposition (None : b ou m) ;
    `none` : la dernière proposition est « Aucune de ces réponses n'est correcte »."""
    values = list(points) + [None] * (len(correct) - len(points))
    return {
        "text": "?",
        "multiple": multiple,
        "ordered": False,
        "scoring": scoring,
        "choices": [
            {"text": str(i), "correct": c, "points": v, "none": none and i == len(correct) - 1}
            for i, (c, v) in enumerate(zip(correct, values, strict=True))
        ],
    }


QUIZ: FrozenQuiz = {
    "questions": [
        question(False, True, False, False, scoring=SIMPLE),
        question(True, True, True, False, scoring=MULTIPLE),
    ],
}
STUDENTS: list[FrozenStudent] = [
    {"number": "00123", "name": "DURAND Élise"},
    {"number": "42", "name": "=1+1"},
]


def test_grade_uses_the_scoring_of_each_question():
    assert grade(QUIZ, {0: [1], 1: [0, 2]}) == [Mark("B", D("-0.5")), Mark("AC", D(0))]
    assert grade(QUIZ, {0: [0], 1: [1]}) == [Mark("A", D(2)), Mark("B", D(1))]


def test_missing_answers_count_as_v():
    assert grade(QUIZ, {}) == [Mark("", D("0.25")), Mark("", D("0.5"))]


def test_max_total_sums_each_question_maximum():
    assert max_total(QUIZ) == D(5)  # 2 + 1 x 3 propositions


def test_results_follow_roster_order_and_mark_absents():
    rows = results(QUIZ, STUDENTS, {"00123": {0: [0]}})
    assert [r.number for r in rows] == ["00123", "42"]
    assert rows[0].total == D("2.5")  # 2 + v (0,5)
    assert rows[1].marks is None and rows[1].total is None


def test_result_total_can_be_negative():
    assert StudentResult("1", "A", [Mark("B", D("-0.5")), Mark("", D(-1))]).total == D("-1.5")


@pytest.mark.parametrize(
    ("value", "text"),
    [
        (D("1.50"), "1,5"),
        (D("2.00"), "2"),
        (D("-0.25"), "-0,25"),
        (D("10"), "10"),
        (D("100.00"), "100"),
        (D("0.00"), "0"),
        (D("-0"), "0"),
    ],
)
def test_decimal_fr(value, text):
    assert decimal_fr(value) == text


@pytest.mark.parametrize(
    ("text", "safe"),
    [
        ("=1+1", "'=1+1"),
        ("+33", "'+33"),
        ("-2", "'-2"),
        ("@SUM(A1)", "'@SUM(A1)"),
        ("\t=1", "'\t=1"),
        ("\r=1", "'\r=1"),
        ("DUPONT=Jean", "DUPONT=Jean"),
        ("Ng Anh", "Ng Anh"),
        ("", ""),
    ],
)
def test_neutralised(text, safe):
    assert neutralised(text) == safe


def test_csv_rows():
    rows = csv_rows(QUIZ, results(QUIZ, STUDENTS, {"00123": {0: [1], 1: [0, 1]}}))
    assert rows == [
        [
            "numéro",
            "nom",
            "note",
            "note max",
            "note /20",
            *["Q1 réponse", "Q1 points"],
            *["Q2 réponse", "Q2 points"],
        ],
        ["00123", "DURAND Élise", "2,5", "5", "10", "B", "-0,5", "AB", "3"],
        ["42", "'=1+1", ABSENT, "5", "", "", "", "", ""],
    ]


def test_csv_rows_mark_no_answer_with_a_dash():
    rows = csv_rows(QUIZ, results(QUIZ, STUDENTS[:1], {"00123": {}}))
    assert rows[1] == ["00123", "DURAND Élise", "0,75", "5", "3", "-", "0,25", "-", "0,5"]


def test_letters_follow_the_bank_order():
    assert letters([]) == ""
    assert letters([0]) == "A"
    assert letters([3, 1]) == "BD"
    assert letters(range(8)) == "ABCDEFGH"


def test_grade_uses_the_points_of_a_choice():
    quiz: FrozenQuiz = {"questions": [question(False, True, False, points=[None, "-2"])]}
    assert grade(quiz, {0: [1]}) == [Mark("B", D(-2))]
    assert grade(quiz, {0: [0]}) == [Mark("A", D(1))]
    assert max_total(quiz) == D(1)


def test_none_of_these_has_the_letter_after_the_last_choice():
    quiz: FrozenQuiz = {"questions": [question(True, False, False, True, none=True)]}
    assert grade(quiz, {0: [2]}) == [Mark("C", D(2))]  # A et B non cochées, justes : 1 + 1
    assert grade(quiz, {0: [0, 2]}) == [Mark("AC", D(0))]  # « Aucune » combinée : e
    assert csv_rows(quiz, results(quiz, STUDENTS[:1], {"00123": {0: [2]}}))[1][5:] == ["C", "2"]
