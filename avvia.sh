#!/usr/bin/env bash
# Avvia Dashboard. Nessuna connessione di rete, nessuna installazione richiesta.
cd "$(dirname "$(readlink -f "$0")")" || exit 1
exec python3 main.py "$@"
