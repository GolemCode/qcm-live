"""Lecture d'un fichier AMC-TXT (SPEC.md §2 ter ; IMP-01 à IMP-07).

Fonction pure : des octets en entrée ; en sortie, les questions à importer, celles qui sont
écartées et les textes ignorés, ou toutes les erreurs de syntaxe (le fichier est alors refusé).
Les règles suivent le lecteur AMC-TXT d'AMC (`AMC::Filter::plain`) : mêmes formes de ligne,
mêmes options, mêmes contrôles. Il est plus strict là où AMC ignorerait un élément sans le dire.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from decimal import Decimal
from pathlib import PurePath

from bank.scoring import (
    LETTERS,
    MAX_CHOICES,
    SCORING_MAX_LENGTH,
    ScoringError,
    format_scoring,
    parse_points,
    parse_scoring,
)

MAX_BYTES = 1_000_000
TITLE_MAX_LENGTH = 200
CHOICE_MAX_LENGTH = 200
GROUP_LABEL_MAX_LENGTH = 100
MAX_REPORTED_ERRORS = 20
TOO_LARGE = "Fichier trop volumineux : 1 Mo au plus."

# Options du fichier reconnues par AMC (`options_names` de plain.pm), sans distinction de casse.
# fmt: off
OPTIONS = (
    "Title", "Presentation", "Code", "Lang", "Font", "BoxColor", "PaperSize",
    "AnswerSheetTitle", "AnswerSheetPresentation", "AnswerSheetColumns", "CompleteMulti",
    "SeparateAnswerSheet", "AutoMarks", "DefaultScoringM", "DefaultScoringS", "L-Question",
    "L-None", "L-Name", "L-Student", "LaTeX", "LaTeX-Preambule", "LaTeX-BeginDocument",
    "LaTeX-BeginCopy", "LaTeX-EndCopy", "PDF-BeginCopy", "PDF-EndCopy", "LaTeXEngine",
    "xltxtra", "ShuffleQuestions", "Columns", "QuestionBlocks", "Arabic", "ArabicFont",
    "Disable", "ManualDuplex", "SingleSided", "L-OpenText", "L-OpenReserved",
    "CodeDigitsDirection", "PackageOptions", "NameFieldWidth", "NameFieldLines",
    "NameFieldLinespace", "TitleWidth", "Pages", "RandomSeed", "PreAssociation",
    "PreAssociationKey", "PreAssociationName",
)
# fmt: on
QUESTION_OPTIONS = frozenset(
    ["horiz", "columns", "ordered", "id", "name", "indicative", "next", "first", "last", "group"]
)
GROUP_OPTIONS = frozenset(["shuffle", "columns", "group", "numquestions", "needspace"])

COMMENT_RE = re.compile(r"^\s*#")
INCLUDE_RE = re.compile(r"^\s*IncludeFile:", re.IGNORECASE)
OPTION_RE = re.compile(rf"^\s*({'|'.join(map(re.escape, OPTIONS))}):\s*(.*)", re.IGNORECASE)
UNKNOWN_OPTION_RE = re.compile(r"^([a-z0-9-]+):", re.IGNORECASE)
GROUP_RE = re.compile(r"^\s*\*([()])(?:\[([^\]]*)\])?\s*(.*)")
QUESTION_RE = re.compile(r"^\s*(\*{1,2})(?:<([^>]*)>)?(?:\[([^\]]*)\])?(?:\{([^}]*)\})?\s*(.*)")
CHOICE_RE = re.compile(r"^\s*([+-])(?:\[([^\]]*)\])?(?:\{([^}]*)\})?\s*(.*)")
VERBATIM_OPEN, VERBATIM_CLOSE = "[verbatim]", "[/verbatim]"
FALSE_RE = re.compile(r"^\s*(no|false|0)\s*$", re.IGNORECASE)  # `parse_bool` d'AMC

# Contenus prévus en I14 : (module d'AMC que `Disable:` désactive, marque, ce qu'elle annonce).
CONTENT_MARKS = (
    ("verbatim", re.compile(re.escape(VERBATIM_OPEN)), "code"),
    ("latex", re.compile(r"\[latex\].*?\[/latex\]", re.DOTALL), "formule ou LaTeX"),
    ("local_latex", re.compile(r"\[\[(?:(?!\]\]).)+\]\]"), "formule"),
    ("images", re.compile(r"!(?:\{[^!\s]+\})?(?:\[[^!\s]+\])?[^!\s]+!"), "image"),
    ("embf", re.compile(r"\[\||\|\]"), "code"),
    ("embf", re.compile(r"\[[_*/]|[_*/]\]"), "mise en forme"),
    ("title", re.compile(r"\[==|==\]"), "mise en forme"),
)
LATEX_SPECIAL_RE = re.compile(r"[\\$%&~^_{}#]")


@dataclass(frozen=True)
class ParsedChoice:
    text: str
    correct: bool
    points: Decimal | None = None


@dataclass(frozen=True)
class ParsedQuestion:
    line: int
    text: str
    multiple: bool
    scoring: str  # celui qui s'applique (IMP-04), sous la forme enregistrée (BAR-01)
    choices: tuple[ParsedChoice, ...]
    none_of_these: bool = False
    ordered: bool = False
    label: str = ""  # étiquette du groupe AMC (IMP-06)

    def key(self) -> ParsedQuestion:
        """Ce qui rend deux questions identiques (IMP-07) : tout, sauf la ligne et l'étiquette."""
        return replace(self, line=0, label="")


@dataclass(frozen=True)
class ParsedFile:
    title: str
    questions: tuple[ParsedQuestion, ...]
    skipped: tuple[tuple[int, str], ...]  # (ligne, raison), IMP-03
    ignored: tuple[tuple[int, str], ...]  # (ligne, texte) des groupes, IMP-06


class AmcSyntaxError(ValueError):
    """Fichier refusé (IMP-02) ; `messages` donne la ligne et la raison de chaque erreur."""

    def __init__(self, messages: list[str]) -> None:
        super().__init__("\n".join(messages))
        self.messages = messages


# --- Lecture des lignes -----------------------------------------------------------------------


@dataclass
class _Text:
    """Texte d'un élément : les lignes d'un paragraphe sont jointes par une espace, les
    paragraphes séparés par une ligne vide."""

    paragraphs: list[list[str]] = field(default_factory=lambda: [[]])

    def add(self, line: str) -> None:
        if line.strip():
            self.paragraphs[-1].append(line.strip())
        elif self.paragraphs[-1]:
            self.paragraphs.append([])

    def __str__(self) -> str:
        return "\n\n".join(" ".join(p) for p in self.paragraphs if p)


@dataclass
class _Choice:
    line: int
    correct: bool
    scoring: str | None
    text: _Text


@dataclass
class _Question:
    line: int
    multiple: bool
    open: bool
    options: dict[str, str]
    scoring: str
    label: str
    text: _Text
    choices: list[_Choice] = field(default_factory=list)


def _split_options(raw: str) -> dict[str, str]:
    """`[ordered,group=geo]` : `clé=valeur`, ou `clé` seule (valeur 1), comme AMC."""
    options = {}
    for part in re.split(r",+", raw):
        key, _, value = part.partition("=")
        if key.strip():  # AMC ignore les parties vides
            options[key.strip()] = value.strip() if "=" in part else "1"
    return options


class _Reader:
    def __init__(self) -> None:
        self.errors: list[tuple[int, str]] = []
        self.options: dict[str, _Text] = {}  # nom en minuscules
        self.option_lines: dict[str, int] = {}
        self.questions: list[_Question] = []
        self.ignored: list[tuple[int, _Text]] = []
        self.groups: list[tuple[int, str]] = []  # groupes ouverts : (ligne, étiquette)
        self.target: _Text | None = None  # élément que prolongent les lignes suivantes
        self.question: _Question | None = None  # question qui reçoit les propositions
        self.verbatim: int | None = None  # ligne d'un bloc [verbatim] encore ouvert

    def error(self, line: int, message: str) -> None:
        self.errors.append((line, message))

    def read(self, lines: list[str]) -> None:
        for number, line in enumerate(lines, start=1):
            if self.verbatim is not None:  # bloc brut : rien n'y est interprété
                self._continue(number, line)
                if VERBATIM_CLOSE in line.lower():
                    self.verbatim = None
                continue
            if VERBATIM_OPEN in line and VERBATIM_CLOSE not in line.lower():
                self._continue(number, line)  # comme AMC : ni question ni commentaire
                self.verbatim = number
            else:
                self._line(number, line)
        if self.verbatim is not None:
            self.error(self.verbatim, "bloc [verbatim] jamais fermé")
        for line, _ in self.groups:
            self.error(line, "groupe ouvert et jamais fermé")

    def _line(self, number: int, line: str) -> None:
        if COMMENT_RE.match(line):
            return
        if INCLUDE_RE.match(line):
            self.error(number, "IncludeFile : un fichier inclus n'est pas pris en charge")
        elif match := OPTION_RE.match(line):
            self.question = None
            name = match.group(1).lower()
            self.target = self.options[name] = _Text()
            self.option_lines[name] = number
            self.target.add(match.group(2))
        elif match := UNKNOWN_OPTION_RE.match(line):
            self.error(number, f"option inconnue « {match.group(1)} »")
        elif match := GROUP_RE.match(line):
            self._group(number, *match.groups())
        elif match := QUESTION_RE.match(line):
            self._question(number, *match.groups())
        elif match := CHOICE_RE.match(line):
            self._choice(number, *match.groups())
        else:
            self._continue(number, line)

    def _continue(self, number: int, line: str) -> None:
        if self.target is not None:
            self.target.add(line)
        elif line.strip():
            self.error(number, "texte avant le premier élément du fichier")

    def _group(self, number: int, kind: str, raw: str | None, text: str) -> None:
        self.question = None
        options = _split_options(raw or "")
        for name in options.keys() - GROUP_OPTIONS:
            self.error(number, f"option de groupe inconnue « {name} »")
        if kind == "(":
            label = options.get("group", self.groups[-1][1] if self.groups else "")
            self.groups.append((number, label))
        elif self.groups:
            self.groups.pop()
        else:
            self.error(number, "groupe fermé sans avoir été ouvert")
        self.target = _Text()
        self.target.add(text)
        self.ignored.append((number, self.target))

    def _question(
        self,
        number: int,
        stars: str,
        open_: str | None,
        raw: str | None,
        scoring: str | None,
        text: str,
    ) -> None:
        options = _split_options(raw or "")
        for name in sorted(options.keys() - QUESTION_OPTIONS):
            self.error(number, f"option de question inconnue « {name} »")
        label = options.get("group", self.groups[-1][1] if self.groups else "")
        self.target = _Text()
        self.target.add(text)
        self.question = _Question(
            number,
            len(stars) == 2,
            open_ is not None,
            options,
            (scoring or "").strip(),
            label,
            self.target,
        )
        self.questions.append(self.question)

    def _choice(
        self, number: int, sign: str, _letter: str | None, scoring: str | None, text: str
    ) -> None:
        if self.question is None:
            self.error(number, "proposition hors d'une question")
            return
        self.target = _Text()
        self.target.add(text)
        self.question.choices.append(_Choice(number, sign == "+", scoring, self.target))


# --- Contrôles et questions écartées ----------------------------------------------------------


@dataclass(frozen=True)
class _Settings:
    complete_multi: bool
    default_scoring: dict[bool, tuple[str, str]]  # multiple -> (option, barème)
    latex: bool
    disabled: str


def _settings(options: dict[str, _Text]) -> _Settings:
    def value(name: str) -> str:
        return str(options[name]) if name in options else ""

    def boolean(name: str, default: bool) -> bool:
        if name not in options:
            return default
        return bool(value(name)) and not FALSE_RE.match(value(name))  # vide : faux

    return _Settings(
        complete_multi=boolean("completemulti", True),
        default_scoring={
            False: ("DefaultScoringS", value("defaultscorings")),
            True: ("DefaultScoringM", value("defaultscoringm")),
        },
        latex=boolean("latex", False),
        disabled=value("disable"),
    )


def _syntax(question: _Question) -> str | None:
    """Contrôles d'AMC sur une question fermée (`check_answers`)."""
    if question.open:
        return None
    if len(question.choices) < 2:
        return "question avec moins de 2 propositions"
    n_correct = sum(choice.correct for choice in question.choices)
    if not question.multiple and "indicative" not in question.options and n_correct != 1:
        plural = "s" if n_correct > 1 else ""
        return f"question simple avec {n_correct} bonne{plural} réponse{plural}"
    return None


def _content(texts: list[str], settings: _Settings) -> str | None:
    for module, mark, what in CONTENT_MARKS:
        if not re.search(rf"\b{module}\b", settings.disabled) and any(map(mark.search, texts)):
            return f"{what} : pas encore pris en charge"
    if settings.latex and any(map(LATEX_SPECIAL_RE.search, texts)):
        return "LaTeX (option LaTeX: 1) : pas encore pris en charge"
    return None


class _Skip(Exception):
    """Question valide mais non prise en charge : écartée, avec la raison (IMP-03)."""


def _scoring(question: _Question, settings: _Settings) -> str:
    """Barème qui s'applique (IMP-04) ; `_Skip` s'il est refusé."""
    if question.scoring:
        source, text = "barème", question.scoring
    else:
        option, text = settings.default_scoring[question.multiple]
        source = f"barème par défaut du fichier ({option})"
        if not text and question.multiple and all(c.scoring is None for c in question.choices):
            text = "haut=2"  # défaut implicite d'AMC-TXT pour une question multiple
    try:
        scoring = format_scoring(parse_scoring(text))
    except ScoringError as error:
        raise _Skip(f"{source} : {error}") from None
    if len(scoring) > SCORING_MAX_LENGTH:
        raise _Skip(f"{source} de plus de {SCORING_MAX_LENGTH} caractères")
    return scoring


def _convert(question: _Question, settings: _Settings) -> ParsedQuestion:
    """La question prête à importer ; `_Skip` donne la raison de l'écarter (IMP-03)."""
    if question.open:
        raise _Skip("question ouverte")
    if "indicative" in question.options:
        raise _Skip("question indicative")
    text, choices = str(question.text), question.choices
    if reason := _content([text, *(str(c.text) for c in choices)], settings):
        raise _Skip(reason)
    if len(choices) > MAX_CHOICES:
        raise _Skip(f"plus de {MAX_CHOICES} propositions")
    if not text:
        raise _Skip("énoncé vide")
    scoring = _scoring(question, settings)
    parsed = []
    for letter, choice in zip(LETTERS, choices, strict=False):
        choice_text = str(choice.text)
        if not choice_text:
            raise _Skip(f"proposition {letter} vide")
        if len(choice_text) > CHOICE_MAX_LENGTH:
            raise _Skip(f"proposition {letter} de plus de {CHOICE_MAX_LENGTH} caractères")
        points = None
        if choice.scoring is not None:
            if question.multiple:
                raise _Skip("barème sur une proposition d'une question multiple")
            try:
                points = parse_points(choice.scoring)
            except ScoringError as error:
                raise _Skip(f"barème de la proposition {letter} : {error}") from None
        parsed.append(ParsedChoice(choice_text, choice.correct, points))
    none_of_these = question.multiple and settings.complete_multi
    if question.multiple and not none_of_these and not any(c.correct for c in parsed):
        raise _Skip("question multiple sans bonne réponse")
    if len(question.label) > GROUP_LABEL_MAX_LENGTH:
        raise _Skip(f"nom de groupe de plus de {GROUP_LABEL_MAX_LENGTH} caractères")
    return ParsedQuestion(
        line=question.line,
        text=text,
        multiple=question.multiple,
        scoring=scoring,
        choices=tuple(parsed),
        none_of_these=none_of_these,
        ordered="ordered" in question.options,
        label=question.label,
    )


# --- Point d'entrée ---------------------------------------------------------------------------


def _decode(data: bytes) -> str:
    """UTF-8 ; un caractère nul (UTF-16, fichier binaire) est refusé, comme dans `roster`."""
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        position = error.start
    else:
        if "\x00" not in text:
            return text
        position = data.index(b"\x00")
    line = data[:position].count(b"\n") + 1
    raise AmcSyntaxError(
        [f"Ligne {line} : le fichier n'est pas en UTF-8. Enregistrez-le en UTF-8."]
    )


def _report(errors: list[tuple[int, str]]) -> list[str]:
    errors.sort(key=lambda error: error[0])
    messages = [f"Ligne {line} : {message}" for line, message in errors[:MAX_REPORTED_ERRORS]]
    if (hidden := len(errors) - MAX_REPORTED_ERRORS) > 0:
        messages.append(f"… et {hidden} autres erreurs.")
    return messages


def parse(data: bytes, filename: str) -> ParsedFile:
    """Lit un fichier AMC-TXT ; `AmcSyntaxError` s'il est refusé (IMP-02)."""
    if len(data) > MAX_BYTES:
        raise AmcSyntaxError([TOO_LARGE])
    reader = _Reader()
    reader.read([line.rstrip("\r") for line in _decode(data).split("\n")])
    errors = reader.errors
    for question in reader.questions:
        if reason := _syntax(question):
            errors.append((question.line, reason))
    title = " ".join(str(reader.options.get("title", "")).split())
    if len(title) > TITLE_MAX_LENGTH:
        message = f"titre de plus de {TITLE_MAX_LENGTH} caractères"
        errors.append((reader.option_lines["title"], message))
    if errors:
        raise AmcSyntaxError(_report(errors))
    if not reader.questions:
        raise AmcSyntaxError(["Le fichier ne contient aucune question."])

    settings = _settings(reader.options)
    questions: list[ParsedQuestion] = []
    skipped: list[tuple[int, str]] = []
    seen: dict[ParsedQuestion, int] = {}
    for draft in reader.questions:
        try:
            question = _convert(draft, settings)
        except _Skip as reason:
            skipped.append((draft.line, str(reason)))
            continue
        if (first := seen.get(question.key())) is not None:
            skipped.append((draft.line, f"doublon de la question de la ligne {first}"))
            continue
        seen[question.key()] = draft.line
        questions.append(question)
    ignored = tuple((line, str(text)) for line, text in reader.ignored if str(text))
    return ParsedFile(
        title=title or PurePath(filename).stem.strip()[:TITLE_MAX_LENGTH] or "QCM importé",
        questions=tuple(questions),
        skipped=tuple(skipped),
        ignored=ignored,
    )
