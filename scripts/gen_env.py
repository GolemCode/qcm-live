"""Crée le fichier .env local avec une clé secrète aléatoire (jamais versionné).

Ne réécrit jamais un .env existant. Usage : `uv run --no-project python scripts/gen_env.py`.
"""

import secrets
import sys
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def main() -> int:
    if ENV_FILE.exists():
        print(f"{ENV_FILE.name} existe déjà : inchangé.")
        return 0
    ENV_FILE.write_text(
        "# Généré par scripts/gen_env.py — local, jamais versionné.\n"
        f"DJANGO_SECRET_KEY={secrets.token_urlsafe(50)}\n"
        "DJANGO_DEBUG=1\n",
        encoding="utf-8",
    )
    ENV_FILE.chmod(0o600)
    print(f"{ENV_FILE.name} créé.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
