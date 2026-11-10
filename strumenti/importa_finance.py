#!/usr/bin/env python3
"""Porta dentro Dashboard tutto quello che c'è nell'archivio di Finance.

Conti, categorie (col loro colore), movimenti, budget, obiettivi e
ricorrenti. Finito, la finanza di Dashboard vive da sola: i movimenti si
scrivono qui dentro, senza aprire più l'altra app.

    python3 strumenti/importa_finance.py              fa vedere cosa farebbe
    python3 strumenti/importa_finance.py --scrivi     e lo porta dentro davvero
    python3 strumenti/importa_finance.py --scrivi --da /altro/finanze.db

**L'archivio di Finance non si tocca**: si apre in sola lettura. E si può
rilanciare quante volte si vuole: un movimento uguale a uno già portato
dentro non entra due volte (stessa data, stesso tipo, stesso importo, stessa
categoria, stessa descrizione).

Con `--scrivi` la sorgente della finanza passa anche a «archivio interno»,
che è quello che rende modificabili i movimenti: senza, Dashboard
continuerebbe a leggere da Finance e le copie resterebbero lì ferme.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vita.db import DB_PATH, Database                                  # noqa: E402
from vita.fonti import (PERCORSO_FINANCE, FonteFinance,                # noqa: E402
                        finance_presente, porta_dentro_finance)


def main() -> int:
    argomenti = argparse.ArgumentParser(description=__doc__)
    argomenti.add_argument("--scrivi", action="store_true")
    argomenti.add_argument("--da", default="", help="un altro archivio di Finance")
    opzioni = argomenti.parse_args()

    percorso = opzioni.da or PERCORSO_FINANCE
    if not finance_presente(percorso):
        print(f"Nessun archivio di Finance in {percorso}")
        return 1

    fonte = FonteFinance(percorso)
    if not fonte.disponibile():
        print(f"Non riesco ad aprire {percorso}")
        return 1
    quanti = {
        "conti": len(fonte.conti()),
        "categorie": len(fonte._righe("SELECT 1 FROM categorie")),
        "movimenti": len(fonte.movimenti()),
        "budget": len(fonte._righe("SELECT 1 FROM budget")),
        "obiettivi": len(fonte.obiettivi()),
        "ricorrenti": len(fonte._righe("SELECT 1 FROM ricorrenti")),
    }
    fonte.chiudi()
    print(f"In {percorso}:")
    for nome, n in quanti.items():
        print(f"  {nome}: {n}")

    if not opzioni.scrivi:
        print("Niente portato dentro: rilanciami con --scrivi.")
        return 0

    db = Database(DB_PATH)
    entrati = porta_dentro_finance(db, percorso)
    print("Portati dentro adesso (i doppioni si saltano):")
    for nome, n in entrati.items():
        print(f"  {nome}: {n}")
    db.imposta("fonte_finanza", "locale")
    print("La finanza di Dashboard adesso legge e scrive il suo archivio.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
