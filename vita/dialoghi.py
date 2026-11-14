"""Finestre di inserimento: una per ogni cosa che si registra nell'app.

Tutte hanno la stessa forma: un modulo di campi, «Salva» e «Annulla». Chi le
apre legge il risultato con `dati()`.

Tre fanno storia a sé e scrivono da sole nell'archivio: «Inserimento dati»
(`DialogoGiorno`), la voce del diario (`DialogoVoce`) e «Importa dati»
(`DialogoImporta`).
"""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, Qt, QTime, Signal
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDateEdit,
                               QDialog, QDialogButtonBox, QDoubleSpinBox,
                               QFileDialog, QFormLayout, QFrame, QGridLayout,
                               QHBoxLayout, QLabel, QLineEdit, QMenu,
                               QPlainTextEdit, QPushButton, QScrollArea,
                               QSlider, QSpinBox, QTimeEdit, QVBoxLayout,
                               QWidget)

from .componenti import (CampoData, CampoDurata, CursoreVoto,
                         DisposizioneFluida, Etichetta, SceltaSonno,
                         ZonaRilascio, minuti_ore)
from .icone_categorie import etichetta_categoria, solo_nome
from .db import (AREE, STATI_ESAME, STATI_PROGETTO, TIPI_ALLENAMENTO,
                 TIPI_PROGETTO)
from .tema import AREE as TINTE, trasparente
from .utils import data_it


def _data(valore: str = "") -> QDateEdit:
    campo = QDateEdit()
    campo.setCalendarPopup(True)
    campo.setDisplayFormat("dd/MM/yyyy")
    if valore:
        try:
            a, m, g = (int(x) for x in valore.split("-"))
            campo.setDate(QDate(a, m, g))
        except ValueError:
            campo.setDate(QDate.currentDate())
    else:
        campo.setDate(QDate.currentDate())
    return campo


def _scheda_modulo(titolo: str, nota: str = "") -> tuple[QFrame, QVBoxLayout]:
    """Riquadro arrotondato con l'etichetta in alto: la forma dei moduli.

    L'intestazione resta raggiungibile come `scheda.intestazione`, così chi la
    usa può metterci accanto un pulsante.
    """
    scheda = QFrame()
    scheda.setObjectName("SchedaModulo")
    lay = QVBoxLayout(scheda)
    lay.setContentsMargins(16, 13, 16, 15)
    lay.setSpacing(10)
    intestazione = QHBoxLayout()
    intestazione.setSpacing(9)
    et = QLabel(titolo.upper())
    et.setObjectName("EtichettaScheda")
    intestazione.addWidget(et)
    if nota:
        spiegazione = QLabel(nota)
        spiegazione.setObjectName("NotaScheda")
        intestazione.addWidget(spiegazione)
    intestazione.addStretch(1)
    lay.addLayout(intestazione)
    scheda.intestazione = intestazione
    return scheda, lay


def piede_pillola(voci) -> tuple[QWidget, dict]:
    """I comandi in fondo dentro un'unica pastiglia, come in One UI.

    `voci` è una sequenza di (chiave, testo, principale). Torna la pastiglia
    e i pulsanti, già pronti da collegare.
    """
    piede = QWidget()
    piede.setObjectName("PiedePillola")
    piede.setAttribute(Qt.WA_StyledBackground, True)
    lay = QHBoxLayout(piede)
    lay.setContentsMargins(6, 4, 6, 4)
    lay.setSpacing(0)
    pulsanti = {}
    for i, (chiave, testo, principale) in enumerate(voci):
        if i:
            filo = QFrame()
            filo.setObjectName("FiloPiede")
            filo.setFixedWidth(1)
            lay.addWidget(filo)
        b = QPushButton(testo)
        if principale:
            b.setObjectName("ComandoForte")
        b.setMinimumHeight(42)
        b.setCursor(Qt.PointingHandCursor)
        # Invio deve salvare, mai annullare: senza questo Qt elegge «default»
        # il primo pulsante della fila, e quello che hai scritto se ne va
        b.setAutoDefault(False)
        b.setDefault(bool(principale))
        lay.addWidget(b, 1)
        pulsanti[chiave] = b
    return piede, pulsanti


def riga_piede(piede: QWidget) -> QHBoxLayout:
    """La pastiglia dei comandi, centrata e larga il giusto."""
    fila = QHBoxLayout()
    fila.setContentsMargins(0, 2, 0, 0)
    fila.addStretch(1)
    piede.setMinimumWidth(300)
    fila.addWidget(piede)
    fila.addStretch(1)
    return fila


class SceltaColore(QPushButton):
    """Quadrato cliccabile che apre la tavolozza di sistema."""

    def __init__(self, colore: str = "#6c8cff", parent=None):
        super().__init__(parent)
        self.setObjectName("CampioneColore")
        self.setFixedSize(42, 32)
        self.colore = colore
        self.clicked.connect(self._scegli)
        self._mostra()

    def _mostra(self) -> None:
        self.setStyleSheet(f"background: {self.colore}; border: none;")

    def _scegli(self) -> None:
        scelto = QColorDialog.getColor(QColor(self.colore), self, "Colore")
        if scelto.isValid():
            self.colore = scelto.name()
            self._mostra()


class DialogoBase(QDialog):
    """Modulo con pulsanti Salva/Annulla già collegati.

    La forma è sempre la stessa: titolo e riga di spiegazione in alto, i campi
    dentro una scheda arrotondata, i pulsanti in fondo a destra. Le finestre
    grandi («Inserimento dati», «Voce del diario») usano la stessa scheda.
    """

    def __init__(self, titolo: str, parent=None, larghezza: int = 460,
                 nota: str = ""):
        super().__init__(parent)
        self.setWindowTitle(titolo)
        self.setMinimumWidth(larghezza)

        esterno = QVBoxLayout(self)
        esterno.setContentsMargins(20, 18, 20, 16)
        esterno.setSpacing(13)

        testata = QVBoxLayout()
        testata.setContentsMargins(0, 0, 0, 0); testata.setSpacing(2)
        et_titolo = QLabel(titolo)
        et_titolo.setObjectName("Sezione")
        testata.addWidget(et_titolo)
        if nota:
            spiegazione = QLabel(nota)
            spiegazione.setObjectName("NotaScheda")
            spiegazione.setWordWrap(True)
            testata.addWidget(spiegazione)
        esterno.addLayout(testata)

        self.scheda = QFrame()
        self.scheda.setObjectName("SchedaModulo")
        dentro = QVBoxLayout(self.scheda)
        dentro.setContentsMargins(16, 14, 16, 15)
        dentro.setSpacing(10)
        self.modulo = QFormLayout()
        self.modulo.setHorizontalSpacing(14)
        self.modulo.setVerticalSpacing(10)
        self.modulo.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.modulo.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        dentro.addLayout(self.modulo)
        esterno.addWidget(self.scheda)
        self.corpo = esterno          # chi eredita può aggiungere altre schede

        self.bottoni, comandi = piede_pillola(
            (("annulla", "Annulla", False), ("salva", "Salva", True)))
        self.b_annulla, self.b_salva = comandi["annulla"], comandi["salva"]
        self.b_annulla.clicked.connect(self.reject)
        self.b_salva.clicked.connect(self.accept)
        esterno.addLayout(riga_piede(self.bottoni))

    def campo(self, etichetta: str, widget):
        """Aggiunge una riga al modulo; i campi hanno tutti la stessa altezza."""
        if not isinstance(widget, (QPushButton, QPlainTextEdit)):
            widget.setMinimumHeight(40)
        if isinstance(widget, QLineEdit):
            widget.setCursorPosition(0)   # i nomi lunghi si leggono dall'inizio
        self.modulo.addRow(etichetta, widget)
        return widget

    @staticmethod
    def _cursore_percento(valore: int = 0) -> QWidget:
        contenitore = QWidget()
        lay = QHBoxLayout(contenitore)
        lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(10)
        cursore = QSlider(Qt.Horizontal)
        cursore.setRange(0, 100); cursore.setValue(int(valore))
        etichetta = QLabel(f"{int(valore)} %")
        etichetta.setFixedWidth(42)
        cursore.valueChanged.connect(lambda v: etichetta.setText(f"{v} %"))
        lay.addWidget(cursore, 1); lay.addWidget(etichetta)
        contenitore.cursore = cursore
        return contenitore


# ------------------------------------------------------------------- salute
class DialogoGiorno(QDialog):
    """La giornata di salute, scritta a mano: una finestra sola, quattro schede.

    Si apre dal pulsante «Inserimento dati» in alto. Resta aperta dopo il
    salvataggio, così si possono recuperare più giorni di fila: le frecce
    accanto alla data scorrono avanti e indietro.
    """

    salvato = Signal(str)

    def __init__(self, db, colori: dict, giorno: str = "", parent=None):
        super().__init__(parent)
        self.db = db
        self.c = colori
        self._caricando = False
        self.salvataggi = 0
        self.setWindowTitle("Inserimento dati")
        self.setMinimumWidth(740)

        esterno = QVBoxLayout(self)
        esterno.setContentsMargins(20, 18, 20, 16)
        esterno.setSpacing(14)
        esterno.addLayout(self._testata(giorno))

        self.campi: dict[str, QWidget] = {}
        griglia = QGridLayout()
        griglia.setHorizontalSpacing(14)
        griglia.setVerticalSpacing(14)
        # il sonno ha il quadrante: si prende tutta la colonna di sinistra
        riga_destra = 0
        for titolo, nota, voci in self._blocchi():
            scheda = self._scheda(titolo, nota, voci)
            if titolo == "Sonno":
                griglia.addWidget(scheda, 0, 0, 3, 1)
            else:
                griglia.addWidget(scheda, riga_destra, 1)
                riga_destra += 1
        griglia.setColumnStretch(0, 5)
        griglia.setColumnStretch(1, 4)
        esterno.addLayout(griglia)

        self.et_nota = QLabel("")
        self.et_nota.setObjectName("NotaScheda")
        self.et_nota.setWordWrap(True)
        self.et_nota.setAlignment(Qt.AlignCenter)
        esterno.addWidget(self.et_nota)
        pastiglia, comandi = piede_pillola(
            (("chiudi", "Chiudi", False), ("salva", "Salva giorno", True)))
        comandi["chiudi"].clicked.connect(self.accept)
        self.b_salva = comandi["salva"]
        self.b_salva.setToolTip("Ctrl+S")
        self.b_salva.clicked.connect(self.salva)
        esterno.addLayout(riga_piede(pastiglia))

        QShortcut(QKeySequence("Ctrl+S"), self, self.salva)
        self.carica()

    # ------------------------------------------------------------- struttura
    def _testata(self, giorno: str) -> QHBoxLayout:
        titolo = QLabel("Dati della giornata")
        titolo.setObjectName("Sezione")
        sotto = QLabel("Quello che l'orologio non porta.")
        sotto.setObjectName("NotaScheda")
        testi = QVBoxLayout()
        testi.setContentsMargins(0, 0, 0, 0); testi.setSpacing(2)
        testi.addWidget(titolo); testi.addWidget(sotto)

        self.data = QDateEdit()
        self.data.setObjectName("ChipData")        # la pastiglia tipo «Oggi»
        self.data.setCalendarPopup(True)
        self.data.setDisplayFormat("dd/MM/yyyy")
        self.data.setAlignment(Qt.AlignCenter)
        self.data.setFixedWidth(168)
        self.data.setDate(QDate.fromString(giorno, "yyyy-MM-dd")
                          if giorno else QDate.currentDate())
        self.data.setMaximumDate(QDate.currentDate().addDays(1))
        self.data.dateChanged.connect(lambda _: self.carica())
        indietro = QPushButton("‹")
        indietro.setToolTip("Giorno precedente")
        avanti = QPushButton("›")
        avanti.setToolTip("Giorno successivo")
        for freccia, passo in ((indietro, -1), (avanti, 1)):
            freccia.setObjectName("FrecciaGiorno")
            freccia.setFixedWidth(34)
            freccia.setMinimumHeight(36)
            freccia.clicked.connect(
                lambda _=False, d=passo: self.data.setDate(self.data.date().addDays(d)))
        self.b_oggi = QPushButton("Oggi")
        self.b_oggi.setObjectName("Segmento")
        self.b_oggi.setMinimumHeight(38)
        self.b_oggi.clicked.connect(lambda: self.data.setDate(QDate.currentDate()))
        self.data.setMinimumHeight(38)

        fila = QHBoxLayout()
        fila.setSpacing(8)
        fila.addLayout(testi, 1)
        fila.addWidget(indietro)
        fila.addWidget(self.data)
        fila.addWidget(avanti)
        fila.addWidget(self.b_oggi)
        return fila

    def _blocchi(self):
        """I quattro gruppi di campi: (titolo, nota, (chiave, nome, widget, ...))."""
        self.passi = QSpinBox(); self.passi.setRange(0, 200000)
        self.passi.setSingleStep(500); self.passi.setGroupSeparatorShown(True)
        self.km = QDoubleSpinBox(); self.km.setRange(0, 999); self.km.setSuffix(" km")
        self.kcal = QSpinBox(); self.kcal.setRange(0, 20000); self.kcal.setSuffix(" kcal")
        self.sonno = CampoDurata()
        self.sonno.cambiato.connect(self._sonno_da_totale)
        self.profondo = CampoDurata()
        self.rem = CampoDurata()
        self.sveglio = CampoDurata()
        self.battito = QSpinBox(); self.battito.setRange(0, 250)
        self.battito.setSuffix(" bpm")
        self.hrv = QSpinBox(); self.hrv.setRange(0, 300); self.hrv.setSuffix(" ms")
        self.stress = QSpinBox(); self.stress.setRange(0, 100)
        self.stress.setSuffix(" su 100")
        self.stress.setToolTip("Come lo conta il braccialetto: più basso è meglio.")
        self.acqua = QDoubleSpinBox(); self.acqua.setRange(0, 15)
        self.acqua.setSuffix(" L"); self.acqua.setSingleStep(0.25)
        self.peso = QDoubleSpinBox(); self.peso.setRange(0, 400)
        self.peso.setSuffix(" kg"); self.peso.setSingleStep(0.1)
        self.grasso = QDoubleSpinBox(); self.grasso.setRange(0, 70)
        self.grasso.setSuffix(" %"); self.grasso.setSingleStep(0.5)
        self.muscolo = QDoubleSpinBox(); self.muscolo.setRange(0, 80)
        self.muscolo.setSuffix(" %"); self.muscolo.setSingleStep(0.5)
        for campo in (self.peso, self.grasso, self.muscolo):
            campo.setDecimals(1)        # un decimale basta: la bilancia non fa di più
        for campo in (self.peso, self.grasso, self.muscolo):
            campo.valueChanged.connect(self._aggiorna_secca)
        return (
            ("Attività", "passi e distanza",
             (("passi", "Passi", self.passi),
              ("km", "Distanza", self.km),
              ("kcal", "Calorie attive", self.kcal))),
            ("Sonno", "le fasi sono facoltative",
             (("sonno", "Totale", self.sonno),
              ("sonno_profondo", "Profondo", self.profondo),
              ("sonno_rem", "REM", self.rem),
              ("sonno_sveglio", "Sveglio", self.sveglio))),
            ("Corpo", "appena svegli",
             (("battito", "Battito a riposo", self.battito),
              ("hrv", "Variabilità (HRV)", self.hrv),
              ("stress", "Stress", self.stress),
              ("acqua", "Acqua", self.acqua))),
            ("Composizione", "dalla bilancia — a 0 il dato si cancella",
             (("peso", "Peso", self.peso),
              ("grasso", "Massa grassa", self.grasso),
              ("muscolo", "Massa muscolare", self.muscolo))),
        )

    def _scheda(self, titolo: str, nota: str, voci) -> QFrame:
        scheda, lay = _scheda_modulo(titolo, nota)
        if titolo == "Sonno":
            lay.addWidget(self._quadrante(), 1)
        griglia = QGridLayout()
        griglia.setHorizontalSpacing(12)
        griglia.setVerticalSpacing(8)
        griglia.setColumnStretch(0, 1)
        for i, (chiave, nome, widget) in enumerate(voci):
            et = QLabel(nome)
            et.setObjectName("TitoloRiga")
            # le durate hanno due caselle in fila: vogliono più spazio
            largo = isinstance(widget, CampoDurata)
            widget.setMinimumWidth(150 if largo else 118)
            widget.setMaximumWidth(176 if largo else 156)
            widget.setMinimumHeight(42)
            griglia.addWidget(et, i, 0)
            griglia.addWidget(widget, i, 1)
            self.campi[chiave] = widget
        lay.addLayout(griglia)
        if titolo == "Composizione":
            self.et_secca = QLabel("")
            self.et_secca.setObjectName("NotaScheda")
            self.et_secca.setWordWrap(True)
            lay.addWidget(self.et_secca)
        lay.addStretch(1)
        return scheda

    def _quadrante(self) -> QWidget:
        """La ghiera del sonno: le ore si prendono trascinando, non scrivendo."""
        contenitore = QWidget()
        colonna = QVBoxLayout(contenitore)
        colonna.setContentsMargins(0, 2, 0, 6)
        colonna.setSpacing(8)
        self.ghiera = SceltaSonno(self.c, TINTE["salute"])
        self.ghiera.setMinimumHeight(248)
        self.ghiera.cambiato.connect(self._sonno_da_ghiera)
        self.et_sonno = QLabel("")
        self.et_sonno.setObjectName("NotaSonno")
        self.et_sonno.setAlignment(Qt.AlignCenter)
        self.et_sonno.setStyleSheet(f"color: {TINTE['salute']};")
        colonna.addWidget(self.ghiera, 1)
        colonna.addWidget(self.et_sonno)
        return contenitore

    def _sonno_da_ghiera(self) -> None:
        """Mosse le maniglie, il totale si aggiorna da sé."""
        minuti = self.ghiera.durata()
        self.sonno.imposta(minuti)
        self._nota_sonno(minuti)

    def _sonno_da_totale(self, minuti: int) -> None:
        """Scritto il totale a mano, la sveglia si sposta di conseguenza."""
        if self._caricando:
            return
        self.ghiera.imposta_durata(minuti)
        self._nota_sonno(minuti)

    def _nota_sonno(self, minuti: int) -> None:
        a_letto, sveglia = self.ghiera.ore()
        ore = minuti / 60
        testo = f"{int(minuti // 60)}h{int(minuti % 60):02d}".replace("h00", " ore")
        self.et_sonno.setText(f"Dormi {testo}  ·  {a_letto} → {sveglia}")

    # ----------------------------------------------------------------- dati
    def giorno(self) -> str:
        return self.data.date().toString("yyyy-MM-dd")

    def _aggiorna_secca(self) -> None:
        """La massa secca non si scrive: è il peso meno la massa grassa."""
        peso, grasso = self.peso.value(), self.grasso.value()
        if peso and grasso:
            secca = peso * (1 - grasso / 100)
            self.et_secca.setText(
                f"massa secca {secca:.1f} kg  ·  grassa "
                f"{peso - secca:.1f} kg".replace(".", ","))
        else:
            self.et_secca.setText("peso e massa grassa danno la massa secca")

    def carica(self) -> None:
        self._caricando = True
        r = self.db.salute_giorno(self.giorno())
        v = dict(r) if r else {}
        self.passi.setValue(int(v.get("passi", 0)))
        self.km.setValue(float(v.get("km", 0)))
        self.kcal.setValue(int(v.get("kcal", 0)))
        self.battito.setValue(int(v.get("battito", 0)))
        self.hrv.setValue(int(v.get("hrv", 0)))
        self.acqua.setValue(float(v.get("acqua", 0)))
        self.stress.setValue(int(v.get("stress", 0) or 0))
        self.peso.setValue(float(v.get("peso", 0)))
        self.grasso.setValue(float(v.get("grasso", 0)))
        self.muscolo.setValue(float(v.get("muscolo", 0)))
        self.sonno.imposta(v.get("sonno", 0))
        # le ore della ghiera: quelle scritte, o dedotte dal totale a partire
        # dalle 23 — un giorno vuoto parte da 23:00 → 07:00
        totale = int(v.get("sonno", 0) or 0)
        a_letto = (v.get("a_letto") or "").strip() or "23:00"
        sveglia = (v.get("sveglia") or "").strip()
        if not sveglia:
            from .componenti import ore_minuti
            sveglia = minuti_ore(ore_minuti(a_letto, 1380) + (totale or 480))
        self.ghiera.imposta(a_letto, sveglia)
        self._nota_sonno(totale or self.ghiera.durata())
        self.profondo.imposta(v.get("sonno_profondo", 0))
        self.rem.imposta(v.get("sonno_rem", 0))
        self.sveglio.imposta(v.get("sonno_sveglio", 0))
        self._aggiorna_secca()
        self.b_oggi.setEnabled(self.giorno() != date.today().isoformat())
        self.et_nota.setText("" if r else "Questo giorno è ancora vuoto.")
        self._caricando = False

    def salva(self) -> None:
        if self._caricando:
            return
        self.db.salva_salute({
            "data": self.giorno(), "passi": self.passi.value(), "km": self.km.value(),
            "kcal": self.kcal.value(), "sonno": self.sonno.valore(),
            "sonno_profondo": self.profondo.valore(), "sonno_rem": self.rem.valore(),
            "sonno_sveglio": self.sveglio.valore(), "battito": self.battito.value(),
            "hrv": self.hrv.value(), "peso": self.peso.value(),
            "grasso": self.grasso.value(), "muscolo": self.muscolo.value(),
            "acqua": self.acqua.value(), "stress": self.stress.value(),
            "note": "",
            "a_letto": self.ghiera.ore()[0], "sveglia": self.ghiera.ore()[1],
        })
        self.salvataggi += 1
        giorno = self.data.date().toString("dd/MM/yyyy")
        self.et_nota.setText(f"Salvato il giorno {giorno}.")
        self.salvato.emit(self.giorno())


class DialogoAllenamento(DialogoBase):
    def __init__(self, voce=None, parent=None):
        super().__init__("Modifica allenamento" if voce else "Nuovo allenamento",
                         parent, nota="Distanza e calorie solo se le sai: "
                         "quello che lasci a zero resta senza dato.")
        v = dict(voce) if voce else {}
        self.id = v.get("id")
        self.data = self.campo("Data", _data(v.get("data", "")))
        self.tipo = self.campo("Tipo", QComboBox())
        self.tipo.setEditable(True)
        self.tipo.addItems(TIPI_ALLENAMENTO)
        if v.get("tipo"):
            self.tipo.setCurrentText(v["tipo"])
        self.durata = self.campo("Durata", CampoDurata())
        self.durata.imposta(v.get("minuti", 45))
        self.km = self.campo("Distanza", QDoubleSpinBox())
        self.km.setRange(0, 999); self.km.setDecimals(2); self.km.setSuffix(" km")
        self.km.setValue(float(v.get("km", 0)))
        self.kcal = self.campo("Calorie", QSpinBox())
        self.kcal.setRange(0, 9999); self.kcal.setSuffix(" kcal")
        self.kcal.setValue(int(v.get("kcal", 0)))
        self.intensita = self.campo("Intensità", QComboBox())
        self.intensita.addItems(["leggera", "media", "intensa"])
        self.intensita.setCurrentText(v.get("intensita", "media"))
        self.note = self.campo("Note", QLineEdit(v.get("note", "")))

    def dati(self) -> dict:
        return {"id": self.id, "data": self.data.date().toString("yyyy-MM-dd"),
                "tipo": self.tipo.currentText().strip() or "Allenamento",
                "minuti": self.durata.valore(), "km": self.km.value(),
                "kcal": self.kcal.value(), "intensita": self.intensita.currentText(),
                "note": self.note.text().strip()}


# ----------------------------------------------------------------- carriera
class DialogoProgetto(DialogoBase):
    def __init__(self, voce=None, parent=None):
        super().__init__("Modifica progetto" if voce else "Nuovo progetto", parent,
                         480, "Un progetto può non avere una scadenza: in quel "
                         "caso lascia la data spenta.")
        v = dict(voce) if voce else {}
        self.id = v.get("id")
        self.nome = self.campo("Nome", QLineEdit(v.get("nome", "")))
        self.nome.setPlaceholderText("es. Smart-Light ALL")
        self.tipo = self.campo("Tipo", QComboBox())
        self.tipo.addItems(TIPI_PROGETTO)
        self.tipo.setCurrentText(v.get("tipo", "personale"))
        self.stato = self.campo("Stato", QComboBox())
        for chiave, nome in STATI_PROGETTO.items():
            self.stato.addItem(nome, chiave)
        indice = self.stato.findData(v.get("stato", "idea"))
        self.stato.setCurrentIndex(max(0, indice))
        self.cliente = self.campo("Cliente", QLineEdit(v.get("cliente", "")))
        self.compenso = self.campo("Compenso previsto", QDoubleSpinBox())
        self.compenso.setRange(0, 999999); self.compenso.setDecimals(2)
        self.compenso.setSuffix(" €")
        self.compenso.setValue(float(v.get("compenso", 0)))
        self.scadenza = self.campo(
            "Scadenza", CampoData(v.get("scadenza", ""), "senza scadenza"))
        self.avanzamento = self.campo("Avanzamento",
                                      self._cursore_percento(v.get("avanzamento", 0)))
        self.colore = self.campo("Colore", SceltaColore(v.get("colore", "#6c8cff")))
        self.note = self.campo("Note", QPlainTextEdit(v.get("note", "")))
        self.note.setFixedHeight(68)

    def dati(self) -> dict:
        return {"id": self.id, "nome": self.nome.text().strip() or "Senza nome",
                "tipo": self.tipo.currentText(), "stato": self.stato.currentData(),
                "cliente": self.cliente.text().strip(),
                "compenso": self.compenso.value(),
                "inizio": "",
                "scadenza": self.scadenza.valore(),
                "avanzamento": self.avanzamento.cursore.value(),
                "colore": self.colore.colore,
                "note": self.note.toPlainText().strip()}


class DialogoLavoro(DialogoBase):
    """Ore lavorate su un progetto."""

    def __init__(self, progetti, voce=None, parent=None):
        super().__init__("Modifica ore" if voce else "Registra ore", parent,
                         nota="Quanto hai lavorato oggi, e su cosa.")
        v = dict(voce) if voce else {}
        self.id = v.get("id")
        self.data = self.campo("Data", _data(v.get("data", "")))
        self.progetto = self.campo("Progetto", QComboBox())
        self.progetto.addItem("— nessuno —", None)
        for p in progetti:
            self.progetto.addItem(p["nome"], p["id"])
        indice = self.progetto.findData(v.get("progetto_id"))
        self.progetto.setCurrentIndex(max(0, indice))
        self.durata = self.campo("Durata", CampoDurata())
        self.durata.imposta(v.get("minuti", 60))
        self.note = self.campo("Su cosa", QLineEdit(v.get("note", "")))
        self.note.setPlaceholderText("es. layout della scheda sensori")

    def dati(self) -> dict:
        return {"id": self.id, "data": self.data.date().toString("yyyy-MM-dd"),
                "progetto_id": self.progetto.currentData(),
                "minuti": self.durata.valore(), "note": self.note.text().strip()}


class DialogoIncasso(DialogoBase):
    """Un incasso di Carriera, che è anche un'entrata di Finanza.

    La spunta in fondo tiene insieme le due cose: lo stesso denaro scritto una
    volta sola, con la categoria di entrata che si sceglie qui.
    """

    def __init__(self, progetti, voce=None, categorie=None, collegabile=True,
                 parent=None):
        super().__init__("Modifica incasso" if voce else "Registra incasso", parent,
                         nota="Soldi entrati davvero, non quelli promessi.")
        v = dict(voce) if voce else {}
        self.id = v.get("id")
        self.data = self.campo("Data", _data(v.get("data", "")))
        self.progetto = self.campo("Progetto", QComboBox())
        self.progetto.addItem("— nessuno —", None)
        for p in progetti:
            self.progetto.addItem(p["nome"], p["id"])
        indice = self.progetto.findData(v.get("progetto_id"))
        self.progetto.setCurrentIndex(max(0, indice))
        self.importo = self.campo("Importo", QDoubleSpinBox())
        self.importo.setRange(0, 999999); self.importo.setDecimals(2)
        self.importo.setSuffix(" €"); self.importo.setSingleStep(10)
        self.importo.setValue(float(v.get("importo", 0)))
        self.categoria = self.campo("Categoria", QComboBox())
        self.categoria.setEditable(True)
        self.categoria.addItems(list(categorie or ["Lavoro"]))
        self.categoria.setCurrentText(v.get("categoria") or "Lavoro")
        self.descrizione = self.campo("Descrizione", QLineEdit(v.get("descrizione", "")))

        self.in_finanza = QCheckBox("Registra anche fra le entrate di Finanza")
        self.in_finanza.setChecked(bool(v.get("movimento_id")) if voce
                                   else bool(collegabile))
        self.in_finanza.setEnabled(bool(collegabile))
        nota = QLabel("L'entrata nasce nell'archivio interno con la categoria "
                      "scelta qui; correggendo l'incasso si corregge anche quella."
                      if collegabile else
                      "La finanza sta leggendo l'archivio di Finance: l'incasso "
                      "resta in Carriera.\nPer collegarli, in Impostazioni → "
                      "Finanza scegli l'archivio interno.")
        nota.setObjectName("NotaScheda")
        nota.setWordWrap(True)
        self.modulo.addRow("", self.in_finanza)
        self.modulo.addRow("", nota)

    def dati(self) -> dict:
        return {"id": self.id, "data": self.data.date().toString("yyyy-MM-dd"),
                "progetto_id": self.progetto.currentData(),
                "importo": self.importo.value(),
                "categoria": self.categoria.currentText().strip() or "Lavoro",
                "descrizione": self.descrizione.text().strip(),
                "in_finanza": self.in_finanza.isChecked()}


# --------------------------------------------------------------- accademica
class DialogoEsame(DialogoBase):
    def __init__(self, voce=None, parent=None):
        super().__init__("Modifica esame" if voce else "Nuovo esame", parent, 480,
                         "La data dell'appello si mette solo quando c'è: "
                         "un esame senza appello resta senza data.")
        v = dict(voce) if voce else {}
        self.id = v.get("id")
        self.nome = self.campo("Materia", QLineEdit(v.get("nome", "")))
        self.nome.setPlaceholderText("es. Meccanica Quantistica")
        self.cfu = self.campo("CFU", QSpinBox())
        self.cfu.setRange(0, 60); self.cfu.setValue(int(v.get("cfu", 6)))
        self.anno = self.campo("Anno di corso", QSpinBox())
        self.anno.setRange(1, 6); self.anno.setValue(int(v.get("anno", 1)))
        self.stato = self.campo("Stato", QComboBox())
        for chiave, nome in STATI_ESAME.items():
            self.stato.addItem(nome, chiave)
        self.stato.setCurrentIndex(max(0, self.stato.findData(v.get("stato", "previsto"))))
        self.voto = self.campo("Voto", QSpinBox())
        self.voto.setRange(0, 30); self.voto.setSpecialValueText("—")
        self.voto.setValue(int(v.get("voto", 0)))
        self.lode = self.campo("Lode", QPushButton("30 e lode"))
        self.lode.setCheckable(True); self.lode.setChecked(bool(v.get("lode", 0)))
        self.data_esame = self.campo(
            "Appello", CampoData(v.get("data_esame", ""), "non fissato"))
        self.avanzamento = self.campo("Preparazione",
                                      self._cursore_percento(v.get("avanzamento", 0)))
        self.note = self.campo("Note", QLineEdit(v.get("note", "")))

    def dati(self) -> dict:
        return {"id": self.id, "nome": self.nome.text().strip() or "Esame",
                "cfu": self.cfu.value(), "voto": self.voto.value(),
                "lode": 1 if self.lode.isChecked() else 0,
                "stato": self.stato.currentData(), "anno": self.anno.value(),
                "data_esame": self.data_esame.valore(),
                "avanzamento": self.avanzamento.cursore.value(),
                "note": self.note.text().strip()}


class DialogoStudio(DialogoBase):
    def __init__(self, materie, voce=None, parent=None):
        super().__init__("Modifica studio" if voce else "Registra studio", parent,
                         nota="Quanto hai studiato e su quale materia.")
        v = dict(voce) if voce else {}
        self.id = v.get("id")
        self.data = self.campo("Data", _data(v.get("data", "")))
        self.materia = self.campo("Materia", QComboBox())
        self.materia.setEditable(True)
        self.materia.addItems(materie)
        self.materia.setCurrentText(v.get("materia", ""))
        self.durata = self.campo("Durata", CampoDurata())
        self.durata.imposta(v.get("minuti", 60))
        self.argomento = self.campo("Argomento", QLineEdit(v.get("argomento", "")))
        self.argomento.setPlaceholderText("es. oscillatore armonico")

    def dati(self) -> dict:
        return {"id": self.id, "data": self.data.date().toString("yyyy-MM-dd"),
                "materia": self.materia.currentText().strip(),
                "minuti": self.durata.valore(),
                "argomento": self.argomento.text().strip()}


class DialogoPercorso(DialogoBase):
    def __init__(self, voce=None, parent=None):
        super().__init__("Modifica percorso" if voce else "Nuovo percorso", parent,
                         470, "Quello che vuoi imparare fuori dal libretto.")
        v = dict(voce) if voce else {}
        self.id = v.get("id")
        self.nome = self.campo("Cosa vuoi imparare", QLineEdit(v.get("nome", "")))
        self.nome.setPlaceholderText("es. Analisi dati con Python")
        self.categoria = self.campo("Ambito", QComboBox())
        self.categoria.setEditable(True)
        self.categoria.addItems(["università", "liceo", "lavoro", "personale", "lingue"])
        self.categoria.setCurrentText(v.get("categoria", "università"))
        self.stato = self.campo("Stato", QComboBox())
        for chiave, nome in (("attivo", "Attivo"), ("attesa", "In attesa"),
                             ("finito", "Finito")):
            self.stato.addItem(nome, chiave)
        self.stato.setCurrentIndex(max(0, self.stato.findData(v.get("stato", "attivo"))))
        self.avanzamento = self.campo("Avanzamento",
                                      self._cursore_percento(v.get("avanzamento", 0)))
        self.risorsa = self.campo("Risorsa", QLineEdit(v.get("risorsa", "")))
        self.risorsa.setPlaceholderText("libro, corso, cartella sul PC…")
        self.colore = self.campo("Colore", SceltaColore(v.get("colore", "#35c4d7")))
        self.note = self.campo("Note", QLineEdit(v.get("note", "")))

    def dati(self) -> dict:
        return {"id": self.id, "nome": self.nome.text().strip() or "Percorso",
                "categoria": self.categoria.currentText().strip(),
                "avanzamento": self.avanzamento.cursore.value(),
                "risorsa": self.risorsa.text().strip(),
                "stato": self.stato.currentData(), "colore": self.colore.colore,
                "note": self.note.text().strip()}


class SceltaStatoAttivita(QWidget):
    """Scelta a tre opzioni ben visibili: Da fare, In corso, Completata."""
    cambiato = Signal(str)

    STATI = (
        ("da_fare", "Da fare", "#8b949e"),
        ("in_corso", "In corso", "#f0b429"),
        ("completata", "Completata", "#16c47f"),
    )

    def __init__(self, valore: str = "da_fare", parent=None):
        super().__init__(parent)
        valori_validi = {k for k, _t, _c in self.STATI}
        self._valore = valore if valore in valori_validi else "da_fare"
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self._bottoni: dict[str, QPushButton] = {}
        for chiave, testo, _colore in self.STATI:
            b = QPushButton(testo)
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _c=False, k=chiave: self.imposta(k))
            lay.addWidget(b)
            self._bottoni[chiave] = b
        self._aggiorna_stile()

    def imposta(self, valore: str) -> None:
        if valore in self._bottoni and valore != self._valore:
            self._valore = valore
            self._aggiorna_stile()
            self.cambiato.emit(self._valore)

    def valore(self) -> str:
        return self._valore

    def _aggiorna_stile(self) -> None:
        for chiave, _testo, colore in self.STATI:
            b = self._bottoni[chiave]
            attivo = (chiave == self._valore)
            b.setChecked(attivo)
            if attivo:
                b.setStyleSheet(
                    f"QPushButton {{ background: {trasparente(colore, 0.22)}; color: {colore};"
                    f" font-weight: 700; border: 1.5px solid {colore}; border-radius: 12px; padding: 5px 14px; }}"
                )
            else:
                b.setStyleSheet(
                    f"QPushButton {{ background: transparent; color: {trasparente(colore, 0.65)};"
                    f" font-weight: 500; border: 1px solid {trasparente(colore, 0.25)}; border-radius: 12px; padding: 5px 14px; }}"
                    f"QPushButton:hover {{ background: {trasparente(colore, 0.1)}; color: {colore}; }}"
                )


# ------------------------------------------------------- scadenze, abitudini
class DialogoScadenza(DialogoBase):
    def __init__(self, voce=None, area: str = "accademica", parent=None,
                 area_fissa: bool = False):
        """`area_fissa=True` toglie la tendina «Area»: la scadenza resta di
        quell'area e basta, senza poterla spostare altrove. Serve a chi apre
        questo modulo da un riquadro già scoperto per un'area sola — il
        riquadro «Attività» di un'area in Home, per esempio — dove la
        tendina lascerebbe scrivere una scadenza di Carriera dentro un
        riquadro che si chiama «Emozioni», e chi la cerca poi non la trova.
        """
        super().__init__("Modifica evento" if voce else "Nuovo evento", parent,
                         nota="Una cosa da fare. La data è facoltativa: senza, "
                              "resta nell'elenco della sua area e basta.")
        v = dict(voce) if voce else {}
        self.id = v.get("id")
        self.titolo = self.campo("Cosa", QLineEdit(v.get("titolo", "")))
        self.titolo.setPlaceholderText("es. Chiamare la terapeuta")
        # La data si può lasciare vuota, come già si fa per l'appello di un
        # esame e per la scadenza di un progetto: «chiamare la terapeuta» è
        # una cosa da fare, non un appuntamento, e inventarle un giorno
        # qualunque la farebbe comparire fra gli impegni di quel giorno —
        # dove non c'entra niente, e dove sembra già in ritardo il giorno dopo.
        self.data = self.campo("Quando", CampoData(v.get("data", ""), "senza data"))
        area_iniziale = v.get("area", area)
        if area_fissa:
            self.area = None
            self._area_fissa = area_iniziale
        else:
            self.area = self.campo("Area", QComboBox())
            for chiave, nome in AREE.items():
                self.area.addItem(nome, chiave)
            self.area.setCurrentIndex(max(0, self.area.findData(area_iniziale)))

        stato_iniziale = v.get("stato")
        if not stato_iniziale:
            stato_iniziale = "completata" if v.get("fatta") else "da_fare"
        self.stato = self.campo("Stato", SceltaStatoAttivita(stato_iniziale))
        self.note = self.campo("Note", QLineEdit(v.get("note", "")))

    def dati(self) -> dict:
        stato = self.stato.valore()
        return {"id": self.id, "data": self.data.valore(),
                "titolo": self.titolo.text().strip() or "Evento",
                "area": self._area_fissa if self.area is None
                        else self.area.currentData(),
                "fatta": 1 if stato == "completata" else 0,
                "stato": stato,
                "note": self.note.text().strip()}


class DialogoAbitudine(DialogoBase):
    def __init__(self, voce=None, parent=None):
        super().__init__("Modifica abitudine" if voce else "Nuova abitudine", parent,
                         nota="Una cosa da spuntare ogni giorno, con il suo colore.")
        v = dict(voce) if voce else {}
        self.id = v.get("id")
        self.nome = self.campo("Nome", QLineEdit(v.get("nome", "")))
        self.nome.setPlaceholderText("es. Leggere 20 pagine")
        self.obiettivo = self.campo("Volte a settimana", QSpinBox())
        self.obiettivo.setRange(1, 7); self.obiettivo.setValue(int(v.get("obiettivo", 7)))
        self.area = self.campo("Area", QComboBox())
        for chiave, nome in AREE.items():
            self.area.addItem(nome, chiave)
        self.area.setCurrentIndex(max(0, self.area.findData(v.get("area", "salute"))))
        self.colore = self.campo("Colore", SceltaColore(v.get("colore", "#2ec27e")))
        self.attiva = self.campo("Attiva", QPushButton("in uso"))
        self.attiva.setCheckable(True)
        self.attiva.setChecked(bool(v.get("attiva", 1)))

    def dati(self) -> dict:
        return {"id": self.id, "nome": self.nome.text().strip() or "Abitudine",
                "colore": self.colore.colore, "obiettivo": self.obiettivo.value(),
                "area": self.area.currentData(),
                "attiva": 1 if self.attiva.isChecked() else 0}


# ------------------------------------------------------------------ finanza
class DialogoMovimento(DialogoBase):
    """Un movimento dell'archivio interno.

    Le categorie sono due elenchi distinti, uno per le entrate e uno per le
    uscite: cambiando il tipo cambia l'elenco. Il campo resta scrivibile, e
    una categoria nuova entra nell'elenco al salvataggio.
    """

    def __init__(self, categorie, voce=None, parent=None, conti=None,
                 colori=None, tinte=None, icone=None):
        super().__init__(
            "Modifica movimento" if voce else "Nuovo movimento", parent,
            nota="Entrata o uscita. La categoria in alto è quella che possiede "
                 "l'importo — finisce nel budget e nella ciambella; le altre "
                 "servono a ritrovarlo.")
        v = dict(voce) if voce else {}
        self.id = v.get("id")
        self.c = colori or {}
        self.tinte = dict(tinte or {})
        self.icone = dict(icone or {})
        if isinstance(categorie, dict):
            self.elenchi = {t: list(categorie.get(t, [])) for t in ("entrata", "uscita")}
        else:                       # un elenco solo: vale per tutti e due i tipi
            self.elenchi = {"entrata": list(categorie), "uscita": list(categorie)}
        self.tipo = self.campo("Tipo", QComboBox())
        self.tipo.addItems(["uscita", "entrata"])
        self.tipo.setCurrentText(v.get("tipo", "uscita"))
        self.data = self.campo("Data", _data(v.get("data", "")))
        self.importo = self.campo("Importo", QDoubleSpinBox())
        self.importo.setRange(0, 9999999); self.importo.setDecimals(2)
        self.importo.setSuffix(" €"); self.importo.setSingleStep(10)
        self.importo.setValue(float(v.get("importo", 0)))
        self.categoria = self.campo("Categoria", QComboBox())
        self.categoria.setEditable(True)
        self.categoria.setToolTip("Scegli dall'elenco o scrivine una nuova: "
                                  "resta per la prossima volta.")
        self._riempi_categorie(self.tipo.currentText(), v.get("categoria", ""))
        self.tipo.currentTextChanged.connect(
            lambda tipo: self._riempi_categorie(tipo, self.categoria.currentText()))
        self.conto = self.campo("Conto", QComboBox())
        self.conto.setEditable(True)
        self.conto.setToolTip("Su che conto è passato: contante, carta, conto "
                              "corrente.\nScrivine uno nuovo e resta.")
        elenco_conti = list(conti or [])
        self.conto.addItems([""] + elenco_conti)
        self.conto.setCurrentText(v.get("conto", "") or
                                  (elenco_conti[0] if elenco_conti and not voce
                                   else ""))
        self.descrizione = self.campo("Descrizione", QLineEdit(v.get("descrizione", "")))

        # --------------------------------------------- le categorie in più
        riquadro = QWidget()
        riquadro.setObjectName("ContenutoSezione")
        self.fluida = DisposizioneFluida(riquadro, 0, 6)
        self.chip: dict[str, Etichetta] = {}
        self._scelte_extra = set(
            x.strip() for x in str(v.get("categorie", "")).split(",") if x.strip())
        # le pastiglie vanno a capo da sole e possono essere tante: dentro
        # un'area che scorre, se no la finestra crescerebbe a dismisura o
        # taglierebbe l'ultima riga
        scorri = QScrollArea()
        scorri.setObjectName("ContenutoSezione")
        scorri.viewport().setObjectName("ContenutoSezione")
        scorri.setWidgetResizable(True)
        scorri.setFrameShape(QScrollArea.NoFrame)
        scorri.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scorri.setMinimumHeight(98)
        scorri.setWidget(riquadro)
        self.campo("Altre categorie", scorri)
        self._rifai_chip()
        self.tipo.currentTextChanged.connect(lambda _t: self._rifai_chip())
        self.categoria.currentTextChanged.connect(lambda _t: self._rifai_chip())

    def _rifai_chip(self) -> None:
        """Le pastiglie delle altre categorie: quelle del tipo scelto, meno la prima.

        La categoria principale non compare qui: è già scelta sopra, e
        metterla anche fra le altre vorrebbe dire scriverla due volte.
        """
        self._scelte_extra = self.extra() | self._scelte_extra
        principale = solo_nome(self.categoria.currentText())
        while self.fluida.count():
            elemento = self.fluida.takeAt(0)
            w = elemento.widget()
            if w is not None:
                w.hide(); w.setParent(None); w.deleteLater()
        self.chip.clear()
        for nome in self.elenchi.get(self.tipo.currentText(), []):
            if nome == principale:
                continue
            chip = Etichetta(etichetta_categoria(nome, self.icone.get(nome)),
                             self.tinte.get(nome, "#7c8cff"), self.c)
            chip.setChecked(nome in self._scelte_extra)
            self.fluida.addWidget(chip)
            self.chip[nome] = chip

    def extra(self) -> set:
        """Le altre categorie accese adesso."""
        return {nome for nome, chip in self.chip.items() if chip.isChecked()}

    def _riempi_categorie(self, tipo: str, scelta: str = "") -> None:
        """Rimette nell'elenco le categorie del tipo scelto, tenendo la scelta."""
        elenco = self.elenchi.get(tipo, [])
        scelta = solo_nome(scelta)
        self.categoria.blockSignals(True)
        self.categoria.clear()
        # il nome viaggia con la sua icona davanti; chi legge `dati()` la
        # toglie, così scriverne una nuova a mano continua a funzionare
        self.categoria.addItems(
            [etichetta_categoria(n, self.icone.get(n)) for n in elenco])
        self.categoria.setCurrentText(
            etichetta_categoria(scelta, self.icone.get(scelta))
            if scelta in elenco else
            (etichetta_categoria(elenco[0], self.icone.get(elenco[0]))
             if elenco else ""))
        self.categoria.blockSignals(False)

    def dati(self) -> dict:
        principale = solo_nome(self.categoria.currentText()) or "Altro"
        return {"id": self.id, "data": self.data.date().toString("yyyy-MM-dd"),
                "tipo": self.tipo.currentText(), "importo": self.importo.value(),
                "categoria": principale,
                "categorie": ", ".join(sorted(self.extra() - {principale})),
                "conto": self.conto.currentText().strip(),
                "descrizione": self.descrizione.text().strip()}


class DialogoObiettivo(DialogoBase):
    def __init__(self, voce=None, parent=None):
        super().__init__("Modifica obiettivo" if voce else "Nuovo obiettivo", parent,
                         nota="Quanto ti serve e, se c'è, entro quando.")
        v = dict(voce) if voce else {}
        self.id = v.get("id")
        self.nome = self.campo("Nome", QLineEdit(v.get("nome", "")))
        self.nome.setPlaceholderText("es. Portatile nuovo")
        self.obiettivo = self.campo("Da raggiungere", QDoubleSpinBox())
        self.obiettivo.setRange(0, 999999); self.obiettivo.setSuffix(" €")
        self.obiettivo.setDecimals(2); self.obiettivo.setSingleStep(50)
        self.obiettivo.setValue(float(v.get("obiettivo", 0)))
        self.accantonato = self.campo("Già accantonato", QDoubleSpinBox())
        self.accantonato.setRange(0, 999999); self.accantonato.setSuffix(" €")
        self.accantonato.setDecimals(2); self.accantonato.setSingleStep(10)
        self.accantonato.setValue(float(v.get("accantonato", 0)))
        self.scadenza = self.campo(
            "Entro", CampoData(v.get("scadenza", ""), "senza scadenza"))
        self.note = self.campo("Note", QLineEdit(v.get("note", "")))

    def dati(self) -> dict:
        return {"id": self.id, "nome": self.nome.text().strip() or "Obiettivo",
                "obiettivo": self.obiettivo.value(),
                "accantonato": self.accantonato.value(),
                "scadenza": self.scadenza.valore(),
                "note": self.note.text().strip()}


# -------------------------------------------------------------------- diario
class DialogoVoce(QDialog):
    """La voce del diario, in una finestra sua: come stai, cosa senti, cosa scrivi.

    Si apre dal pulsante «Scrivi voce» in alto nella pagina Emozioni, da un
    giorno del calendario dell'umore o da una riga dell'elenco. Aperta su un
    giorno, segue la data: se quel giorno è già scritto lo riapre invece di
    aggiungere un doppione. Aperta dal pulsante, parte sempre da una voce
    nuova — di voci, in una giornata, se ne possono scrivere più d'una.
    """

    salvato = Signal()

    def __init__(self, db, colori: dict, voce=None, giorno: str = "", parent=None):
        super().__init__(parent)
        self.db = db
        self.c = colori
        self.voce_id: int | None = None
        self.etichette: dict[str, Etichetta] = {}
        self._segue_data = voce is None and bool(giorno)
        self.setWindowTitle("Voce del diario")
        self.setMinimumSize(560, 520)
        self.resize(680, 720)

        esterno = QVBoxLayout(self)
        esterno.setContentsMargins(20, 18, 20, 16)
        esterno.setSpacing(14)
        esterno.addLayout(self._testata(voce, giorno))

        area, lay = self._corpo()
        lay.addWidget(self._scheda_voti())
        lay.addWidget(self._scheda_emozioni())
        lay.addWidget(self._scheda_testo(), 1)
        esterno.addWidget(area, 1)
        esterno.addLayout(self._piede())

        QShortcut(QKeySequence("Ctrl+S"), self, self.salva)
        if voce is not None:
            self.carica(voce)
        elif giorno:
            self._carica_giorno()
        else:
            self._azzera()

    # ------------------------------------------------------------- struttura
    def _testata(self, voce, giorno: str) -> QHBoxLayout:
        titolo = QLabel("Com'è andata")
        titolo.setObjectName("Sezione")
        sotto = QLabel("Come stai, cosa senti, com'è andata.")
        sotto.setWordWrap(True)      # col testo grande, su una riga non ci sta
        sotto.setObjectName("NotaScheda")
        testi = QVBoxLayout()
        testi.setContentsMargins(0, 0, 0, 0); testi.setSpacing(2)
        testi.addWidget(titolo); testi.addWidget(sotto)

        iniziale = (voce["data"] if voce is not None else giorno)
        self.data = _data(iniziale)
        self.data.setFixedWidth(136)
        self.data.setMaximumDate(QDate.currentDate())
        self.data.dateChanged.connect(lambda _: self._data_cambiata())
        indietro = QPushButton("‹")
        indietro.setToolTip("Giorno precedente")
        avanti = QPushButton("›")
        avanti.setToolTip("Giorno successivo")
        for freccia, passo in ((indietro, -1), (avanti, 1)):
            freccia.setObjectName("FrecciaGiorno")
            freccia.setFixedWidth(32)
            freccia.clicked.connect(
                lambda _=False, d=passo: self.data.setDate(self.data.date().addDays(d)))
        self.b_oggi = QPushButton("Oggi")
        self.b_oggi.clicked.connect(lambda: self.data.setDate(QDate.currentDate()))
        self.ora = QTimeEdit(QTime.fromString(voce["ora"], "HH:mm")
                             if voce is not None and voce["ora"] else QTime.currentTime())
        self.ora.setDisplayFormat("HH:mm")
        self.ora.setFixedWidth(78)
        self.ora.setToolTip("L'ora della voce")
        for campo in (self.data, indietro, avanti, self.b_oggi, self.ora):
            campo.setMinimumHeight(36)

        fila = QHBoxLayout()
        fila.setSpacing(8)
        fila.addLayout(testi, 1)
        fila.addWidget(indietro)
        fila.addWidget(self.data)
        fila.addWidget(avanti)
        fila.addWidget(self.b_oggi)
        fila.addSpacing(4)
        fila.addWidget(self.ora)
        return fila

    def _corpo(self) -> tuple[QScrollArea, QVBoxLayout]:
        """Le schede scorrono: la finestra resta usabile anche se rimpicciolita."""
        interno = QWidget()
        interno.setObjectName("ContenutoSezione")
        lay = QVBoxLayout(interno)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        area = QScrollArea()
        area.setObjectName("ContenutoSezione")
        area.viewport().setObjectName("ContenutoSezione")
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.NoFrame)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        area.setWidget(interno)
        return area, lay

    def _scheda_voti(self) -> QFrame:
        scheda, lay = _scheda_modulo("Come stai", "da 1 a 10, a sensazione")
        self.cursori: dict[str, CursoreVoto] = {}
        griglia = QGridLayout()
        griglia.setHorizontalSpacing(26)
        griglia.setVerticalSpacing(14)
        for i, (chiave, nome, colore, con_faccia) in enumerate((
                ("umore", "Umore", self.c["accento"], True),
                ("energia", "Energia", "#35c4d7", False),
                ("stress", "Stress", "#f7913a", False),
                ("lucidita", "Lucidità", "#b07cff", False))):
            cursore = CursoreVoto(nome, self.c, colore, con_faccia)
            self.cursori[chiave] = cursore
            griglia.addWidget(cursore, i // 2, i % 2)
        griglia.setColumnStretch(0, 1)
        griglia.setColumnStretch(1, 1)
        lay.addLayout(griglia)
        return scheda

    def _scheda_emozioni(self) -> QFrame:
        scheda, lay = _scheda_modulo("Che emozioni senti",
                                     "tocca quelle che riconosci")
        self.b_nuova = QPushButton("+")
        self.b_nuova.setObjectName("AggiungiAccanto")
        self.b_nuova.setFixedSize(30, 26)
        self.b_nuova.setToolTip("Aggiungi un'emozione al tuo elenco")
        self.b_nuova.clicked.connect(self._nuova_emozione)
        scheda.intestazione.addWidget(self.b_nuova)

        riquadro = QWidget()
        riquadro.setObjectName("ContenutoSezione")
        self.fluida = DisposizioneFluida(riquadro, 0, 7)
        scorri = QScrollArea()
        scorri.setObjectName("ContenutoSezione")
        scorri.viewport().setObjectName("ContenutoSezione")
        scorri.setWidgetResizable(True)
        scorri.setFrameShape(QScrollArea.NoFrame)
        scorri.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scorri.setWidget(riquadro)
        scorri.setMinimumHeight(74)
        scorri.setMaximumHeight(146)
        lay.addWidget(scorri)
        self.ricostruisci_etichette()
        return scheda

    def _scheda_testo(self) -> QFrame:
        scheda, lay = _scheda_modulo("Diario", "facoltativo, anche due righe")
        self.testo = QPlainTextEdit()
        self.testo.setObjectName("CampoDiario")
        self.testo.setPlaceholderText(
            "Com'è andata? Cosa ti ha mosso l'umore, in bene o in male…")
        self.testo.setMinimumHeight(120)
        lay.addWidget(self.testo, 1)
        return scheda

    def _piede(self) -> QHBoxLayout:
        self.et_nota = QLabel("")
        self.et_nota.setObjectName("NotaScheda")
        self.et_nota.setWordWrap(True)
        b_annulla = QPushButton("Annulla")
        b_annulla.clicked.connect(self.reject)
        self.b_salva = QPushButton("Salva voce")
        self.b_salva.setObjectName("Primario")
        self.b_salva.setToolTip("Ctrl+S")
        self.b_salva.clicked.connect(self.salva)
        for pulsante in (b_annulla, self.b_salva):
            pulsante.setMinimumHeight(36)
        piede = QHBoxLayout()
        piede.setSpacing(10)
        piede.addWidget(self.et_nota, 1)
        piede.addWidget(b_annulla)
        piede.addWidget(self.b_salva)
        return piede

    # -------------------------------------------------------------- emozioni
    def ricostruisci_etichette(self) -> None:
        scelte = self.scelte()
        while self.fluida.count():
            elemento = self.fluida.takeAt(0)
            w = elemento.widget()
            if w is not None:
                w.hide(); w.setParent(None); w.deleteLater()
        self.etichette.clear()
        for r in self.db.catalogo_emozioni():
            chip = Etichetta(r["nome"], r["colore"], self.c)
            chip.setChecked(r["nome"] in scelte)
            chip.setContextMenuPolicy(Qt.CustomContextMenu)
            chip.customContextMenuRequested.connect(
                lambda punto, nome=r["nome"], w=chip: self._menu_emozione(nome, w, punto))
            self.fluida.addWidget(chip)
            self.etichette[r["nome"]] = chip

    def _menu_emozione(self, nome: str, chip, punto) -> None:
        menu = QMenu(self)
        menu.addAction(f"Togli «{nome}» dall'elenco",
                       lambda: self._elimina_emozione(nome))
        menu.exec(chip.mapToGlobal(punto))

    def _elimina_emozione(self, nome: str) -> None:
        r = self.db.uno("SELECT id FROM emozioni WHERE nome=?", (nome,))
        if r:
            self.db.elimina("emozioni", r["id"])
            self.ricostruisci_etichette()

    def _nuova_emozione(self) -> None:
        dialogo = DialogoEmozione(parent=self)
        if not dialogo.exec():
            return
        d = dialogo.dati()
        if not d["nome"]:
            return
        self.db.esegui(
            "INSERT OR IGNORE INTO emozioni(nome, colore, tipo) VALUES(?,?,?)",
            (d["nome"], d["colore"], d["tipo"]))
        self.ricostruisci_etichette()
        if d["nome"] in self.etichette:
            self.etichette[d["nome"]].setChecked(True)

    def scelte(self) -> list[str]:
        return [nome for nome, chip in self.etichette.items() if chip.isChecked()]

    # ------------------------------------------------------------------ dati
    def giorno(self) -> str:
        return self.data.date().toString("yyyy-MM-dd")

    def _data_cambiata(self) -> None:
        if self._segue_data:
            self._carica_giorno()
        self.b_oggi.setEnabled(self.giorno() != date.today().isoformat())

    def _carica_giorno(self) -> None:
        """Riapre la voce già scritta in quel giorno, se c'è."""
        voci = self.db.voci(self.giorno(), self.giorno())
        if voci:
            self.carica(voci[0])
        else:
            self._azzera()

    def _azzera(self) -> None:
        """Svuota i campi lasciando stare la data: lì si decide il giorno."""
        self.voce_id = None
        for cursore in self.cursori.values():
            cursore.imposta(5.0)
        for chip in self.etichette.values():
            chip.setChecked(False)
        self.testo.clear()
        self.et_nota.setText(
            "Nuova voce di oggi." if self.giorno() == date.today().isoformat()
            else f"Nuova voce del {data_it(self.giorno())}.")
        self.b_salva.setText("Salva voce")
        self.b_oggi.setEnabled(self.giorno() != date.today().isoformat())

    def carica(self, voce) -> None:
        self.voce_id = voce["id"]
        a, m, g = (int(x) for x in voce["data"].split("-"))
        self.data.blockSignals(True)
        self.data.setDate(QDate(a, m, g))
        self.data.blockSignals(False)
        if voce["ora"]:
            self.ora.setTime(QTime.fromString(voce["ora"], "HH:mm"))
        for chiave, cursore in self.cursori.items():
            cursore.imposta(float(voce[chiave]))
        scelte = {x.strip() for x in voce["emozioni"].split(",") if x.strip()}
        for nome, chip in self.etichette.items():
            chip.setChecked(nome in scelte)
        self.testo.setPlainText(voce["testo"])
        self.et_nota.setText(f"Stai modificando la voce del {data_it(voce['data'])}"
                             + (f" alle {voce['ora']}." if voce["ora"] else "."))
        self.b_salva.setText("Salva modifiche")
        self.b_oggi.setEnabled(self.giorno() != date.today().isoformat())

    def salva(self) -> None:
        self.voce_id = self.db.salva_voce({
            "id": self.voce_id,
            "data": self.giorno(),
            "ora": self.ora.time().toString("HH:mm"),
            "umore": self.cursori["umore"].valore(),
            "energia": self.cursori["energia"].valore(),
            "stress": self.cursori["stress"].valore(),
            "lucidita": self.cursori["lucidita"].valore(),
            "emozioni": ", ".join(self.scelte()),
            "testo": self.testo.toPlainText().strip(),
        })
        self.salvato.emit()
        self.accept()


class DialogoEmozione(DialogoBase):
    """Aggiunge una voce al catalogo delle emozioni."""

    def __init__(self, nome: str = "", parent=None):
        super().__init__("Nuova emozione", parent, 380)
        self.nome = self.campo("Nome", QLineEdit(nome))
        self.nome.setPlaceholderText("es. nostalgico")
        self.tipo = self.campo("Tipo", QComboBox())
        self.tipo.addItems(["positiva", "neutra", "negativa"])
        self.colore = self.campo("Colore", SceltaColore("#6c8cff"))

    def dati(self) -> dict:
        return {"nome": self.nome.text().strip().lower(),
                "tipo": self.tipo.currentText(), "colore": self.colore.colore}


# ------------------------------------------------------------- importazione
class DialogoImporta(QDialog):
    """Porta dentro Dashboard un'esportazione di Samsung Health.

    Si trascina la cartella (o lo zip) dentro al riquadro, oppure la si sceglie
    a mano. Se Dashboard ne trova già una sul PC la propone, ma l'ultima parola è
    sempre di chi importa.
    """

    def __init__(self, db, percorso: str = "", colori: dict | None = None, parent=None):
        super().__init__(parent)
        self.db = db
        self.c = colori or {"accento": "#2ec27e", "bordo": "#2c313f",
                            "pannello2": "#222634", "testo": "#e7e9ee",
                            "testo2": "#9aa1b1"}
        self.percorso = ""
        self.importati = 0
        self.setWindowTitle("Importa dati di salute")
        self.setMinimumWidth(580)
        self.setAcceptDrops(True)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 14)
        lay.setSpacing(12)

        spiegazione = QLabel(
            "Sul telefono: <b>Samsung Health → Impostazioni → Scarica dati "
            "personali</b>. Ne esce una cartella (o uno zip) di file "
            "<code>.csv</code>: portala sul PC e buttala qui sotto.")
        spiegazione.setWordWrap(True)
        spiegazione.setTextFormat(Qt.RichText)
        lay.addWidget(spiegazione)

        self.zona = ZonaRilascio(self.c)
        self.zona.scelto.connect(self._imposta_percorso)
        self.zona.chiesto_sfoglia.connect(self._menu_scelta)
        lay.addWidget(self.zona)

        b_cartella = QPushButton("Scegli una cartella…")
        b_cartella.clicked.connect(self._scegli_cartella)
        b_zip = QPushButton("Scegli uno zip…")
        b_zip.clicked.connect(self._scegli_zip)
        fila = QHBoxLayout()
        fila.setSpacing(8)
        fila.addWidget(b_cartella)
        fila.addWidget(b_zip)
        fila.addStretch(1)

        # quelle già sul PC: una comodità, non un obbligo
        from .importa import esportazioni_trovate
        self.candidati = esportazioni_trovate()
        self.trovate = QComboBox()
        if self.candidati:
            import os
            from datetime import date as _date

            from .utils import data_it
            self.trovate.blockSignals(True)
            self.trovate.addItem("— già sul PC —", "")
            for trovato, quando in self.candidati:
                giorno = _date.fromtimestamp(quando).isoformat()
                self.trovate.addItem(
                    f"{os.path.basename(trovato)}  ({data_it(giorno)})", trovato)
            self.trovate.blockSignals(False)
            self.trovate.currentIndexChanged.connect(self._scelta_trovata)
            self.trovate.setMaximumWidth(300)
            fila.addWidget(self.trovate)
        else:
            self.trovate.hide()
        lay.addLayout(fila)

        self.sovrascrivi = QCheckBox(
            "Sovrascrivi i dati già presenti (altrimenti riempie solo i campi vuoti)")
        self.allenamenti = QCheckBox("Importa anche gli allenamenti")
        self.allenamenti.setChecked(True)
        lay.addWidget(self.sovrascrivi)
        lay.addWidget(self.allenamenti)

        self.esito = QLabel("")
        self.esito.setWordWrap(True)
        self.esito.setObjectName("NotaScheda")
        lay.addWidget(self.esito)

        bottoni = QDialogButtonBox()
        self.b_importa = bottoni.addButton("Importa", QDialogButtonBox.AcceptRole)
        self.b_importa.setObjectName("Primario")
        self.b_importa.setEnabled(False)
        bottoni.addButton("Chiudi", QDialogButtonBox.RejectRole)
        bottoni.accepted.connect(self._importa)
        bottoni.rejected.connect(self.reject)
        lay.addWidget(bottoni)

        if percorso:
            self._imposta_percorso(percorso)

    # ------------------------------------------------------- scelta del file
    def _menu_scelta(self) -> None:
        menu = QMenu(self)
        menu.addAction("Scegli una cartella…", self._scegli_cartella)
        menu.addAction("Scegli uno zip…", self._scegli_zip)
        menu.exec(self.zona.mapToGlobal(self.zona.rect().center()))

    def _scelta_trovata(self, indice: int) -> None:
        trovato = self.trovate.itemData(indice)
        if trovato:
            self._imposta_percorso(trovato)

    def _scegli_cartella(self) -> None:
        import os
        scelto = QFileDialog.getExistingDirectory(
            self, "Cartella esportata da Samsung Health", self._cartella_iniziale())
        if scelto:
            self._imposta_percorso(scelto)

    def _scegli_zip(self) -> None:
        scelto, _ = QFileDialog.getOpenFileName(
            self, "Zip esportato da Samsung Health", self._cartella_iniziale(),
            "Archivi (*.zip);;Tutti i file (*)")
        if scelto:
            self._imposta_percorso(scelto)

    def _cartella_iniziale(self) -> str:
        import os
        ultima = self.db.leggi("ultima_importazione", "")
        if ultima and os.path.exists(os.path.dirname(ultima)):
            return os.path.dirname(ultima)
        scaricati = os.path.expanduser("~/Scaricati")
        return scaricati if os.path.isdir(scaricati) else os.path.expanduser("~")

    def _imposta_percorso(self, scelto: str) -> None:
        import os

        from .importa import sembra_esportazione
        scelto = scelto.rstrip("/")
        if not os.path.exists(scelto):
            self.esito.setText(f"Non trovo {scelto}")
            return
        if not sembra_esportazione(scelto):
            self.zona.azzera()
            self.b_importa.setEnabled(False)
            self.percorso = ""
            self.esito.setText(
                "Qui dentro non vedo file di Samsung Health. Serve la cartella "
                "(o lo zip) dell'esportazione, quella con i file che cominciano "
                "per «com.samsung».")
            return
        self.percorso = scelto
        self.b_importa.setEnabled(True)
        quanto = "zip" if os.path.isfile(scelto) else "cartella"
        self.zona.mostra_scelta(scelto, f"{quanto} · pronta da importare")
        gia = self.db.leggi("ultima_importazione", "")
        self.esito.setText(
            "Questa l'hai già importata: rifarlo non crea doppioni."
            if gia == scelto else "")

    # ------------------------------------------------- trascinamento sul bordo
    def dragEnterEvent(self, evento):
        if evento.mimeData().hasUrls():
            evento.acceptProposedAction()

    def dropEvent(self, evento):
        for url in evento.mimeData().urls():
            if url.isLocalFile():
                self._imposta_percorso(url.toLocalFile())
                evento.acceptProposedAction()
                return

    # ---------------------------------------------------------- importazione
    def _importa(self) -> None:
        import os

        from .importa import importa_samsung_health
        if not self.percorso:
            return
        self.b_importa.setEnabled(False)
        self.esito.setText("Lettura in corso…")
        self.repaint()
        try:
            risultato = importa_samsung_health(
                self.db, self.percorso, self.sovrascrivi.isChecked(),
                self.allenamenti.isChecked())
        except Exception as errore:
            self.esito.setText(f"Non sono riuscito a leggere: {errore}")
            self.b_importa.setEnabled(True)
            return
        self.importati = risultato.giorni_salute + risultato.allenamenti
        self.esito.setText(str(risultato).replace("\n", " · "))
        self.b_importa.setEnabled(True)
        self.zona.mostra_scelta(
            self.percorso,
            f"importata · {risultato.giorni_salute} giorni, "
            f"{risultato.allenamenti} allenamenti"
            if risultato.file_letti else "nessun file riconosciuto")
        if risultato.file_letti:
            self.db.imposta("ultima_importazione", self.percorso)
            try:
                self.db.imposta("ultima_importazione_quando",
                                os.path.getmtime(self.percorso))
            except OSError:
                pass
