"""`make accept INC=n` : exigences de l'incrément n et tests qui les vérifient.

Si `make verify` a fini vert sur ce même état du dépôt (REX exclu), son résultat est repris sans
relancer les tests (6 à 7 min en I13 et I14). Sinon, les tests sont relancés, comme avant I15.
"""

from __future__ import annotations

import os
import sys

from tests import spec_trace


def main(argv: list[str]) -> int:
    increment = int(argv[0])
    record = spec_trace.RECORD_FILE
    loaded = None
    if record.exists():
        loaded = spec_trace.load_record(
            record.read_text(encoding="utf-8"), spec_trace.state_key(spec_trace.ROOT)
        )
    if loaded is None:
        print("Aucun `make verify` vert sur cet état du dépôt : les tests sont relancés.")
        sys.stdout.flush()
        command = [sys.executable, "-m", "pytest", "--spec-check", f"--spec-inc={increment}", "-q"]
        os.execv(sys.executable, command)  # noqa: S606 : remplace ce processus, code de retour compris
    coverage, finished_at = loaded
    requirements = spec_trace.parse_spec(spec_trace.SPEC_FILE.read_text(encoding="utf-8"))
    up_to = spec_trace.current_increment(spec_trace.PYPROJECT.read_text(encoding="utf-8"))
    print(
        f"Résultat repris du `make verify` vert du {finished_at} "
        "(dépôt inchangé depuis, REX exclu)."
    )
    print(f"Couverture de SPEC.md (incrément I{increment})")
    for line in spec_trace.report_lines(requirements, coverage, up_to=up_to, only=increment):
        print(line)
    missing = spec_trace.missing_requirements(requirements, coverage, up_to=up_to, only=increment)
    if missing:
        print("ÉCHEC : exigence(s) sans test E2E passé : " + ", ".join(r.id for r in missing))
        return 1
    print("Toutes les exigences exigibles sont vérifiées.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
