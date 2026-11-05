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
#   4i = intero a 4 byte, 4f = virgola mobile, 1 = un byte solo, T = un'ora,
#   16 = un blocco di sedici byte (l'identificatore di una sessione)
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
    # sonno: la sessione (tipo 16) e le sue fasi (tipo 17) portano lo stesso
    # identificatore, ed è così che si rimettono insieme
    0x50: ("efficienza", "4f"), 0x51: ("sonno_tipo", "1"),
    0x52: ("fase", "4i"), 0x55: ("sessione", "16"),
    0x56: ("sonno_quante_fasi", "1"), 0x75: ("sessione", "16"),
    0xA9: ("ossigeno", "1"), 0xAB: ("ossigeno_min", "1"),
    0xAC: ("ossigeno_max", "1"),
}
MISURE = {"T": 4, "4i": 4, "4f": 4, "1": 1, "16": 16}
# i codici delle fasi sono quelli di Samsung Health, gli stessi che legge
# l'importazione dal telefono (vedi `vita/importa.py`)
FASI = {40001: "sveglio", 40002: "leggero", 40003: "profondo", 40004: "rem"}
# tipi che non mettono la lunghezza davanti al record: i campi si leggono
# uno dopo l'altro, e il record finisce quando un campo ricompare
SENZA_LUNGHEZZA = (PASSI, SONNO_EPISODI, SONNO_FASI)
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


def _campi(dati: bytes, i: int, fine: int,
           ferma_sui_ripetuti: bool = False) -> tuple[dict, int]:
    """Legge i campi di un record fino a `fine`.

    Con `ferma_sui_ripetuti` il record finisce quando un campo ricompare: è
    il modo di riconoscere la fine dove non c'è una lunghezza davanti. Quel
    campo non viene consumato — è già il primo del record dopo, o della coda
    che descrive il braccialetto.
    """
    valori: dict = {}
    while i < fine:
        numero = dati[i]
        if numero not in CAMPI:
            break                        # campo che non conosciamo: si smette
        nome, forma = CAMPI[numero]
        if ferma_sui_ripetuti and nome in valori:
            break
        i += 1
        if forma == "B":                 # blocco con la lunghezza davanti
            if i + 4 > fine:
                break
            lunghezza = int.from_bytes(dati[i:i + 4], "little")
            i += 4
            valori[nome] = dati[i:i + lunghezza]
            i += lunghezza
            continue
        if forma == "16":                # identificatore di sessione
            if i + 16 > fine:
                break
            valori[nome] = dati[i:i + 4].hex()
            i += 16
            continue
        try:
            valori[nome], i = _valore(dati, i, forma)
        except (ValueError, IndexError):
            break
        if forma == "T":
            valori[nome + "_data"] = quando(valori[nome]).date().isoformat()
    return valori, i


def _plausibile(secondi: int) -> bool:
    """Un'ora che può essere vera: dal 2018 a domani."""
    from time import time
    adesso = int(time() - EPOCA.timestamp()) + 86400
    return 880_000_000 < secondi < adesso


def _prossimo_record(dati: bytes, da: int) -> int:
    """Dove ricomincia un record, dopo un buco.

    I lotti grossi arrivano a pezzi e **qualche pezzo si perde per strada**
    (vedi `vita/banda.py`): in mezzo al lotto ci si ritrova con dei byte che
    non vogliono dire niente. Invece di buttare via tutto il resto si cerca
    il prossimo inizio credibile — un byte di «continua» seguito dal campo
    `05` con dentro un'ora che può essere vera — e si riprende da lì.
    """
    for i in range(da, len(dati) - 10):
        if dati[i] not in (0, 1):
            continue
        # senza lunghezza davanti: «continua», poi subito il campo 05
        if dati[i + 1] == 0x05 and _plausibile(
                int.from_bytes(dati[i + 2:i + 6], "little")):
            return i
        # con la lunghezza davanti: «continua», quattro byte di lunghezza
        # (un numero piccolo), poi il campo 05
        lunghezza = int.from_bytes(dati[i + 1:i + 5], "little")
        if (0 < lunghezza <= len(dati) - i and dati[i + 5] == 0x05
                and _plausibile(int.from_bytes(dati[i + 6:i + 10], "little"))):
            return i
    return -1


# Quanto può valere, al massimo, un campo di un record sano. Dopo un buco la
# ricerca del prossimo record può cadere in mezzo a dei byte qualunque e
# tirarne fuori uno che sembra un record: questi limiti lo fermano.
LIMITI = {
    "passi": 5_000, "passi2": 5_000, "metri": 20_000, "kcal": 1_000,
    "piani": 500, "battito": 240, "battito_min": 240, "battito_max": 240,
    "stress": 100, "stress_min": 100, "stress_max": 100,
    "ossigeno": 100, "ossigeno_min": 100, "ossigeno_max": 100,
}


def _sano(valori: dict) -> bool:
    """Un record con dentro numeri impossibili è spazzatura: si butta."""
    for nome, massimo in LIMITI.items():
        valore = valori.get(nome)
        if valore is not None and not 0 <= float(valore) <= massimo:
            return False
    inizio, fine = valori.get("inizio"), valori.get("fine")
    if inizio and fine and not 0 <= fine - inizio <= 2 * 86400:
        return False
    return True


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
        if continua not in (0, 1):       # coda del lotto, o un pezzo perso
            i = _prossimo_record(messaggio, i)
            if i < 0:
                break
            continue
        i += 1
        if i >= len(messaggio):
            break
        if tipo in SENZA_LUNGHEZZA:
            fine = (min(len(messaggio), i + LUNGHEZZA_PASSI) if tipo == PASSI
                    else len(messaggio))
            valori, dopo = _campi(messaggio, i, fine,
                                  ferma_sui_ripetuti=tipo != PASSI)
            i = fine if tipo == PASSI else dopo
        else:
            if i + 4 > len(messaggio):
                break
            lunghezza = int.from_bytes(messaggio[i:i + 4], "little")
            i += 4
            if not 0 < lunghezza <= len(messaggio) - i:
                i = _prossimo_record(messaggio, i)
                if i < 0:
                    break
                continue
            fine = i + lunghezza
            valori, _ = _campi(messaggio, i, fine)
            i = fine
        if valori and _sano(valori):
            record.append(valori)
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


def notti(lotti) -> dict[str, dict]:
    """Le notti, dai lotti del sonno (16) e delle sue fasi (17).

    Il braccialetto manda la sessione — da quando ti sei addormentato a
    quando ti sei alzato — e, a parte, i pezzi in cui l'ha divisa: leggero,
    profondo, REM, sveglio. I due lotti portano lo stesso identificatore di
    sessione, ed è così che si rimettono insieme.

    **Una notte vale per il giorno in cui ti svegli**: è la stessa regola che
    segue l'importazione da Samsung Health, se no la stessa notte finirebbe
    scritta in due giorni diversi a seconda di dove arriva.
    """
    sessioni: dict[str, tuple[int, int]] = {}
    pezzi: list[tuple[str, int, int, int]] = []
    for messaggio in lotti:
        tipo, record = leggi(messaggio)
        if tipo == SONNO_EPISODI:
            for r in record:
                inizio, fine = r.get("inizio"), r.get("fine")
                if not inizio or not fine or fine <= inizio:
                    continue
                minuti = (fine - inizio) // 60
                # oltre le dodici ore non è sonno: è il braccialetto sul tavolo
                if not 20 <= minuti <= 12 * 60:
                    continue
                sessioni[r.get("sessione") or str(inizio)] = (inizio, fine)
        elif tipo == SONNO_FASI:
            for r in record:
                if r.get("fase") in FASI and r.get("inizio") and r.get("fine"):
                    pezzi.append((r.get("sessione") or "", r["inizio"],
                                  r["fine"], r["fase"]))

    giorni: dict[str, dict] = {}
    for chiave, (inizio, fine) in sessioni.items():
        giorno = quando(fine).date().isoformat()
        voce = giorni.setdefault(giorno, {"intervalli": [], "sessioni": set(),
                                          "fasi": {}})
        voce["intervalli"].append((inizio, fine))
        voce["sessioni"].add(chiave)

    def giorno_del_pezzo(chiave: str, inizio: int) -> str:
        for giorno, voce in giorni.items():
            if chiave and chiave in voce["sessioni"]:
                return giorno
        for giorno, voce in giorni.items():
            if any(a <= inizio <= b for a, b in voce["intervalli"]):
                return giorno
        return ""      # fase orfana: senza la sua notte non si sa dove metterla

    for chiave, inizio, fine, codice in pezzi:
        giorno = giorno_del_pezzo(chiave, inizio)
        if not giorno:
            continue
        nome = FASI[codice]
        minuti = max(0, (fine - inizio) // 60)
        giorni[giorno]["fasi"][nome] = giorni[giorno]["fasi"].get(nome, 0) + minuti

    pronte: dict[str, dict] = {}
    for giorno, voce in giorni.items():
        unione: list[list[int]] = []
        for apertura, chiusura in sorted(voce["intervalli"]):
            if unione and apertura <= unione[-1][1]:
                unione[-1][1] = max(unione[-1][1], chiusura)
            else:
                unione.append([apertura, chiusura])
        minuti = sum((b - a) // 60 for a, b in unione)
        if not 20 <= minuti <= 14 * 60:
            continue
        riga = {"sonno": minuti,
                "a_letto": quando(unione[0][0]).strftime("%H:%M"),
                "sveglia": quando(unione[-1][1]).strftime("%H:%M")}
        # le fasi si scrivono solo se coprono quasi tutta la notte: se un
        # pezzo del lotto si è perso per strada, la divisione che ne viene
        # fuori è falsa — meglio la sola durata che un grafico sbagliato
        coperto = sum(voce["fasi"].values())
        if coperto >= 0.9 * minuti:
            for nome, campo in (("profondo", "sonno_profondo"),
                                ("rem", "sonno_rem"), ("sveglio", "sonno_sveglio")):
                if voce["fasi"].get(nome):
                    riga[campo] = voce["fasi"][nome]
        pronte[giorno] = riga
    return pronte


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
                                              "minimi": [], "stress": []})
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
        if riga:
            giorni[giorno] = riga

    # il sonno si conta a parte: la notte appartiene al giorno del risveglio,
    # non a quello in cui il record è stato scritto
    for giorno, riga in notti(lotti).items():
        giorni.setdefault(giorno, {}).update(riga)
    return giorni
