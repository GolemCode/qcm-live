"""Contenu du QR code de fin de session (FIN-01) : fonction pure."""

from live.receipt import letters, question_ref, receipt


def test_letters_are_board_letters_in_order():
    assert letters([]) == ""
    assert letters([0]) == "A"
    assert letters([3, 1]) == "BD"
    assert letters(range(8)) == "ABCDEFGH"


def test_question_ref_is_rank_in_quiz():
    assert question_ref(0) == "Q1"
    assert question_ref(11) == "Q12"


def test_receipt_lists_questions_in_received_order():
    text = receipt("012345", "00123", [(1, [0]), (0, [1, 3]), (2, [])])
    assert text == "Session 012345\nÉtudiant 00123\nQ2 A\nQ1 BD\nQ3 -"


def test_receipt_without_questions_keeps_identity():
    assert receipt("000001", "7", []) == "Session 000001\nÉtudiant 7"
