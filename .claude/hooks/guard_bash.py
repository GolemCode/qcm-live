"""Hook PreToolUse (Bash) : refuse les commandes qui contournent les filets de sécurité.

Refusé : contourner les hooks git (--no-verify), pousser en force, pousser ou committer
sur main, lire le fichier .env (secrets locaux).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys

READERS = r"(cat|less|more|head|tail|grep|rg|sed|awk|bat|xxd|od|strings|nl|source|\.)"

RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"--no-verify\b"), "Ne pas contourner les hooks git (--no-verify)."),
    (
        re.compile(r"\bgit\s+commit\b[^|;&]*\s-[a-zA-Z]*n[a-zA-Z]*\b"),
        "Ne pas contourner les hooks git (commit -n).",
    ),
    (
        re.compile(r"\bgit\s+push\b[^|;&]*\s(--force(?!-with-lease)\b|-[a-zA-Z]*f\b)"),
        "Pas de push forcé (utiliser --force-with-lease sur une branche de travail).",
    ),
    (
        re.compile(r"\bgit\s+push\b[^|;&]*\s(\S+:)?(refs/heads/)?main\b"),
        "Pas de push sur main : passer par une PR (branche inc/<n>-<slug>).",
    ),
    (
        re.compile(
            rf"(^|[\s;&|(]){READERS}(?=[ \t])[^|;&\n]*[\s/'\"=]\.env(?=$|[\s'\";|&])",
            re.MULTILINE,
        ),
        "Le fichier .env contient des secrets : ne pas le lire.",
    ),
]


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


def decide(command: str, branch: str) -> str | None:
    """Renvoie la raison du refus, ou None si la commande est acceptée."""
    for pattern, reason in RULES:
        if pattern.search(command):
            return reason
    if branch == "main":
        if re.search(r"\bgit\s+commit\b", command):
            return "Pas de commit sur main : créer une branche inc/<n>-<slug>."
        if re.search(r"\bgit\s+push\s*($|[;&|])", command):
            return "Pas de push depuis main : passer par une PR."
    return None


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
