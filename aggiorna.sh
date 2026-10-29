#!/usr/bin/env bash
# Aggiorna Dashboard preservando i dati: l'archivio vive fuori dal codice.
set -euo pipefail

REPO="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
DATI="${XDG_DATA_HOME:-$HOME/.local/share}/Vita"
cd "$REPO"

if [ -d .git ]; then
    echo "Backup dell'archivio…"
    if [ -f "$DATI/vita.db" ]; then
        mkdir -p "$DATI/backup"
        cp "$DATI/vita.db" "$DATI/backup/vita-$(date +%Y%m%d-%H%M%S).db"
    fi
    PRIMA="$(git rev-parse --short HEAD)"
    git pull --ff-only
    echo
    echo "Novità da $PRIMA a $(git rev-parse --short HEAD):"
    git log --oneline "$PRIMA..HEAD" || true
else
    echo "Questa copia non viene da un repository git: niente da scaricare."
fi

./installa.sh
