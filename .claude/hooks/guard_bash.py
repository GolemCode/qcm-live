"""Hook PreToolUse (Bash) : refuse les commandes qui contournent les filets de sécurité.

Refusé :
- contourner les hooks git (`--no-verify`, `commit -n`, variable `SKIP=` de pre-commit) ;
- pousser en force (`--force`, `-f`, refspec `+…`) ;
- pousser ou committer sur main (seuls les tags d'incrément peuvent partir de main) ;
- lire le fichier .env par une commande courante (secrets locaux) ;
- masquer le code de retour d'une vérification (pipe sans pipefail, `;` ou `|| true` après elle).

L'analyse se fait sur les arguments (shlex) et non sur le texte brut, pour ne pas confondre
une option avec le contenu d'un message de commit.

Ce garde évite les accidents : ce n'est pas une frontière de sécurité. Un filtre de texte ne voit
pas ce que fait un programme (voir REX.md, section R, et test_guard_is_not_a_security_boundary).
"""

from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys

SEPARATOR_CHARS = set(";&|()\n")
READERS = {
    "cat",
    "less",
    "more",
    "head",
    "tail",
    "grep",
    "rg",
    "sed",
    "awk",
    "bat",
    "xxd",
    "od",
    "strings",
    "nl",
    "source",
    ".",
    "base64",
    "tac",
    "cut",
    "sort",
    "uniq",
    "cp",
    "mv",
    "dd",
    "diff",
    "cmp",
    "vi",
    "vim",
    "nano",
}
# Options courtes de `git commit` qui consomment l'argument suivant (ex. -m "message").
COMMIT_VALUE_FLAGS = set("mFCct")
COMMIT_LONG_VALUE_FLAGS = {"--message", "--file", "--reuse-message", "--reedit-message"}
# Options globales de git qui consomment l'argument suivant (ex. git -C dir commit).
GIT_GLOBAL_VALUE_FLAGS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}
TAG_REF = re.compile(r"^(refs/tags/)?inc-(\d+|r)$")
# Redirections qui contiennent « & » sans être un séparateur de commandes (2>&1, &>fichier).
FD_REDIRECT = re.compile(r"\d*>&\d*-?|&>>?")
HEREDOC = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?")
VERIFY_TARGETS = {"lint", "test", "e2e", "check", "verify", "verify-tests", "accept"}
VERIFY_TOOLS = {"pytest", "pyright", "ruff"}
UV_RUN_VALUE_FLAGS = {"--env-file", "--with", "--python", "-p", "--group", "--project"}
PIPE_MASKS = (
    "Un pipe remplace le code de retour de la vérification par celui de la dernière commande "
    "(incident I5). Écrire `set -o pipefail; …`, ou rediriger vers un fichier puis le lire."
)
SEQUENCE_MASKS = (
    "Après une vérification, `;` ou `|| …` remplace son code de retour par celui de la commande "
    "suivante (incident I6). Enchaîner avec `&&`, ou terminer par `exit $code`."
)

Segment = tuple[list[str], str]  # (arguments d'une commande simple, séparateur qui la suit)


def _segments(text: str) -> list[Segment]:
    """Découpe en commandes simples ; le retour à la ligne sépare les commandes.

    Lève ValueError si le texte n'est pas analysable (guillemet non fermé…).
    """
    lexer = shlex.shlex(FD_REDIRECT.sub(" ", text), posix=True, punctuation_chars=";&|()\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    lexer.commenters = ""
    segments: list[Segment] = []
    current: list[str] = []
    for word in lexer:
        if all(char in SEPARATOR_CHARS for char in word):
            if current:
                segments.append((current, word))
            current = []
        else:
            current.append(word)
    if current:
        segments.append((current, ""))
    return segments


def split_segments(command: str) -> list[Segment]:
    """Comme _segments ; si le tout n'est pas analysable (apostrophe dans un heredoc…),
    analyse ligne par ligne en ignorant les seules lignes illisibles."""
    try:
        return _segments(command)
    except ValueError:
        segments: list[Segment] = []
        for line in command.splitlines():
            try:
                segments.extend(_segments(line))
            except ValueError:
                continue
        return segments


def split_commands(command: str) -> list[list[str]]:
    return [tokens for tokens, _ in split_segments(command)]


def strip_heredocs(command: str) -> str:
    """Retire le corps des heredocs : du texte (un message de commit…), pas des commandes."""
    kept: list[str] = []
    delimiter = None
    for line in command.split("\n"):
        if delimiter is not None:
            if line.strip() == delimiter:
                delimiter = None
            continue
        kept.append(line)
        if match := HEREDOC.search(line):
            delimiter = match.group(1)
    return "\n".join(kept)


def is_verification(tokens: list[str]) -> bool:
    """`[VAR=x] [timeout n] [uv run [options]] make check|pytest|pyright|ruff|python -m pytest`."""
    i = 0
    while i < len(tokens) and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[i]):
        i += 1
    if i < len(tokens) and tokens[i] == "timeout":
        i += 2
    if tokens[i : i + 2] == ["uv", "run"]:
        i += 2
        while i < len(tokens) and tokens[i].startswith("-"):
            i += 2 if tokens[i] in UV_RUN_VALUE_FLAGS else 1
    if i >= len(tokens):
        return False
    head = tokens[i].rsplit("/", 1)[-1]
    args = tokens[i + 1 :]
    if head == "make":
        return "-n" not in args and any(arg in VERIFY_TARGETS for arg in args)
    if head in VERIFY_TOOLS:
        return "--version" not in args
    return head.startswith("python") and args[:2] == ["-m", "pytest"]


def masks_exit_code(command: str) -> str | None:
    """Renvoie la raison si le code de retour d'une vérification ne survit pas à la commande."""
    segments = split_segments(strip_heredocs(command))
    pipefail = False
    for index, (tokens, separator) in enumerate(segments):
        if tokens[0] == "set" and any("pipefail" in token for token in tokens):
            pipefail = True
        if not is_verification(tokens):
            continue
        rest = segments[index + 1 :]
        if separator in {"|", "|&"}:
            if not pipefail:
                return PIPE_MASKS
        elif rest and separator != "&&" and rest[-1][0][0] != "exit":
            return SEQUENCE_MASKS
    return None


def git_subcommand(tokens: list[str]) -> tuple[str, list[str]] | None:
    """Pour `[VAR=x …] git [options globales] sous-commande args`, renvoie (sous-commande, args)."""
    i = 0
    while i < len(tokens) and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", tokens[i]):
        i += 1
    if i >= len(tokens) or tokens[i] != "git":
        return None
    i += 1
    while i < len(tokens) and tokens[i].startswith("-"):
        i += 2 if tokens[i] in GIT_GLOBAL_VALUE_FLAGS else 1
    if i >= len(tokens):
        return None
    return tokens[i], tokens[i + 1 :]


def commit_bypasses_hooks(args: list[str]) -> bool:
    skip_next = False
    for arg in args:
        if skip_next:
            skip_next = False
            continue
        if arg == "--no-verify":
            return True
        if arg in COMMIT_LONG_VALUE_FLAGS:
            skip_next = True
            continue
        if arg.startswith("--"):
            continue
        if arg.startswith("-") and len(arg) > 1:
            for char in arg[1:]:
                if char == "n":
                    return True
                if char in COMMIT_VALUE_FLAGS:
                    # La suite du groupe (ou l'argument suivant) est la valeur de l'option.
                    skip_next = arg.endswith(char)
                    break
    return False


def check_push(args: list[str], branch: str) -> str | None:
    positional = [a for a in args if not a.startswith("-")]
    if "--force" in args or any(re.fullmatch(r"-[a-zA-Z]*f[a-zA-Z]*", a) for a in args):
        return "Pas de push forcé (utiliser --force-with-lease sur une branche de travail)."
    refspecs = positional[1:]
    if any(ref.startswith("+") for ref in refspecs):
        return "Pas de push forcé (refspec « + »)."
    for ref in refspecs:
        destination = ref.split(":")[-1]
        if destination in {"main", "refs/heads/main"}:
            return "Pas de push sur main : passer par une PR (branche inc/<n>-<slug>)."
    if branch == "main" and not (refspecs and all(TAG_REF.match(r) for r in refspecs)):
        return "Depuis main, seuls les tags d'incrément (inc-<n>) peuvent être poussés."
    return None


def names_env_file(token: str) -> bool:
    value = token.rsplit("=", 1)[-1]  # dd if=.env
    return value == ".env" or value.endswith("/.env")


def decide(command: str, branch: str) -> str | None:
    """Renvoie la raison du refus, ou None si la commande est acceptée."""
    masked = masks_exit_code(command)
    if masked:
        return masked
    for tokens in split_commands(command):
        if any(t.startswith("SKIP=") for t in tokens):
            return "Ne pas désactiver les hooks pre-commit (SKIP=…)."
        if tokens[0] in READERS and any(names_env_file(t) for t in tokens[1:]):
            return "Le fichier .env contient des secrets : ne pas le lire."
        sub = git_subcommand(tokens)
        if sub is None:
            continue
        name, args = sub
        if name == "commit":
            if commit_bypasses_hooks(args):
                return "Ne pas contourner les hooks git (--no-verify / -n)."
            if branch == "main":
                return "Pas de commit sur main : créer une branche inc/<n>-<slug>."
        elif name == "push":
            reason = check_push(args, branch)
            if reason:
                return reason
    return None


def current_branch() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip()


def main() -> int:
    payload = json.load(sys.stdin)
    command = payload.get("tool_input", {}).get("command", "")
    reason = decide(command, current_branch())
    if reason:
        json.dump(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            },
            sys.stdout,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
