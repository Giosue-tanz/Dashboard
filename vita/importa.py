"""Importazione dei dati di salute da esportazioni esterne.

Il Galaxy Fit2 non consegna lo storico al PC: passi, sonno e allenamenti
viaggiano con il protocollo proprietario di Samsung verso il telefono. La via
che funziona davvero è l'esportazione di **Samsung Health** (sul telefono:
Samsung Health → Impostazioni → Scarica dati personali), che produce una
cartella o uno zip di file CSV. Qui dentro quei file vengono letti e riversati
nell'archivio di Dashboard.

Niente rete: si legge solo il file che gli si indica.
"""
from __future__ import annotations

import csv
import io
import os
import zipfile
from datetime import date, datetime, timedelta

# Codici di Samsung Health per le fasi del sonno
FASI = {40001: "sveglio", 40002: "leggero", 40003: "profondo", 40004: "rem"}

# Codici degli allenamenti: quelli incerti restano «Allenamento»
ESERCIZI = {
    1001: "Camminata", 1002: "Corsa", 11007: "Bicicletta", 13001: "Nuoto",
    9002: "Yoga", 14001: "Ellittica", 15006: "Palestra", 15003: "Palestra",
}


class Risultato:
    """Che cosa è stato letto e che cosa è finito nell'archivio."""

    def __init__(self):
        self.giorni_salute = 0
        self.allenamenti = 0
        self.file_letti: list[str] = []
        self.saltati: list[str] = []
        self.campi: dict[str, int] = {}

    def conta(self, campo: str) -> None:
        self.campi[campo] = self.campi.get(campo, 0) + 1

    def __str__(self) -> str:
        if not self.file_letti:
            return "Nessun file riconosciuto."
        righe = [f"{len(self.file_letti)} file letti",
                 f"{self.giorni_salute} giorni di salute aggiornati",
                 f"{self.allenamenti} allenamenti importati"]
        if self.campi:
            righe.append("dati: " + ", ".join(
                f"{campo} ({quanti})" for campo, quanti in sorted(self.campi.items())))
        if self.saltati:
            righe.append(f"{len(self.saltati)} file ignorati "
                         "(preferenze, cibo, badge: niente che serva qui)")
        return "\n".join(righe)


# ------------------------------------------------------------------ lettura
def _righe_csv(contenuto: str) -> list[dict]:
    """Legge un CSV di Samsung Health: la prima riga dichiara il tipo di dato."""
    testo = contenuto.lstrip("﻿")
    prima, resto = (testo.split("\n", 1) + [""])[:2]
    # la prima riga dichiara il tipo e la versione del dato, per esempio
    # «com.samsung.shealth.sleep,7010053,12»: non è l'intestazione delle colonne
    campi_prima = [c for c in prima.split(",") if c.strip()]
    if prima.strip().startswith("com.samsung") and len(campi_prima) <= 5:
        testo = resto
    lettore = csv.DictReader(io.StringIO(testo))
    return [r for r in lettore if any((v or "").strip() for v in r.values())]


def _colonna(intestazioni, *candidati) -> str | None:
    """Trova una colonna per nome esatto, per suffisso o per contenuto."""
    disponibili = [h for h in intestazioni if h]
    for candidato in candidati:
        for h in disponibili:
            if h == candidato:
                return h
    for candidato in candidati:
        for h in disponibili:
            if h.endswith("." + candidato) or h.endswith("/" + candidato):
                return h
    for candidato in candidati:
        for h in disponibili:
            if candidato in h:
                return h
    return None


def _numero(valore) -> float:
    try:
        return float(str(valore).strip().replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def _istante(valore) -> datetime | None:
    """Accetta sia i millisecondi dall'epoca sia le date scritte per esteso."""
    if valore is None:
        return None
    testo = str(valore).strip()
    if not testo:
        return None
    if testo.replace("-", "").isdigit() and len(testo) >= 10:
        numero = int(testo)
        if numero > 10_000_000_000:        # millisecondi
            numero //= 1000
        try:
            return datetime.fromtimestamp(numero)
        except (OverflowError, OSError, ValueError):
            return None
    for formato in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S",
                    "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(testo[:26], formato)
        except ValueError:
            continue
    return None


def _giorno(valore) -> str:
    istante = _istante(valore)
    return istante.date().isoformat() if istante else ""


# ------------------------------------------------------------- i vari tipi
def _passi(righe, giorni: dict) -> None:
    if not righe:
        return
    testate = righe[0].keys()
    c_data = _colonna(testate, "day_time", "start_time", "create_time")
    c_passi = _colonna(testate, "count", "step_count", "total_step_count")
    c_km = _colonna(testate, "distance", "total_distance")
    c_kcal = _colonna(testate, "calorie", "total_calorie")
    if not c_data or not c_passi:
        return
    for r in righe:
        giorno = _giorno(r.get(c_data))
        if not giorno:
            continue
        voce = giorni.setdefault(giorno, {})
        passi = int(_numero(r.get(c_passi)))
        # più righe per giorno (una per sorgente): vale la più completa
        if passi >= voce.get("passi", 0):
            voce["passi"] = passi
            if c_km:
                voce["km"] = round(_numero(r.get(c_km)) / 1000, 2)
            if c_kcal:
                voce["kcal"] = int(_numero(r.get(c_kcal)))


def _sonno(righe, giorni: dict, notti: list | None = None) -> None:
    if not righe:
        return
    testate = righe[0].keys()
    c_inizio = _colonna(testate, "start_time", "sleep.start_time")
    c_fine = _colonna(testate, "end_time", "sleep.end_time")
    if not c_inizio or not c_fine:
        return
    # Samsung scrive più righe per la stessa notte (la sessione «integrata» e i
    # suoi pezzi): sommarle darebbe notti da trenta ore. Gli intervalli che si
    # sovrappongono vanno uniti, non addizionati.
    intervalli: dict[str, list] = {}
    for r in righe:
        inizio, fine = _istante(r.get(c_inizio)), _istante(r.get(c_fine))
        if not inizio or not fine or fine <= inizio:
            continue
        minuti = int((fine - inizio).total_seconds() // 60)
        # oltre le dodici ore di fila non è sonno: è il braccialetto lasciato
        # sul tavolo. Samsung quelle sessioni le registra lo stesso.
        if not 20 <= minuti <= 12 * 60:
            continue
        # la notte vale per il giorno in cui ci si sveglia
        intervalli.setdefault(fine.date().isoformat(), []).append((inizio, fine))

    for giorno, elenco in intervalli.items():
        elenco.sort()
        unione: list = []
        for apertura, chiusura in elenco:
            if unione and apertura <= unione[-1][1]:
                unione[-1] = (unione[-1][0], max(unione[-1][1], chiusura))
            else:
                unione.append((apertura, chiusura))
        minuti = sum(int((b - a).total_seconds() // 60) for a, b in unione)
        if minuti > 14 * 60:
            # giornata improbabile: si tiene solo il periodo più lungo
            unione = [max(unione, key=lambda v: v[1] - v[0])]
            minuti = int((unione[0][1] - unione[0][0]).total_seconds() // 60)
        if minuti < 20:
            continue
        voce = giorni.setdefault(giorno, {})
        voce["sonno"] = max(voce.get("sonno", 0), minuti)
        if notti is not None:
            notti.extend((a, b, giorno) for a, b in unione)


def _fasi_sonno(righe, giorni: dict, notti: list | None = None) -> None:
    """Le fasi vanno sommate alla notte a cui appartengono.

    Un segmento che finisce alle 23:40 fa parte della notte che si chiude il
    mattino dopo: attribuirlo al giorno in cui finisce spezzerebbe la notte
    in due.
    """
    if not righe:
        return
    testate = righe[0].keys()
    c_inizio = _colonna(testate, "start_time")
    c_fine = _colonna(testate, "end_time")
    c_fase = _colonna(testate, "stage", "sleep_stage")
    if not (c_inizio and c_fine and c_fase):
        return
    notti = notti or []
    for r in righe:
        inizio, fine = _istante(r.get(c_inizio)), _istante(r.get(c_fine))
        fase = FASI.get(int(_numero(r.get(c_fase))))
        if not inizio or not fine or not fase or fine <= inizio:
            continue
        minuti = int((fine - inizio).total_seconds() // 60)
        giorno = ""
        for apertura, chiusura, quando in notti:
            if apertura <= inizio <= chiusura:
                giorno = quando
                break
        if not giorno:
            if notti:
                # la notte a cui apparteneva è stata scartata: lo sono anche le fasi
                continue
            # senza nessuna notte di riferimento: dalla sera in poi vale il giorno dopo
            giorno = (fine + timedelta(hours=6)).date().isoformat() \
                if fine.hour >= 18 else fine.date().isoformat()
        voce = giorni.setdefault(giorno, {})
        chiave = {"profondo": "sonno_profondo", "rem": "sonno_rem",
                  "sveglio": "sonno_sveglio"}.get(fase)
        if chiave:
            voce[chiave] = voce.get(chiave, 0) + minuti


def _battito(righe, giorni: dict) -> None:
    if not righe:
        return
    testate = righe[0].keys()
    c_data = _colonna(testate, "start_time", "create_time")
    c_min = _colonna(testate, "heart_rate_min", "min")
    c_valore = _colonna(testate, "heart_rate", "value")
    if not c_data or not (c_min or c_valore):
        return
    minimi: dict[str, list[float]] = {}
    for r in righe:
        giorno = _giorno(r.get(c_data))
        valore = _numero(r.get(c_min)) if c_min else 0.0
        if not valore:
            valore = _numero(r.get(c_valore)) if c_valore else 0.0
        if giorno and 25 <= valore <= 220:
            minimi.setdefault(giorno, []).append(valore)
    for giorno, valori in minimi.items():
        # il battito a riposo si approssima con il minimo della giornata
        giorni.setdefault(giorno, {})["battito"] = int(min(valori))


def _peso(righe, giorni: dict) -> None:
    """Peso e, se la bilancia le manda, massa grassa e muscolare in percentuale."""
    if not righe:
        return
    testate = righe[0].keys()
    c_data = _colonna(testate, "start_time", "create_time")
    c_peso = _colonna(testate, "weight")
    c_grasso = _colonna(testate, "body_fat", "body_fat_percentage")
    c_muscolo = _colonna(testate, "skeletal_muscle", "skeletal_muscle_percentage")
    if not c_data or not c_peso:
        return
    for r in righe:
        giorno = _giorno(r.get(c_data))
        valore = _numero(r.get(c_peso))
        if not giorno or not 20 <= valore <= 350:
            continue
        voce = giorni.setdefault(giorno, {})
        voce["peso"] = round(valore, 1)
        for campo, colonna, massimo in (("grasso", c_grasso, 70),
                                        ("muscolo", c_muscolo, 80)):
            if not colonna:
                continue
            percentuale = _numero(r.get(colonna))
            if 2 <= percentuale <= massimo:
                voce[campo] = round(percentuale, 1)


def _acqua(righe, giorni: dict) -> None:
    if not righe:
        return
    testate = righe[0].keys()
    c_data = _colonna(testate, "start_time", "create_time")
    c_quantita = _colonna(testate, "amount", "water_intake")
    if not c_data or not c_quantita:
        return
    for r in righe:
        giorno = _giorno(r.get(c_data))
        quantita = _numero(r.get(c_quantita))
        if not giorno or quantita <= 0:
            continue
        litri = quantita / 1000 if quantita > 20 else quantita * 0.25
        voce = giorni.setdefault(giorno, {})
        voce["acqua"] = round(voce.get("acqua", 0.0) + litri, 2)


def _stress(righe, giorni: dict) -> None:
    """Lo stress della giornata: Samsung lo scrive misura per misura, da 0 a 100.

    Di un giorno si tiene la media delle misure, che è il numero che poi
    compare negli indicatori.
    """
    if not righe:
        return
    testate = righe[0].keys()
    c_data = _colonna(testate, "start_time", "create_time", "update_time")
    c_valore = _colonna(testate, "score", "stress.score", "value")
    if not c_data or not c_valore:
        return
    somme: dict[str, list[float]] = {}
    for r in righe:
        giorno = _giorno(r.get(c_data))
        valore = _numero(r.get(c_valore))
        if not giorno or not 0 < valore <= 100:
            continue
        somme.setdefault(giorno, []).append(valore)
    for giorno, misure in somme.items():
        giorni.setdefault(giorno, {})["stress"] = round(
            sum(misure) / len(misure), 1)


def _allenamenti(righe) -> list[dict]:
    if not righe:
        return []
    testate = righe[0].keys()
    c_inizio = _colonna(testate, "start_time", "exercise.start_time")
    c_durata = _colonna(testate, "duration", "exercise.duration")
    c_fine = _colonna(testate, "end_time")
    c_tipo = _colonna(testate, "exercise_type", "exercise.exercise_type")
    c_km = _colonna(testate, "distance")
    c_kcal = _colonna(testate, "calorie")
    if not c_inizio:
        return []
    fuori = []
    for r in righe:
        inizio = _istante(r.get(c_inizio))
        if not inizio:
            continue
        minuti = 0
        if c_durata:
            durata = _numero(r.get(c_durata))
            minuti = int(durata / 60000) if durata > 10000 else int(durata / 60)
        if not minuti and c_fine:
            fine = _istante(r.get(c_fine))
            if fine and fine > inizio:
                minuti = int((fine - inizio).total_seconds() // 60)
        if not 1 <= minuti <= 12 * 60:
            continue
        codice = int(_numero(r.get(c_tipo))) if c_tipo else 0
        fuori.append({
            "data": inizio.date().isoformat(),
            "tipo": ESERCIZI.get(codice, "Allenamento"),
            "minuti": minuti,
            "km": round(_numero(r.get(c_km)) / 1000, 2) if c_km else 0.0,
            "kcal": int(_numero(r.get(c_kcal))) if c_kcal else 0,
            "intensita": "media",
            "note": f"Samsung Health · {inizio:%H:%M}" + (
                f" · codice {codice}" if codice and codice not in ESERCIZI else ""),
        })
    return fuori


# Il nome del file dice che cosa contiene. Gli accostamenti vanno provati in
# quest'ordine: «sleep_stage» contiene «sleep», quindi viene prima.
def tipo_di_file(nome: str) -> str:
    n = nome.lower()
    if "sleep_stage" in n:
        return "fasi"
    if "sleep_data" in n:
        return ""                       # formato interno, non documentato
    if "sleep" in n:
        return "sonno"
    if "exercise" in n and "recovery" not in n:
        return "allenamenti"
    if "heart_rate" in n:
        return "battito"
    if "weight" in n:
        return "peso"
    if "water_intake" in n:
        return "acqua"
    if "stress" in n:
        return "stress"
    if any(chiave in n for chiave in ("step_daily_trend", "pedometer_day_summary",
                                      "activity.day_summary")):
        return "passi"
    return ""


# L'ordine di lavorazione conta: le notti servono a collocare le fasi del sonno
ORDINE = ("passi", "sonno", "fasi", "battito", "peso", "acqua", "stress")


# ------------------------------------------------- trovare l'esportazione
CARTELLE_TIPICHE = ["Scaricati", "Downloads", "Download", "Scrivania", "Desktop",
                    "Documenti", "Documents"]


def sembra_esportazione(percorso: str) -> bool:
    """Vero se è uno zip o una cartella di Samsung Health."""
    try:
        if os.path.isfile(percorso):
            if not percorso.lower().endswith(".zip"):
                return False
            with zipfile.ZipFile(percorso) as archivio:
                return any("com.samsung" in n and n.lower().endswith(".csv")
                           for n in archivio.namelist()[:400])
        if os.path.isdir(percorso):
            for radice, _, nomi in os.walk(percorso):
                if any(n.startswith("com.samsung") and n.lower().endswith(".csv")
                       for n in nomi):
                    return True
                if radice.count(os.sep) - percorso.count(os.sep) > 2:
                    break
    except (OSError, zipfile.BadZipFile):
        return False
    return False


def esportazioni_trovate(cartelle: list[str] | None = None,
                         massimo: int = 6) -> list[tuple[str, float]]:
    """Esportazioni di Samsung Health nelle cartelle dove finiscono i download.

    Restituisce coppie (percorso, data di modifica), dalla più recente.
    """
    casa = os.path.expanduser("~")
    radici = cartelle or [os.path.join(casa, nome) for nome in CARTELLE_TIPICHE]
    candidati: dict[str, float] = {}
    for radice in radici:
        if not os.path.isdir(radice):
            continue
        try:
            voci = sorted(os.listdir(radice))[:400]
        except OSError:
            continue
        for nome in voci:
            percorso = os.path.join(radice, nome)
            minuscolo = nome.lower()
            indizio = any(parola in minuscolo for parola in
                          ("samsung", "shealth", "health"))
            if not indizio and not os.path.isdir(percorso):
                continue
            if sembra_esportazione(percorso):
                try:
                    candidati[percorso] = os.path.getmtime(percorso)
                except OSError:
                    pass
    return sorted(candidati.items(), key=lambda v: -v[1])[:massimo]


# ---------------------------------------------------------------- ingresso
def _file_csv(percorso: str):
    """Restituisce coppie (nome, contenuto) da una cartella o da uno zip."""
    if os.path.isfile(percorso) and percorso.lower().endswith(".zip"):
        with zipfile.ZipFile(percorso) as archivio:
            for nome in archivio.namelist():
                if nome.lower().endswith(".csv"):
                    with archivio.open(nome) as f:
                        yield os.path.basename(nome), f.read().decode(
                            "utf-8", "replace")
        return
    if os.path.isfile(percorso):
        with open(percorso, encoding="utf-8", errors="replace") as f:
            yield os.path.basename(percorso), f.read()
        return
    for radice, _, nomi in os.walk(percorso):
        for nome in sorted(nomi):
            if nome.lower().endswith(".csv"):
                with open(os.path.join(radice, nome), encoding="utf-8",
                          errors="replace") as f:
                    yield nome, f.read()


def importa_samsung_health(db, percorso: str, sovrascrivi: bool = False,
                           con_allenamenti: bool = True) -> Risultato:
    """Legge un'esportazione di Samsung Health e la riversa nell'archivio."""
    risultato = Risultato()
    giorni: dict[str, dict] = {}
    allenamenti: list[dict] = []
    raccolta: dict[str, list] = {}

    # prima si legge tutto, poi si lavora nell'ordine giusto
    for nome, contenuto in _file_csv(percorso):
        tipo = tipo_di_file(nome)
        if not tipo:
            risultato.saltati.append(nome)
            continue
        try:
            righe = _righe_csv(contenuto)
        except Exception:
            risultato.saltati.append(nome)
            continue
        if not righe:
            continue
        raccolta.setdefault(tipo, []).append(righe)
        risultato.file_letti.append(nome)

    notti: list = []
    for tipo in ORDINE:
        for righe in raccolta.get(tipo, []):
            if tipo == "passi":
                _passi(righe, giorni)
            elif tipo == "sonno":
                _sonno(righe, giorni, notti)
            elif tipo == "fasi":
                _fasi_sonno(righe, giorni, notti)
            elif tipo == "battito":
                _battito(righe, giorni)
            elif tipo == "peso":
                _peso(righe, giorni)
            elif tipo == "acqua":
                _acqua(righe, giorni)
            elif tipo == "stress":
                _stress(righe, giorni)
    for righe in raccolta.get("allenamenti", []):
        allenamenti += _allenamenti(righe)

    # ------------------------------------------------------- scrittura
    # qualche riga di Samsung porta date vuote o all'epoca zero: si scartano
    domani = (date.today() + timedelta(days=1)).isoformat()
    giorni = {g: v for g, v in giorni.items() if "2005-01-01" <= g <= domani}
    for giorno, valori in sorted(giorni.items()):
        esistente = db.salute_giorno(giorno)
        attuale = dict(esistente) if esistente else {}
        nuovo = {"data": giorno}
        cambiato = False
        for campo in ("passi", "km", "kcal", "sonno", "sonno_profondo", "sonno_rem",
                      "sonno_sveglio", "battito", "hrv", "peso", "grasso",
                      "muscolo", "acqua", "stress"):
            importato = valori.get(campo)
            precedente = attuale.get(campo, 0) or 0
            if importato and (sovrascrivi or not precedente):
                nuovo[campo] = importato
                cambiato = True
                risultato.conta(campo)
            else:
                nuovo[campo] = precedente
        nuovo["note"] = attuale.get("note", "")
        if cambiato:
            db.salva_salute(nuovo)
            risultato.giorni_salute += 1

    if con_allenamenti:
        for a in allenamenti:
            gia = db.query(
                "SELECT id FROM allenamenti WHERE data=? AND minuti=? AND tipo=? "
                "AND note=?", (a["data"], a["minuti"], a["tipo"], a["note"]))
            if gia:
                continue
            db.salva_allenamento(a)
            risultato.allenamenti += 1
    return risultato
