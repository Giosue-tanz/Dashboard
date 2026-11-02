#!/usr/bin/env python3
"""Porta nell'archivio i lotti già scaricati dal braccialetto.

Ogni volta che il braccialetto consegna qualcosa, Dashboard mette il lotto
grezzo in `~/.local/share/Vita/banda/`. Questo comando li rilegge tutti e ne
scrive i giorni **e le ore del battito**: serve da rete di sicurezza, perché
il braccialetto i dati li consegna **una volta sola** e poi se li dimentica —
e perché quando impariamo a leggere un campo in più non serve aspettare la
prossima sincronizzazione, basta rileggere quello che c'è già.

    python3 strumenti/importa_lotti.py            fa vedere cosa farebbe
    python3 strumenti/importa_lotti.py --scrivi   e li scrive davvero

Scrive solo dove non c'è già un valore: quello che hai messo a mano vince.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vita.db import DATA_DIR, DB_PATH, Database                       # noqa: E402
from vita.lotti import misure_battito, per_giorno                     # noqa: E402

CARTELLA = os.path.join(DATA_DIR, "banda")


def raccogli() -> list[bytes]:
    """I lotti registrati, senza doppioni."""
    if not os.path.isdir(CARTELLA):
        return []
    visti, lotti = set(), []
    for nome in sorted(os.listdir(CARTELLA)):
        if not nome.endswith(".bin"):
            continue
        with open(os.path.join(CARTELLA, nome), "rb") as f:
            dati = f.read()
        if dati in visti:
            continue
        visti.add(dati)
        lotti.append(dati)
    return lotti


def main() -> int:
    argomenti = argparse.ArgumentParser(description=__doc__)
    argomenti.add_argument("--scrivi", action="store_true")
    opzioni = argomenti.parse_args()

    lotti = raccogli()
    giorni = per_giorno(lotti)
    ore = misure_battito(lotti)
    print(f"{len(lotti)} lotti · {len(giorni)} giorni con dati · "
          f"{len(ore)} ore di battito")

    db = Database(DB_PATH)
    if ore:
        # le ore del battito si riscrivono sempre: l'ora è la chiave, quindi
        # rileggere lo stesso lotto non crea doppioni
        quante = db.salva_battiti(ore) if opzioni.scrivi else len(ore)
        giornate = len({m["quando"][:10] for m in ore})
        print(f"  battito: {quante} ore su {giornate} giornate"
              + ("" if opzioni.scrivi else "  (da scrivere)"))
    if not giorni:
        print("Scritti." if opzioni.scrivi else
              "Niente scritto: rilanciami con --scrivi.")
        return 0

    for giorno, misure in sorted(giorni.items()):
        riga = db.salute_giorno(giorno)
        valori = dict(riga) if riga else {}
        nuovi = {c: v for c, v in misure.items() if v and not (valori.get(c) or 0)}
        gia = {c: valori.get(c) for c in misure if valori.get(c)}
        print(f"  {giorno}: {nuovi or 'niente di nuovo'}"
              + (f"   (già scritto: {gia})" if gia else ""))
        if opzioni.scrivi and nuovi:
            valori.update(nuovi)
            valori.update({"data": giorno, "note": valori.get("note", "")})
            db.salva_salute(valori)
    print("Scritti." if opzioni.scrivi else
          "Niente scritto: rilanciami con --scrivi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
