"""Consommation de Claude Code sur une période : tokens et appels, par agent.

Lit les transcriptions locales de Claude Code (`~/.claude/projects/<projet>/*.jsonl` et
`<session>/subagents/*.jsonl`). Un même appel à l'API s'y écrit sur plusieurs lignes (une par
bloc de contenu) avec le même identifiant : il n'est compté qu'une fois.

Tokens = entrée + écriture du cache + lecture du cache + sortie, ce que facture l'API à des
tarifs différents : la répartition est donnée à côté du total.

Usage : uv run --no-env-file python scripts/usage.py 2026-11-17T01:54 2026-11-17T13:26
"""

from __future__ import annotations

import itertools
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Au-delà de cet écart entre deux appels, la session attend le commanditaire : pas du travail.
IDLE = 15 * 60
KINDS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")


def transcripts_dir(project: Path) -> Path:
    return Path.home() / ".claude" / "projects" / str(project.resolve()).replace("/", "-")


def agent_type(transcript: Path) -> str:
    meta = transcript.with_suffix(".meta.json")
    if transcript.parent.name != "subagents":
        return "principal"
    try:
        return json.loads(meta.read_text(encoding="utf-8")).get("agentType", "?")
    except (OSError, ValueError):
        return "?"


def calls(transcript: Path, start: datetime, end: datetime):
    """(identifiant, horodatage, usage) de chaque appel à l'API de la période."""
    with transcript.open(encoding="utf-8") as lines:
        for line in lines:
            if '"usage"' not in line:
                continue
            try:
                entry = json.loads(line)
                stamp = datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00"))
                message = entry["message"]
                usage = message["usage"]
            except (ValueError, KeyError, TypeError):
                continue
            if start <= stamp.astimezone() <= end:
                yield message.get("id") or entry.get("uuid"), stamp, usage


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    start, end = (datetime.fromisoformat(arg).astimezone() for arg in argv)
    folder = transcripts_dir(Path.cwd())
    seen: set[str] = set()
    totals: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    stamps: list[datetime] = []
    for transcript in sorted(folder.glob("*.jsonl")) + sorted(folder.glob("*/subagents/*.jsonl")):
        who = agent_type(transcript)
        for call_id, stamp, usage in calls(transcript, start, end):
            if call_id in seen:
                continue
            seen.add(call_id)
            stamps.append(stamp)
            totals[who]["appels"] += 1
            for kind in KINDS:
                totals[who][kind] += int(usage.get(kind) or 0)
    if not stamps:
        print("Aucun appel sur cette période.")
        return 1
    grand = sum(sum(t[k] for k in KINDS) for t in totals.values())
    stamps.sort()
    gaps = [(b - a).total_seconds() for a, b in itertools.pairwise(stamps)]
    active = sum(gap for gap in gaps if gap <= IDLE)
    first, last = stamps[0].astimezone(), stamps[-1].astimezone()
    print(f"Période : {first:%Y-%m-%d %H:%M} → {last:%Y-%m-%d %H:%M}")
    print(f"Temps actif : {active / 3600:.1f} h (écarts de plus de {IDLE // 60} min exclus)")
    print(f"Total : {grand / 1e6:.1f} M tokens, {sum(t['appels'] for t in totals.values())} appels")
    print("agent              appels   total M   entrée  cache écrit  cache lu   sortie (M)")
    for who, t in sorted(totals.items(), key=lambda item: -sum(item[1][k] for k in KINDS)):
        parts = " ".join(f"{t[k] / 1e6:9.2f}" for k in KINDS)
        print(f"{who:18} {t['appels']:6} {sum(t[k] for k in KINDS) / 1e6:9.1f} {parts}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
