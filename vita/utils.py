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


# -------------------------------------------------------------- orari di orologio
def ore_minuti(testo: str, difetto: int = 0) -> int:
    """«23:00» diventa 1380 minuti; quello che non si capisce vale il difetto."""
    try:
        o, m = testo.split(":")
        return (int(o) % 24) * 60 + int(m) % 60
    except (AttributeError, ValueError):
        return difetto


def minuti_ore(minuti: int) -> str:
    """1380 minuti ridiventa «23:00», qualunque giro di mezzanotte abbia fatto."""
    minuti = int(round(minuti)) % 1440
    return f"{minuti // 60:02d}:{minuti % 60:02d}"


def minuti_notturni(minuti: int, ancora: int = 18 * 60) -> int:
    """Un orario (0..1439) rimesso su un asse che comincia la sera.

    Da `ancora` (le 18, di norma) in poi resta uguale; prima di mezzanotte
    in poi diventa «il giorno dopo». Così 01:07 (67) diventa più tardi di
    23:40 (1420) — 1507 contro 1420 — invece che più presto solo perché il
    numero è più piccolo: sulla stessa notte, le ore piccole vengono *dopo*
    le ore di sera, non prima.

    Ancorare su un'ora fissa, e non sul primo orario che capita, è quello
    che conta: con un riferimento preso dai dati, l'asse di un grafico
    cambiava a seconda di quale notte finiva per prima nell'elenco — la
    stessa settimana disegnata in un ordine diverso usciva con una scala
    diversa. Le 18 sono fisse: nessuno va a letto prima, e il conto non
    dipende più da cosa c'è vicino.
    """
    return minuti if minuti >= ancora else minuti + 1440


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


# ------------------------------------------------- periodi da sfogliare
# Tre modi di guardare gli stessi dati: giorno per giorno, settimana per
# settimana, mese per mese. `scarto` dice di quanti passi si è tornati
# indietro: 0 è adesso.
MODI_PERIODO = {"giorni": "Giorni", "settimane": "Settimane", "mesi": "Mesi"}
# in «giorni» la finestra è una settimana: sette candele larghe, e le
# frecce scorrono da una settimana all'altra invece che da un giorno
QUANTI_PREDEFINITI = {"giorni": 7, "settimane": 12, "mesi": 12}


def intervalli(modo: str = "giorni", quanti: int = 0,
               scarto: int = 0) -> list[tuple[str, str, str]]:
    """Gli intervalli da mostrare, dal più vecchio al più recente.

    Ognuno è (etichetta, primo giorno, ultimo giorno). L'ultimo della lista è
    quello «scelto»: oggi, o il giorno/settimana/mese a cui sei tornato.
    """
    quanti = quanti or QUANTI_PREDEFINITI.get(modo, 14)
    finestre: list[tuple[str, str, str]] = []
    oggi = date.today()
    if modo == "giorni":
        # la settimana del calendario, da lunedì: così «indietro» vuol dire
        # «la settimana prima», non «un giorno prima»
        lunedi = (oggi - timedelta(days=oggi.weekday())
                  - timedelta(weeks=scarto))
        for i in range(quanti):
            giorno = lunedi + timedelta(days=i)
            finestre.append((data_it(giorno.isoformat())[:5],
                             giorno.isoformat(), giorno.isoformat()))
    elif modo == "settimane":
        lunedi = oggi - timedelta(days=oggi.weekday()) - timedelta(weeks=scarto)
        for i in range(quanti - 1, -1, -1):
            inizio = lunedi - timedelta(weeks=i)
            fine = inizio + timedelta(days=6)
            finestre.append((data_it(inizio.isoformat())[:5],
                             inizio.isoformat(), fine.isoformat()))
    else:                                     # mesi
        primo = _indietro_mesi(oggi.replace(day=1), scarto)
        for i in range(quanti - 1, -1, -1):
            inizio = _indietro_mesi(primo, i)
            dopo = _indietro_mesi(inizio, -1)
            fine = dopo - timedelta(days=1)
            finestre.append((etichetta_mese(inizio.isoformat()[:7]),
                             inizio.isoformat(), fine.isoformat()))
    return finestre


def nome_intervallo(modo: str, dal: str, al: str, scarto: int = 0) -> str:
    """Come si chiama l'intervallo scelto: «oggi», «questa settimana», o le date."""
    if modo in ("giorni", "settimane"):
        if scarto == 0:
            return "questa settimana"
        if scarto == 1:
            return "settimana scorsa"
        return f"{data_it(dal)[:5]} – {data_it(al)[:5]}"
    if scarto == 0:
        return "questo mese"
    if scarto == 1:
        return "mese scorso"
    return etichetta_mese(dal[:7])


def media(valori) -> float:
    valori = [v for v in valori if v is not None]
    return sum(valori) / len(valori) if valori else 0.0


def scarto(testo: str, valore: float, decimali: int = 1) -> str:
    """«+1,2» / «−0,4»: il segno meno è quello tipografico, non il trattino."""
    segno = "+" if valore > 0 else ("−" if valore < 0 else "")
    return f"{testo}{segno}{numero(abs(valore), decimali)}" if testo else \
        f"{segno}{numero(abs(valore), decimali)}"
