#!/usr/bin/env python3
"""Prove sui lotti veri del braccialetto, quelli registrati in casa.

Non serve il braccialetto: legge i file in `~/.local/share/Vita/banda/` e
controlla che i numeri che ne escono abbiano senso.

    python3 strumenti/prova_lotti.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vita.db import DATA_DIR                                           # noqa: E402
from vita.lotti import (BATTITO, NOMI_TIPO, PASSI, STRESS, leggi,      # noqa: E402
                        per_giorno, quando)

CARTELLA = os.path.join(DATA_DIR, "banda")
errori = []


def prova(nome, condizione, dettaglio=""):
    if condizione:
        print(f"  ok   {nome}")
    else:
        errori.append(nome)
        print(f"  NO   {nome}   {dettaglio}")


# un lotto di passi e uno di stress, registrati davvero dal Galaxy Fit2
PASSI_VERO = bytes.fromhex(
    "8203e00300070105 3ddb4845 01 00db4845 02 3bdb4845 03 80ee3600"
    "10 0d000000 11 d65b1f41 12 8ffb293e 13 82f0073f 14 00000000 15 0d000000"
    .replace(" ", ""))
STRESS_VERO = bytes.fromhex(
    "8203e0030013 01 1f000000 05 94d34845 01 94d34845 02 94d34845 03 80ee3600"
    "60 2a 66 00 67 2a 61 10270000".replace(" ", ""))
BATTITO_VERO = bytes.fromhex(
    "8203e003000a0001 1f000000 05 25de4845 01 25de4845 02 25de4845 03 80ee3600"
    "20 53 21 44 22 5e 23 01 25 35 53".replace(" ", ""))

print("i tipi")
tipo, record = leggi(PASSI_VERO)
prova("un lotto di passi si riconosce", tipo == PASSI, tipo)
prova("e dentro c'è un record", len(record) == 1, len(record))
if record:
    r = record[0]
    prova("tredici passi", r.get("passi") == 13, r.get("passi"))
    prova("quasi dieci metri", 9.9 < r.get("metri", 0) < 10.0, r.get("metri"))
    prova("mezza caloria", 0.5 < r.get("kcal", 0) < 0.54, r.get("kcal"))
    prova("l'ora è del 2026", quando(r["inizio"]).year == 2026, quando(r["inizio"]))

tipo, record = leggi(STRESS_VERO)
prova("un lotto di stress si riconosce", tipo == STRESS, tipo)
prova("stress 42", record and record[0].get("stress") == 42,
      record[0] if record else None)

tipo, record = leggi(BATTITO_VERO)
prova("un lotto di battito si riconosce", tipo == BATTITO, tipo)
if record:
    prova("83 bpm, da 68 a 94",
          (record[0].get("battito"), record[0].get("battito_min"),
           record[0].get("battito_max")) == (83, 68, 94), record[0])

print("il riepilogo per giorno")
giorni = per_giorno([PASSI_VERO, STRESS_VERO, BATTITO_VERO])
prova("esce almeno un giorno", bool(giorni), giorni)
if giorni:
    valori = list(giorni.values())[0]
    prova("coi passi dentro", valori.get("passi") == 13, valori)
prova("un messaggio di servizio non diventa un giorno",
      per_giorno([bytes.fromhex("8202e003000519011902432703043304")]) == {})
prova("un lotto storpiato non fa danni", leggi(b"\x82\x03\xe0") == (0, []))

print("i lotti registrati in casa")
if os.path.isdir(CARTELLA):
    file = [f for f in sorted(os.listdir(CARTELLA)) if f.endswith(".bin")]
    interi = []
    for nome in file:
        with open(os.path.join(CARTELLA, nome), "rb") as f:
            dati = f.read()
        if dati.startswith(b"\x82\x03"):
            interi.append(dati)
    letti = sum(1 for d in interi if leggi(d)[1])
    print(f"  {len(file)} file · {len(interi)} lotti interi · {letti} con record")
    for giorno, valori in sorted(per_giorno(interi).items()):
        print(f"    {giorno}: {valori}")
else:
    print("  (nessun lotto registrato: va bene, non è un errore)")

print(f"\n{len(errori)} errori" if errori else "\ntutto a posto")
sys.exit(1 if errori else 0)
