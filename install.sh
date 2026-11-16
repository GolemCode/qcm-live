#!/bin/sh
# Installe ou met à jour QCM Live (INS-01, INS-02), sans droits d'administrateur :
#
#   curl -LsSf https://raw.githubusercontent.com/GolemCode/qcm-live/main/install.sh | sh
#
# - Données (base, réglages, environnement Python) : ~/.local/share/qcm-live (ou
#   QCM_DATA_DIR), lisibles par vous seul. Relancer la même ligne met à jour le code sans
#   toucher aux données.
# - uv (gestionnaire Python d'Astral) est installé dans ~/.local/bin s'il manque ; il installe
#   à son tour Python si besoin. Il ne sert qu'à l'installation.
# - QCM_LIVE_ARCHIVE=<fichier.tar.gz> installe depuis une archive locale (clé USB, tests) au
#   lieu de télécharger la dernière version.
#
# Tout est dans une fonction, appelée à la dernière ligne : un téléchargement interrompu
# n'exécute rien.

set -eu

ARCHIVE_URL="https://github.com/GolemCode/qcm-live/archive/refs/heads/main.tar.gz"
UV_INSTALLER="https://astral.sh/uv/install.sh"

say() {
    printf '%s\n' "$*"
}

fail() {
    say "Erreur : $*" >&2
    exit 1
}

find_uv() {
    if command -v uv >/dev/null 2>&1; then
        command -v uv
    elif [ -x "$HOME/.local/bin/uv" ]; then
        printf '%s\n' "$HOME/.local/bin/uv"
    else
        say "Installation de uv (gestionnaire Python, dans ~/.local/bin)…" >&2
        command -v curl >/dev/null 2>&1 || fail "curl est nécessaire pour installer uv."
        curl -LsSf "$UV_INSTALLER" | env UV_NO_MODIFY_PATH=1 sh >&2 || fail "uv n'a pas pu être installé."
        [ -x "$HOME/.local/bin/uv" ] || fail "uv introuvable après son installation."
        printf '%s\n' "$HOME/.local/bin/uv"
    fi
}

main() {
    [ -n "${HOME:-}" ] || fail "la variable HOME est vide."
    data="${QCM_DATA_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/qcm-live}"
    if [ -d "$data/app" ]; then
        say "Mise à jour de QCM Live dans $data"
    else
        say "Installation de QCM Live dans $data"
    fi
    mkdir -p "$data"
    chmod 700 "$data"

    uv=$(find_uv)

    work=$(mktemp -d)
    trap 'rm -rf "$work"' EXIT
    if [ -n "${QCM_LIVE_ARCHIVE:-}" ]; then
        cp "$QCM_LIVE_ARCHIVE" "$work/app.tar.gz"
    else
        say "Téléchargement de la dernière version…"
        curl -LsSf "$ARCHIVE_URL" -o "$work/app.tar.gz" || fail "téléchargement impossible."
    fi

    # Nouvelle version à côté de l'ancienne, environnement Python mis à jour, puis échange :
    # en cas d'échec avant l'échange, l'ancienne version reste en place.
    rm -rf "$data/app.new" "$data/app.old"
    mkdir "$data/app.new"
    tar -xzf "$work/app.tar.gz" -C "$data/app.new" --strip-components=1
    say "Préparation de l'environnement Python…"
    UV_PROJECT_ENVIRONMENT="$data/venv" "$uv" sync --quiet --locked --no-dev --project "$data/app.new" \
        || fail "l'installation des dépendances a échoué (rien n'a été remplacé)."
    if [ -d "$data/app" ]; then
        mv "$data/app" "$data/app.old"
    fi
    mv "$data/app.new" "$data/app"
    rm -rf "$data/app.old"

    # Questions (compte, démonstration) au clavier, même sous `curl | sh` où l'entrée
    # standard est le script : on lit le terminal, s'il y en a un.
    if (exec </dev/tty) 2>/dev/null; then
        input=/dev/tty
    else
        input=/dev/null
    fi
    QCM_DATA_DIR="$data" PYTHONPATH="$data/app" "$data/venv/bin/python" -m config.install <"$input"
}

main "$@"
