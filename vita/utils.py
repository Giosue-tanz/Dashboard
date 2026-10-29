"""Funzioni di supporto: date, durate, formattazione dei numeri."""
from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta

MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
        "agosto", "settembre", "ottobre", "novembre", "dicembre"]
GIORNI = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
GIORNI_CORTI = ["L", "M", "M", "G", "V", "S", "D"]


# ------------------------------------------------------------------- numeri
def numero(valore: float, decimali: int = 1) -> str:
    """Numero all'italiana: virgola decimale e punto per le migliaia."""
    testo = f"{valore:,.{decimali}f}"
    return testo.replace(",", "~").replace(".", ",").replace("~", ".")


def euro(valore: float, valuta: str = "€") -> str:
    segno = "-" if valore < 0 else ""
    return f"{segno}{numero(abs(valore), 2)} {valuta}"


def compatto(valore: float) -> str:
    a = abs(valore)
    if a >= 1_000_000:
        return numero(valore / 1_000_000, 1) + "M"
    if a >= 10_000:
        return numero(valore / 1_000, 1) + "k"
    if a == int(a):
        return numero(valore, 0)
    return numero(valore, 1)


def voto(valore: float) -> str:
    """Un voto da 0 a 10 con una cifra, senza decimale inutile."""
    return numero(valore, 1) if abs(valore - round(valore)) > 0.04 else numero(valore, 0)


def durata(minuti: float) -> str:
    """90 → «1h30», 45 → «45m», 0 → «—»."""
    minuti = int(round(minuti or 0))
    if minuti <= 0:
        return "—"
    ore, resto = divmod(minuti, 60)
    if not ore:
        return f"{resto}m"
    return f"{ore}h{resto:02d}" if resto else f"{ore}h"


def ore(minuti: float, decimali: int = 1) -> str:
    return numero((minuti or 0) / 60, decimali) + "h"


# -------------------------------------------------------------------- date
def oggi() -> str:
    return date.today().isoformat()


def adesso() -> str:
    return datetime.now().strftime("%H:%M")


def data_it(iso: str) -> str:
    try:
        a, m, g = iso.split("-")
        return f"{g}/{m}/{a}"
    except Exception:
        return iso


def data_lunga(iso: str) -> str:
    """2026-10-23 → «venerdì 23 ottobre 2026»."""
    try:
        d = date.fromisoformat(iso)
    except Exception:
        return iso
    return f"{GIORNI[d.weekday()]} {d.day} {MESI[d.month - 1]} {d.year}"


def data_breve(iso: str) -> str:
    """2026-10-23 → «23 ott»."""
    try:
        d = date.fromisoformat(iso)
    except Exception:
        return iso
    return f"{d.day} {MESI[d.month - 1][:3]}"


def relativa(iso: str) -> str:
    """«oggi», «ieri», «3 giorni fa», altrimenti la data breve."""
    try:
        d = date.fromisoformat(iso)
    except Exception:
        return iso
    scarto = (date.today() - d).days
    if scarto == 0:
        return "oggi"
    if scarto == 1:
        return "ieri"
    if 2 <= scarto <= 6:
        return f"{scarto} giorni fa"
    if scarto < 0:
        return f"fra {-scarto} giorni" if scarto < -1 else "domani"
    return data_breve(iso)


def etichetta_mese(iso_mese: str) -> str:
    try:
        a, m = iso_mese.split("-")
        return f"{MESI[int(m) - 1][:3]} {a[2:]}"
    except Exception:
        return iso_mese


def giorni(dal: str, al: str) -> list[str]:
    """Tutte le date dell'intervallo, estremi compresi."""
    d, a = date.fromisoformat(dal), date.fromisoformat(al)
    return [(d + timedelta(days=i)).isoformat() for i in range((a - d).days + 1)]


def ultimi_giorni(quanti: int) -> list[str]:
    o = date.today()
    return [(o - timedelta(days=i)).isoformat() for i in range(quanti - 1, -1, -1)]


def settimana_corrente() -> tuple[str, str]:
    """Da lunedì a domenica della settimana in corso."""
    o = date.today()
    lun = o - timedelta(days=o.weekday())
    return lun.isoformat(), (lun + timedelta(days=6)).isoformat()


def mese_corrente() -> tuple[str, str]:
    o = date.today()
    return (date(o.year, o.month, 1).isoformat(),
            date(o.year, o.month, monthrange(o.year, o.month)[1]).isoformat())


def mese_precedente() -> tuple[str, str]:
    o = date.today()
    anno, mese = (o.year - 1, 12) if o.month == 1 else (o.year, o.month - 1)
    return (date(anno, mese, 1).isoformat(),
            date(anno, mese, monthrange(anno, mese)[1]).isoformat())


def anno_corrente() -> tuple[str, str]:
    a = date.today().year
    return date(a, 1, 1).isoformat(), date(a, 12, 31).isoformat()


def _indietro_mesi(riferimento: date, mesi: int) -> date:
    totale = riferimento.year * 12 + (riferimento.month - 1) - mesi
    return date(totale // 12, totale % 12 + 1, 1)


# Periodi selezionabili sui singoli riquadri
PERIODI = {
    "oggi": "Oggi",
    "settimana": "Ultimi 7 giorni",
    "quattordici": "Ultimi 14 giorni",
    "trenta": "Ultimi 30 giorni",
    "mese": "Mese corrente",
    "mese_scorso": "Mese scorso",
    "tre_mesi": "Ultimi 3 mesi",
    "sei_mesi": "Ultimi 6 mesi",
    "dodici_mesi": "Ultimi 12 mesi",
    "anno": "Anno corrente",
    "anno_scorso": "Anno scorso",
    "tutto": "Tutto",
}

FINESTRE = {"7": "7 giorni", "14": "14 giorni", "30": "30 giorni",
            "90": "90 giorni", "180": "6 mesi", "365": "un anno",
            "730": "due anni"}


def intervallo(periodo: str) -> tuple[str, str]:
    """(dal, al) in formato ISO per una delle chiavi di PERIODI."""
    o = date.today()
    if periodo == "oggi":
        return o.isoformat(), o.isoformat()
    if periodo in ("settimana", "quattordici", "trenta"):
        quanti = {"settimana": 7, "quattordici": 14, "trenta": 30}[periodo]
        return (o - timedelta(days=quanti - 1)).isoformat(), o.isoformat()
    if periodo == "mese":
        return mese_corrente()
    if periodo == "mese_scorso":
        return mese_precedente()
    if periodo == "anno":
        return anno_corrente()
    if periodo == "tutto":
        return "0001-01-01", "9999-12-31"
    if periodo == "anno_scorso":
        return date(o.year - 1, 1, 1).isoformat(), date(o.year - 1, 12, 31).isoformat()
    if periodo in ("tre_mesi", "sei_mesi", "dodici_mesi"):
        mesi = {"tre_mesi": 2, "sei_mesi": 5, "dodici_mesi": 11}[periodo]
        return _indietro_mesi(o, mesi).isoformat(), o.isoformat()
    return o.isoformat(), o.isoformat()


def intervallo_precedente(periodo: str) -> tuple[str, str]:
    """Finestra precedente della stessa ampiezza, per i confronti."""
    if periodo == "mese":
        return mese_precedente()
    if periodo == "anno_scorso":
        o = date.today()
        return (date(o.year - 2, 1, 1).isoformat(),
                date(o.year - 2, 12, 31).isoformat())
    if periodo == "tutto":
        return "0001-01-01", "0001-01-01"
    dal, al = intervallo(periodo)
    d, a = date.fromisoformat(dal), date.fromisoformat(al)
    passo = (a - d).days + 1
    return (d - timedelta(days=passo)).isoformat(), (d - timedelta(days=1)).isoformat()


def media(valori) -> float:
    valori = [v for v in valori if v is not None]
    return sum(valori) / len(valori) if valori else 0.0


def scarto(testo: str, valore: float, decimali: int = 1) -> str:
    """«+1,2» / «−0,4»: il segno meno è quello tipografico, non il trattino."""
    segno = "+" if valore > 0 else ("−" if valore < 0 else "")
    return f"{testo}{segno}{numero(abs(valore), decimali)}" if testo else \
        f"{segno}{numero(abs(valore), decimali)}"
