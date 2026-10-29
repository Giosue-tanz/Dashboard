#!/usr/bin/env python3
"""Importa nell'archivio di Dashboard l'ultima esportazione di Samsung Health.

Senza argomenti cerca da solo in Scaricati, Scrivania e Documenti l'ultima
cartella (o zip) esportata da Samsung Health e la legge.

    python3 strumenti/importa_salute.py                 # cerca e importa
    python3 strumenti/importa_salute.py ~/Scaricati/samsunghealth.zip
    python3 strumenti/importa_salute.py --elenco        # mostra cosa trova
    python3 strumenti/importa_salute.py --sovrascrivi   # vince il dato importato

Pensato anche per essere richiamato da un'attività periodica: se non trova
niente di nuovo esce senza toccare l'archivio.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vita.db import Database
from vita.importa import esportazioni_trovate, importa_samsung_health, sembra_esportazione


def main() -> int:
    argomenti = argparse.ArgumentParser(description=__doc__)
    argomenti.add_argument("percorso", nargs="?", default="",
                           help="cartella o zip esportato da Samsung Health")
    argomenti.add_argument("--elenco", action="store_true",
                           help="elenca le esportazioni trovate e basta")
    argomenti.add_argument("--sovrascrivi", action="store_true",
                           help="sostituisce anche i dati già presenti")
    argomenti.add_argument("--forza", action="store_true",
                           help="reimporta anche se è la stessa dell'ultima volta")
    argomenti.add_argument("--archivio", default="",
                           help="usa un altro file di archivio (per le prove)")
    opzioni = argomenti.parse_args()

    trovate = esportazioni_trovate()
    if opzioni.elenco:
        if not trovate:
            print("Nessuna esportazione trovata in Scaricati, Scrivania o Documenti.")
            return 1
        for percorso, quando in trovate:
            print(f"{datetime.fromtimestamp(quando):%d/%m/%Y %H:%M}  {percorso}")
        return 0

    percorso = opzioni.percorso
    if percorso:
        percorso = os.path.expanduser(percorso)
        if not sembra_esportazione(percorso):
            print(f"Non sembra un'esportazione di Samsung Health: {percorso}")
            return 1
        quando = os.path.getmtime(percorso)
    else:
        if not trovate:
            print("Nessuna esportazione trovata. Scaricala da Samsung Health "
                  "(Impostazioni → Scarica dati personali) e copiala in Scaricati.")
            return 1
        percorso, quando = trovate[0]

    db = Database(os.path.expanduser(opzioni.archivio)) if opzioni.archivio else Database()
    ultima = db.leggi("ultima_importazione_quando", "")
    if ultima and float(ultima) >= quando and not opzioni.forza:
        print(f"Già importata: {percorso}")
        print("Niente di nuovo. (--forza per rifarlo comunque)")
        db.chiudi()
        return 0

    print(f"Leggo {percorso}…")
    risultato = importa_samsung_health(db, percorso, opzioni.sovrascrivi)
    print(risultato)
    if risultato.file_letti:
        db.imposta("ultima_importazione", percorso)
        db.imposta("ultima_importazione_quando", quando)
    db.chiudi()
    return 0 if risultato.file_letti else 2


if __name__ == "__main__":
    sys.exit(main())
