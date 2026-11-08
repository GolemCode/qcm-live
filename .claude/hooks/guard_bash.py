"""Hook PreToolUse (Bash) : refuse les commandes qui contournent les filets de sécurité.

Refusé :
- contourner les hooks git (`--no-verify`, `commit -n`, variable `SKIP=` de pre-commit) ;
- pousser en force (`--force`, `-f`, refspec `+…`) ;
- pousser ou committer sur main (seuls les tags d'incrément peuvent partir de main) ;
- nommer le fichier .env dans une commande, ou le charger par `uv run --env-file` (secrets
  locaux), sauf quelques commandes autorisées, dont certaines peuvent le lire (`git commit -F`) ;
- masquer le code de retour d'une vérification (pipe sans pipefail, `;` ou `|| true` après elle).

L'analyse se fait sur les arguments (shlex) et non sur le texte brut, pour ne pas confondre
une option avec le contenu d'un message de commit. Le corps d'un heredoc n'est pas analysé :
c'est du texte, sauf s'il est donné à un shell.

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
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
# Commandes autorisées à nommer .env : usages courants, mais pas une garantie (`make -f .env`).
ENV_FILE_ALLOWED = {"ls", "stat", "test", "[", "make", "uv"}
GIT_ENV_FILE_ALLOWED = {"commit", "log", "status", "check-ignore", "ls-files"}
# Préfixes qui ne changent pas la commande exécutée.
BARE_PREFIXES = {"!", "time", "command", "nohup", "exec"}
ENV_VALUE_FLAGS = {"-u", "--unset", "-C", "--chdir", "-S", "--split-string"}
TIMEOUT_VALUE_FLAGS = {"-k", "--kill-after", "-s", "--signal"}
# Options courtes de `git commit` qui consomment l'argument suivant (ex. -m "message").
COMMIT_VALUE_FLAGS = set("mFCct")
COMMIT_LONG_VALUE_FLAGS = {"--message", "--file", "--reuse-message", "--reedit-message"}
# Options globales de git qui consomment l'argument suivant (ex. git -C dir commit).
GIT_GLOBAL_VALUE_FLAGS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace"}
TAG_REF = re.compile(r"^(refs/tags/)?inc-(\d+|r)$")
# Redirections qui contiennent « & » sans être un séparateur de commandes (2>&1, &>fichier).
FD_REDIRECT = re.compile(r"\d*>&\d*-?|&>>?")
HEREDOC = re.compile(r"(?<!<)<<(?!<)-?\s*(?:'([^']+)'|\"([^\"]+)\"|(\w+))")
SHELL = re.compile(r"(?<![\w.-])(ba|z|da)?sh\b|/dev/stdin")
PIPES = {"|", "|&"}
VERIFY_TARGETS = {"lint", "test", "e2e", "check", "verify", "verify-tests", "accept"}
VERIFY_TOOLS = {"pytest", "pyright", "ruff"}
UV_RUN_VALUE_FLAGS = {
    "--directory",
    "--env-file",
    "--extra",
    "--group",
    "--index",
    "--only-group",
    "--package",
    "--project",
    "--python",
    "--with",
    "--with-editable",
    "--with-requirements",
    "-p",
}
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
            # `&&\n` vaut `&&`, et `)` laisse la place au séparateur qui le suit : `(a) && b`.
            separator = word.strip("()\n") or "\n"
            if current:
                segments.append((current, separator))
            elif segments and separator != "\n":
                segments[-1] = (segments[-1][0], separator)
            current = []
        else:
            current.append(word)
    if current:
        segments.append((current, ""))
    return segments


def split_segments(command: str) -> list[Segment]:
    """Comme _segments ; si le tout n'est pas analysable (apostrophe dans une ligne…),
    analyse ligne par ligne en ignorant les seules lignes illisibles.
    Une suite de ligne (`\\` en fin de ligne) ne sépare pas les arguments d'une commande."""
    command = command.replace("\\\n", " ")
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


def strip_heredocs(command: str) -> str:
    """Retire le corps des heredocs : du texte (un message de commit…), pas des commandes.

    Dans le doute, le texte reste analysé : si un shell figure sur la ligne (`cat <<EOF | bash`),
    ou si aucune ligne de fin n'existe (`<<` dans une chaîne, `$((1<<2))`).
    """
    lines = command.split("\n")
    kept: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        kept.append(line)
        i += 1
        match = HEREDOC.search(line)
        if match and not SHELL.search(line):
            delimiter = next(group for group in match.groups() if group)
            end = next((j for j in range(i, len(lines)) if lines[j].strip() == delimiter), None)
            if end is not None:
                i = end + 1
    return "\n".join(kept)


def skip_options(tokens: list[str], start: int, value_flags: set[str]) -> int:
    """Indice du premier mot qui n'est pas une option, à partir de `start`."""
    i = start
    while i < len(tokens) and tokens[i].startswith("-"):
        i += 2 if tokens[i] in value_flags else 1
    return i


def effective_command(tokens: list[str]) -> list[str]:
    """La commande réelle, sans ses préfixes : `VAR=x`, `time`, `env`, `timeout n`, `uv run`…"""
    i = 0
    while i < len(tokens):
        if ASSIGNMENT.match(tokens[i]) or tokens[i] in BARE_PREFIXES:
            i += 1
        elif tokens[i] == "env":
            i = skip_options(tokens, i + 1, ENV_VALUE_FLAGS)
        elif tokens[i] == "timeout":
            i = skip_options(tokens, i + 1, TIMEOUT_VALUE_FLAGS) + 1
        elif tokens[i : i + 2] == ["uv", "run"]:
            i = skip_options(tokens, i + 2, UV_RUN_VALUE_FLAGS)
        else:
            break
    return tokens[i:]


def is_verification(command: list[str]) -> bool:
    """`make check`, `pytest`, `pyright`, `ruff`, `python -m pytest`… (sans préfixe)."""
    if not command:
        return False
    head = command[0].rsplit("/", 1)[-1]
    args = command[1:]
    if head == "make":
        return "-n" not in args and any(arg in VERIFY_TARGETS for arg in args)
    if head in VERIFY_TOOLS:
        return "--version" not in args
    return head.startswith("python") and args[:2] == ["-m", "pytest"]


def masks_exit_code(segments: list[Segment]) -> str | None:
    """Renvoie la raison si le code de retour d'une vérification ne survit pas à la commande.

    Après la vérification, seul `&&` le conserve jusqu'au bout, ou un `|` sous pipefail, ou
    un `exit` final qui rend un vrai code (`exit $code`, jamais `exit` seul ni `exit 0`).
    """
    if not segments:
        return None
    final = segments[-1][0]
    honest_exit = len(final) == 2 and final[0] == "exit" and final[1] != "0"
    pipefail = False
    for index, (tokens, _) in enumerate(segments):
        if tokens[0] == "set" and "pipefail" in tokens:
            pipefail = "+o" not in tokens
        if not is_verification(effective_command(tokens)):
            continue
        separators = [separator for _, separator in segments[index:-1]]
        if segments[-1][1] == "&":
            separators.append("&")
        # Plus loin dans la chaîne, un pipe ne touche plus au code de la vérification.
        if separators and separators[0] in PIPES and not pipefail:
            return PIPE_MASKS
        if not honest_exit and any(s != "&&" and s not in PIPES for s in separators):
            return SEQUENCE_MASKS
    return None


def git_subcommand(command: list[str]) -> tuple[str, list[str]] | None:
    """Pour `git [options globales] sous-commande args`, renvoie (sous-commande, args)."""
    if not command or command[0] != "git":
        return None
    i = skip_options(command, 1, GIT_GLOBAL_VALUE_FLAGS)
    if i >= len(command):
        return None
    return command[i], command[i + 1 :]


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
    value = re.split(r"[=<>:]", token)[-1]  # dd if=.env, cat<.env, git show HEAD:.env
    return value == ".env" or value.endswith("/.env")


def loads_env_file(tokens: list[str]) -> bool:
    """`--env-file .env`, ou `--env-file=.env`, quelle que soit la commande lancée ensuite."""
    return any(
        (word == "--env-file" and names_env_file(following))
        or (word.startswith("--env-file=") and names_env_file(word))
        for word, following in zip(tokens, [*tokens[1:], ""], strict=True)
    )


def may_name_env_file(command: list[str]) -> bool:
    if command[0] == "git":
        sub = git_subcommand(command)
        return sub is not None and sub[0] in GIT_ENV_FILE_ALLOWED
    return command[0] in ENV_FILE_ALLOWED


def decide(command: str, branch: str) -> str | None:
    """Renvoie la raison du refus, ou None si la commande est acceptée."""
    segments = split_segments(strip_heredocs(command))
    masked = masks_exit_code(segments)
    if masked:
        return masked
    for tokens, _ in segments:
        if any(t.startswith("SKIP=") for t in tokens):
            return "Ne pas désactiver les hooks pre-commit (SKIP=…)."
        if loads_env_file(tokens):
            return "Le fichier .env contient des secrets : ne pas le charger (--env-file)."
        effective = effective_command(tokens)
        if (
            effective
            and not may_name_env_file(effective)
            and any(names_env_file(t) for t in effective)
        ):
            return "Le fichier .env contient des secrets : ne pas le lire."
        sub = git_subcommand(effective)
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
