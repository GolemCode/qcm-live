"""LaTeX léger des énoncés et des propositions (CNT-01 à CNT-04) : chaque forme reconnue, chaque
refus, et le texte qui reste tel quel."""

import pytest

from bank.content import (
    Break,
    Code,
    ContentError,
    Image,
    Math,
    Style,
    Text,
    image_alt,
    images,
    parse,
    plain,
)


@pytest.mark.parametrize(
    "text",
    ["Remise de 50 % sur A & B", "x_1 ^ 2 ~ 3 # 4", "{environ}", "}{", "a\n\nb", ""],
)
def test_text_is_written_as_is(text):
    assert parse(text) == ([Text(text)] if text else [])


@pytest.mark.parametrize(
    ("text", "shown"),
    [
        (r"3 \$", "3 $"),
        (r"\% \& \_ \# \{ \}", "% & _ # { }"),
        (r"a\textbackslash{}b", "a\\b"),
        (r"a\textbackslash b", "a\\ b"),
    ],
)
def test_escapes(text, shown):
    assert parse(text) == [Text(shown)]


@pytest.mark.parametrize(
    ("text", "math"),
    [
        (r"$\frac{1}{2}$", Math(r"\frac{1}{2}", False)),
        ("$$ x^2 $$", Math("x^2", True)),
        (r"\(a\)", Math("a", False)),
        (r"\[a\]", Math("a", True)),
        (r"$a \$ b$", Math(r"a \$ b", False)),  # un dollar échappé ne ferme pas la formule
        (r"\(\{a\}\)", Math(r"\{a\}", False)),
    ],
)
def test_formulas(text, math):
    assert parse(text)[0] == math


def test_formula_among_text():
    assert parse("Que vaut $x$ ?") == [Text("Que vaut "), Math("x", False), Text(" ?")]


@pytest.mark.parametrize(
    ("text", "error"),
    [
        ("Que vaut $x ?", "formule non fermée"),
        ("$$x$", "formule non fermée"),
        (r"\(x", "formule non fermée"),
        (r"\[x\)", "formule non fermée"),
        ("$ $", "formule vide"),
        (r"\hspace{1cm}", r"commande LaTeX non prise en charge : \hspace"),
        (r"\'e", r"commande LaTeX non prise en charge : \'"),
        ("a \\", "barre oblique inverse seule en fin de texte : écrire \\textbackslash{}"),
        (r"\textbf gras", r"argument manquant après \textbf"),
        (r"\textbf{gras", r"accolade non fermée après \textbf"),
        (r"\textbf{a {b}", r"accolade non fermée après \textbf"),
        (r"\verb", r"délimiteur manquant après \verb"),
        (r"\verb x", r"délimiteur manquant après \verb"),
        (r"\verb|a", r"\verb non fermé"),
        ("\\verb|a\nb|", r"\verb non fermé"),
        (r"\begin{verbatim} a", "bloc verbatim non fermé"),
        (r"\begin{itemize}", "environnement LaTeX non pris en charge : itemize"),
        (r"\begin", "environnement LaTeX non pris en charge"),
        (r"\includegraphics", r"argument manquant après \includegraphics"),
        (r"\includegraphics[width=2cm", r"crochet non fermé après \includegraphics"),
        (r"\includegraphics{a.png", r"accolade non fermée après \includegraphics"),
        (r"\includegraphics{ }", "nom d'image vide"),
    ],
)
def test_refused(text, error):
    with pytest.raises(ContentError) as raised:
        parse(text)
    assert str(raised.value) == error


def test_emphasis_nests_and_balances_braces():
    assert parse(r"\textbf{a \emph{b} {c}} \textit{d}\underline{$x$}") == [
        Style("strong", (Text("a "), Style("em", (Text("b"),)), Text(" {c}"))),
        Text(" "),
        Style("em", (Text("d"),)),
        Style("u", (Math("x", False),)),
    ]


def test_nesting_is_bounded():  # sinon RecursionError, donc une erreur 500
    deep = "\\textbf{" * 1000 + "x" + "}" * 1000
    with pytest.raises(ContentError) as raised:
        parse(deep)
    assert str(raised.value) == "mise en forme imbriquée sur plus de 20 niveaux"
    assert parse("\\textbf{" * 20 + "x" + "}" * 20)  # tout juste accepté


def test_escaped_brace_in_an_argument():
    assert parse(r"\textbf{\}}") == [Style("strong", (Text("}"),))]


def test_inline_code():
    assert parse(r"\texttt{a_b {c}} \verb|\x{|") == [Code("a_b {c}"), Text(" "), Code(r"\x{")]


def test_verbatim_block_keeps_spaces_and_lines():
    text = "Que fait ce code ?\n\\begin{verbatim}\ndef f(x):\n    return $x\n\\end{verbatim}\nSuite"
    assert parse(text) == [
        Text("Que fait ce code ?\n"),
        Code("def f(x):\n    return $x", block=True),
        Text("Suite"),
    ]


def test_line_break():
    assert parse(r"a\\b") == [Text("a"), Break(), Text("b")]


def test_images():
    text = r"Voir \includegraphics[width=2cm]{ graphe.png } et \textbf{\includegraphics{b.svg}}"
    assert parse(text)[1] == Image("graphe.png")  # sans les espaces
    assert images(text) == ["graphe.png", "b.svg"]


@pytest.mark.parametrize(
    ("text", "shown"),
    [
        (r"Que vaut $\frac{1}{2}$ ?", r"Que vaut \frac{1}{2} ?"),
        (r"\textbf{a} \texttt{b}\\c \includegraphics{g-0123abcd.png}", "a b\nc image g"),
        ("$x", "$x"),  # refusé : tel quel
    ],
)
def test_plain(text, shown):
    assert plain(text) == shown


@pytest.mark.parametrize(
    ("name", "alt"),
    [("graphe-3fa9c2d1.png", "image graphe"), ("img/logo.svg", "image logo"), ("a-b", "image a-b")],
)
def test_image_alt(name, alt):
    assert image_alt(name) == alt
