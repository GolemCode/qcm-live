"""Mode classe (CLA-01) : le PC de l'enseignant sert l'application aux téléphones de la salle.

Lancé par la commande de l'enseignant (`qcm-live`, config/launcher.py) ou, en développement,
par `make classe` (`--port` pour changer de port, `--adresse` pour imposer l'adresse annoncée).

- Serveur de production (waitress), sans mode debug, quel que soit `DJANGO_DEBUG`.
- Il écoute sur toutes les interfaces : les téléphones le joignent par le réseau local.
- Toutes les adresses du PC sont listées dans le terminal avec leur carte (CLA-02), la plus
  probable est projetée au tableau ; l'enseignant en change au tableau, sans redémarrer.
- Un pare-feu actif est signalé, avec la commande pour l'ouvrir, jamais lancée (CLA-03).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sys
from collections.abc import Callable, Sequence

from config import firewall, network
from config.network import LanAddress

DEFAULT_PORT = 8000
GUIDE_URL = "https://github.com/GolemCode/qcm-live/blob/main/GUIDE.md"
# Un fil par requête en cours : une classe interroge l'état chaque seconde, et ces
# requêtes sont brèves. 4 (valeur par défaut de waitress) laisse peu de marge.
THREADS = 16
# Adresse imposée à la main : une adresse IPv4 ou un nom de machine, sans schéma ni port.
HOST_RE = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?")


def projected(adresse: str | None, addresses: Sequence[LanAddress]) -> str:
    """Adresse annoncée : celle imposée, sinon la plus probable du PC ; 127.0.0.1 sans réseau."""
    if adresse:
        return adresse
    return addresses[0]["address"] if addresses else "127.0.0.1"


def classroom_environ(host: str, port: int, addresses: Sequence[LanAddress] = ()) -> dict[str, str]:
    """Réglages imposés par le mode classe : jamais de debug, l'adresse du réseau local
    projetée au tableau (et donc acceptée par Django, voir `JOIN_URL` dans settings.py), les
    autres adresses du PC (acceptées aussi, pour en changer sans redémarrer), et l'espace
    enseignant réservé au PC lui-même."""
    return {
        "DJANGO_DEBUG": "0",
        "QCM_JOIN_URL": f"http://{host}:{port}/",
        "QCM_LAN_ADDRESSES": json.dumps(list(addresses)),
        "QCM_TEACHER_LOCAL_ONLY": "1",
    }


def banner(
    join_url: str,
    port: int,
    addresses: Sequence[LanAddress] = (),
    advices: Sequence[firewall.Advice] = (),
) -> str:
    lines = [
        "QCM Live, mode classe.",
        f"  Sur les téléphones des étudiants, ouvrir : {join_url}",
        f"  Sur ce PC, espace enseignant : http://localhost:{port}/prof/",
    ]
    if addresses:
        lines.append(
            "Adresses de ce PC (pour en projeter une autre : « Changer d'adresse », au tableau) :"
        )
        for item in addresses:
            virtual = " (réseau virtuel)" if item["virtual"] else ""
            lines.append(f"  {item['address']:<16} {item['interface']}{virtual}")
    if advices:
        lines.append("Pare-feu : il peut bloquer les téléphones. Pour ouvrir le port :")
        for advice in advices:
            lines.append(f"  {advice.text}")
            lines += [f"    {command}" for command in advice.commands]
        lines.append("  QCM Live ne modifie jamais le pare-feu.")
    lines += [f"Guide de l'enseignant : {GUIDE_URL}", "Ctrl+C pour arrêter."]
    return "\n".join(lines)


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if sys.platform != "win32":  # sous Windows, cette option permet de voler le port
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("0.0.0.0", port))  # noqa: S104 — comme le serveur
        except OSError:
            return False
    return True


def port_taken(port: int) -> str:
    return (
        f"Le port {port} est déjà utilisé : QCM Live est peut-être déjà lancé, dans une autre "
        f"fenêtre. Sinon, choisissez un autre port : --port {port + 1}."
    )


def _host(value: str) -> str:
    if not HOST_RE.fullmatch(value):
        raise ValueError(value)
    return value


def add_server_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="port d'écoute")
    parser.add_argument("--adresse", type=_host, help="adresse du PC à annoncer")


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="make classe", description="Mode classe de QCM Live.")
    add_server_arguments(parser)
    return parser.parse_args(argv)


def serve(
    adresse: str | None,
    port: int,
    *,
    before_migrate: Callable[[], None] | None = None,
    on_ready: Callable[[str], None] | None = None,
) -> int:  # pragma: no cover — testé de bout en bout (CLA-01, INS-03)
    """Prépare l'environnement, applique les migrations et sert l'application jusqu'à Ctrl+C.
    `before_migrate` : sauvegarde du lanceur ; `on_ready(adresse de l'espace enseignant)` :
    ouverture du navigateur, une fois le port ouvert."""
    if not port_free(port):
        print(port_taken(port), file=sys.stderr)
        return 1
    addresses = network.lan_addresses()
    host = projected(adresse, addresses)
    environ = classroom_environ(host, port, addresses)
    os.environ.update(environ)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

    import django
    from django.core.management import call_command
    from waitress.server import create_server

    django.setup()  # avec l'environnement ci-dessus
    if before_migrate:
        before_migrate()
    call_command("migrate", interactive=False, verbosity=0)
    from config.wsgi import application

    try:
        # Toutes les interfaces : les téléphones viennent du réseau local.
        server = create_server(application, host="0.0.0.0", port=port, threads=THREADS)  # noqa: S104
    except OSError:
        print(port_taken(port), file=sys.stderr)
        return 1
    if host.startswith("127."):
        print("Attention : aucun réseau détecté, les téléphones ne pourront pas se connecter.")
    advices = [firewall.advice(found, port) for found in firewall.detect()]
    print(banner(environ["QCM_JOIN_URL"], port, addresses, advices), flush=True)
    if on_ready:
        on_ready(f"http://localhost:{port}/prof/")
    try:
        server.run()
    except KeyboardInterrupt:
        print("Serveur arrêté.")
    return 0


def main(argv: Sequence[str] | None = None) -> int:  # pragma: no cover — testé de bout en bout
    args = parse_args(argv)
    return serve(args.adresse, args.port)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
