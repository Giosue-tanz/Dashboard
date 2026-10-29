"""I tre indicatori della barra laterale: emotività, finanza, salute.

Ogni punteggio è una somma di voci dichiarate, non un numero magico: la finestra
mostra il dettaglio nel suggerimento, così si vede sempre da dove arriva.

La finanza fa eccezione nel mostrarsi: il numero in barra è il **patrimonio**,
cioè il saldo di tutti i conti, mentre il punteggio resta nell'anello e nel
dettaglio — di soldi si vuole sapere quanti sono, non quanto valgono da 1 a 100.

In barra si legge il valore e basta: niente confronti con il periodo prima.
"""
from __future__ import annotations

from datetime import date, timedelta

from .utils import euro, intervallo, media, mese_corrente, settimana_corrente

# Obiettivi di riferimento, modificabili dalle impostazioni
PREDEFINITI = {
    "obiettivo_passi": 10000.0,
    "obiettivo_sonno": 450.0,        # minuti
    "obiettivo_allenamenti": 3.0,    # a settimana
    "obiettivo_studio": 1200.0,      # minuti a settimana
    "obiettivo_acqua": 2.0,          # litri
}


def _quota(valore: float, obiettivo: float, punti: float) -> float:
    if obiettivo <= 0:
        return 0.0
    return max(0.0, min(1.0, valore / obiettivo)) * punti


def _finestra(giorni: int = 7) -> tuple[str, str]:
    fine = date.today()
    inizio = fine - timedelta(days=giorni - 1)
    return inizio.isoformat(), fine.isoformat()


# ------------------------------------------------------------------ emotività
def emotivita(db) -> tuple[float, list[tuple[str, float, float]]]:
    dal, al = _finestra(7)
    m = db.medie_periodo(dal, al)
    giorni_scritti = len(db.medie_giorno(dal, al))
    if not m["n"]:
        return 0.0, [("nessuna voce negli ultimi 7 giorni", 0, 100)]
    voci = [
        ("umore medio", _quota(m["umore"] - 1, 9, 45), 45),
        ("energia", _quota(m["energia"] - 1, 9, 15), 15),
        # stress 1 = calma piena, stress 10 = nessun punto
        ("calma (stress basso)", _quota(10 - m["stress"], 9, 20), 20),
        ("costanza del diario", _quota(giorni_scritti, 7, 20), 20),
    ]
    return sum(v for _, v, _ in voci), voci


# ---------------------------------------------------------------------- salute
def salute(db) -> tuple[float, list[tuple[str, float, float]]]:
    dal, al = _finestra(7)
    giorni = db.giorni_salute(dal, al)
    passi = media([r["passi"] for r in giorni.values() if r["passi"]])
    sonno = media([r["sonno"] for r in giorni.values() if r["sonno"]])
    allen = len(db.allenamenti(dal, al))
    voci = [
        ("passi", _quota(passi, db.leggi_num("obiettivo_passi",
                                             PREDEFINITI["obiettivo_passi"]), 30), 30),
        ("sonno", _quota(sonno, db.leggi_num("obiettivo_sonno",
                                             PREDEFINITI["obiettivo_sonno"]), 30), 30),
        ("allenamenti", _quota(allen, db.leggi_num("obiettivo_allenamenti",
                                                   PREDEFINITI["obiettivo_allenamenti"]), 25), 25),
        ("giorni registrati", _quota(len(giorni), 7, 15), 15),
    ]
    return sum(v for _, v, _ in voci), voci


# --------------------------------------------------------------------- finanza
def finanza(db, fonte) -> tuple[float, list[tuple[str, float, float]]]:
    dal, al = mese_corrente()
    entrate, uscite = fonte.totali_periodo(dal, al)
    risparmio = entrate - uscite
    tasso = (risparmio / entrate) if entrate > 0 else (0.0 if uscite else 0.5)

    budget = fonte.budget()
    if budget:
        rispettati = sum(1 for _, limite, speso in budget if limite > 0 and speso <= limite)
        punti_budget = _quota(rispettati, max(1, len([b for b in budget if b[1] > 0])), 30)
        nota_budget = f"budget rispettati ({rispettati}/{len(budget)})"
    else:
        punti_budget = 30.0 if risparmio >= 0 else 0.0
        nota_budget = "conti in ordine (nessun budget impostato)"

    obiettivi = fonte.obiettivi()
    if obiettivi:
        avanzamenti = [min(1.0, acc / obi) for _, obi, acc, _ in obiettivi if obi > 0]
        punti_obiettivi = media(avanzamenti) * 20 if avanzamenti else 0.0
        nota_obiettivi = f"obiettivi di risparmio ({len(obiettivi)})"
    else:
        punti_obiettivi = 10.0
        nota_obiettivi = "nessun obiettivo impostato"

    movimenti = len(fonte.movimenti(dal, al))
    voci = [
        ("quota risparmiata", max(0.0, min(1.0, tasso / 0.3)) * 40, 40),
        (nota_budget, punti_budget, 30),
        (nota_obiettivi, punti_obiettivi, 20),
        ("movimenti registrati", _quota(movimenti, 10, 10), 10),
    ]
    return sum(v for _, v, _ in voci), voci


# ----------------------------------------------------------------------- tutti
def tutti(db, fonte) -> dict[str, dict]:
    """I tre indicatori con il dettaglio delle voci che li compongono."""
    risultato = {}
    for chiave, funzione in (("emotivita", lambda: emotivita(db)),
                             ("finanza", lambda: finanza(db, fonte)),
                             ("salute", lambda: salute(db))):
        valore, voci = funzione()
        risultato[chiave] = {"valore": round(valore), "voci": voci}
    risultato["finanza"].update(patrimonio(fonte))
    return risultato


def patrimonio(fonte) -> dict:
    """Il saldo di tutti i conti, conto per conto."""
    try:
        saldo = float(fonte.saldo())
    except Exception:
        saldo = 0.0
    try:
        conti = list(fonte.conti())
    except Exception:
        conti = []
    return {"saldo": saldo, "conti": conti}


def dettaglio_finanza(dati: dict) -> str:
    """Suggerimento della finanza: prima il patrimonio, poi i conti, poi il punteggio."""
    righe = [f"Patrimonio: {euro(dati.get('saldo', 0.0))}",
             "il saldo di tutti i conti", ""]
    for nome, saldo in dati.get("conti", []):
        righe.append(f"  {nome}: {euro(saldo)}")
    if dati.get("conti"):
        righe.append("")
    righe.append(f"Stato dei conti: {dati['valore']} su 100")
    for voce, punti, massimo in dati["voci"]:
        righe.append(f"  {voce}: {punti:.0f} / {massimo:.0f}")
    return "\n".join(righe)


def dettaglio_testo(nome: str, dati: dict) -> str:
    """Testo del suggerimento: le voci che compongono il punteggio."""
    righe = [f"{nome}: {dati['valore']} su 100", ""]
    for voce, punti, massimo in dati["voci"]:
        righe.append(f"  {voce}: {punti:.0f} / {massimo:.0f}")
    return "\n".join(righe)
