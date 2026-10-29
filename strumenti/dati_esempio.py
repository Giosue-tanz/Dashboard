#!/usr/bin/env python3
"""Riempie un archivio di prova con dati finti, per vedere l'app piena.

    python3 strumenti/dati_esempio.py /percorso/prova.db

Senza argomenti scrive in /tmp/vita-prova.db: l'archivio vero non viene toccato.
"""
from __future__ import annotations

import os
import random
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vita.db import Database

EMOZIONI_POSITIVE = ["sereno", "soddisfatto", "concentrato", "motivato", "grato"]
EMOZIONI_NEGATIVE = ["stanco", "ansioso", "teso", "irritato"]
DIARIO = [
    "Laboratorio: la misura è venuta meglio del previsto.",
    "Pomeriggio perso dietro a un bug stupido.",
    "Bella giornata, ho chiuso tutto quello che volevo.",
    "Troppe cose insieme, fatico a stare dietro allo studio.",
    "Allenamento tosto, poi serata tranquilla.",
    "Esercizi di meccanica quantistica: comincio a vederci chiaro.",
    "Giornata storta, meglio andare a dormire presto.",
]
MATERIE = ["Meccanica Quantistica", "Laboratorio di Fisica 3", "Fisica 3",
           "Struttura della Materia"]


def riempi(percorso: str, giorni: int = 120) -> None:
    db = Database(percorso)
    random.seed(11)
    oggi = date.today()

    # ------------------------------------------------------------ progetti
    progetti = [
        ("Smart-Light ALL", "cliente", "corso", "Studio Rossi", 1200, 72, "#2ec27e"),
        ("Sito studio legale", "cliente", "corso", "Avv. Bianchi", 800, 45, "#6c8cff"),
        ("Ripetizioni di fisica", "personale", "corso", "", 0, 100, "#35c4d7"),
        ("Scheda sensori", "personale", "pausa", "", 0, 30, "#b07cff"),
        ("Plugin KiCad", "personale", "idea", "", 0, 0, "#f7913a"),
        ("Riparazione ampli", "cliente", "fatto", "Marco", 180, 100, "#f06fb4"),
    ]
    ids = []
    for nome, tipo, stato, cliente, compenso, avanzamento, colore in progetti:
        ids.append(db.salva_progetto({
            "nome": nome, "tipo": tipo, "stato": stato, "cliente": cliente,
            "compenso": compenso, "inizio": "", "avanzamento": avanzamento,
            "colore": colore, "note": "",
            "scadenza": (oggi + timedelta(days=random.randint(5, 40))).isoformat()
                        if stato == "corso" else ""}))

    # --------------------------------------------------------------- esami
    esami = [
        ("Analisi Matematica 1", 12, 28, "superato", 1), ("Fisica Generale 1", 12, 26, "superato", 1),
        ("Geometria", 9, 30, "superato", 1), ("Chimica", 6, 25, "superato", 1),
        ("Analisi Matematica 2", 9, 27, "superato", 2), ("Fisica Generale 2", 12, 27, "superato", 2),
        ("Metodi Matematici", 9, 28, "superato", 2), ("Laboratorio di Fisica 2", 9, 29, "superato", 2),
        ("Fisica 3", 9, 0, "corso", 3), ("Meccanica Quantistica", 9, 0, "corso", 3),
        ("Laboratorio di Fisica 3", 9, 0, "corso", 3),
        ("Struttura della Materia", 6, 0, "previsto", 3),
    ]
    for i, (nome, cfu, voto, stato, anno) in enumerate(esami):
        db.salva_esame({
            "nome": nome, "cfu": cfu, "voto": voto, "lode": 0, "stato": stato,
            "anno": anno, "avanzamento": 100 if stato == "superato"
            else random.randint(20, 75), "note": "",
            "data_esame": (oggi + timedelta(days=60 + i * 7)).isoformat()
                          if stato != "superato" else ""})

    for nome, categoria, avanzamento, risorsa in (
            ("Meccanica quantistica — formalismo", "università", 55, "Sakurai cap. 1-3"),
            ("Analisi dati con Python", "personale", 80, "incertezze e fit grafici"),
            ("Elettronica analogica", "lavoro", 40, "per i progetti"),
            ("Inglese tecnico B2 → C1", "lingue", 62, "30 minuti al giorno"),
            ("LaTeX avanzato", "università", 88, "relazioni di laboratorio"),
            ("Relatività ristretta — ripasso", "liceo", 35, "appunti vecchi")):
        db.salva_percorso({"nome": nome, "categoria": categoria,
                           "avanzamento": avanzamento, "risorsa": risorsa,
                           "stato": "attivo", "colore": random.choice(
                               ["#35c4d7", "#b07cff", "#6c8cff", "#2ec27e", "#f7913a"]),
                           "note": ""})

    for giorno, titolo, area in (
            (4, "Relazione di Laboratorio 3", "accademica"),
            (7, "Esercizi di MQ — foglio 4", "accademica"),
            (12, "Consegna del sito", "carriera"),
            (18, "Fattura Smart-Light", "carriera"),
            (25, "Visita di controllo", "salute")):
        db.salva_scadenza({"data": (oggi + timedelta(days=giorno)).isoformat(),
                           "titolo": titolo, "area": area, "fatta": 0, "note": ""})

    # ------------------------------------------------- la vita quotidiana
    abitudini = db.abitudini()
    peso = 73.2
    for i in range(giorni, -1, -1):
        g = oggi - timedelta(days=i)
        iso = g.isoformat()
        festivo = g.weekday() >= 5

        umore = min(10, max(2, random.gauss(6.8 + (giorni - i) / giorni, 1.2)))
        if random.random() < 0.85:
            emozioni = random.sample(EMOZIONI_POSITIVE, 2) if umore >= 6.5 \
                else random.sample(EMOZIONI_NEGATIVE, 2)
            db.salva_voce({
                "data": iso, "ora": f"{random.randint(20, 23)}:{random.choice('012345')}0",
                "umore": round(umore, 1),
                "energia": round(min(10, max(2, umore + random.gauss(0, 1))), 1),
                "stress": round(min(10, max(1, 10 - umore + random.gauss(0, 1.3))), 1),
                "lucidita": round(min(10, max(2, umore + random.gauss(0.4, 1))), 1),
                "emozioni": ", ".join(emozioni), "testo": random.choice(DIARIO)})

        sonno = int(random.gauss(430, 45))
        profondo = int(sonno * random.uniform(0.15, 0.22))
        rem = int(sonno * random.uniform(0.18, 0.25))
        peso += random.gauss(-0.015, 0.12)
        db.salva_salute({
            "data": iso, "passi": max(1200, int(random.gauss(8600, 2600))),
            "km": round(random.uniform(3, 9), 1), "kcal": int(random.gauss(400, 120)),
            "sonno": sonno, "sonno_profondo": profondo, "sonno_rem": rem,
            "sonno_sveglio": int(random.uniform(15, 45)),
            "battito": int(random.gauss(62, 3)), "hrv": int(random.gauss(46, 6)),
            "peso": round(peso, 1), "acqua": round(random.uniform(1.0, 2.4), 2),
            "note": ""})

        if random.random() < 0.45:
            db.salva_allenamento({
                "data": iso, "tipo": random.choice(["Palestra", "Corsa", "Bicicletta"]),
                "minuti": random.choice([45, 50, 60, 70]),
                "km": round(random.uniform(0, 8), 1), "kcal": int(random.gauss(420, 90)),
                "intensita": random.choice(["leggera", "media", "intensa"]), "note": ""})

        if not festivo and random.random() < 0.8:
            db.esegui("INSERT INTO studio(data, materia, minuti, argomento) "
                      "VALUES(?,?,?,?)",
                      (iso, random.choice(MATERIE), random.choice([60, 90, 120, 150]),
                       "esercizi"))
        if random.random() < 0.55:
            db.esegui("INSERT INTO lavoro(data, progetto_id, minuti, note) "
                      "VALUES(?,?,?,?)",
                      (iso, random.choice(ids[:3]), random.choice([60, 90, 120, 180]),
                       "avanzamento"))
        if random.random() < 0.08:
            db.esegui("INSERT INTO incassi(data, progetto_id, importo, descrizione) "
                      "VALUES(?,?,?,?)",
                      (iso, random.choice(ids[:3]), random.choice([50, 180, 200, 400]),
                       "pagamento"))
        for a in abitudini:
            if random.random() < a["obiettivo"] / 7 * 0.85:
                db.esegui("INSERT OR IGNORE INTO registro(data, abitudine_id) "
                          "VALUES(?,?)", (iso, a["id"]))

        # movimenti dell'archivio interno
        if random.random() < 0.7:
            db.salva_movimento({
                "data": iso, "tipo": "uscita",
                "importo": round(random.uniform(4, 60), 2),
                "categoria": random.choice(
                    ["Spesa alimentare", "Trasporti", "Tempo libero", "Istruzione"]),
                "descrizione": "spesa"})
        if g.day == 27:
            db.salva_movimento({"data": iso, "tipo": "entrata", "importo": 450,
                                "categoria": "Ripetizioni", "descrizione": "lezioni"})

    for categoria, mensile in (("Spesa alimentare", 220), ("Trasporti", 60),
                               ("Tempo libero", 90), ("Istruzione", 50)):
        db.salva_budget(categoria, mensile)
    for nome, obiettivo, accantonato, giorni_ in (
            ("Portatile nuovo", 1000, 640, 240), ("Fondo emergenze", 2000, 800, 0),
            ("Viaggio estate", 500, 110, 200)):
        db.salva_obiettivo({"nome": nome, "obiettivo": obiettivo,
                            "accantonato": accantonato, "note": "",
                            "scadenza": (oggi + timedelta(days=giorni_)).isoformat()
                                        if giorni_ else ""})
    db.imposta("fonte_finanza", "locale")
    db.chiudi()
    print(f"Archivio di prova pronto: {percorso}")


if __name__ == "__main__":
    riempi(sys.argv[1] if len(sys.argv) > 1 else "/tmp/vita-prova.db")
