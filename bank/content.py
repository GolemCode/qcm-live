"""Contenu d'un énoncé ou d'une proposition : du LaTeX léger (CNT-01 à CNT-04).

Module pur. Hors des formules et des commandes reconnues, le texte s'écrit tel quel (« 50 % »,
« A & B », « x_1 ») : seuls `$` et `\\` sont spéciaux. Reconnus :

- formules : `$…$`, `\\(…\\)` en ligne ; `$$…$$`, `\\[…\\]` en bloc (rendues par KaTeX) ;
- code : `\\texttt{…}`, `\\verb|…|`, `\\begin{verbatim}…\\end{verbatim}` ;
- mise en forme : `\\textbf`, `\\textit`, `\\emph`, `\\underline` ;
- image : `\\includegraphics[options]{nom}`, les options étant ignorées ;
- `\\\\` (saut de ligne), `\\$ \\% \\& \\_ \\# \\{ \\}` et `\\textbackslash{}`.

Hors d'un argument, une accolade est du texte ; dans un argument, les accolades s'équilibrent.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass

ESCAPES = frozenset("$%&_#{}")
STYLES = {"textbf": "strong", "textit": "em", "emph": "em", "underline": "u"}
COMMAND_RE = re.compile(r"[A-Za-z]+|.", re.DOTALL)
VERBATIM_BEGIN, VERBATIM_END = r"\begin{verbatim}", r"\end{verbatim}"


MAX_NESTING = 20


class ContentError(ValueError):
    """Texte refusé ; le message dit pourquoi (« formule non fermée »)."""


@dataclass(frozen=True)
class Text:
    text: str


@dataclass(frozen=True)
class Math:
    tex: str
    display: bool


@dataclass(frozen=True)
class Code:
    text: str
    block: bool = False


@dataclass(frozen=True)
class Image:
    name: str


@dataclass(frozen=True)
class Style:
    tag: str  # strong, em ou u
    children: tuple[Node, ...]


@dataclass(frozen=True)
class Break:
    pass


Node = Text | Math | Code | Image | Style | Break


class _Parser:
    def __init__(self, source: str) -> None:
        self.source = source
        self.pos = 0
        self.level = 0  # arguments ouverts : l'analyse est récursive

    def nodes(self, in_argument: bool) -> list[Node]:
        """Contenu jusqu'à la fin, ou jusqu'à l'accolade qui ferme l'argument (non consommée)."""
        out: list[Node] = []
        text: list[str] = []
        depth = 0

        def flush() -> None:
            if text:
                out.append(Text("".join(text)))
                text.clear()

        source = self.source
        while self.pos < len(source):
            char = source[self.pos]
            if char == "$":
                flush()
                out.append(self.math_dollar())
            elif char == "\\":
                node = self.command()
                if isinstance(node, str):
                    text.append(node)
                else:
                    flush()
                    out.append(node)
            elif in_argument and char == "{":
                depth += 1
                text.append(char)
                self.pos += 1
            elif in_argument and char == "}":
                if depth == 0:
                    break
                depth -= 1
                text.append(char)
                self.pos += 1
            else:
                text.append(char)
                self.pos += 1
        flush()
        if in_argument and depth:
            raise ContentError("accolade non fermée")
        return out

    def math_dollar(self) -> Math:
        display = self.source.startswith("$$", self.pos)
        opening = "$$" if display else "$"
        return self.math_until(self.pos + len(opening), opening, display)

    def math_until(self, start: int, closing: str, display: bool) -> Math:
        """Formule jusqu'au délimiteur fermant ; une commande (`\\$`, `\\}`) n'y ferme rien."""
        index = start
        source = self.source
        while index < len(source):
            if source.startswith(closing, index):
                tex = source[start:index]
                if not tex.strip():
                    raise ContentError("formule vide")
                self.pos = index + len(closing)
                return Math(tex.strip(), display)
            index += 2 if source[index] == "\\" else 1
        raise ContentError("formule non fermée")

    def command(self) -> Node | str:
        """Une commande, à partir de sa barre oblique ; une chaîne pour un caractère échappé."""
        source = self.source
        match = COMMAND_RE.match(source, self.pos + 1)
        if match is None:
            raise ContentError(
                "barre oblique inverse seule en fin de texte : écrire \\textbackslash{}"
            )
        name = match.group()
        self.pos = match.end()
        if name in ESCAPES:
            return name
        if name == "\\":
            return Break()
        if name == "(":
            return self.math_until(self.pos, r"\)", False)
        if name == "[":
            return self.math_until(self.pos, r"\]", True)
        if name == "textbackslash":
            if source.startswith("{}", self.pos):
                self.pos += 2
            return "\\"
        if name in STYLES:
            return Style(STYLES[name], tuple(self.argument(name)))
        if name == "texttt":
            return Code(_plain(self.argument(name)))
        if name == "verb":
            return self.verb()
        if name == "begin":
            return self.verbatim()
        if name == "includegraphics":
            return self.image()
        raise ContentError(f"commande LaTeX non prise en charge : \\{name}")

    def argument(self, name: str) -> list[Node]:
        if not self.source.startswith("{", self.pos):
            raise ContentError(f"argument manquant après \\{name}")
        self.pos += 1
        if self.level == MAX_NESTING:  # sinon RecursionError, donc une erreur 500
            raise ContentError(f"mise en forme imbriquée sur plus de {MAX_NESTING} niveaux")
        self.level += 1
        nodes = self.nodes(in_argument=True)
        self.level -= 1
        if self.pos >= len(self.source):
            raise ContentError(f"accolade non fermée après \\{name}")
        self.pos += 1  # l'accolade fermante
        return nodes

    def verb(self) -> Code:
        source = self.source
        if self.pos >= len(source) or source[self.pos].isspace() or source[self.pos].isalpha():
            raise ContentError("délimiteur manquant après \\verb")
        delimiter = source[self.pos]
        end = source.find(delimiter, self.pos + 1)
        if end < 0 or "\n" in source[self.pos + 1 : end]:
            raise ContentError("\\verb non fermé")
        code = source[self.pos + 1 : end]
        self.pos = end + 1
        return Code(code)

    def verbatim(self) -> Code:
        source = self.source
        start = self.pos - len(r"\begin")
        if not source.startswith(VERBATIM_BEGIN, start):
            environment = re.match(r"\{([^}]*)\}", source[self.pos :])
            name = environment.group(1) if environment else ""
            raise ContentError(f"environnement LaTeX non pris en charge : {name}".rstrip(" :"))
        body = start + len(VERBATIM_BEGIN)
        end = source.find(VERBATIM_END, body)
        if end < 0:
            raise ContentError("bloc verbatim non fermé")
        code = source[body:end]
        code = code.removeprefix("\n").removesuffix("\n")
        self.pos = end + len(VERBATIM_END)
        if source.startswith("\n", self.pos):  # le bloc finit déjà la ligne
            self.pos += 1
        return Code(code, block=True)

    def image(self) -> Image:
        source = self.source
        if source.startswith("[", self.pos):
            end = source.find("]", self.pos)
            if end < 0:
                raise ContentError("crochet non fermé après \\includegraphics")
            self.pos = end + 1
        if not source.startswith("{", self.pos):
            raise ContentError("argument manquant après \\includegraphics")
        end = source.find("}", self.pos)
        if end < 0:
            raise ContentError("accolade non fermée après \\includegraphics")
        name = source[self.pos + 1 : end]
        if not name.strip():
            raise ContentError("nom d'image vide")
        self.pos = end + 1
        return Image(name.strip())


def parse(text: str) -> list[Node]:
    """Le texte analysé ; `ContentError` s'il est refusé."""
    return _Parser(text).nodes(in_argument=False)


def walk(nodes: list[Node] | tuple[Node, ...]) -> Iterator[Node]:
    """Tous les nœuds, mise en forme comprise, dans l'ordre du texte."""
    for node in nodes:
        yield node
        if isinstance(node, Style):
            yield from walk(node.children)


def images(text: str) -> list[str]:
    """Noms des images citées, dans l'ordre ; `ContentError` si le texte est refusé."""
    return [node.name for node in walk(parse(text)) if isinstance(node, Image)]


def _plain(nodes: list[Node] | tuple[Node, ...]) -> str:
    return "".join(_plain_node(node) for node in nodes)


def _plain_node(node: Node) -> str:
    match node:
        case Text(text) | Code(text):
            return text
        case Math(tex):
            return tex
        case Image(name):
            return image_alt(name)
        case Style(_, children):
            return _plain(children)
        case Break():
            return "\n"


def plain(text: str) -> str:
    """Le texte sans balisage (attribut `aria-label`, titre) ; tel quel s'il est refusé."""
    try:
        return _plain(parse(text))
    except ContentError:
        return text


IMAGE_SUFFIX_RE = re.compile(r"-[0-9a-f]{8}$")


def image_alt(name: str) -> str:
    """Texte de remplacement d'une image : « image » et son nom d'origine (`graphe-3fa9….png`
    donne « image graphe »)."""
    stem = name.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    return f"image {IMAGE_SUFFIX_RE.sub('', stem)}"
