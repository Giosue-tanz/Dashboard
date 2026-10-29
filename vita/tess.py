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
import subprocess
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta

from PySide6.QtCore import QRect, QSize, QThread, QTimer, Qt, Signal
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QMenu, QPushButton, QScrollArea,
                               QSizePolicy, QVBoxLayout, QWidget)

from . import punteggi as calcolo
from .componenti import BarraAttesa, Interruttore
from .utils import (data_it, data_lunga, durata, euro, media, numero,
                    relativa, settimana_corrente, ultimi_giorni)

BASE_PREDEFINITA = os.path.expanduser("~/Scrivania/WORK/AI-Locale")
SERVIZIO = "ai-locale.service"

# il nome mostrato di una conversazione, tenuto da parte sulla voce: serve
# quando si rinomina, per far ricomparire nell'editor quello che si legge
RUOLO_NOME = Qt.UserRole + 1


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


def contesto(db, fonte, aree: set[str] | None = None) -> str:
    """Il riassunto della Dashboard che Tess riceve insieme alla domanda.

    Solo numeri già presenti nell'archivio: nessun testo del diario, che resta
    cosa tua. Serve perché Tess risponda sui tuoi dati senza fartene l'elenco.
    Con `aree` si tiene dentro solo una parte del riassunto.
    """
    oggi = date.today().isoformat()
    righe = [f"Dati della Dashboard di Giosuè, aggiornati a {data_lunga(oggi)}.",
             "Sono già in tuo possesso: usali, non chiederglieli.", ""]

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

    # --------------------------------------------------------- scadenze
    prossime = db.query(
        "SELECT * FROM scadenze WHERE fatta=0 AND data >= ? ORDER BY data LIMIT 4",
        (oggi,))
    if prossime:
        righe.append("IN ARRIVO: " + ", ".join(
            f"{s['cosa']} il {s['data']}" for s in prossime))

    aree = set(AREE_CONTESTO) if aree is None else aree
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
RIGA_ONESTA = "Se un dato non c'è, dillo invece di inventarlo."


def solo_istruzioni_tue(db) -> bool:
    """L'interruttore «solo le mie»: tono e lunghezza non vengono mandati."""
    return db.leggi("tess_solo_mie", "0") == "1"


def istruzioni(db) -> str:
    """Le istruzioni di Tess, messe insieme da come l'hai impostata."""
    nome = (db.leggi("tess_nome", "") or "Tess").strip()
    sue = db.leggi("tess_istruzioni", "").strip()
    pezzi = [f"Ti chiami {nome} e stai rispondendo dentro la Dashboard di "
             "Giosuè.", RIGA_DATI]
    # con l'interruttore acceso comandano solo le sue istruzioni: lo stile
    # pronto (tono e lunghezza) resta fuori
    if not (solo_istruzioni_tue(db) and sue):
        pezzi.append(TONI.get(db.leggi("tess_tono", TONO_PREDEFINITO),
                              TONI[TONO_PREDEFINITO]))
        pezzi.append(LUNGHEZZE.get(db.leggi("tess_lunghezza", LUNGHEZZA_PREDEFINITA),
                                   LUNGHEZZE[LUNGHEZZA_PREDEFINITA]))
    pezzi.append(RIGA_ONESTA)
    if sue:
        # quello che scrive lui conta più di tutto il resto
        pezzi.append("Istruzioni sue, che valgono sopra le altre: " + sue)
    return " ".join(pezzi)


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
        self._rinominando = ""
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
        self.lay_chat.setContentsMargins(2, 2, 8, 2)
        self.lay_chat.setSpacing(8)
        self.lay_chat.addStretch(1)
        self.chat.setWidget(dentro)
        self.bolle: list[QLabel] = []

        # a sinistra le conversazioni di prima: un clic e torni lì
        self.colonna_chat = QWidget()
        self.colonna_chat.setObjectName("ContenutoSezione")
        lato = QVBoxLayout(self.colonna_chat)
        lato.setContentsMargins(0, 0, 10, 0)
        lato.setSpacing(8)
        riga_cima = QHBoxLayout()
        riga_cima.setContentsMargins(0, 0, 0, 0)
        riga_cima.setSpacing(6)
        intestazione = QLabel("CONVERSAZIONI")
        intestazione.setObjectName("EtichettaScheda")
        self.b_piega = QPushButton("‹")
        self.b_piega.setObjectName("Linguetta")
        self.b_piega.setFixedSize(28, 28)
        self.b_piega.setToolTip("Chiudi l'elenco: resta solo la chat.")
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
        self.elenco.itemChanged.connect(self._nome_scritto)
        delegato = self.elenco.itemDelegate()
        if delegato is not None:
            # chiusa la casella (con Invio o con Esc) la voce torna a due righe
            delegato.closeEditor.connect(self._fine_rinomina)
        self.elenco.setContextMenuPolicy(Qt.CustomContextMenu)
        self.elenco.customContextMenuRequested.connect(self._menu_chat)
        lato.addLayout(riga_cima)
        lato.addWidget(self.b_nuova)
        lato.addWidget(self.elenco, 1)
        self.colonna_chat.setFixedWidth(232)

        # a colonna chiusa resta questa linguetta, per riaprirla
        self.linguetta = QPushButton("›")
        self.linguetta.setObjectName("LinguettaLato")
        self.linguetta.setFixedSize(22, 64)
        self.linguetta.setToolTip("Mostra le conversazioni di prima.")
        self.linguetta.clicked.connect(lambda: self.piega_colonna(True))
        self.linguetta.hide()

        fianco = QHBoxLayout()
        fianco.setContentsMargins(0, 0, 0, 0)
        fianco.setSpacing(8)
        fianco.addWidget(self.colonna_chat)
        fianco.addWidget(self.linguetta, 0, Qt.AlignTop)
        fianco.addWidget(self.chat, 1)
        self.riga_chat = QWidget()
        self.riga_chat.setObjectName("ContenutoSezione")
        self.riga_chat.setLayout(fianco)
        lay.addWidget(self.riga_chat, 1)

        # -------------------------------------------------- barra in fondo
        self.campo = QLineEdit()
        self.campo.setObjectName("CampoTess")
        self.campo.setPlaceholderText("Chiedi a Tess dei tuoi dati…")
        self.campo.setMinimumHeight(38)
        self.campo.returnPressed.connect(self.invia)
        self.b_invia = QPushButton("Invia")
        self.b_invia.setObjectName("Primario")
        self.b_invia.setMinimumHeight(38)
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
        self.b_dati = Interruttore(colori, db.leggi("tess_dati", "1") == "1")
        self.b_dati.setToolTip(
            "Manda a Tess il riassunto dei tuoi numeri (salute, esami, "
            "progetti, abitudini, finanza).\nSpento, Tess risponde senza "
            "sapere niente di te.")
        et_dati.setToolTip(self.b_dati.toolTip())
        self.b_dati.cambiato.connect(
            lambda acceso: db.imposta("tess_dati", "1" if acceso else "0"))
        fila_dati.addWidget(et_dati)
        fila_dati.addWidget(self.b_dati)
        self.barra = QHBoxLayout()
        self.barra.setSpacing(8)
        self.barra.addWidget(self.campo, 1)
        self.barra.addWidget(self.dati)
        self.barra.addWidget(self.b_invia)
        self.riga_barra = QWidget()
        self.riga_barra.setObjectName("ContenutoSezione")
        self.riga_barra.setLayout(self.barra)
        lay.addWidget(self.riga_barra)

        self._mostra_stato(False)

    # ---------------------------------------------------------- aspetto
    def _mostra_stato(self, pronta: bool, messaggio: str = "") -> None:
        self.pronta = pronta
        self.benvenuto.setVisible(not pronta)
        self.riga_chat.setVisible(pronta)
        self.riga_barra.setVisible(pronta)
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
            self._scrivi("tu" if riga["ruolo"] == "user" else "tess", riga["testo"])
        self.aggiorna_elenco()

    def aggiorna_elenco(self) -> None:
        """Riempie la colonna di sinistra con le conversazioni già fatte."""
        self.elenco.blockSignals(True)
        self.elenco.clear()
        for r in self.db.conversazioni_tess():
            chat_id = r["conversazione"]
            quando = relativa(chat_id[:10])
            ora = chat_id[11:16]
            apertura = (r["apertura"] or "conversazione").strip()
            # il nome che le hai dato; se non glielo hai dato, la prima domanda
            nome = ((r["titolo"] or "").strip() or apertura[:44])[:60] or "conversazione"
            voce = QListWidgetItem(f"{quando} · {ora}\n{nome}")
            voce.setData(Qt.UserRole, chat_id)
            voce.setData(RUOLO_NOME, nome)
            voce.setToolTip(f"{r['messaggi']} messaggi · {apertura[:160]}\n"
                            "Doppio clic per rinominare")
            self.elenco.addItem(voce)
            if chat_id == self.chat_id:
                self.elenco.setCurrentItem(voce)
        self.elenco.blockSignals(False)
        vuoto = self.elenco.count() == 0
        self.elenco.setVisible(not vuoto)
        self._misura_voci()
        self._sistema_colonna()

    def _misura_voci(self) -> None:
        """Dà a ogni voce la larghezza della colonna e l'altezza che le serve.

        Lasciata a sé, una voce appena più larga della colonna viene tagliata
        con i puntini invece di andare a capo: la misura si fa a mano.
        """
        if self.elenco.count() == 0:
            return
        self.elenco.ensurePolished()
        largo = max(140, self.elenco.viewport().width() - 2)
        metriche = QFontMetrics(self.elenco.font())
        for i in range(self.elenco.count()):
            voce = self.elenco.item(i)
            riquadro = metriche.boundingRect(QRect(0, 0, largo - 34, 10000),
                                             Qt.TextWordWrap, voce.text())
            voce.setSizeHint(QSize(largo, riquadro.height() + 26))

    # ------------------------------------------------- la colonna dei nomi
    def piega_colonna(self, aperta: bool) -> None:
        """Apre o chiude l'elenco dei nomi, e si ricorda la scelta."""
        self.colonna_aperta = aperta
        self.db.imposta("tess_colonna", "1" if aperta else "0")
        self._sistema_colonna()

    def _sistema_colonna(self) -> None:
        """Decide se si vede la colonna o solo la linguetta.

        Oltre alla tua scelta conta lo spazio: in un riquadro stretto la
        colonna si ritira comunque, perché si mangerebbe la chat.
        """
        larga = self.width() > 700
        aperta = larga and self.colonna_aperta
        self.colonna_chat.setVisible(aperta)
        self.linguetta.setVisible(larga and not aperta)

    # ---------------------------------------------------------- rinominare
    def rinomina_chat(self, voce: QListWidgetItem) -> None:
        """Fa riscrivere il nome sulla voce stessa, al posto suo."""
        chat_id = voce.data(Qt.UserRole)
        if not chat_id:
            return
        self._rinominando = chat_id
        self.elenco.blockSignals(True)
        # la riga resta alta com'è: senza questo si accorcerebbe a una riga
        # sola appena le tolgo la data, e la casella verrebbe schiacciata
        voce.setSizeHint(self.elenco.visualItemRect(voce).size())
        voce.setText(voce.data(RUOLO_NOME) or "")   # nell'editor solo il nome
        voce.setFlags(voce.flags() | Qt.ItemIsEditable)
        self.elenco.blockSignals(False)
        self.elenco.editItem(voce)

    def _nome_scritto(self, voce: QListWidgetItem) -> None:
        """Confermato con Invio: il nome nuovo finisce nell'archivio.

        Vuoto vale «nessun nome»: torna a farsi chiamare con la prima domanda.
        """
        if self._rinominando:
            self.db.rinomina_conversazione_tess(self._rinominando, voce.text())

    def _fine_rinomina(self, *_) -> None:
        self._rinominando = ""
        self.aggiorna_elenco()      # la voce torna a due righe, col nome giusto

    def _scegli_chat(self, voce: QListWidgetItem) -> None:
        chat_id = voce.data(Qt.UserRole)
        if chat_id and chat_id != self.chat_id:
            self.carica_chat(chat_id)

    def _menu_chat(self, punto) -> None:
        voce = self.elenco.itemAt(punto)
        if voce is None:
            return
        chat_id = voce.data(Qt.UserRole)
        menu = QMenu(self)
        menu.addAction("Riapri", lambda: self.carica_chat(chat_id))
        menu.addAction("Rinomina…", lambda: self.rinomina_chat(voce))
        menu.addSeparator()
        menu.addAction("Chiudi l'elenco", lambda: self.piega_colonna(False))
        menu.addAction("Elimina", lambda: self._elimina_chat(chat_id))
        menu.exec(self.elenco.viewport().mapToGlobal(punto))

    def _elimina_chat(self, chat_id: str) -> None:
        self.db.elimina_conversazione_tess(chat_id)
        if chat_id == self.chat_id:
            self.pulisci()
        else:
            self.aggiorna_elenco()

    def _svuota_bolle(self) -> None:
        self.messaggi.clear()
        while self.lay_chat.count() > 1:
            voce = self.lay_chat.takeAt(0)
            disposizione = voce.layout()
            if disposizione is None:
                continue
            while disposizione.count():
                w = disposizione.takeAt(0).widget()
                if w is not None:
                    w.hide(); w.setParent(None); w.deleteLater()
            disposizione.deleteLater()
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
        self._scrivi("tu", domanda)
        self.messaggi.append({"role": "user", "content": domanda})
        nuova = not self.db.conversazione_tess(self.chat_id)
        self.db.salva_messaggio_tess(self.chat_id, "user", domanda)
        if nuova:
            self.aggiorna_elenco()

        sistema = [{"role": "system", "content": istruzioni(self.db)}]
        if self.b_dati.acceso():
            try:
                sistema.append({"role": "system",
                                "content": contesto(self.db, self.fonte,
                                                    aree_scelte(self.db))})
            except Exception:
                pass
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
            self.db.salva_messaggio_tess(self.chat_id, "assistant", self._in_corso)

    def _errore(self, messaggio: str) -> None:
        self.b_invia.setEnabled(True)
        self._bolla_corrente.setText(f"({messaggio})")
        self._mostra_stato(self.motore.attiva())

    # ------------------------------------------------- disegno della chat
    def _scrivi(self, chi: str, testo: str) -> QLabel:
        """Aggiunge una bolla: la sua, a destra; quella di Tess, a sinistra."""
        bolla = QLabel(testo)
        bolla.setObjectName("BollaTu" if chi == "tu" else "BollaTess")
        bolla.setWordWrap(True)
        bolla.setTextInteractionFlags(Qt.TextSelectableByMouse)
        bolla.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        fila = QHBoxLayout()
        fila.setContentsMargins(0, 0, 0, 0)
        if chi == "tu":
            fila.addStretch(1)
            fila.addWidget(bolla)
        else:
            fila.addWidget(bolla)
            fila.addStretch(1)
        self.lay_chat.insertLayout(self.lay_chat.count() - 1, fila)
        self.bolle.append(bolla)
        self._larghezza_bolle()
        for ritardo in (0, 60):          # dopo che il riquadro si è assestato
            QTimer.singleShot(ritardo, self._in_fondo)
        return bolla

    def _larghezza_bolle(self) -> None:
        """Ogni bolla larga quanto il suo testo, fino a tre quarti del riquadro."""
        massimo = max(180, int(self.chat.viewport().width() * 0.74))
        for bolla in self.bolle:
            bolla.ensurePolished()      # il carattere è quello del foglio di stile
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
