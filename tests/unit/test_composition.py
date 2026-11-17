"""Ordre d'un QCM recomposé (CMP-04)."""

from bank.composition import arrange


def test_new_quiz_follows_the_bank():
    assert arrange([], [1, 2, 3], {}) == [1, 2, 3]


def test_quiz_without_file_keeps_its_order_and_appends_in_bank_order():
    assert arrange([5, 2, 9], [1, 2, 5, 7, 9], {}) == [5, 2, 9, 1, 7]


def test_removed_questions_leave_the_order():
    assert arrange([5, 2, 9], [2, 9], {}) == [2, 9]


def test_quiz_from_file_follows_the_file_then_the_others():
    ranks = {10: 1, 11: 2, 12: 3}
    # 11 a été retiré puis est remis : il retrouve sa place, avant les ajouts (4 puis 2).
    assert arrange([10, 12, 4, 2], [2, 4, 10, 11, 12], ranks) == [10, 11, 12, 4, 2]


def test_file_order_wins_over_the_current_order():
    assert arrange([12, 10], [10, 12], {10: 1, 12: 3}) == [10, 12]


def test_question_from_another_file_is_an_ordinary_question():
    assert arrange([10, 30], [10, 30, 31], {10: 1}) == [10, 30, 31]
