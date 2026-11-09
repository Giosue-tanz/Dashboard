"""Tess dentro la Dashboard: la stessa AI locale, con i tuoi dati già in mano.

Tess vive in `~/Scrivania/WORK/AI-Locale`: motore Ollama in una rete isolata,
nessuna connessione verso internet. Qui non si duplica niente — si parla con
quel motore e basta, sulla sua API locale.

Due regole che reggono tutto il file:

* **si accende solo quando lo chiedi.** Finché non premi «Attiva Tess» non
  parte nessun servizio, non si carica nessun modello, non si occupa VRAM.
* **i dati restano in casa.** Il riassunto della Dashboard che Tess riceve
  viaggia da questo processo al motore sul tuo PC, e si può spegnere con
  l'interruttore nel riquadro.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta

from PySide6.QtCore import (QEasingCurve, QEvent, QPoint, QPropertyAnimation,
                            QRect, QSize, QThread, QTimer, Qt, Signal)
from PySide6.QtGui import QColor, QFontMetrics
from PySide6.QtWidgets import (QApplication, QFrame, QGraphicsDropShadowEffect,
                               QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMenu, QMessageBox,
                               QPlainTextEdit, QPushButton, QScrollArea,
                               QSizePolicy, QVBoxLayout, QWidget)

from . import punteggi as calcolo
from .componenti import (BarraAttesa, BottoneIcona, BottonePannello,
                         Interruttore)
from .utils import (GIORNI, MESI, data_it, data_lunga, durata, euro, media,
                    numero, relativa, settimana_corrente, ultimi_giorni)

BASE_PREDEFINITA = os.path.expanduser("~/Scrivania/WORK/AI-Locale")
SERVIZIO = "ai-locale.service"

# il nome mostrato di una conversazione, tenuto da parte sulla voce: serve
# quando si rinomina, per far ricomparire nell'editor quello che si legge
RUOLO_NOME = Qt.UserRole + 1
RUOLO_GRUPPO = Qt.UserRole + 2      # «OGGI», «IERI»… sono titoletti, non chat


def base(db) -> str:
    """Dove sta installata Tess: modificabile dalle impostazioni."""
    return db.leggi("percorso_tess", "") or BASE_PREDEFINITA


def configurazione(cartella: str) -> dict:
    """Legge `config/env` di Tess: indirizzo del motore e nome del modello."""
    dati = {"host": "172.28.0.1:11434", "nome": "Tess"}
    percorso = os.path.join(cartella, "config", "env")
    try:
        with open(percorso, encoding="utf-8") as f:
            for riga in f:
                riga = riga.strip()
                if riga.startswith("export OLLAMA_HOST="):
                    dati["host"] = riga.split("=", 1)[1].strip().strip('"\'')
                elif riga.startswith("NOME_AI="):
                    dati["nome"] = riga.split("=", 1)[1].strip().strip('"\'')
    except OSError:
        pass
    return dati


class Motore:
    """Il motore di Tess visto da qui: c'è, risponde, si accende."""

    def __init__(self, db):
        self.db = db
        self.cartella = base(db)
        conf = configurazione(self.cartella)
        self.host = conf["host"]
        self.nome = conf["nome"]

    # ------------------------------------------------------------- stato
    def installata(self) -> bool:
        return os.path.isdir(os.path.join(self.cartella, "config"))

    def chiama(self, percorso: str, dati: dict | None = None, attesa: float = 2.0):
        """Una chiamata all'API locale del motore. Niente rete, solo questo PC."""
        url = f"http://{self.host}{percorso}"
        corpo = json.dumps(dati).encode() if dati is not None else None
        richiesta = urllib.request.Request(
            url, data=corpo, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(richiesta, timeout=attesa) as risposta:
            return json.loads(risposta.read().decode())

    def attiva(self) -> bool:
        try:
            self.chiama("/api/version", attesa=1.5)
            return True
        except Exception:
            return False

    def modello(self) -> str:
        """Il modello da usare: quello col nome di Tess, se c'è."""
        try:
            disponibili = [m["name"] for m in self.chiama("/api/tags").get("models", [])]
        except Exception:
            return self.nome
        for nome in disponibili:
            if nome.split(":")[0].lower() == self.nome.lower():
                return nome
        return disponibili[0] if disponibili else self.nome

    def accendi(self) -> tuple[bool, str]:
        """Avvia il servizio del motore (non l'interfaccia web, qui non serve)."""
        try:
            esito = subprocess.run(
                ["systemctl", "--user", "start", SERVIZIO],
                capture_output=True, text=True, timeout=30)
        except FileNotFoundError:
            return False, "systemctl non disponibile su questo sistema."
        except subprocess.TimeoutExpired:
            return False, "Il servizio ci sta mettendo troppo."
        if esito.returncode != 0:
            return False, (esito.stderr or "").strip() or "Il servizio non è partito."
        return True, ""

    def in_memoria(self) -> bool:
        """Il modello è già salito in VRAM?"""
        try:
            caricati = self.chiama("/api/ps").get("models", [])
        except Exception:
            return False
        atteso = self.modello().split(":")[0].lower()
        return any(m["name"].split(":")[0].lower() == atteso for m in caricati)

    def precarica(self) -> bool:
        """Porta il modello in VRAM prima che arrivi la prima domanda.

        Il motore risponde subito dopo l'avvio, ma il modello entra in memoria
        solo alla prima richiesta: sono i secondi che si aspettavano dopo aver
        scritto. Qui quell'attesa si sposta sull'accensione, dove è prevista.
        """
        try:
            self.chiama("/api/generate",
                        {"model": self.modello(), "prompt": "", "keep_alive": -1},
                        attesa=180)
            return True
        except Exception:
            return False

    def spegni(self) -> None:
        subprocess.run(["systemctl", "--user", "stop", SERVIZIO],
                       capture_output=True, text=True, timeout=30)


class Accensione(QThread):
    """Accende il motore, poi carica il modello: due attese, una sola volta."""

    fase = Signal(str)                 # «motore» · «modello»
    pronta = Signal(bool, str)

    def __init__(self, motore: Motore, parent=None):
        super().__init__(parent)
        self.motore = motore

    def run(self) -> None:
        if not self.motore.installata():
            self.pronta.emit(
                False, f"Non trovo Tess in {self.motore.cartella}.")
            return
        if not self.motore.attiva():
            self.fase.emit("motore")
            ok, errore = self.motore.accendi()
            if not ok:
                self.pronta.emit(False, errore)
                return
        acceso = False
        for _ in range(40):                     # fino a ~20 secondi
            if self.motore.attiva():
                acceso = True
                break
            self.msleep(500)
        if not acceso:
            self.pronta.emit(False, "Il motore non risponde sulla sua porta locale.")
            return
        if not self.motore.in_memoria():
            self.fase.emit("modello")
            self.motore.precarica()
        self.pronta.emit(True, "")


class Risposta(QThread):
    """Una domanda a Tess, con la risposta che arriva a pezzi mentre la scrive."""

    pezzo = Signal(str)
    finita = Signal()
    errore = Signal(str)

    def __init__(self, motore: Motore, messaggi: list[dict], parent=None):
        super().__init__(parent)
        self.motore = motore
        self.messaggi = messaggi
        self._fermare = False

    def ferma(self) -> None:
        self._fermare = True

    def run(self) -> None:
        corpo = json.dumps({
            "model": self.motore.modello(),
            "messages": self.messaggi,
            "stream": True,
        }).encode()
        richiesta = urllib.request.Request(
            f"http://{self.motore.host}/api/chat", data=corpo,
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(richiesta, timeout=120) as risposta:
                for riga in risposta:
                    if self._fermare:
                        break
                    riga = riga.strip()
                    if not riga:
                        continue
                    try:
                        dati = json.loads(riga.decode())
                    except ValueError:
                        continue
                    testo = (dati.get("message") or {}).get("content", "")
                    if testo:
                        self.pezzo.emit(testo)
                    if dati.get("done"):
                        break
        except urllib.error.URLError as e:
            self.errore.emit(f"Il motore non risponde ({e.reason}).")
            return
        except Exception as e:                  # noqa: BLE001 — qualunque intoppo
            self.errore.emit(str(e))
            return
        self.finita.emit()


# --------------------------------------------------------------- il contesto
# A quale area appartiene ogni blocco del riassunto: serve per lasciarne
# fuori quelli che non vuoi far vedere a Tess (Impostazioni → Tess).
AREE_CONTESTO = {
    "salute": ("OGGI", "SALUTE"),
    "punteggi": ("PUNTEGGI",),
    "accademica": ("ACCADEMICA", "ESAMI"),
    "carriera": ("PROGETTI", "LAVORO"),
    "abitudini": ("ABITUDINI",),
    "finanza": ("FINANZA",),
    "scadenze": ("IN ARRIVO",),
}


def aree_scelte(db) -> set[str]:
    """Le aree che Tess può vedere: di suo le vede tutte."""
    salvate = db.leggi("tess_aree", "")
    if not salvate:
        return set(AREE_CONTESTO)
    return {a for a in salvate.split(",") if a in AREE_CONTESTO}


# Quanti giorni del passato Tess si porta dietro uno per uno: due settimane
# coprono «ieri», «lunedì», «la settimana scorsa» senza allungare troppo il
# riassunto.
GIORNI_DETTAGLIATI = 14

# Come si dice che un dato quel giorno non c'è. Un trattino il modello lo
# salta e va a pescare il numero della riga vicina: una parola no.
MANCA = "non registrato"


def _etichetta_giorno(iso: str) -> str:
    """«oggi, giovedì 29 ottobre 2026 (29/10)»: giorno della settimana e data
    già fatti, e scritti in tutti e due i modi in cui li si nomina.

    Scritta solo come 29/10/2026 il modello fatica ad agganciarla a «il 29
    ottobre», e finisce per rispondere con la riga sbagliata.
    """
    d = date.fromisoformat(iso)
    scarto = (date.today() - d).days
    davanti = "oggi, " if scarto == 0 else ("ieri, " if scarto == 1 else "")
    return f"{davanti}{data_lunga(iso)} ({data_it(iso)})"


def giorno_per_giorno(db, aree: set[str], quanti: int = GIORNI_DETTAGLIATI,
                      giorni: list[str] | None = None) -> list[str]:
    """Una riga per giorno con i numeri di quel giorno, non le medie.

    È la parte che evita le risposte inventate: senza, a «quanti passi ho fatto
    martedì?» un modello piccolo risponde lo stesso, a caso. Con `giorni` si
    chiede la riga di giornate precise invece degli ultimi tot.
    """
    giorni = giorni or ultimi_giorni(quanti)
    dal, al = giorni[0], giorni[-1]
    salute = db.giorni_salute(dal, al)
    umori = {r["data"]: r for r in db.medie_giorno(dal, al)}
    studio: dict[str, int] = {}
    for r in db.studio(dal, al):
        studio[r["data"]] = studio.get(r["data"], 0) + int(r["minuti"] or 0)
    lavoro: dict[str, int] = {}
    for r in db.lavoro(dal, al):
        lavoro[r["data"]] = lavoro.get(r["data"], 0) + int(r["minuti"] or 0)
    mosse: dict[str, list[str]] = {}
    for r in db.allenamenti(dal, al):
        mosse.setdefault(r["data"], []).append(
            f"{r['tipo']} {durata(r['minuti'])}" if r["minuti"] else r["tipo"])
    abitudini = db.abitudini()
    segnate = db.registro(dal, al) if abitudini else set()

    def valore(riga, campo, decimali=0, unita=""):
        """Il numero formattato, o «» quando quel giorno non c'è."""
        if riga is None or not riga[campo]:
            return ""
        return f"{numero(float(riga[campo]), decimali)}{unita}"

    righe = []
    for giorno in reversed(giorni):
        s, u = salute.get(giorno), umori.get(giorno)
        # i dati che ci sono davanti, quelli che mancano in coda per nome: una
        # riga mezza vuota di «non registrato» fa pescare il campo sbagliato
        presenti, mancanti = [], []
        def metti(nome, scritto):
            (presenti.append(f"{nome} {scritto}") if scritto
             else mancanti.append(nome))
        if "salute" in aree:
            metti("passi", valore(s, "passi"))
            metti("sonno", durata(s["sonno"]) if s and s["sonno"] else "")
            metti("umore", valore(u, "umore", 1, "/10"))
            metti("energia", valore(u, "energia", 1))
            metti("stress", valore(u, "stress", 1))
            metti("battito", valore(s, "battito", 0, " bpm"))
            metti("peso", valore(s, "peso", 1, " kg"))
            metti("allenamento", ", ".join(mosse.get(giorno, [])))
        if "accademica" in aree:
            metti("studio", durata(studio[giorno]) if studio.get(giorno) else "")
        if "carriera" in aree:
            metti("lavoro", durata(lavoro[giorno]) if lavoro.get(giorno) else "")
        if "abitudini" in aree and abitudini:
            quante = sum(1 for (g, _) in segnate if g == giorno)
            metti("abitudini", f"{quante}/{len(abitudini)}" if quante else "")
        if not presenti and not mancanti:
            continue
        testa = f"{_etichetta_giorno(giorno)}: "
        if not presenti:
            righe.append(testa + "nessun dato registrato")
            continue
        righe.append(testa + " · ".join(presenti))
        if mancanti:
            # su una riga sua: in coda ai valori se la pesca al posto loro
            righe.append(f"   (quel giorno non sono stati registrati: "
                         + ", ".join(mancanti) + ")")
    return righe


# Parole con cui si nomina un giorno nelle domande. Il giorno chiesto lo
# trova il codice: un modello piccolo, lasciato a cercarselo nella tabella,
# finisce per rispondere col numero della riga sbagliata.
_RELATIVI = {
    "oggi": 0, "stamattina": 0, "stasera": 0, "stanotte": 0,
    "ieri": 1, "l'altro ieri": 2, "altro ieri": 2, "altroieri": 2,
    "domani": -1, "dopodomani": -2,          # giorni che non esistono ancora
}
_MESI_NUMERO = {nome: i + 1 for i, nome in enumerate(MESI)}
_MESI_NUMERO.update({nome[:3]: i + 1 for i, nome in enumerate(MESI)})
_SETTIMANA = {}
for _i, _nome in enumerate(GIORNI):
    _SETTIMANA[_nome] = _i
    _SETTIMANA[_nome.replace("ì", "i")] = _i


def _nominato(testo: str, parola: str) -> bool:
    return any(f" {parola}{coda}" in testo for coda in (" ", ",", "?", ".", ";", "!"))


def date_chieste(domanda: str, oggi: date | None = None,
                 quante: int = 3) -> list[date]:
    """I giorni nominati in una domanda, dal più recente.

    Riconosce «ieri», «martedì», «il 24 ottobre», «24/10», «2026-10-24».
    Lista vuota quando la domanda non parla di giorni precisi.
    """
    oggi = oggi or date.today()
    testo = " " + domanda.lower().strip() + " "
    trovate: set[date] = set()

    def aggiungi(anno, mese, giorno, anno_detto=True):
        try:
            quando = date(anno, mese, giorno)
        except ValueError:
            return
        # senza anno si intende l'ultima volta che è capitata quella data
        if not anno_detto and quando > oggi:
            quando = quando.replace(year=anno - 1)
        trovate.add(quando)

    for m in re.finditer(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", testo):
        aggiungi(int(m[1]), int(m[2]), int(m[3]))
    for m in re.finditer(r"\b(\d{1,2})[/.](\d{1,2})(?:[/.](\d{2,4}))?\b", testo):
        anno = int(m[3]) if m[3] else oggi.year
        aggiungi(anno + 2000 if anno < 100 else anno, int(m[2]), int(m[1]), bool(m[3]))
    nomi = "|".join(_MESI_NUMERO)
    for m in re.finditer(rf"\b(\d{{1,2}})\s+({nomi})[a-z]*\b(?:\s+(\d{{4}}))?",
                         testo):
        anno = int(m[3]) if m[3] else oggi.year
        aggiungi(anno, _MESI_NUMERO[m[2]], int(m[1]), bool(m[3]))

    # dalle più lunghe: «l'altro ieri» contiene «ieri»
    for parola, indietro in sorted(_RELATIVI.items(), key=lambda kv: -len(kv[0])):
        if _nominato(testo, parola):
            trovate.add(oggi - timedelta(days=indietro))
            break
    for nome, indice in _SETTIMANA.items():
        if _nominato(testo, nome):
            # «di martedì» quando oggi è martedì vuol dire oggi
            trovate.add(oggi - timedelta(days=(oggi.weekday() - indice) % 7))
    return sorted(trovate, reverse=True)[:quante]


def data_chiesta(domanda: str, oggi: date | None = None) -> date | None:
    """Il giorno nominato in una domanda, o None."""
    giorni = date_chieste(domanda, oggi, quante=1)
    return giorni[0] if giorni else None


def blocco_giorni_chiesti(db, aree: set[str], quando: list[date]) -> list[str]:
    """Le righe dei giorni nominati nella domanda, e nient'altro.

    Quando la domanda parla di un giorno, il resto della tabella sparisce: con
    quattordici righe davanti un modello piccolo copia il numero della riga
    sbagliata, con una sola legge quella giusta.
    """
    oggi = date.today()
    passati = [q for q in quando if q <= oggi]
    futuri = [q for q in quando if q > oggi]
    righe = []
    if passati:
        dettaglio = giorno_per_giorno(db, aree,
                                      giorni=sorted(q.isoformat() for q in passati))
        if dettaglio:
            righe.append(
                "GIORNO CHIESTO nella domanda. Rispondi usando solo queste "
                "righe: il numero che ti serve è qui dentro, non prenderlo da "
                "nessun'altra parte. Un dato elencato fra quelli «non "
                "registrati» quel giorno non c'è: dillo, non è uno zero e non "
                "è il valore di un altro giorno.")
            righe.extend(dettaglio)
    for q in futuri:
        righe.append(f"GIORNO CHIESTO: {data_lunga(q.isoformat())} non è ancora "
                     "arrivato. Nessuno può sapere quei numeri: rispondi che "
                     "è un giorno che deve ancora venire, non dire zero.")
    return righe


def contesto(db, fonte, aree: set[str] | None = None,
             domanda: str = "") -> str:
    """Il riassunto della Dashboard che Tess riceve insieme alla domanda.

    Solo numeri già presenti nell'archivio: nessun testo del diario, che resta
    cosa tua. Serve perché Tess risponda sui tuoi dati senza fartene l'elenco.
    Con `aree` si tiene dentro solo una parte del riassunto; con `domanda` si
    mette in cima il giorno che la domanda nomina, già trovato.
    """
    oggi = date.today().isoformat()
    aree = set(AREE_CONTESTO) if aree is None else aree
    righe = [f"Dati veri della Dashboard di Giosuè. Oggi è {data_lunga(oggi)}.",
             "Sono già in tuo possesso: usali, non chiederglieli. Riporta i "
             "numeri come stanno scritti qui: non arrotondarli, non stimarli, "
             "non inventarne altri.", ""]

    chiesti = date_chieste(domanda) if domanda else []
    blocco = blocco_giorni_chiesti(db, aree, chiesti) if chiesti else []
    if blocco:
        righe.extend(blocco + [""])

    # ------------------------------------------------------------- oggi
    medie = db.medie_periodo(oggi, oggi)
    salute_oggi = db.salute_giorno(oggi)
    pezzi = []
    if medie["n"]:
        pezzi.append(f"umore {numero(medie['umore'], 1)}/10, "
                     f"energia {numero(medie['energia'], 1)}, "
                     f"stress {numero(medie['stress'], 1)}, "
                     f"lucidità {numero(medie['lucidita'], 1)}")
    else:
        pezzi.append("nessuna voce di diario scritta")
    if salute_oggi and salute_oggi["passi"]:
        obiettivo_passi = db.leggi_num("obiettivo_passi", 10000)
        quota = (salute_oggi["passi"] / obiettivo_passi * 100) if obiettivo_passi else 0
        pezzi.append(f"{numero(salute_oggi['passi'], 0)} passi "
                     f"({quota:.0f}% dell'obiettivo di {numero(obiettivo_passi, 0)})")
    if salute_oggi and salute_oggi["sonno"]:
        pezzi.append(f"ha dormito {durata(salute_oggi['sonno'])}")
    minuti_studio = db.minuti_studio(oggi, oggi)
    minuti_lavoro = db.minuti_lavoro(oggi, oggi)
    if minuti_studio:
        pezzi.append(f"{durata(minuti_studio)} di studio")
    if minuti_lavoro:
        pezzi.append(f"{durata(minuti_lavoro)} di lavoro")
    righe.append("OGGI: " + " · ".join(pezzi))

    # --------------------------------------------------------- punteggi
    try:
        dati = calcolo.tutti(db, fonte)
        righe.append(
            f"PUNTEGGI (0-100): emotività {dati['emotivita']['valore']}, "
            f"salute {dati['salute']['valore']}, "
            f"finanza {dati['finanza']['valore']} "
            f"(patrimonio {euro(dati['finanza'].get('saldo', 0.0))})")
    except Exception:
        pass

    # ----------------------------------------------------------- salute
    settimana = ultimi_giorni(7)
    giorni = db.giorni_salute(settimana[0], settimana[-1])
    def medio(campo):
        valori = [float(r[campo]) for r in giorni.values() if r[campo]]
        return media(valori), len(valori)
    passi, n_passi = medio("passi")
    sonno, n_sonno = medio("sonno")
    battito, n_battito = medio("battito")
    salute_righe = []
    if n_passi:
        salute_righe.append(f"passi medi {numero(passi, 0)} su {n_passi} giorni")
    if n_sonno:
        salute_righe.append(f"sonno medio {durata(sonno)} su {n_sonno} notti")
    if n_battito:
        salute_righe.append(f"battito a riposo {numero(battito, 0)} bpm")
    dal, al = settimana_corrente()
    allenamenti = len(db.allenamenti(dal, al))
    # `medio` torna (media, quanti giorni): prenderlo come un numero solo
    # faceva saltare tutto il riassunto, e Tess restava senza dati
    stress, n_stress = medio("stress")
    if n_stress:
        salute_righe.append(f"stress medio {numero(stress, 0)} su 100")
    salute_righe.append(f"{allenamenti} allenamenti questa settimana")
    righe.append("SALUTE (7 giorni): " + " · ".join(salute_righe))

    # ------------------------------------------------------- accademica
    libretto = db.riepilogo_libretto()
    da_dare = [e for e in db.esami() if e["stato"] != "superato"]
    totale_cfu = int(db.leggi_num("cfu_laurea", 180))
    acquisiti = int(libretto["cfu"])
    # i conti già fatti: un modello piccolo sbaglia le sottrazioni
    righe.append(
        f"ACCADEMICA: {libretto['n']} esami superati · "
        f"{acquisiti} CFU acquisiti sui {totale_cfu} della laurea, "
        f"ne mancano {max(0, totale_cfu - acquisiti)} · "
        f"media {numero(libretto['media'], 1)} · "
        f"media ponderata {numero(libretto['ponderata'], 1)}")
    if da_dare:
        elenco = ", ".join(
            f"{e['nome']} ({e['cfu']} CFU"
            + (f", appello {data_it(e['data_esame'])}" if e["data_esame"] else "")
            + ")" for e in da_dare[:6])
        righe.append(f"ESAMI DA DARE ({len(da_dare)} in tutto): {elenco}")

    # ---------------------------------------------------------- carriera
    progetti = [p for p in db.progetti() if p["stato"] in ("corso", "pausa")]
    if progetti:
        righe.append("PROGETTI: " + ", ".join(
            f"{p['nome']} {p['avanzamento']}%" for p in progetti[:6]))
    ore = db.minuti_lavoro(dal, al)
    if ore:
        righe.append(f"LAVORO: {durata(ore)} questa settimana")

    # --------------------------------------------------------- abitudini
    serie = []
    for a in db.abitudini():
        giorni_serie = db.serie_abitudine(a["id"])
        if giorni_serie:
            serie.append(f"{a['nome']} da {giorni_serie} "
                         f"{'giorno' if giorni_serie == 1 else 'giorni'}")
    if serie:
        righe.append("ABITUDINI IN CORSO: " + ", ".join(serie))

    # ----------------------------------------------------------- finanza
    try:
        mese_dal, mese_al = (date.today().replace(day=1).isoformat(), oggi)
        entrate, uscite = fonte.totali_periodo(mese_dal, mese_al)
        righe.append(f"FINANZA (mese): entrate {euro(entrate)}, uscite {euro(uscite)}")
    except Exception:
        pass

    # ---------------------------------------------------- giorno per giorno
    dettaglio = [] if blocco else giorno_per_giorno(db, aree)
    if dettaglio:
        righe.append("")
        righe.append(
            f"GIORNO PER GIORNO: una riga per giorno, dal più recente, "
            f"da {data_lunga(ultimi_giorni(GIORNI_DETTAGLIATI)[0])} a oggi. "
            "Sono gli unici giorni che conosci uno per uno: di una data fuori "
            "da questo elenco di' che non ce l'hai, non tirare a indovinare. "
            "Cerca la riga che porta la data chiesta e leggi solo quella: "
            "mai il numero di un altro giorno, nemmeno quello più vicino. "
            "Sotto ogni riga c'è l'elenco di quello che quel giorno non è "
            "stato registrato: se ti chiede uno di quelli, rispondi che non "
            "c'è — non è uno zero. Il giorno della settimana è già scritto: "
            "usa quello, non ricavarlo.")
        righe.extend(dettaglio)
        righe.append("")

    # --------------------------------------------------------- scadenze
    prossime = db.query(
        "SELECT * FROM scadenze WHERE fatta=0 AND data >= ? ORDER BY data LIMIT 4",
        (oggi,))
    if prossime:
        righe.append("IN ARRIVO: " + ", ".join(
            f"{s['titolo']} {data_lunga(s['data'])}" for s in prossime))

    fuori = tuple(parola for area, parole in AREE_CONTESTO.items()
                  if area not in aree for parola in parole)
    if fuori:
        righe = [r for r in righe if not r.startswith(fuori)]
    return "\n".join(righe)


# Come deve comportarsi Tess: si sceglie da Impostazioni → Tess.
TONI = {
    "asciutta": "Parla asciutto: nessun giro di parole, nessun complimento.",
    "incoraggiante": "Sii calda e incoraggiante: nota i progressi e dillo, "
                     "senza però addolcire i numeri.",
    "diretta": "Sii diretta anche quando la risposta non piace: se un dato va "
               "male, dillo chiaro e di' cosa cambieresti.",
    "ironica": "Puoi essere ironica e leggera, ma i numeri restano seri.",
    "professionale": "Tono professionale e ordinato, come un referto breve.",
}
LUNGHEZZE = {
    "brevi": "Rispondi in due o tre righe.",
    "normali": "Risposte brevi, al punto.",
    "lunghe": "Puoi allargarti quando serve, restando ordinata.",
}
TONO_PREDEFINITO, LUNGHEZZA_PREDEFINITA = "asciutta", "normali"

ISTRUZIONI = (
    "Sei Tess e stai rispondendo dentro la Dashboard di Giosuè. "
    "Hai sott'occhio i suoi dati: parla di quelli, con i numeri giusti, senza "
    "ripeterglieli tutti. Risposte brevi, al punto, come al solito. "
    "Se un dato non c'è, dillo invece di inventarlo."
)


# Come sta coi dati: li ha sott'occhio, ma non li recita. Questa riga è la
# sola che non si tocca: senza, un modello piccolo comincia ogni risposta con
# l'elenco dei numeri del giorno.
RIGA_DATI = (
    "Hai i suoi dati sott'occhio: tienili lì, non elencarli. Tirali in ballo "
    "quando te li chiede o quando c'entrano davvero con quello di cui state "
    "parlando, e solo nei momenti opportuni."
)
RIGA_ONESTA = (
    "Se un dato non c'è, dillo invece di inventarlo. Di un giorno preciso "
    "rispondi solo se quel giorno è nei dati che hai sott'occhio: niente "
    "stime, e il giorno della settimana prendilo da lì invece di ricavarlo."
)


def solo_istruzioni_tue(db) -> bool:
    """L'interruttore «solo le mie»: tono e lunghezza non vengono mandati."""
    return db.leggi("tess_solo_mie", "0") == "1"


def componi_istruzioni(nome: str, sue: str, tono: str, lunghezza: str,
                       solo_mie: bool) -> str:
    """Le istruzioni che Tess riceve, a partire dai pezzi.

    Una funzione sola per quelle vere e per l'anteprima delle impostazioni:
    erano due copie della stessa regola, e bastava cambiarne una perché
    l'anteprima raccontasse una cosa diversa da quella che arriva a Tess.
    """
    nome = (nome or "Tess").strip()
    sue = (sue or "").strip()
    if solo_mie and sue:
        # «Solo le mie» vuol dire **solo le mie**: fuori il nome, lo stile e
        # le due righe di prudenza. Prima restavano dentro, e chi se le era
        # già scritte nelle sue istruzioni — come è naturale fare — se le
        # ritrovava due volte di fila nello stesso prompt.
        return sue
    pezzi = [f"Ti chiami {nome} e stai rispondendo dentro la Dashboard di "
             "Giosuè.", RIGA_DATI,
             TONI.get(tono, TONI[TONO_PREDEFINITO]),
             LUNGHEZZE.get(lunghezza, LUNGHEZZE[LUNGHEZZA_PREDEFINITA]),
             RIGA_ONESTA]
    if sue:
        # quello che scrive lui conta più di tutto il resto
        pezzi.append("Istruzioni sue, che valgono sopra le altre: " + sue)
    return " ".join(pezzi)


def istruzioni(db) -> str:
    """Le istruzioni di Tess, messe insieme da come l'hai impostata."""
    return componi_istruzioni(
        db.leggi("tess_nome", ""),
        db.leggi("tess_istruzioni", ""),
        db.leggi("tess_tono", TONO_PREDEFINITO),
        db.leggi("tess_lunghezza", LUNGHEZZA_PREDEFINITA),
        solo_istruzioni_tue(db))


# ----------------------------------------------------------- pezzi della chat
class Messaggio(QWidget):
    """Un messaggio in pagina.

    Tess parla **senza bolla**: un filo della sua tinta a sinistra e il testo
    largo quanto la pagina — una risposta lunga si legge come un testo, non
    come un cartello. Quello che scrivi tu resta in una bolla a destra, in
    grigio: l'occhio capisce di chi è la riga senza blocchi di colore.

    Sotto, al passaggio del mouse, compaiono le azioni — copia, e per le tue
    domande anche modifica — con l'eliminazione per tutti. Il posto della riga
    è già suo anche quando non si vede, così la chat non salta su e giù.
    """

    modificato = Signal(int, str)        # id della riga, testo nuovo
    eliminato = Signal(int)

    def __init__(self, chi: str, testo: str, colori: dict,
                 id_messaggio: int = 0, parent=None):
        super().__init__(parent)
        self.chi = chi
        self.c = colori
        self.id_messaggio = id_messaggio
        self.editor: QPlainTextEdit | None = None
        self.setObjectName("ContenutoSezione")
        self.setAttribute(Qt.WA_StyledBackground, True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.testo = QLabel(testo)
        self.testo.setWordWrap(True)
        self.testo.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.testo.setObjectName("BollaTu" if chi == "tu" else "TestoTess")
        self.testo.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)

        self.riga = QHBoxLayout()
        self.riga.setContentsMargins(0, 0, 0, 0)
        self.riga.setSpacing(11)
        if chi == "tu":
            self.riga.addStretch(1)
            self.riga.addWidget(self.testo)
        else:
            # un filo verticale alto quanto la risposta, al posto del tondo
            self.filo = QFrame()
            self.filo.setObjectName("FiloTess")
            self.riga.addWidget(self.filo)
            self.riga.addWidget(self.testo, 1)
        lay.addLayout(self.riga)

        self.azioni = QHBoxLayout()
        self.azioni.setContentsMargins(0 if chi == "tu" else 13, 0, 0, 0)
        self.azioni.setSpacing(2)
        if chi == "tu":
            self.azioni.addStretch(1)
        self.bottoni: list[QPushButton] = []
        # icone disegnate invece di parole: una fila di tre scritte sotto
        # ogni messaggio pesava più del messaggio
        if chi == "tu":
            self.b_modifica = self._azione("matita", "Modifica la domanda",
                                           self.apri_modifica)
        self.b_copia = self._azione("copia", "Copia il testo", self._copia)
        self.b_elimina = self._azione("cestino", "Elimina questo messaggio",
                                      self._chiedi_elimina)
        if chi != "tu":
            self.azioni.addStretch(1)
        lay.addLayout(self.azioni)
        self._misura()

    def _azione(self, figura: str, suggerimento: str, cosa) -> QPushButton:
        b = BottoneIcona(figura, self.c, suggerimento)
        b.clicked.connect(cosa)
        b.setVisible(False)
        self.azioni.addWidget(b)
        self.bottoni.append(b)
        return b

    def _misura(self) -> None:
        """Le azioni e il filo seguono il carattere del foglio di stile."""
        for b in self.bottoni:
            b._misura()
        self.azioni.setContentsMargins(0 if self.chi == "tu" else 13, 0, 0, 0)

    # ------------------------------------------------------------ azioni
    def _copia(self) -> None:
        QApplication.clipboard().setText(self.testo.text())
        # il segno di spunta al posto dei fogli: «fatto», senza parole
        self.b_copia.imposta_figura("fatto")
        self.b_copia.setToolTip("Copiato")
        QTimer.singleShot(1400, self._fine_copia)

    def _fine_copia(self) -> None:
        self.b_copia.imposta_figura("copia")
        self.b_copia.setToolTip("Copia il testo")

    def _chiedi_elimina(self) -> None:
        self.eliminato.emit(self.id_messaggio)

    def apri_modifica(self) -> None:
        """Il testo diventa una casella, lì dov'è: niente finestre."""
        if self.editor is not None:
            return
        self.editor = QPlainTextEdit(self.testo.text())
        self.editor.setObjectName("ModificaMessaggio")
        self.editor.setTabChangesFocus(True)
        self.editor.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.editor.textChanged.connect(self._adatta_editor)
        self.testo.hide()
        if self.chi == "tu":
            # davanti resta un filo di margine, non metà riga
            self.riga.setStretch(0, 1)
            self.riga.insertWidget(self.riga.count() - 1, self.editor, 5)
        else:
            self.riga.insertWidget(1, self.editor, 1)

        self.conferma = QWidget()
        self.conferma.setObjectName("ContenutoSezione")
        fila = QHBoxLayout(self.conferma)
        fila.setContentsMargins(0, 2, 0, 0)
        fila.setSpacing(8)
        nota = QLabel("Le risposte dopo questa verranno rifatte")
        nota.setObjectName("NotaScheda")
        b_annulla = QPushButton("Annulla")
        b_annulla.setObjectName("Segmento")
        b_annulla.clicked.connect(self.chiudi_modifica)
        b_salva = QPushButton("Salva e richiedi")
        b_salva.setObjectName("Primario")
        b_salva.clicked.connect(self._salva)
        fila.addStretch(1)
        fila.addWidget(nota)
        fila.addWidget(b_annulla)
        fila.addWidget(b_salva)
        self.layout().addWidget(self.conferma)
        for b in self.bottoni:
            b.setVisible(False)
        self._adatta_editor()
        # la misura buona si sa solo dopo che il layout l'ha sistemata
        QTimer.singleShot(0, self._adatta_editor)
        self.editor.setFocus()
        cursore = self.editor.textCursor()
        cursore.movePosition(cursore.MoveOperation.End)
        self.editor.setTextCursor(cursore)

    def _adatta_editor(self) -> None:
        """La casella è alta quanto il testo che contiene, non una riga.

        In un `QPlainTextEdit` l'altezza del documento si conta in righe, non
        in pixel: la misura in pixel la dà il carattere.
        """
        if self.editor is None:
            return
        doc = self.editor.document()
        doc.setTextWidth(max(80, self.editor.viewport().width()))
        righe = max(1, int(doc.size().height()))
        passo = QFontMetrics(self.editor.font()).lineSpacing()
        # 16 di riempimento dal foglio di stile, più la cornice
        alto = righe * passo + 2 * int(self.editor.frameWidth()) + 16
        self.editor.setFixedHeight(max(38, min(alto, 300)))

    def chiudi_modifica(self) -> None:
        if self.editor is None:
            return
        self.editor.setParent(None)
        self.editor.deleteLater()
        self.editor = None
        self.conferma.setParent(None)
        self.conferma.deleteLater()
        self.testo.show()

    def _salva(self) -> None:
        if self.editor is None:
            return
        nuovo = self.editor.toPlainText().strip()
        self.chiudi_modifica()
        if nuovo and nuovo != self.testo.text():
            self.testo.setText(nuovo)
            self.modificato.emit(self.id_messaggio, nuovo)

    # ------------------------------------------------------------ aspetto
    def enterEvent(self, ev):
        super().enterEvent(ev)
        if self.editor is None:
            vero = bool(self.testo.text().strip()) and self.id_messaggio > 0
            for b in self.bottoni:
                b.setVisible(vero)

    def leaveEvent(self, ev):
        super().leaveEvent(ev)
        for b in self.bottoni:
            b.setVisible(False)

    def changeEvent(self, ev):
        super().changeEvent(ev)
        if ev.type() in (QEvent.StyleChange, QEvent.FontChange,
                         QEvent.ApplicationFontChange):
            self._misura()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        # la casella di modifica va riadattata: l'altezza dipende da quanto
        # è larga, e la larghezza la decide il layout qui attorno
        self._adatta_editor()

    def minimumSizeHint(self) -> QSize:
        chiesto = super().minimumSizeHint()
        return QSize(60, chiesto.height())


class VoceChat(QWidget):
    """Una conversazione nell'elenco: il nome, quando, e il «⋯».

    Il menu prima stava solo sul tasto destro, e infatti nessuno lo trovava:
    eliminare una chat era impossibile senza saperlo. Adesso c'è un bottone
    che si vede — al passaggio del mouse, e sempre su quella aperta.
    """

    scelta = Signal(str)
    menu_chiesto = Signal(str, object)
    rinominata = Signal(str, str)

    def __init__(self, chat_id: str, nome: str, quando: str, colori: dict,
                 parent=None):
        super().__init__(parent)
        self.chat_id = chat_id
        self.nome = nome
        self.c = colori
        self.aperta = False
        self.setObjectName("VoceChat")
        # un QWidget nostro il fondo del foglio di stile non lo disegna da sé
        self.setAttribute(Qt.WA_StyledBackground, True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 9, 8, 9)
        lay.setSpacing(8)
        self.et_nome = QLabel(nome)
        self.et_nome.setObjectName("NomeChat")
        # in larghezza si lascia accorciare coi puntini; in altezza no: deve
        # starci tutto, anche con il testo grande
        self.et_nome.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.et_quando = QLabel(quando)
        self.et_quando.setObjectName("QuandoChat")
        # la casella per rinominare nasce solo quando serve: una per riga,
        # sempre lì, sarebbe un widget nascosto per ogni conversazione
        self.campo: QLineEdit | None = None
        self.b_menu = QPushButton("⋯")
        self.b_menu.setObjectName("MenuChat")
        self.b_menu.setCursor(Qt.PointingHandCursor)
        self.b_menu.setFocusPolicy(Qt.NoFocus)
        self.b_menu.setToolTip("Rinomina o elimina questa conversazione")
        self.b_menu.clicked.connect(
            lambda: self.menu_chiesto.emit(
                self.chat_id, self.b_menu.mapToGlobal(
                    QPoint(0, self.b_menu.height()))))
        self.b_menu.setVisible(False)
        lay.addWidget(self.et_nome, 1)
        lay.addWidget(self.et_quando)
        lay.addWidget(self.b_menu)
        self._misura()

    def _misura(self) -> None:
        self.b_menu.ensurePolished()
        lato = max(22, QFontMetrics(self.b_menu.font()).height() + 4)
        self.b_menu.setFixedSize(lato, lato)

    def accendi(self, acceso: bool) -> None:
        """La conversazione aperta si vede: tinta d'accento e «⋯» sempre lì."""
        self.aperta = acceso
        self.b_menu.setVisible(acceso)
        self.setProperty("aperta", "si" if acceso else "no")
        self.style().unpolish(self)      # senza, la proprietà non si vede
        self.style().polish(self)

    def _scrivi_nome(self) -> None:
        """Il nome accorciato coi puntini, alla larghezza che c'è adesso."""
        posto = max(40, self.et_nome.width())
        self.et_nome.setText(QFontMetrics(self.et_nome.font()).elidedText(
            self.nome, Qt.ElideRight, posto))

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._scrivi_nome()

    def modifica(self) -> None:
        """Il nome si riscrive lì dove sta, non in una finestrella."""
        if self.campo is not None:
            return
        self.campo = QLineEdit(self.nome, self)
        self.campo.setObjectName("RinominaChat")
        self.campo.returnPressed.connect(self._confermato)
        self.campo.editingFinished.connect(self._confermato)
        self.layout().insertWidget(0, self.campo, 1)
        self.et_nome.hide()
        self.et_quando.hide()
        self.campo.show()
        self.campo.setFocus()
        self.campo.selectAll()

    def _confermato(self) -> None:
        if self.campo is None:
            return
        nuovo = self.campo.text().strip()
        casella, self.campo = self.campo, None
        casella.hide()
        casella.deleteLater()
        self.et_nome.show()
        self.et_quando.show()
        if nuovo != self.nome:
            self.rinominata.emit(self.chat_id, nuovo)

    def enterEvent(self, ev):
        super().enterEvent(ev)
        self.b_menu.setVisible(True)

    def leaveEvent(self, ev):
        super().leaveEvent(ev)
        self.b_menu.setVisible(self.aperta)

    def mousePressEvent(self, ev):
        super().mousePressEvent(ev)
        if ev.button() == Qt.LeftButton and self.campo is None:
            self.scelta.emit(self.chat_id)


# ------------------------------------------------------------------ il widget
class RiquadroTess(QWidget):
    """Il riquadro di Tess nel cruscotto: si accende a richiesta, poi è una chat.

    Finché nessuno preme «Attiva Tess» qui dentro non succede niente: nessun
    processo, nessun modello in memoria.
    """

    stato_cambiato = Signal(bool)          # attiva / non attiva

    def __init__(self, db, colori: dict, fonte=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.c = colori
        self.fonte = fonte
        self.motore = Motore(db)
        self.messaggi: list[dict] = []
        # le chat restano nell'archivio della Dashboard: il motore non le tiene
        self.chat_id = db.ultima_conversazione_tess()
        # la colonna dei nomi si può chiudere: la scelta resta fra due avvii
        self.colonna_aperta = db.leggi("tess_colonna", "1") == "1"
        self.voci: dict[str, VoceChat] = {}     # le righe dell'elenco, per chat
        self.conversazione: Risposta | None = None
        self.accensione: Accensione | None = None
        self.pronta = False
        self.setObjectName("ContenutoSezione")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        # ------------------------------------------------ quando è spenta
        self.benvenuto = QWidget()
        self.benvenuto.setObjectName("ContenutoSezione")
        colonna = QVBoxLayout(self.benvenuto)
        colonna.setContentsMargins(0, 0, 0, 0)
        colonna.setSpacing(12)
        colonna.addStretch(1)
        self.et_titolo = QLabel("Tess")
        self.et_titolo.setObjectName("ValoreScheda")
        self.et_titolo.setAlignment(Qt.AlignCenter)
        self.et_stato = QLabel("")
        self.et_stato.setObjectName("NotaScheda")
        self.et_stato.setWordWrap(True)
        self.et_stato.setAlignment(Qt.AlignCenter)
        self.et_stato.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Minimum)
        colonna.addWidget(self.et_titolo)
        colonna.addWidget(self.et_stato, 0, Qt.AlignHCenter)

        # mentre si accende: la stessa barra dell'app Tess, più il cronometro
        self.barra_attesa = BarraAttesa(colori)
        self.barra_attesa.setFixedWidth(260)
        self.barra_attesa.hide()
        self.et_tempo = QLabel("")
        self.et_tempo.setObjectName("NotaScheda")
        self.et_tempo.setAlignment(Qt.AlignCenter)
        self.et_tempo.hide()
        colonna.addWidget(self.barra_attesa, 0, Qt.AlignHCenter)
        colonna.addWidget(self.et_tempo, 0, Qt.AlignHCenter)
        self._cronometro = QTimer(self)
        self._cronometro.setInterval(200)
        self._cronometro.timeout.connect(self._batti)
        self._inizio_attesa = None
        lay.addWidget(self.benvenuto, 1)

        # ------------------------------------------------------ la chat
        self.chat = QScrollArea()
        self.chat.setObjectName("ContenutoSezione")
        self.chat.viewport().setObjectName("ContenutoSezione")
        self.chat.setWidgetResizable(True)
        self.chat.setFrameShape(QScrollArea.NoFrame)
        self.chat.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.chat.setMinimumHeight(90)
        dentro = QWidget()
        dentro.setObjectName("ContenutoSezione")
        self.lay_chat = QVBoxLayout(dentro)
        self.lay_chat.setContentsMargins(2, 14, 8, 6)
        self.lay_chat.setSpacing(7)
        self.lay_chat.addStretch(1)
        # la conversazione sta in una colonna larga al massimo novecento
        # pixel, in mezzo alla pagina: una riga di testo lunga due schermi
        # non si legge, si scansiona
        self.colonna_testo = dentro
        dentro.setMaximumWidth(900)
        centro = QWidget()
        centro.setObjectName("ContenutoSezione")
        fila_centro = QHBoxLayout(centro)
        fila_centro.setContentsMargins(0, 0, 0, 0)
        fila_centro.addStretch(1)
        fila_centro.addWidget(dentro, 20)
        fila_centro.addStretch(1)
        self.chat.setWidget(centro)
        self.bolle: list[QLabel] = []
        # i messaggi in pagina, per ritrovarli quando si correggono
        self.in_pagina: list[Messaggio] = []

        # a sinistra le conversazioni di prima: un clic e torni lì
        self.colonna_chat = QWidget()
        self.colonna_chat.setObjectName("ContenutoSezione")
        lato = QVBoxLayout(self.colonna_chat)
        lato.setContentsMargins(10, 12, 10, 12)
        lato.setSpacing(8)
        riga_cima = QHBoxLayout()
        riga_cima.setContentsMargins(0, 0, 0, 0)
        riga_cima.setSpacing(6)
        intestazione = QLabel("CONVERSAZIONI")
        intestazione.setObjectName("EtichettaScheda")
        self.b_piega = BottonePannello(colori, True)
        self.b_piega.imposta(True)
        self.b_piega.clicked.connect(lambda: self.piega_colonna(False))
        riga_cima.addWidget(intestazione)
        riga_cima.addStretch(1)
        riga_cima.addWidget(self.b_piega)
        self.b_nuova = QPushButton("+  Nuova")
        self.b_nuova.setObjectName("Segmento")
        self.b_nuova.setMinimumHeight(34)
        self.b_nuova.setToolTip("Comincia una conversazione nuova.\n"
                                "Quella di adesso resta nell'elenco.")
        self.b_nuova.clicked.connect(self.pulisci)
        self.elenco = QListWidget()
        self.elenco.setObjectName("ElencoChat")
        self.elenco.setFrameShape(QListWidget.NoFrame)
        self.elenco.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # i nomi vanno letti per intero: vanno a capo invece di finire in «…»
        self.elenco.setWordWrap(True)
        self.elenco.itemClicked.connect(self._scegli_chat)
        # si rinomina a mano, non per sbaglio: nessun avvio automatico
        self.elenco.setEditTriggers(QListWidget.NoEditTriggers)
        self.elenco.itemDoubleClicked.connect(self.rinomina_chat)
        self.elenco.setSelectionMode(QListWidget.SingleSelection)
        self.elenco.setContextMenuPolicy(Qt.CustomContextMenu)
        self.elenco.customContextMenuRequested.connect(self._menu_da_elenco)
        lato.addLayout(riga_cima)
        lato.addWidget(self.b_nuova)
        lato.addWidget(self.elenco, 1)
        # la larghezza vera gliela dà l'apertura: mentre si stringe il
        # minimo deve stare a zero, se no il layout non la lascia rimpicciolire
        self.colonna_chat.setMinimumWidth(0)
        self.colonna_chat.setMaximumWidth(self.LARGO_PANNELLO)

        # a colonna chiusa il bottone si sposta in cima alla chat, dove sta
        # nelle app: lì si capisce che riapre il pannello
        # in testata, sempre: un clic apre il cassetto, un altro lo richiude
        self.linguetta = BottonePannello(colori, False)
        self.linguetta.imposta(False)
        self.linguetta.setToolTip("Le tue conversazioni")
        self.linguetta.clicked.connect(
            lambda: self.piega_colonna(not self.colonna_aperta))

        # la testa della conversazione aperta: nome e «⋯», come nell'app
        self.testa_chat = QWidget()
        self.testa_chat.setObjectName("TestataChat")
        self.testa_chat.setAttribute(Qt.WA_StyledBackground, True)
        testa = QHBoxLayout(self.testa_chat)
        testa.setContentsMargins(2, 0, 2, 10)
        testa.setSpacing(10)
        self.et_chat = QLabel("")
        self.et_chat.setObjectName("TitoloChat")
        self.b_chat = QPushButton("⋯")
        self.b_chat.setObjectName("MenuChat")
        self.b_chat.setFixedSize(26, 26)
        self.b_chat.setCursor(Qt.PointingHandCursor)
        self.b_chat.setFocusPolicy(Qt.NoFocus)
        self.b_chat.setToolTip("Rinomina o elimina questa conversazione")
        self.b_chat.clicked.connect(self._menu_questa_chat)
        testa.addWidget(self.et_chat, 1)
        # la pastiglia del modello e dei dati si aggiunge qui sotto, appena
        # l'interruttore esiste
        self.testa_layout = testa
        testa.addWidget(self.b_chat)          # «⋯» della conversazione
        testa.addWidget(self.linguetta)       # apre e chiude il pannello

        # -------------------------------------------------- barra in fondo
        self.campo = QLineEdit()
        self.campo.setObjectName("CampoTess")
        self.campo.setPlaceholderText("Chiedi a Tess dei tuoi dati…")
        self.campo.setMinimumHeight(38)
        self.campo.returnPressed.connect(self.invia)
        self.b_invia = QPushButton("↑")
        self.b_invia.setObjectName("InviaTondo")
        self.b_invia.setCursor(Qt.PointingHandCursor)
        self.b_invia.setToolTip("Manda la domanda  (Invio)")
        self.b_invia.clicked.connect(self.invia)
        self.b_attiva = QPushButton("Attiva Tess")
        self.b_attiva.setObjectName("Primario")
        self.b_attiva.setMinimumHeight(40)
        self.b_attiva.setMinimumWidth(200)
        self.b_attiva.clicked.connect(self.attiva)
        colonna.addWidget(self.b_attiva, 0, Qt.AlignHCenter)
        colonna.addStretch(1)
        self.dati = QWidget()
        self.dati.setObjectName("ContenutoSezione")
        fila_dati = QHBoxLayout(self.dati)
        fila_dati.setContentsMargins(6, 0, 6, 0)
        fila_dati.setSpacing(8)
        et_dati = QLabel("dati")
        et_dati.setObjectName("NotaScheda")
        self.b_dati = Interruttore(colori, db.leggi("tess_dati", "1") == "1",
                                   area="tess")
        self.b_dati.setToolTip(
            "Manda a Tess il riassunto dei tuoi numeri (salute, esami, "
            "progetti, abitudini, finanza).\nSpento, Tess risponde senza "
            "sapere niente di te.")
        et_dati.setToolTip(self.b_dati.toolTip())
        self.b_dati.cambiato.connect(
            lambda acceso: db.imposta("tess_dati", "1" if acceso else "0"))
        fila_dati.addWidget(et_dati)
        fila_dati.addWidget(self.b_dati)
        # Tutto dentro una sola pastiglia, come nell'app: il campo, il
        # comando dei dati e il tondo per mandare. Prima erano tre cose
        # separate in fila, e la riga sembrava una barra di strumenti.
        self.barra = QHBoxLayout()
        self.barra.setContentsMargins(8, 6, 8, 6)
        self.barra.setSpacing(8)
        self.barra.addWidget(self.campo, 1)
        self.barra.addWidget(self.dati)
        self.barra.addWidget(self.b_invia)
        self.riga_barra = QWidget()
        self.riga_barra.setObjectName("BarraTess")
        self.riga_barra.setLayout(self.barra)
        self.riga_barra.setMaximumWidth(900)
        # dentro la scheda, in fondo alla colonna di lettura
        self.sotto = QWidget()
        self.sotto.setObjectName("ContenutoSezione")
        fila_sotto = QHBoxLayout(self.sotto)
        fila_sotto.setContentsMargins(0, 8, 0, 2)
        fila_sotto.addStretch(1)
        fila_sotto.addWidget(self.riga_barra, 20)
        fila_sotto.addStretch(1)

        # la pastiglia in testata: come sta il motore e se i dati sono accesi
        self.pastiglia = QWidget()
        self.pastiglia.setObjectName("PastigliaModello")
        self.pastiglia.setAttribute(Qt.WA_StyledBackground, True)
        fila_p = QHBoxLayout(self.pastiglia)
        fila_p.setContentsMargins(10, 3, 6, 3)
        fila_p.setSpacing(8)
        self.et_modello = QLabel("dati")
        self.et_modello.setObjectName("NomeModello")
        self.et_modello.setToolTip(self.b_dati.toolTip())
        fila_p.addWidget(self.et_modello)
        fila_p.addWidget(self.b_dati)
        # la pastiglia dei dati prima del «⋯»: i comandi della conversazione
        # restano gli ultimi, accanto al pannello
        self.testa_layout.insertWidget(self.testa_layout.count() - 2,
                                       self.pastiglia)
        self.dati.hide()               # l'interruttore adesso vive in testata

        # ------------------------------------------------- come sta in pagina
        # Niente scatola intorno alla conversazione: il testo sta sulla pagina
        # come su un foglio. A destra, staccato, il pannello delle chat —
        # quello sì un riquadro, perché è un elenco e non un discorso.
        centro = QWidget()
        centro.setObjectName("ContenutoSezione")
        colonna_centro = QVBoxLayout(centro)
        colonna_centro.setContentsMargins(0, 0, 0, 0)
        colonna_centro.setSpacing(0)
        colonna_centro.addWidget(self.testa_chat)
        colonna_centro.addWidget(self.chat, 1)
        colonna_centro.addWidget(self.sotto)

        self.colonna_chat.setObjectName("PannelloChat")
        self.colonna_chat.setAttribute(Qt.WA_StyledBackground, True)
        self.riga_chat = QWidget()
        self.riga_chat.setObjectName("ContenutoSezione")
        fianco = QHBoxLayout(self.riga_chat)
        fianco.setContentsMargins(0, 0, 0, 0)
        fianco.setSpacing(14)
        fianco.addWidget(centro, 1)
        fianco.addWidget(self.colonna_chat)
        lay.addWidget(self.riga_chat, 1)
        self._anim_cassetto = None

        self._misura_barra()
        self._mostra_stato(False)

    # ---------------------------------------------------------- aspetto
    def _misura_barra(self) -> None:
        """Il tondo dell'invio è alto quanto il campo, e tondo davvero."""
        for widget in (self.campo, self.b_invia):
            widget.ensurePolished()
        lato = max(34, self.campo.minimumHeight())
        self.b_invia.setFixedSize(lato, lato)
        self.b_invia.setStyleSheet(f"border-radius: {lato // 2}px;")
    def _mostra_stato(self, pronta: bool, messaggio: str = "") -> None:
        self.pronta = pronta
        self.benvenuto.setVisible(not pronta)
        self.riga_chat.setVisible(pronta)
        self.sotto.setVisible(pronta)
        if pronta:
            self.aggiorna_elenco()
        self.et_stato.setText(messaggio or (
            "La tua AI locale: gira sul tuo PC, isolata dalla rete, e risponde "
            "sui dati della Dashboard. Si accende solo quando glielo dici tu: "
            "finché è spenta non occupa né memoria né scheda video."))
        self._adatta_benvenuto()
        self.stato_cambiato.emit(pronta)

    def aggiorna_tema(self, colori: dict) -> None:
        self.c = colori
        self.b_dati.aggiorna_tema(colori)

    def sincronizza(self) -> None:
        """Guarda com'è messo il motore adesso e si mette in pari.

        Serve quando si torna sulla pagina: il motore può essere stato acceso
        o spento da fuori (dal terminale, dall'icona di Tess sul desktop).
        """
        if self.accensione and self.accensione.isRunning():
            return
        vero = self.motore.attiva()
        if vero != self.pronta:
            self._mostra_stato(vero)
            if vero and not self.bolle:
                if self.chat_id:
                    self.carica_chat(self.chat_id)
                if not self.bolle:
                    self._scrivi("tess", "Ci sono. Cosa guardiamo?")

    # --------------------------------------------------------- accensione
    def attiva(self) -> None:
        """Accende il motore: è l'unico momento in cui parte qualcosa."""
        if self.pronta or (self.accensione and self.accensione.isRunning()):
            return
        self.b_attiva.setEnabled(False)
        self.et_stato.setText("Accendo Tess…")
        self._adatta_benvenuto()
        self._attesa(True)
        self.accensione = Accensione(self.motore, self)
        self.accensione.fase.connect(self._fase)
        self.accensione.pronta.connect(self._accesa)
        self.accensione.start()

    def _batti(self) -> None:
        """Il cronometro dell'accensione: secondi, e un avviso se tarda."""
        if self._inizio_attesa is None:
            return
        secondi = (datetime.now() - self._inizio_attesa).total_seconds()
        self.et_tempo.setText(f"{secondi:.0f}s"
                              + ("   ·   ci sta mettendo più del solito"
                                 if secondi > 28 else ""))

    def _attesa(self, in_corso: bool) -> None:
        self.b_attiva.setVisible(not in_corso)
        self.et_tempo.setVisible(in_corso)
        if in_corso:
            self._inizio_attesa = datetime.now()
            self.et_tempo.setText("0s")
            self.barra_attesa.avvia()
            self._cronometro.start()
        else:
            self._cronometro.stop()
            self._inizio_attesa = None
            self.barra_attesa.ferma()

    def _fase(self, quale: str) -> None:
        if quale == "motore":
            self.et_stato.setText("Accendo il motore…")
        else:
            self.et_stato.setText(
                "Carico il modello nella scheda video: qualche secondo, una "
                "volta sola. Poi risponde subito.")
        self._adatta_benvenuto()

    def _accesa(self, riuscita: bool, errore: str) -> None:
        self._attesa(False)
        self.b_attiva.setEnabled(True)
        if not riuscita:
            self._mostra_stato(False, f"Non sono riuscito ad accendere Tess. {errore}")
            return
        self._mostra_stato(True)
        if not self.bolle:
            if self.chat_id:
                self.carica_chat(self.chat_id)       # si riprende da dov'era
            if not self.bolle:
                self._scrivi("tess", "Ci sono. Cosa guardiamo?")
        self.campo.setFocus()

    def spegni(self) -> None:
        self.motore.spegni()
        self._mostra_stato(False, "Tess è spenta: la VRAM è di nuovo libera.")

    # ------------------------------------------------------------- chat
    def carica_chat(self, chat_id: str) -> None:
        """Rimette in pagina una conversazione salvata, Tess compresa."""
        self._svuota_bolle()
        self.chat_id = chat_id
        for riga in self.db.conversazione_tess(chat_id):
            self.messaggi.append({"role": riga["ruolo"], "content": riga["testo"]})
            self._scrivi("tu" if riga["ruolo"] == "user" else "tess",
                         riga["testo"], riga["id"])
        self.aggiorna_elenco()

    @staticmethod
    def _gruppo(giorno: str) -> str:
        """Sotto che titoletto va una conversazione di quel giorno."""
        try:
            scarto = (date.today() - date.fromisoformat(giorno)).days
        except ValueError:
            return "PRIMA"
        if scarto <= 0:
            return "OGGI"
        if scarto == 1:
            return "IERI"
        if scarto <= 7:
            return "ULTIMI 7 GIORNI"
        if scarto <= 30:
            return "ULTIMI 30 GIORNI"
        return "PRIMA"

    def aggiorna_elenco(self) -> None:
        """Riempie la colonna di sinistra con le conversazioni già fatte.

        Raggruppate per quando sono state fatte, e ognuna col suo «⋯»: il
        menu sul tasto destro c'era già, ma non lo trovava nessuno.
        """
        self.elenco.blockSignals(True)
        self.elenco.clear()
        self.voci: dict[str, VoceChat] = {}
        gruppo_corrente = ""
        for r in self.db.conversazioni_tess():
            chat_id = r["conversazione"]
            gruppo = self._gruppo(chat_id[:10])
            if gruppo != gruppo_corrente:
                gruppo_corrente = gruppo
                titoletto = QListWidgetItem(gruppo)
                titoletto.setFlags(Qt.NoItemFlags)
                titoletto.setData(RUOLO_GRUPPO, True)
                self.elenco.addItem(titoletto)
            apertura = (r["apertura"] or "conversazione").strip()
            # il nome che le hai dato; se non glielo hai dato, la prima domanda
            nome = ((r["titolo"] or "").strip() or apertura[:44])[:60] or "conversazione"
            voce = QListWidgetItem()
            voce.setData(Qt.UserRole, chat_id)
            voce.setData(RUOLO_NOME, nome)
            self.elenco.addItem(voce)
            riga = VoceChat(chat_id, nome, chat_id[11:16], self.c)
            riga.setToolTip(f"{r['messaggi']} messaggi · "
                            f"{relativa(chat_id[:10])} alle {chat_id[11:16]}\n"
                            f"{apertura[:160]}")
            riga.scelta.connect(self._apri_chat)
            riga.menu_chiesto.connect(self._menu_chat)
            riga.rinominata.connect(self._rinominata)
            riga.accendi(chat_id == self.chat_id)
            self.elenco.setItemWidget(voce, riga)
            self.voci[chat_id] = riga
            if chat_id == self.chat_id:
                self.elenco.setCurrentItem(voce)
        self.elenco.blockSignals(False)
        vuoto = self.elenco.count() == 0
        self.elenco.setVisible(not vuoto)
        self._misura_voci()
        self._sistema_colonna()
        self.et_chat.setText(self._nome_chat_aperta())
        self.b_chat.setVisible(bool(self.chat_id))

    # lo spazio fra una conversazione e l'altra, che il foglio di stile mette
    # come «margin-bottom» sulla voce: va tolto dall'altezza che si chiede,
    # se no il nome resta con quattro pixel in meno di quelli che gli servono
    # — ed è così che le scritte sembravano tagliate di sotto
    STACCO_VOCE = 4

    def _misura_voci(self) -> None:
        """Dà a ogni voce la larghezza della colonna e l'altezza che le serve."""
        if self.elenco.count() == 0:
            return
        self.elenco.ensurePolished()
        largo = max(140, self.elenco.viewport().width() - 2)
        alto_titolo = QFontMetrics(self.elenco.font()).height() + 14
        for i in range(self.elenco.count()):
            voce = self.elenco.item(i)
            riga = self.elenco.itemWidget(voce)
            if riga is None:                     # è un titoletto di gruppo
                voce.setSizeHint(QSize(largo, alto_titolo + self.STACCO_VOCE))
                continue
            riga.ensurePolished()      # prima, il carattere è ancora quello di serie
            riga.setFixedWidth(largo)
            voce.setSizeHint(QSize(largo,
                                   riga.sizeHint().height() + self.STACCO_VOCE))

    # ------------------------------------------------- la colonna dei nomi
    LARGO_PANNELLO = 246

    def piega_colonna(self, aperta: bool) -> None:
        """Apre o chiude il pannello delle conversazioni, a destra.

        Non scompare di colpo: si stringe, così l'occhio segue dove va.
        """
        self.colonna_aperta = aperta
        self.db.imposta("tess_colonna", "1" if aperta else "0")
        self.linguetta.imposta(aperta)
        if self._anim_cassetto is not None:
            self._anim_cassetto.stop()
        self.colonna_chat.setMinimumWidth(0)
        if aperta:
            self.colonna_chat.show()
        anim = QPropertyAnimation(self.colonna_chat, b"maximumWidth", self)
        anim.setDuration(170)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.setStartValue(self.colonna_chat.maximumWidth())
        anim.setEndValue(self.LARGO_PANNELLO if aperta else 0)
        if aperta:
            def assestata():
                self.colonna_chat.setMinimumWidth(self.LARGO_PANNELLO)
                self._misura_voci()
            anim.finished.connect(assestata)
        else:
            anim.finished.connect(self.colonna_chat.hide)
        self._anim_cassetto = anim
        anim.start()

    def _sistema_colonna(self) -> None:
        """Il pannello a destra c'è se l'hai voluto tu e se c'è posto."""
        corre = (self._anim_cassetto is not None
                 and self._anim_cassetto.state() == QPropertyAnimation.Running)
        if corre:
            return
        largo = self.width() > 640
        aperta = largo and self.colonna_aperta
        self.colonna_chat.setMinimumWidth(self.LARGO_PANNELLO if aperta else 0)
        self.colonna_chat.setMaximumWidth(self.LARGO_PANNELLO if aperta else 0)
        self.colonna_chat.setVisible(aperta)
        if aperta:
            QTimer.singleShot(0, self._misura_voci)
        self.linguetta.setVisible(largo)
        self.linguetta.imposta(aperta)

    # ---------------------------------------------------------- rinominare
    def rinomina_chat(self, voce) -> None:
        """Fa riscrivere il nome sulla voce stessa, al posto suo.

        Accetta la voce dell'elenco o direttamente l'identificativo della
        conversazione: la pagina lo chiama in tutti e due i modi.
        """
        chat_id = voce.data(Qt.UserRole) if hasattr(voce, "data") else voce
        riga = self.voci.get(chat_id)
        if riga is not None:
            riga.modifica()

    def _rinominata(self, chat_id: str, nome: str) -> None:
        """Vuoto vale «nessun nome»: torna a farsi chiamare con la prima domanda."""
        self.db.rinomina_conversazione_tess(chat_id, nome)
        self.aggiorna_elenco()

    def _apri_chat(self, chat_id: str) -> None:
        if chat_id and chat_id != self.chat_id:
            self.carica_chat(chat_id)

    def _scegli_chat(self, voce: QListWidgetItem) -> None:
        chat_id = voce.data(Qt.UserRole)
        if chat_id and chat_id != self.chat_id:
            self.carica_chat(chat_id)

    def _menu_chat(self, chat_id: str, dove) -> None:
        """Il menu di una conversazione: lo apre il «⋯», o il tasto destro."""
        if not chat_id:
            return
        menu = QMenu(self)
        menu.addAction("Riapri", lambda: self.carica_chat(chat_id))
        menu.addAction("Rinomina…", lambda: self.rinomina_chat(chat_id))
        menu.addSeparator()
        menu.addAction("Elimina", lambda: self._chiedi_elimina(chat_id))
        menu.exec(dove)

    def _menu_da_elenco(self, punto) -> None:
        voce = self.elenco.itemAt(punto)
        if voce is None:
            return
        self._menu_chat(voce.data(Qt.UserRole),
                        self.elenco.viewport().mapToGlobal(punto))

    def _menu_questa_chat(self) -> None:
        """Il «⋯» in cima: agisce sulla conversazione che hai davanti."""
        if not self.chat_id:
            return
        self._menu_chat(self.chat_id, self.b_chat.mapToGlobal(
            QPoint(0, self.b_chat.height())))

    def _nome_chat_aperta(self) -> str:
        riga = self.voci.get(self.chat_id)
        return riga.nome if riga is not None else "Conversazione nuova"

    def _chiedi_elimina(self, chat_id: str) -> None:
        """Una conversazione cancellata non torna: una domanda prima."""
        riga = self.voci.get(chat_id)
        nome = riga.nome if riga is not None else "questa conversazione"
        risposta = QMessageBox.question(
            self, "Eliminare la conversazione?",
            f"«{nome}» verrà eliminata dall'archivio, con tutti i suoi "
            "messaggi. Non si può tornare indietro.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if risposta == QMessageBox.Yes:
            self._elimina_chat(chat_id)

    def _elimina_chat(self, chat_id: str) -> None:
        self.db.elimina_conversazione_tess(chat_id)
        if chat_id == self.chat_id:
            self.pulisci()
        else:
            self.aggiorna_elenco()

    # ------------------------------------------------- un messaggio solo
    def _elimina_messaggio(self, id_messaggio: int) -> None:
        """Toglie un messaggio dalla conversazione, in pagina e nell'archivio."""
        if not id_messaggio or not self.chat_id:
            return
        risposta = QMessageBox.question(
            self, "Elimina messaggio",
            "Tolgo questo messaggio dalla conversazione?\n\n"
            "Resta tutto il resto; Tess non lo vedrà più nemmeno quando "
            "rilegge la chat.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if risposta != QMessageBox.Yes:
            return
        self.db.elimina_messaggio_tess(id_messaggio)
        if self.db.conversazione_tess(self.chat_id):
            self.carica_chat(self.chat_id)
        else:                       # era l'ultimo rimasto: la chat non c'è più
            self.db.elimina_conversazione_tess(self.chat_id)
            self.pulisci()

    def _modifica_messaggio(self, id_messaggio: int, testo: str) -> None:
        """Corregge una domanda e rifà la risposta da lì in poi.

        Le risposte che venivano dopo rispondevano a un'altra domanda: restano
        solo i messaggi precedenti, e Tess riparte da quello corretto.
        """
        if not id_messaggio or not self.chat_id:
            return
        self.db.modifica_messaggio_tess(id_messaggio, testo)
        self.db.taglia_da_messaggio_tess(self.chat_id, id_messaggio)
        self.carica_chat(self.chat_id)
        if self.pronta and not (self.conversazione and self.conversazione.isRunning()):
            self._interroga(testo)

    def _svuota_bolle(self) -> None:
        self.messaggi.clear()
        self.in_pagina.clear()
        while self.lay_chat.count() > 1:
            voce = self.lay_chat.takeAt(0)
            w = voce.widget()
            if w is not None:
                w.hide(); w.setParent(None); w.deleteLater()
        self.bolle.clear()

    def pulisci(self) -> None:
        """Una conversazione nuova: quella di prima resta nello storico."""
        self._svuota_bolle()
        self.chat_id = ""
        self._scrivi("tess", "Ci sono. Cosa guardiamo?")
        self.aggiorna_elenco()

    def invia(self) -> None:
        domanda = self.campo.text().strip()
        if not domanda or not self.pronta:
            return
        if self.conversazione and self.conversazione.isRunning():
            return
        self.campo.clear()
        if not self.chat_id:
            self.chat_id = datetime.now().isoformat(timespec="seconds")
        nuova = not self.db.conversazione_tess(self.chat_id)
        id_riga = self.db.salva_messaggio_tess(self.chat_id, "user", domanda)
        self._scrivi("tu", domanda, id_riga)
        self.messaggi.append({"role": "user", "content": domanda})
        if nuova:
            self.aggiorna_elenco()
        self._interroga(domanda)

    def _interroga(self, domanda: str) -> None:
        """Manda al motore quello che c'è in `self.messaggi`.

        Sta a parte da `invia` perché la stessa domanda si rifà quando ne
        correggi una di prima: lì il messaggio in pagina c'è già.
        """
        sistema = [{"role": "system", "content": istruzioni(self.db)}]
        if self.b_dati.acceso():
            try:
                sistema.append({"role": "system",
                                "content": contesto(self.db, self.fonte,
                                                    aree_scelte(self.db),
                                                    domanda)})
            except Exception as errore:
                # senza riassunto Tess risponderebbe lo stesso, a caso: meglio
                # che lo dica, e che si veda anche qui che è andato storto
                sistema.append({"role": "system", "content":
                                "Il riassunto dei dati non è disponibile: "
                                "dillo chiaramente e non inventare numeri."})
                self._scrivi("tess", "⚠ Non sono riuscita a leggere i tuoi "
                                     f"dati ({type(errore).__name__}): "
                                     "rispondo senza.")
        self._inizia_risposta()
        self.conversazione = Risposta(self.motore, sistema + self.messaggi, self)
        self.conversazione.pezzo.connect(self._aggiungi_pezzo)
        self.conversazione.finita.connect(self._chiudi_risposta)
        self.conversazione.errore.connect(self._errore)
        self.conversazione.start()

    def _inizia_risposta(self) -> None:
        self.b_invia.setEnabled(False)
        self._in_corso = ""
        self._bolla_corrente = self._scrivi("tess", "…")

    def _aggiungi_pezzo(self, testo: str) -> None:
        self._in_corso += testo
        self._bolla_corrente.setText(self._in_corso)
        self._larghezza_bolle()
        self._in_fondo()

    def _chiudi_risposta(self) -> None:
        self.b_invia.setEnabled(True)
        if self._in_corso:
            self.messaggi.append({"role": "assistant", "content": self._in_corso})
            id_riga = self.db.salva_messaggio_tess(self.chat_id, "assistant",
                                                   self._in_corso)
            # adesso che è finita ha una riga nell'archivio: si può togliere
            if self.in_pagina:
                self.in_pagina[-1].id_messaggio = id_riga

    def _errore(self, messaggio: str) -> None:
        self.b_invia.setEnabled(True)
        self._bolla_corrente.setText(f"({messaggio})")
        self._mostra_stato(self.motore.attiva())

    # ------------------------------------------------- disegno della chat
    def _scrivi(self, chi: str, testo: str, id_messaggio: int = 0) -> QLabel:
        """Aggiunge un messaggio: il tuo in una bolla a destra, quello di Tess
        col suo filo a sinistra.

        `id_messaggio` è la riga nell'archivio: senza, il messaggio non si può
        né correggere né togliere (è il caso di quello che sta arrivando).
        """
        messaggio = Messaggio(chi, testo, self.c, id_messaggio)
        messaggio.modificato.connect(self._modifica_messaggio)
        messaggio.eliminato.connect(self._elimina_messaggio)
        self.lay_chat.insertWidget(self.lay_chat.count() - 1, messaggio)
        self.in_pagina.append(messaggio)
        self.bolle.append(messaggio.testo)
        self._larghezza_bolle()
        for ritardo in (0, 60):          # dopo che il riquadro si è assestato
            QTimer.singleShot(ritardo, self._in_fondo)
        return messaggio.testo

    def _larghezza_bolle(self) -> None:
        """La bolla veste il testo; quella di Tess invece non c'è.

        Le tue domande sono corte e stanno bene in una bolla cucita addosso,
        fino a tre quarti della pagina. Le risposte di Tess sono lunghe e si
        prendono la riga intera: una colonna stretta di testo al centro dello
        schermo si legge peggio, non meglio.
        """
        posto = min(self.colonna_testo.width() or 900, 900)
        massimo = max(180, int(posto * 0.74))
        for bolla in self.bolle:
            bolla.ensurePolished()      # il carattere è quello del foglio di stile
            if bolla.objectName() != "BollaTu":
                bolla.setMinimumWidth(0)
                bolla.setMaximumWidth(16777215)
                continue
            metriche = QFontMetrics(bolla.font())
            naturale = max((metriche.horizontalAdvance(r)
                            for r in bolla.text().split("\n")), default=0) + 36
            # QLabel con a capo automatico sceglie da sé una larghezza quadrata:
            # qui gliela si impone, così la bolla veste il testo
            largo = max(70, min(naturale, massimo))
            bolla.setMinimumWidth(largo)
            bolla.setMaximumWidth(largo)

    def _in_fondo(self) -> None:
        barra = self.chat.verticalScrollBar()
        barra.setValue(barra.maximum())

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._sistema_colonna()
        self._misura_voci()
        self._larghezza_bolle()
        self._adatta_benvenuto()

    def _adatta_benvenuto(self) -> None:
        """Dà al testo d'ingresso la larghezza e l'altezza che gli servono.

        Un'etichetta che va a capo, dentro un layout, si prende l'altezza di
        una riga sola e taglia il resto: qui la misura si fa a mano.
        """
        self.et_stato.ensurePolished()
        largo = min(620, max(300, int(self.width() * 0.72)))
        self.et_stato.setFixedWidth(largo)
        metriche = QFontMetrics(self.et_stato.font())
        riquadro = metriche.boundingRect(QRect(0, 0, largo, 10000),
                                         Qt.TextWordWrap | Qt.AlignHCenter,
                                         self.et_stato.text())
        self.et_stato.setMinimumHeight(riquadro.height() + 8)

    # ------------------------------------------------------------ chiusura
    def chiudi(self) -> None:
        """Ferma i fili aperti: la finestra si chiude senza aspettare Tess."""
        for filo in (self.conversazione, self.accensione):
            if filo and filo.isRunning():
                if hasattr(filo, "ferma"):
                    filo.ferma()
                filo.quit()
                filo.wait(1500)
