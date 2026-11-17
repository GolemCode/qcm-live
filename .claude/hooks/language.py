"""Hooks PostToolUse et Stop : un message de Claude écrit en anglais.

La conversation avec le commanditaire se tient en français (CLAUDE.md, règle 7). La consigne
n'a pas suffi : en I11, 71 messages sur 75 étaient en anglais (rex/M.md).

- PostToolUse : le texte écrit juste avant l'appel d'outil est en anglais ? Claude en est
  averti aussitôt (`additionalContext`), au milieu du tour. Ce hook n'arrête rien.
- Stop : un message du tour est en anglais ? Claude est renvoyé au travail pour le redire
  en français, une fois par arrêt. C'est une entrée Stop à part de `stop_check.py` : une
  erreur ici ne bloque pas `make check`.

C'est une détection heuristique, après coup : le message anglais est déjà affiché, et un
message très court ou mêlé de français peut passer. Elle compte des mots-outils, hors code.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Mots-outils, étalonnés sur les journaux des sessions I0 à I11 : aucun message français
# détecté, tous les messages anglais d'I11 détectés.
_ENGLISH_WORDS = (
    "the and is are was were to of that this these those with for it it's its not but be been "
    "have has had will now i i'm i'll i've let let's which from so then what we you there "
    "they should would could need done all into also than only just here my our your "
    "everything next running writing"
)
ENGLISH = frozenset(_ENGLISH_WORDS.split())
_FRENCH_WORDS = (
    "le la les et est des du un une que qui pour pas dans sur avec je ce cette il elle au aux "
    "mais ou donc puis sont à de ne se qu'il c'est j'ai d'abord n'est l'on été être fait plus "
    "par sans comme"
)
FRENCH = frozenset(_FRENCH_WORDS.split())
CODE = re.compile(r"```.*?```|`[^`\n]*`", re.DOTALL)
WORD = re.compile(r"[\w'./-]+")
NOT_A_WORD = re.compile(r"[\d/._-]")  # identifiants, chemins, versions : ni anglais ni français
TAIL_BYTES = 1_000_000  # un journal de session dépasse 10 Mo ; le tour en cours tient à la fin
HOOK_FEEDBACK = "Stop hook feedback"  # début du retour d'un hook Stop, au journal
RULE = "Langue (CLAUDE.md, règle 7) : la conversation avec le commanditaire se tient en français."


def looks_english(text: str) -> bool:
    """Le texte, hors code, est-il en anglais ? Un message sans mot-outil ne l'est pas."""
    prose = CODE.sub(" ", text.replace("\u2019", "'")).lower()  # apostrophe typographique
    tokens = (word.rstrip(".-/'") for word in WORD.findall(prose))  # « now. » compte
    words = [word for word in tokens if word and not NOT_A_WORD.search(word)]
    english = sum(word in ENGLISH for word in words)
    french = sum(word in FRENCH for word in words)
    return (english >= 2 and french == 0) or (english >= 3 and english > 2 * french)


def read_tail(path: Path, size: int = TAIL_BYTES) -> list[dict]:
    """Les dernières lignes du journal (JSONL). Une ligne coupée ou illisible est ignorée."""
    try:
        with path.open("rb") as stream:
            stream.seek(0, 2)
            start = max(0, stream.tell() - size)
            stream.seek(start)
            data = stream.read()
    except OSError:
        return []
    lines = data.split(b"\n")
    if start:
        lines = lines[1:]  # première ligne coupée par le décalage
    rows = []
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _blocks(row: dict) -> list[dict]:
    content = (row.get("message") or {}).get("content")
    return (
        [block for block in content if isinstance(block, dict)] if isinstance(content, list) else []
    )


def _main_thread(row: dict, kind: str) -> bool:
    """Une ligne du fil principal (les sous-agents écrivent leurs propres lignes)."""
    return row.get("type") == kind and not row.get("isSidechain")


def _values(row: dict, kind: str, key: str) -> list[str]:
    """Les blocs `kind` d'une ligne de Claude, fil principal seulement."""
    if not _main_thread(row, "assistant"):
        return []
    return [block.get(key, "") for block in _blocks(row) if block.get("type") == kind]


def _texts(row: dict) -> list[str]:
    return _values(row, "text", "text")


def _calls(row: dict) -> list[str]:
    return _values(row, "tool_use", "id")


def _said_to_claude(row: dict) -> str:
    content = (row.get("message") or {}).get("content")
    if isinstance(content, str):
        return content
    return " ".join(block.get("text", "") for block in _blocks(row))


def _is_prompt(row: dict) -> bool:
    """Un message entrant qui ouvre un nouveau tour : du commanditaire, ou le retour d'un hook Stop.

    Ni un résultat d'outil, ni une ligne méta (rappel système, message d'une autre session) :
    elles arrivent au milieu d'un tour.
    """
    if not _main_thread(row, "user"):
        return False
    if any(block.get("type") == "tool_result" for block in _blocks(row)):
        return False
    return not row.get("isMeta") or _said_to_claude(row).startswith(HOOK_FEEDBACK)


def texts_before_tool(rows: list[dict], tool_use_id: str | None) -> list[str]:
    """Le texte écrit juste avant cet appel d'outil (le dernier appel, sans identifiant).

    Seul le premier de plusieurs appels parallèles reçoit ce texte : un avertissement par
    message, pas un par appel.
    """
    ids = [_calls(row) for row in rows]
    calls = [i for i, found in enumerate(ids) if found]
    matching = [i for i in calls if tool_use_id in ids[i]]
    if tool_use_id is not None:  # appel d'un sous-agent, ou pas encore écrit : rien à dire
        calls = matching
    end = (calls or [None])[-1]
    if end is None:
        return []
    texts = _texts(rows[end])
    for i in range(end - 1, -1, -1):
        if _main_thread(rows[i], "user") or ids[i]:
            break
        texts[:0] = _texts(rows[i])
    return texts


def turn_texts(rows: list[dict]) -> list[str]:
    """Les messages de Claude depuis le dernier message entrant."""
    starts = [i for i, row in enumerate(rows) if _is_prompt(row)]
    begin = starts[-1] + 1 if starts else 0
    return [text for row in rows[begin:] for text in _texts(row)]


def _english(texts: list[str]) -> list[str]:
    return [text for text in texts if looks_english(text)]


def _quote(text: str) -> str:
    """Un extrait d'une ligne, de 100 caractères au plus."""
    excerpt = " ".join(text.split())
    return excerpt if len(excerpt) <= 100 else excerpt[:99] + "…"


def _rows(payload: dict) -> list[dict]:
    path = payload.get("transcript_path")
    return read_tail(Path(path)) if path else []


def turn_problem(rows: list[dict], last_message: str | None = None) -> str | None:
    """Pour le hook Stop : un message du tour en anglais, à redire en français.

    Au moment du hook Stop, le journal n'a pas toujours le dernier message (constaté dans une
    vraie session) : il arrive aussi par `last_assistant_message`, compté une seule fois.
    """
    texts = turn_texts(rows)
    if last_message and last_message.strip() not in (text.strip() for text in texts):
        texts.append(last_message)
    english = _english(texts)
    if not english:
        return None
    return (
        f"{RULE} {len(english)} message(s) de ce tour en anglais, dont « {_quote(english[0])} ». "
        "Redis en français, brièvement, ce que tu viens d'annoncer, et continue en français."
    )


def stop_problem(payload: dict) -> str | None:
    """`turn_problem` à partir de la charge du hook Stop.

    Le retour d'un hook Stop entre au journal comme un message entrant, qui ouvre un nouveau
    tour. Après un renvoi pour la langue, l'arrêt suivant passe (une relance par arrêt) ;
    après un renvoi pour une autre raison (`stop_check.py`), la langue est contrôlée.
    """
    rows = _rows(payload)
    if payload.get("stop_hook_active"):
        prompts = [row for row in rows if _is_prompt(row)]
        if prompts and RULE in _said_to_claude(prompts[-1]):
            return None
    return turn_problem(rows, payload.get("last_assistant_message"))


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    if not isinstance(payload, dict):
        return 0
    if payload.get("hook_event_name") == "Stop":
        problem = stop_problem(payload)
        if problem:
            print(problem, file=sys.stderr)
            return 2
        return 0
    english = _english(texts_before_tool(_rows(payload), payload.get("tool_use_id")))
    if english:
        context = (
            f"{RULE} Ton dernier message était en anglais : « {_quote(english[0])} ». "
            "Écris les suivants en français."
        )
        output = {"hookEventName": "PostToolUse", "additionalContext": context}
        print(json.dumps({"hookSpecificOutput": output}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
