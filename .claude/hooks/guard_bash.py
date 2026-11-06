"""Hook PreToolUse (Bash) : refuse les commandes qui contournent les filets de sécurité.

Refusé :
- contourner les hooks git (`--no-verify`, `commit -n`, variable `SKIP=` de pre-commit) ;
- pousser en force (`--force`, `-f`, refspec `+…`) ;
- pousser ou committer sur main (seuls les tags d'incrément peuvent partir de main) ;
- lire le fichier .env (secrets locaux).

L'analyse se fait sur les arguments (shlex) et non sur le texte brut, pour ne pas confondre
une option avec le contenu d'un message de commit.
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
}
# Options courtes de `git commit` qui consomment l'argument suivant (ex. -m "message").
COMMIT_VALUE_FLAGS = set("mFCct")
COMMIT_LONG_VALUE_FLAGS = {"--message", "--file", "--reuse-message", "--reedit-message"}
# Options globales de git qui consomment l'argument suivant (ex. git -C dir commit).
GIT_GLOBAL_VALUE_FLAGS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}
TAG_REF = re.compile(r"^(refs/tags/)?inc-\d+$")


def _split(text: str) -> list[list[str]]:
    """Découpe en commandes simples ; le retour à la ligne sépare les commandes.

    Lève ValueError si le texte n'est pas analysable (guillemet non fermé…).
    """
    lexer = shlex.shlex(text, posix=True, punctuation_chars=";&|()\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    lexer.commenters = ""
    commands: list[list[str]] = [[]]
    for word in lexer:
        if all(char in SEPARATOR_CHARS for char in word):
            commands.append([])
        else:
            commands[-1].append(word)
    return [cmd for cmd in commands if cmd]


def split_commands(command: str) -> list[list[str]]:
    """Comme _split ; si le tout n'est pas analysable (apostrophe dans un heredoc…),
    analyse ligne par ligne en ignorant les seules lignes illisibles."""
    try:
        return _split(command)
    except ValueError:
        commands: list[list[str]] = []
        for line in command.splitlines():
            try:
                commands.extend(_split(line))
            except ValueError:
                continue
        return commands


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


def decide(command: str, branch: str) -> str | None:
    """Renvoie la raison du refus, ou None si la commande est acceptée."""
    for tokens in split_commands(command):
        if any(t.startswith("SKIP=") for t in tokens):
            return "Ne pas désactiver les hooks pre-commit (SKIP=…)."
        if tokens[0] in READERS and any(t == ".env" or t.endswith("/.env") for t in tokens[1:]):
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
