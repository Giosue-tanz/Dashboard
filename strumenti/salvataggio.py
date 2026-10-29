#!/usr/bin/env python3
"""Salvataggio automatico dell'archivio su una chiavetta o un disco esterno.

Pensato per girare da solo ogni sera. Se la chiavetta non è infilata non è un
errore: lo script lo scrive e se ne va buono, e al prossimo giro riprova.

    python3 strumenti/salvataggio.py                    salva adesso
    python3 strumenti/salvataggio.py --cartella PERCORSO   ... e ricordalo
    python3 strumenti/salvataggio.py --installa         ogni sera alle 22:30
    python3 strumenti/salvataggio.py --disinstalla      smetti
    python3 strumenti/salvataggio.py --stato            com'è andata l'ultima volta

La copia non è un `cp`: si passa dall'API di backup di SQLite, così l'archivio
resta coerente anche se la Dashboard è aperta e ci sta scrivendo dentro.

Vengono salvati l'archivio della Dashboard e, se c'è, quello di Finance.
Restano le ultime quattordici copie di ogni archivio più la prima di ogni
mese, che non si cancella mai: un anno di storia in pochi megabyte.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import subprocess
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vita.db import DB_PATH, Database                                  # noqa: E402
from vita.salvataggio import (ORA_PREDEFINITA, acceso, disinstalla,     # noqa: E402
                              installa, prossimo_giro, salva)

# ------------------------------------------------------------------ avvio
def main() -> int:
    argomenti = argparse.ArgumentParser(description=__doc__)
    argomenti.add_argument("--cartella", default="",
                           help="dove salvare (e me lo ricordo per le prossime volte)")
    argomenti.add_argument("--installa", action="store_true",
                           help="accendi il salvataggio di ogni sera")
    argomenti.add_argument("--ora", default=ORA_PREDEFINITA, help="a che ora (22:30)")
    argomenti.add_argument("--disinstalla", action="store_true")
    argomenti.add_argument("--stato", action="store_true")
    argomenti.add_argument("--silenzioso", action="store_true",
                           help="scrive solo se qualcosa non va (lo usa systemd)")
    opzioni = argomenti.parse_args()

    db = Database(DB_PATH)
    if opzioni.cartella:
        db.imposta("cartella_salvataggio", os.path.abspath(
            os.path.expanduser(opzioni.cartella)))

    if opzioni.disinstalla:
        print(disinstalla())
        return 0
    if opzioni.installa:
        print(installa(opzioni.ora))
        if not db.leggi("cartella_salvataggio", ""):
            print("manca la cartella: lanciami con --cartella PERCORSO")
    if opzioni.stato:
        print(f"cartella:   {db.leggi('cartella_salvataggio', '(nessuna)')}")
        print(f"automatico: {'acceso' if acceso() else 'spento'}"
              + (f" · prossimo giro {prossimo_giro()}" if acceso() else ""))
        print(f"ultimo:     {db.leggi('ultimo_salvataggio', 'mai')} "
              f"{db.leggi('ultimo_salvataggio_esito', '')}")
        return 0

    cartella = db.leggi("cartella_salvataggio", "")
    if not opzioni.silenzioso:
        print(f"Salvo in {cartella or '(nessuna cartella scelta)'}")
    riuscito, racconto = salva(cartella, db, parlato=not opzioni.silenzioso)
    db.imposta("ultimo_salvataggio_esito", ("fatto · " if riuscito else "") + racconto)
    if riuscito:
        db.imposta("ultimo_salvataggio", datetime.now().isoformat(timespec="minutes"))
    if not opzioni.silenzioso or not riuscito:
        print(("Fatto: " if riuscito else "Non salvato: ") + racconto)
    # la chiavetta staccata non è un guasto: systemd non deve segnare rosso
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
