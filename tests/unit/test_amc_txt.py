"""Lecture d'un fichier AMC-TXT (SPEC.md §2 ter ; IMP-01 à IMP-07) : chaque règle, avec le cas
refusé et le cas tout juste accepté."""

from decimal import Decimal as D

import pytest

from bank.amc_txt import (
    CHOICE_MAX_LENGTH,
    GROUP_LABEL_MAX_LENGTH,
    MAX_BYTES,
    TITLE_MAX_LENGTH,
    AmcSyntaxError,
    ParsedChoice,
    parse,
)

YES_NO = "+ Oui\n- Non\n"
UNSUPPORTED_FORMULA = "directive « formula » non prise en charge"


def read(text: str, name: str = "controle.txt"):
    return parse(text.encode(), name)


def errors(text: str | bytes) -> list[str]:
    with pytest.raises(AmcSyntaxError) as error:
        parse(text.encode() if isinstance(text, str) else text, "x.txt")
    return error.value.messages


def skipped(text: str) -> list[tuple[int, str]]:
    return list(read(text).skipped)


def only(text: str):
    (question,) = read(text).questions
    return question


# --- Fichier ------------------------------------------------------------------------------


def test_size_limit():
    filler = "# " + "x" * (MAX_BYTES - len("# \n* Q ?\n" + YES_NO)) + "\n"
    accepted = filler + "* Q ?\n" + YES_NO
    assert len(accepted.encode()) == MAX_BYTES
    assert read(accepted).questions
    assert errors(accepted + "#") == ["Fichier trop volumineux : 1 Mo au plus."]


def test_utf8_is_required_and_the_line_is_given():
    data = "* Été ?\n+ Oui\n- Non\n* Où ?\n".encode() + "+ Là\n".encode("cp1252")
    assert errors(data) == ["Ligne 5 : le fichier n'est pas en UTF-8. Enregistrez-le en UTF-8."]


def test_nul_character_is_refused_with_its_line():  # UTF-16 ou fichier binaire
    data = b"* Q ?\n+ Oui\x00\n- Non\n"
    assert errors(data) == ["Ligne 2 : le fichier n'est pas en UTF-8. Enregistrez-le en UTF-8."]
    assert errors("* Q ?\n".encode("utf-16")) == [
        "Ligne 1 : le fichier n'est pas en UTF-8. Enregistrez-le en UTF-8."
    ]


def test_bom_and_windows_line_ends_are_accepted():
    parsed = parse("﻿Title: T\r\n* Q ?\r\n+ Oui\r\n- Non\r\n".encode(), "x.txt")
    assert parsed.title == "T"
    assert parsed.questions[0].choices[1].text == "Non"


def test_no_question_at_all():
    assert errors("Title: Vide\n# rien\n") == ["Le fichier ne contient aucune question."]
    assert errors("") == ["Le fichier ne contient aucune question."]


def test_file_whose_questions_are_all_skipped_parses_with_no_question():
    parsed = read("*<lines=2> Racontez.\n")
    assert parsed.questions == ()
    assert parsed.skipped == ((1, "question ouverte"),)


def test_errors_are_sorted_by_line_and_capped_at_20():
    assert len(errors("- x\n" * 20)) == 20  # tout juste : pas de compte
    messages = errors("Couleur: x\n" + "- x\n" * 21 + "*(\n")
    assert messages[0] == "Ligne 1 : option inconnue « Couleur »"
    assert messages[19] == "Ligne 20 : proposition hors d'une question"
    assert messages[20] == "… et 3 autres erreurs."
    assert len(messages) == 21


def test_text_before_the_first_element():
    assert errors("Bonjour\n* Q ?\n" + YES_NO) == [
        "Ligne 1 : texte avant le premier élément du fichier"
    ]
    assert read("\n  \n# note\n* Q ?\n" + YES_NO).questions  # vide ou commentaire : permis


def test_include_file_is_refused():
    assert errors("IncludeFile: autre.txt\n* Q ?\n" + YES_NO) == [
        "Ligne 1 : IncludeFile : un fichier inclus n'est pas pris en charge"
    ]


# --- Options du fichier -------------------------------------------------------------------


def test_title_from_option_or_file_name():
    assert read("Title: Partiel\n* Q ?\n" + YES_NO).title == "Partiel"
    assert read("title:   Deux   mots  \n* Q ?\n" + YES_NO).title == "Deux mots"  # casse
    assert read("* Q ?\n" + YES_NO, "partiel-2024.txt").title == "partiel-2024"
    assert read("* Q ?\n" + YES_NO, "dossier/ds.v2.txt").title == "ds.v2"
    assert read("* Q ?\n" + YES_NO, "").title == "QCM importé"


def test_title_length():
    assert len(read(f"Title: {'T' * TITLE_MAX_LENGTH}\n* Q ?\n" + YES_NO).title) == 200
    assert errors(f"# t\nTitle: {'T' * (TITLE_MAX_LENGTH + 1)}\n* Q ?\n" + YES_NO) == [
        "Ligne 2 : titre de plus de 200 caractères"
    ]


def test_layout_options_are_accepted_without_effect():
    text = "Lang: FR\nColumns: 2\nPresentation: Bonne chance\n  sur deux lignes.\n"
    text += "ShuffleQuestions: 0\nPaperSize: A4\n* Q ?\n" + YES_NO
    assert only(text).text == "Q ?"


def test_unknown_option():
    assert errors("Couleur: bleu\n* Q ?\n" + YES_NO) == ["Ligne 1 : option inconnue « Couleur »"]
    assert errors("* Q ?\nVoir: page 2\n" + YES_NO) == ["Ligne 2 : option inconnue « Voir »"]


def test_an_option_ends_the_current_question():
    assert errors("* Q ?\n+ Oui\nLang: FR\n- Non\n") == [
        "Ligne 1 : question avec moins de 2 propositions",
        "Ligne 4 : proposition hors d'une question",
    ]


# --- Questions et propositions ------------------------------------------------------------


def test_simple_and_multiple_questions():
    simple = only("* Capitale ?\n+ Rome\n- Milan\n")
    assert (simple.line, simple.text, simple.multiple) == (1, "Capitale ?", False)
    assert simple.choices == (ParsedChoice("Rome", True), ParsedChoice("Milan", False))
    multiple = only("  ** Pairs ?\n  + Deux\n  - Sept\n")
    assert multiple.multiple and multiple.text == "Pairs ?"


def test_continuation_lines_and_paragraphs():
    question = only("* Première ligne\n  suite.\n\n\nParagraphe 2.\n+ Oui,\nvraiment\n- Non\n\n")
    assert question.text == "Première ligne suite.\n\nParagraphe 2."
    assert question.choices[0].text == "Oui, vraiment"
    assert question.choices[1].text == "Non"


def test_choice_outside_a_question():
    assert errors("- Seule\n") == ["Ligne 1 : proposition hors d'une question"]


def test_at_least_two_choices():
    assert errors("* Q ?\n+ Oui\n") == ["Ligne 1 : question avec moins de 2 propositions"]
    assert errors("** Q ?\n") == ["Ligne 1 : question avec moins de 2 propositions"]
    assert len(only("* Q ?\n+ Oui\n- Non\n").choices) == 2


def test_a_simple_question_has_exactly_one_right_answer():
    assert errors("* Q ?\n- A\n- B\n") == ["Ligne 1 : question simple avec 0 bonne réponse"]
    assert errors("* Q ?\n+ A\n+ B\n") == ["Ligne 1 : question simple avec 2 bonnes réponses"]


def test_choice_letter_is_ignored_and_points_are_read():
    question = only("*{b=3} Q ?\n+[a] Oui\n-[b]{-2} Non\n-{0.5} Peut-être\n")
    assert [c.text for c in question.choices] == ["Oui", "Non", "Peut-être"]
    assert [c.points for c in question.choices] == [None, D(-2), D("0.5")]


def test_question_options():
    question = only("*[ordered,id=q1,horiz,columns=2] Q ?\n" + YES_NO)
    assert question.ordered
    assert not only("* Q ?\n" + YES_NO).ordered
    assert errors("*[ordre] Q ?\n" + YES_NO) == ["Ligne 1 : option de question inconnue « ordre »"]


def test_empty_parts_of_options_and_scoring_are_ignored_like_amc():
    question = only("*[,ordered, ,]{b=2,,m=-1,} Q ?\n" + YES_NO)
    assert (question.ordered, question.scoring) == (True, "b=2,m=-1")


def test_open_and_indicative_questions_are_skipped():
    assert skipped("*<lines=3> Expliquez.\n\n* Q ?\n" + YES_NO) == [(1, "question ouverte")]
    # Une question ouverte n'a pas à avoir de propositions ; une indicative, pas de bonne.
    assert skipped("*[indicative] Avis ?\n- Oui\n- Non\n\n* Q ?\n" + YES_NO) == [
        (1, "question indicative")
    ]


def test_more_than_8_choices():
    eight = "** Q ?\n+ 1\n" + "".join(f"- {i}\n" for i in range(2, 9))
    assert len(only(eight).choices) == 8
    nine = eight + "- 9\n\n* R ?\n" + YES_NO
    assert skipped(nine) == [(1, "plus de 8 propositions")]


def test_choice_length():
    ok = "x" * CHOICE_MAX_LENGTH
    assert only(f"* Q ?\n+ {ok}\n- Non\n").choices[0].text == ok
    assert skipped(f"* Q ?\n- Oui\n+ {ok}x\n\n* R ?\n" + YES_NO) == [
        (1, "proposition B de plus de 200 caractères")
    ]


def test_empty_statement_or_choice():
    assert skipped("* \n+ Oui\n- Non\n\n* R ?\n" + YES_NO) == [(1, "énoncé vide")]
    assert skipped("* Q ?\n+ Oui\n-\n\n* R ?\n" + YES_NO) == [(1, "proposition B vide")]


def test_duplicates_inside_the_file():
    text = "* Q ?\n" + YES_NO + "\n* Q ?\n" + YES_NO
    assert skipped(text) == [(5, "doublon de la question de la ligne 1")]
    # Mêmes énoncé et propositions, autre barème ou autre réponse juste : pas un doublon.
    assert len(read("* Q ?\n" + YES_NO + "\n*{b=2} Q ?\n" + YES_NO).questions) == 2
    assert len(read("* Q ?\n" + YES_NO + "\n* Q ?\n- Oui\n+ Non\n").questions) == 2
    assert len(read("* Q ?\n" + YES_NO + "\n*[ordered] Q ?\n" + YES_NO).questions) == 2
    # Seule l'étiquette diffère : doublon.
    grouped = "* Q ?\n" + YES_NO + "*([group=g]\n* Q ?\n" + YES_NO + "*)\n"
    assert skipped(grouped) == [(5, "doublon de la question de la ligne 1")]


# --- Barème (IMP-04) ----------------------------------------------------------------------


def test_scoring_of_the_question_replaces_the_default():
    text = "DefaultScoringS: b=3,v=-1\n\n*{b=2,m=-1} Q ?\n" + YES_NO + "\n* R ?\n" + YES_NO
    first, second = read(text).questions
    assert (first.scoring, second.scoring) == ("b=2,m=-1", "b=3,v=-1")


def test_default_scoring_of_multiple_questions():
    assert only("** Q ?\n" + YES_NO).scoring == "haut=2"  # défaut implicite d'AMC-TXT
    assert only("DefaultScoringM: b=1,m=-0.5\n** Q ?\n" + YES_NO).scoring == "b=1,m=-0.5"
    assert only("* Q ?\n" + YES_NO).scoring == ""


def test_unsupported_scoring_skips_the_question():
    assert skipped("*{b=2,P=4} Q ?\n" + YES_NO + "\n* R ?\n- A\n+ B\n") == [
        (1, "barème : directive « P » non prise en charge")
    ]
    assert skipped("DefaultScoringM: formula=1\n** Q ?\n" + YES_NO + "\n* R ?\n" + YES_NO) == [
        (2, "barème par défaut du fichier (DefaultScoringM) : " + UNSUPPORTED_FORMULA)
    ]


def test_scoring_length():
    def long(length: int) -> str:  # barème valide, déjà sous sa forme normalisée
        head = "b=1,m=1,v=1,e=1,d=1,p=1,haut=1,mz=1,MAX=0."
        return head + "1" * (length - len(head))

    assert only(f"*{{{long(200)}}} Q ?\n" + YES_NO).scoring == long(200)
    assert skipped(f"*{{{long(201)}}} Q ?\n" + YES_NO + "\n* R ?\n- A\n+ B\n") == [
        (1, "barème de plus de 200 caractères")
    ]


def test_points_of_a_choice():
    assert skipped("** Q ?\n+{1} Oui\n- Non\n\n* R ?\n" + YES_NO) == [
        (1, "barème sur une proposition d'une question multiple")
    ]
    assert skipped("* Q ?\n+ Oui\n-{b=1} Non\n\n* R ?\n" + YES_NO) == [
        (1, "barème de la proposition B : valeur non numérique : « b=1 »")
    ]
    assert skipped("* Q ?\n+ Oui\n-{1000000} Non\n\n* R ?\n" + YES_NO)[0][1].startswith(
        "barème de la proposition B : « 1000000 »"
    )


# --- « Aucune de ces réponses n'est correcte » (IMP-05) -----------------------------------


def test_complete_multi_by_default():
    question = only("** Q ?\n- A\n- B\n")
    assert question.none_of_these
    assert not only("* Q ?\n" + YES_NO).none_of_these


@pytest.mark.parametrize("value", ["0", "no", "false", " FALSE ", ""])  # vide : faux, comme AMC
def test_complete_multi_off(value):
    text = f"CompleteMulti: {value}\n** Q ?\n" + YES_NO + "\n** R ?\n- A\n- B\n"
    parsed = read(text)
    assert not parsed.questions[0].none_of_these
    assert parsed.skipped == ((6, "question multiple sans bonne réponse"),)


def test_complete_multi_on():
    assert only("CompleteMulti: 1\n** Q ?\n- A\n- B\n").none_of_these


# --- Groupes (IMP-06) ---------------------------------------------------------------------


def test_groups_give_their_label_and_their_text_is_ignored():
    text = "*([group=geo,shuffle=1,numquestions=1,columns=2,needspace=3cm] Texte du\ngroupe.\n"
    text += "* Q1 ?\n" + YES_NO + "*([group=fleuves]\n* Q2 ?\n" + YES_NO + "*)\n"
    text += "* Q3 ?\n" + YES_NO + "*) Fin du groupe.\n* Q4 ?\n" + YES_NO
    parsed = read(text)
    assert [q.label for q in parsed.questions] == ["geo", "fleuves", "geo", ""]
    assert parsed.ignored == ((1, "Texte du groupe."), (14, "Fin du groupe."))


def test_label_of_the_question_wins_and_nested_groups_inherit():
    text = "*([group=a]\n*(\n*[group=b] Q1 ?\n" + YES_NO + "* Q2 ?\n" + YES_NO + "*)\n*)\n"
    assert [q.label for q in read(text).questions] == ["b", "a"]


def test_group_errors():
    assert errors("*)\n* Q ?\n" + YES_NO) == ["Ligne 1 : groupe fermé sans avoir été ouvert"]
    assert errors("* Q ?\n" + YES_NO + "*(\n") == ["Ligne 4 : groupe ouvert et jamais fermé"]
    assert errors("*([tirage=2]\n* Q ?\n" + YES_NO + "*)\n") == [
        "Ligne 1 : option de groupe inconnue « tirage »"
    ]


def test_label_length():
    ok = "g" * GROUP_LABEL_MAX_LENGTH
    assert only(f"*[group={ok}] Q ?\n" + YES_NO).label == ok
    assert skipped(f"*[group={ok}g] Q ?\n" + YES_NO + "\n* R ?\n- A\n+ B\n") == [
        (1, "nom de groupe de plus de 100 caractères")
    ]


def test_a_group_line_ends_the_current_question():
    assert errors("*(\n* Q ?\n+ Oui\n*)\n- Non\n") == [
        "Ligne 2 : question avec moins de 2 propositions",
        "Ligne 5 : proposition hors d'une question",
    ]


# --- Contenu : conversion en LaTeX léger (CNT-01 à CNT-04, IMP-08) -------------------------

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 8


@pytest.mark.parametrize(
    ("written", "stored"),
    [
        ("Que vaut [[$x^2$]] ?", "Que vaut $x^2$ ?"),
        ("Que vaut [latex]$\\frac{1}{2}$[/latex] ?", "Que vaut $\\frac{1}{2}$ ?"),
        ("Que fait [|print(a_b)|] ?", "Que fait \\texttt{print(a_b)} ?"),
        ("Le mot [*important*] ?", "Le mot \\textbf{important} ?"),
        ("Le mot [_penché_] ?", "Le mot \\textit{penché} ?"),
        ("Le mot [/souligné/] ?", "Le mot \\underline{souligné} ?"),
        ("[== Titre ==] ?", "\\textbf{ Titre } ?"),
        ("[*a [_b_]*] ?", "\\textbf{a \\textit{b}} ?"),
        ("5 $ et C:\\temp {x} ?", "5 \\$ et C:\\textbackslash{}temp \\{x\\} ?"),
        ("Fermé_] sans ouverture ?", "Fermé_] sans ouverture ?"),
    ],
)
def test_contents_are_converted_to_light_latex(written, stored):
    assert only(f"* {written}\n" + YES_NO).text == stored
    # Dans une proposition aussi.
    assert only(f"* Q ?\n+ Oui\n- {written}\n").choices[1].text == stored


@pytest.mark.parametrize(
    ("written", "reason"),
    [
        ("Le mot [*ouvert ?", "mise en forme non fermée"),
        ("Que vaut [[$x]] ?", "énoncé : formule non fermée"),
        ("Que vaut [[\\hspace{1cm}]] ?", "énoncé : commande LaTeX non prise en charge : \\hspace"),
    ],
)
def test_content_that_cannot_be_shown_is_skipped(written, reason):
    assert skipped(f"* {written}\n" + YES_NO + "\n* R ?\n- A\n+ B\n") == [(1, reason)]


def test_content_error_in_a_choice_names_it():
    assert skipped("* Q ?\n+ Oui\n- [[$x]]\n\n* R ?\n- A\n+ B\n") == [
        (1, "proposition B : formule non fermée")
    ]


def test_converted_choice_length_is_checked():
    fits = "[*" + "x" * (CHOICE_MAX_LENGTH - len("\\textbf{}")) + "*]"
    assert len(only(f"* Q ?\n+ {fits}\n- Non\n").choices[0].text) == CHOICE_MAX_LENGTH
    too_long = f"* Q ?\n+ x{fits}\n- Non\n\n* R ?\n- A\n+ B\n"
    assert skipped(too_long) == [(1, f"proposition A de plus de {CHOICE_MAX_LENGTH} caractères")]


def test_plain_text_that_looks_like_marks_is_accepted():
    for text in ("Combien ! d'élèves ?", "Un [crochet] ?", "a/b et c*d ?", "100 % et A & B ?"):
        assert only(f"* {text}\n" + YES_NO).text == text


def test_verbatim_block():
    text = "* Que fait ce code ?\n[verbatim]\n* pas une question\n  - ni une proposition\n"
    text += "\n# ni un commentaire\n[/verbatim]\n" + YES_NO
    assert only(text).text == (
        "Que fait ce code ? \\begin{verbatim}\n* pas une question\n  - ni une proposition\n"
        "\n# ni un commentaire\n\\end{verbatim}"
    )
    assert errors("* Q ?\n" + YES_NO + "[verbatim]\n- x\n") == [
        "Ligne 4 : bloc [verbatim] jamais fermé"
    ]


def test_verbatim_on_one_line_and_closing_in_capitals():
    assert only("* [verbatim]a  b[/VERBATIM] ?\n" + YES_NO).text == (
        "\\begin{verbatim}\na  b\n\\end{verbatim} ?"
    )


def test_line_opening_verbatim_is_text_of_the_previous_element_like_amc():
    # AMC ne lit ni question ni commentaire sur la ligne qui ouvre le bloc.
    text = "* Q ?\n" + YES_NO + "* R [verbatim]\n- x\n[/verbatim]\n* S ?\n" + YES_NO
    first, second = read(text).questions
    assert first.choices[1].text == "Non * R \\begin{verbatim}\n- x\n\\end{verbatim}"
    assert second.text == "S ?"
    commented = "* Q ?\n" + YES_NO + "# astuce : [verbatim]\n* R ?\n" + YES_NO + "[/verbatim]\n"
    assert [q.text for q in read(commented).questions] == ["Q ?"]
    assert (
        only("* Q [VERBATIM] ?\n" + YES_NO).text == "Q [VERBATIM] ?"
    )  # ouverture sensible à la casse


def test_disable_turns_a_mark_back_into_text():
    assert only("Disable: embf\n* Le mot [*gras*] ?\n" + YES_NO).text == "Le mot [*gras*] ?"
    assert only("Disable: images\n* Le cri !Ah! ?\n" + YES_NO).text == "Le cri !Ah! ?"
    assert only("Disable: title\n* [==T==] ?\n" + YES_NO).text == "[==T==] ?"
    assert only("Disable: local_latex\n* [[$x$]] ?\n" + YES_NO).text == "[[\\$x\\$]] ?"
    # `[/verbatim]` ouvrirait sinon un souligné (embf), jamais fermé.
    disabled = "Disable: verbatim, embf\n* Q ?\n+ [verbatim]x[/verbatim]\n- Non\n"
    assert only(disabled).choices[0].text == "[verbatim]x[/verbatim]"


def test_latex_option_makes_the_text_latex():
    assert only("LaTeX: 1\n* Que vaut $x$ ?\n" + YES_NO).text == "Que vaut $x$ ?"
    text = "LaTeX: 1\n* Coût en $ ?\n" + YES_NO + "\n* R ?\n- A\n+ B\n"
    assert skipped(text) == [(2, "énoncé : formule non fermée")]
    assert only("LaTeX: 0\n* Coût en $ ?\n" + YES_NO).text == "Coût en \\$ ?"


# --- Images (CNT-03, IMP-08) ------------------------------------------------------------------


def with_files(text: str, files: dict[str, bytes]):
    return parse(text.encode(), "x.txt", files)


def test_image_is_stored_under_its_content_name():
    text = "* Voir !{center}[width=2cm]img/../img/b.png! ?\n" + YES_NO
    parsed = with_files(text, {"img/b.png": PNG})
    (image,) = parsed.images
    assert image.name.startswith("b-") and image.data == PNG
    assert parsed.questions[0].text == f"Voir \\includegraphics{{{image.name}}} ?"


def test_missing_image_refuses_the_file_with_the_question_line():
    text = "* Q ?\n" + YES_NO + "* Voir ?\n+ !a.png!\n- !b.png!\n"
    assert errors(text) == ["Ligne 4 : image absente : a.png", "Ligne 4 : image absente : b.png"]
    # Même dans une question qui serait écartée, et même une image PDF.
    assert errors("*<> Ouverte !a.pdf! ?\n") == ["Ligne 1 : image absente : a.pdf"]


def test_refused_image_skips_its_question_only():
    text = "".join(
        f"* {k} !{name}! ?\n" + YES_NO
        for k, name in [("PDF", "f.pdf"), ("GIF", "g.gif"), ("PNG", "b.png")]
    )
    parsed = with_files(text, {"f.pdf": b"%PDF", "g.gif": b"GIF89a", "b.png": PNG})
    assert parsed.skipped == (
        (1, "image PDF ou EPS, à convertir en PNG, JPEG ou SVG : f.pdf"),
        (4, "format d'image non pris en charge (PNG, JPEG ou SVG) : g.gif"),
    )
    assert [question.line for question in parsed.questions] == [7]
    assert len(parsed.images) == 1


def test_images_of_skipped_questions_are_not_kept():
    text = "* !b.png! [[$x]] ?\n" + YES_NO + "* Q ?\n" + YES_NO
    parsed = with_files(text, {"b.png": PNG})
    assert parsed.skipped == ((1, "énoncé : formule non fermée"),)
    assert parsed.images == ()
