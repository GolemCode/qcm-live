"""Résultats d'une session (RES-01, RES-02) : notation sur la copie figée et export CSV."""

from decimal import Decimal as D

import pytest

from bank.scoring import Scale
from live.results import (
    ABSENT,
    Mark,
    StudentResult,
    csv_rows,
    decimal_fr,
    grade,
    max_total,
    neutralised,
    results,
)
from live.snapshot import FrozenQuestion, FrozenQuiz, FrozenStudent

SIMPLE = Scale(b=D(2), m=D("-0.5"), v=D("0.25"))
MULTIPLE = Scale(b=D(1), m=D(-1), v=D("0.5"), p=D(0))


def question(multiple: bool, *correct: bool) -> FrozenQuestion:
    return {
        "text": "?",
        "multiple": multiple,
        "choices": [{"text": str(i), "correct": c} for i, c in enumerate(correct)],
    }


QUIZ: FrozenQuiz = {
    "scales": {"simple": SIMPLE.to_json(), "multiple": MULTIPLE.to_json()},
    "questions": [question(False, True, False, False), question(True, True, True, False)],
}
STUDENTS: list[FrozenStudent] = [
    {"number": "00123", "name": "DURAND Élise"},
    {"number": "42", "name": "=1+1"},
]


def test_grade_uses_the_scale_of_each_kind():
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
        ["numéro", "nom", "note", "note max", "Q1 réponse", "Q1 points", "Q2 réponse", "Q2 points"],
        ["00123", "DURAND Élise", "2,5", "5", "B", "-0,5", "AB", "3"],
        ["42", "'=1+1", ABSENT, "5", "", "", "", ""],
    ]


def test_csv_rows_mark_no_answer_with_a_dash():
    rows = csv_rows(QUIZ, results(QUIZ, STUDENTS[:1], {"00123": {}}))
    assert rows[1] == ["00123", "DURAND Élise", "0,75", "5", "-", "0,25", "-", "0,5"]
