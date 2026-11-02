"""Leggere i dati di salute che manda il braccialetto.

Dopo l'adozione (vedi `vita/sap.py`) il braccialetto consegna quello che ha
raccolto in **lotti**: messaggi che cominciano con `82 03 E0 <numero>` e poi
un byte che dice di che si tratta —

    7    passi, con distanza e calorie, un record ogni minuto di attività
    10   battito, con minimo e massimo del periodo
    16   episodi di sonno        17   fasi del sonno
    19   stress                  112  ossigeno nel sangue

Dentro, i record sono tutti fatti così:

    [continua] [lunghezza 4B]* [campo valore] [campo valore] …

dove ogni campo è un numero che dice *cosa è* seguito dal valore. Le ore sono
secondi dal 1990, le distanze e le calorie numeri a virgola mobile. La
lunghezza c'è nei record dei «vitali» (battito, stress, sonno); quelli dei
passi hanno misura fissa, perché i campi sono sempre gli stessi dieci.

Questo file non parla col Bluetooth: byte dentro, numeri fuori. Si prova sui
lotti veri registrati, con `python3 strumenti/prova_lotti.py`.
"""
from __future__ import annotations

import struct
from datetime import datetime, timedelta, timezone

EPOCA = datetime(1990, 1, 1, tzinfo=timezone.utc)

# che cosa contiene un lotto
PASSI, BATTITO, SONNO_EPISODI, SONNO_FASI, STRESS, OSSIGENO = 7, 10, 16, 17, 19, 112
NOMI_TIPO = {PASSI: "passi", BATTITO: "battito", SONNO_EPISODI: "sonno",
             SONNO_FASI: "fasi del sonno", STRESS: "stress",
             OSSIGENO: "ossigeno"}

# Quanto è lungo il valore di ogni campo, e come si legge.
#   4i = intero a 4 byte, 4f = virgola mobile, 1 = un byte solo, T = un'ora
CAMPI = {
    0x01: ("inizio", "T"), 0x02: ("fine", "T"), 0x03: ("durata", "4i"),
    0x05: ("quando", "T"),
    # passi
    0x10: ("passi", "4i"), 0x11: ("metri", "4f"), 0x12: ("piani", "4f"),
    0x13: ("kcal", "4f"), 0x14: ("tipo_attivita", "4i"), 0x15: ("passi2", "4i"),
    # battito
    0x20: ("battito", "1"), 0x21: ("battito_min", "1"), 0x22: ("battito_max", "1"),
    0x23: ("affidabile", "1"), 0x25: ("stato", "1"), 0x53: ("nota", "1"),
    0x24: ("campioni", "B"),            # blocco con la sua lunghezza davanti
    # stress
    0x60: ("stress", "1"), 0x66: ("stress_min", "1"), 0x67: ("stress_max", "1"),
    0x61: ("stress_durata", "4i"),
    # sonno
    0x50: ("sonno_minuti", "4f"), 0x51: ("sonno_tipo", "4i"),
    0x52: ("fase", "1"), 0x55: ("episodio", "B"),
    0x56: ("sonno_dato", "4i"),
    0x75: ("codice", "B"),
    0xA9: ("ossigeno", "1"), 0xAB: ("ossigeno_min", "1"),
    0xAC: ("ossigeno_max", "1"),
}
MISURE = {"T": 4, "4i": 4, "4f": 4, "1": 1}
# i campi dei passi, nell'ordine in cui arrivano: il record non dice quanto è
# lungo, lo sappiamo perché i campi sono sempre questi
RECORD_PASSI = (0x05, 0x01, 0x02, 0x03, 0x10, 0x11, 0x12, 0x13, 0x14, 0x15)
LUNGHEZZA_PASSI = sum(1 + MISURE[CAMPI[c][1]] for c in RECORD_PASSI)


def quando(secondi: int) -> datetime:
    """I secondi dal 1990 come li conta il braccialetto, in data e ora locale."""
    return (EPOCA + timedelta(seconds=int(secondi))).astimezone()


def _valore(dati: bytes, i: int, forma: str):
    """Legge un valore, e dice dov'è finito."""
    if forma == "1":
        return dati[i], i + 1
    pezzo = dati[i:i + 4]
    if len(pezzo) < 4:
        raise ValueError("record troncato")
    if forma == "4f":
        return struct.unpack("<f", pezzo)[0], i + 4
    return int.from_bytes(pezzo, "little"), i + 4


def _campi(dati: bytes, i: int, fine: int) -> tuple[dict, int]:
    """Legge i campi di un record fino a `fine`."""
    valori: dict = {}
    while i < fine:
        numero = dati[i]
        i += 1
        if numero not in CAMPI:
            break                        # campo che non conosciamo: si smette
        nome, forma = CAMPI[numero]
        if forma == "B":                 # blocco con la lunghezza davanti
            if i + 4 > fine:
                break
            lunghezza = int.from_bytes(dati[i:i + 4], "little")
            i += 4
            valori[nome] = dati[i:i + lunghezza]
            i += lunghezza
            continue
        try:
            valori[nome], i = _valore(dati, i, forma)
        except (ValueError, IndexError):
            break
        if forma == "T":
            valori[nome + "_data"] = quando(valori[nome]).date().isoformat()
    return valori, i


def leggi(messaggio: bytes) -> tuple[int, list[dict]]:
    """Legge un lotto intero. Torna (tipo, record)."""
    # 82 03 è il lotto di dati; 82 02 è il messaggio di servizio che lo chiude
    if len(messaggio) < 7 or messaggio[0] != 0x82 or messaggio[1] != 0x03:
        return 0, []
    # 82 | 03 | E0 numero(2) | tipo | record…
    tipo = messaggio[5]
    i = 6
    record: list[dict] = []
    while i < len(messaggio):
        continua = messaggio[i]
        if continua not in (0, 1):       # finito: dopo i record c'è altro
            break
        i += 1
        if i >= len(messaggio):
            break
        if tipo == PASSI:
            fine = min(len(messaggio), i + LUNGHEZZA_PASSI)
        else:
            if i + 4 > len(messaggio):
                break
            lunghezza = int.from_bytes(messaggio[i:i + 4], "little")
            i += 4
            if not 0 < lunghezza <= len(messaggio) - i:
                break
            fine = i + lunghezza
        valori, i = _campi(messaggio, i, fine)
        if valori:
            record.append(valori)
        i = fine
    return tipo, record


# ------------------------------------------------------- dai record ai giorni
def misure_battito(lotti) -> list[dict]:
    """Le misure del battito una per una, con l'ora a cui appartengono.

    Il braccialetto manda un record per ogni ora: la media di quell'ora, la
    più bassa e la più alta. Tenerle tutte è quello che permette di
    disegnare la giornata, invece del solo numero a riposo.
    """
    misure = []
    for messaggio in lotti:
        tipo, record = leggi(messaggio)
        if tipo != BATTITO:
            continue
        for r in record:
            secondi = r.get("inizio") or r.get("quando")
            if not secondi or not r.get("battito"):
                continue
            misure.append({
                "quando": quando(secondi).astimezone().strftime("%Y-%m-%dT%H:00"),
                "valore": int(r["battito"]),
                "minimo": int(r.get("battito_min") or 0),
                "massimo": int(r.get("battito_max") or 0),
            })
    return misure


def per_giorno(lotti) -> dict[str, dict]:
    """Mette insieme i record di tanti lotti, un riepilogo per giorno.

    Dei passi si sommano passi, metri e calorie; del battito si tiene la media
    e il più basso (che è quello a riposo); dello stress la media.
    """
    grezzi: dict[str, dict] = {}
    for messaggio in lotti:
        tipo, record = leggi(messaggio)
        for r in record:
            giorno = r.get("inizio_data") or r.get("quando_data")
            if not giorno:
                continue
            voce = grezzi.setdefault(giorno, {"passi": 0, "metri": 0.0,
                                              "kcal": 0.0, "battiti": [],
                                              "minimi": [], "stress": [],
                                              "sonno": 0})
            if tipo == PASSI:
                voce["passi"] += int(r.get("passi", 0))
                voce["metri"] += float(r.get("metri", 0.0))
                voce["kcal"] += float(r.get("kcal", 0.0))
            elif tipo == BATTITO:
                if r.get("battito"):
                    voce["battiti"].append(int(r["battito"]))
                if r.get("battito_min"):
                    voce["minimi"].append(int(r["battito_min"]))
            elif tipo == STRESS:
                if r.get("stress"):
                    voce["stress"].append(int(r["stress"]))
            elif tipo == SONNO_EPISODI:
                voce["sonno"] += int(r.get("sonno_minuti", 0) or 0)

    giorni: dict[str, dict] = {}
    for giorno, v in grezzi.items():
        riga: dict = {}
        if v["passi"]:
            riga["passi"] = v["passi"]
            riga["km"] = round(v["metri"] / 1000, 2)
        if v["kcal"]:
            riga["kcal"] = int(round(v["kcal"]))
        if v["battiti"]:
            riga["battito"] = int(round(min(v["minimi"] or v["battiti"])))
        if v["stress"]:
            riga["stress"] = round(sum(v["stress"]) / len(v["stress"]), 1)
        if v["sonno"]:
            riga["sonno"] = int(v["sonno"])
        if riga:
            giorni[giorno] = riga
    return giorni
