"""Mode classe (CLA-01) : le PC de l'enseignant sert l'application aux téléphones de la salle.

Usage : `make classe` (ou `uv run --env-file .env python -m config.classroom`), avec
`--port` pour changer de port et `--adresse` pour imposer l'adresse annoncée si la détection
choisit la mauvaise interface réseau (VPN, par exemple).

- Serveur de production (waitress), sans mode debug, quel que soit `DJANGO_DEBUG` dans `.env`.
- Il écoute sur toutes les interfaces : les téléphones le joignent par le réseau local.
- L'adresse à ouvrir sur les téléphones est affichée dans le terminal et projetée au tableau.
"""

from __future__ import annotations

import argparse
import os
import socket
import sys
from collections.abc import Mapping, Sequence

DEFAULT_PORT = 8000
DEFAULT_HOSTS = "localhost,127.0.0.1"
# Adresse de documentation (RFC 5737) : « connecter » une socket UDP vers elle choisit
# l'interface de la route par défaut, sans envoyer aucun paquet.
PROBE = ("192.0.2.1", 9)
# Un fil par requête en cours : une classe interroge l'état chaque seconde, et ces
# requêtes sont brèves. 4 (valeur par défaut de waitress) laisse peu de marge.
THREADS = 16


def lan_address() -> str:
    """Adresse IPv4 du PC sur le réseau local ; 127.0.0.1 s'il n'a pas de réseau."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        try:
            probe.connect(PROBE)
        except OSError:
            return "127.0.0.1"
        return probe.getsockname()[0]


def classroom_environ(environ: Mapping[str, str], host: str, port: int) -> dict[str, str]:
    """Réglages imposés par le mode classe : jamais de debug, et l'adresse du réseau local
    acceptée par Django et projetée au tableau."""
    hosts = environ.get("DJANGO_ALLOWED_HOSTS", DEFAULT_HOSTS)
    return {
        "DJANGO_DEBUG": "0",
        "DJANGO_ALLOWED_HOSTS": f"{hosts},{host}",
        "QCM_JOIN_URL": f"http://{host}:{port}/",
    }


def banner(join_url: str, port: int) -> str:
    return (
        "QCM Live, mode classe.\n"
        f"  Sur les téléphones des étudiants, ouvrir : {join_url}\n"
        f"  Sur ce PC, espace enseignant : http://localhost:{port}/prof/\n"
        "Ctrl+C pour arrêter."
    )


def _port(value: str) -> int:
    port = int(value)
    if not 1 <= port <= 65535:
        raise ValueError(value)
    return port


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="make classe", description="Mode classe de QCM Live.")
    parser.add_argument("--port", type=_port, default=DEFAULT_PORT, help="port d'écoute")
    parser.add_argument("--adresse", help="adresse du PC à annoncer (détectée par défaut)")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:  # pragma: no cover — testé de bout en bout
    args = parse_args(argv)
    host = args.adresse or lan_address()
    os.environ.update(classroom_environ(os.environ, host, args.port))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

    import django
    from django.conf import settings
    from django.core.management import call_command
    from waitress.server import create_server

    django.setup()
    if settings.DEBUG:
        raise SystemExit("Le mode classe refuse de démarrer en mode debug.")
    call_command("migrate", interactive=False, verbosity=0)

    from config.wsgi import application

    # Toutes les interfaces : les téléphones viennent du réseau local.
    server = create_server(application, host="0.0.0.0", port=args.port, threads=THREADS)  # noqa: S104
    print(banner(settings.JOIN_URL, args.port), flush=True)
    if host.startswith("127."):
        print("Attention : aucun réseau détecté, les téléphones ne pourront pas se connecter.")
    try:
        server.run()
    except KeyboardInterrupt:
        print("Serveur arrêté.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
