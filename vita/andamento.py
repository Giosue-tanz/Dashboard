"""Finestra «Andamento»: i dati passati, scorrendo avanti e indietro nel tempo.

Funziona come la scheda di dettaglio di Samsung Health: in alto si sceglie il
dato (passi, battito, sonno, peso…), poi l'ampiezza — settimana, mese,
trimestre, anno — e con le frecce si scorre indietro nel tempo un periodo alla
volta. Sotto il grafico c'è l'elenco dei giorni: doppio clic e si corregge il
dato nella finestra d'inserimento.
"""
from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QHeaderView, QLabel,
                               QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from .componenti import (DisposizioneFluida, abilita_deselezione,
                         etichetta, stile_tabella)
from .grafici import GraficoBarre
from .utils import data_it, durata, media, numero

MESI = ("gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
        "agosto", "settembre", "ottobre", "novembre", "dicembre")
MESI_BREVI = ("gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set",
              "ott", "nov", "dic")

# campo -> (nome, nome sulla pastiglia, tinta, unità, decimali, riassunto)
MISURE: dict[str, tuple[str, str, str, str, int, str]] = {
    "passi": ("Passi", "Passi", "", "passi", 0, "somma"),
    "battito": ("Battito a riposo", "Battito", "#ff5a5a", "bpm", 0, "media"),
    "sonno": ("Sonno", "Sonno", "#3d7bfd", "", 0, "media"),
    "peso": ("Peso", "Peso", "#2bc4e0", "kg", 1, "media"),
    "grasso": ("Massa grassa", "Grassa", "#ff9f45", "%", 1, "media"),
    "muscolo": ("Massa muscolare", "Muscolo", "#a46bff", "%", 1, "media"),
    "kcal": ("Calorie attive", "Calorie", "#ff9f45", "kcal", 0, "somma"),
    "km": ("Distanza", "Distanza", "#16c47f", "km", 1, "somma"),
    "hrv": ("Variabilità (HRV)", "HRV", "#2bc4e0", "ms", 0, "media"),
    "acqua": ("Acqua", "Acqua", "#3d7bfd", "L", 1, "somma"),
}

AMPIEZZE = {"settimana": "Settimana", "mese": "Mese", "trimestre": "3 mesi",
            "anno": "Anno"}


def _mesi_indietro(riferimento: date, mesi: int) -> date:
    """Primo giorno del mese spostato indietro di `mesi`."""
    totale = riferimento.year * 12 + (riferimento.month - 1) - mesi
    return date(totale // 12, totale % 12 + 1, 1)


def _fine_mese(giorno: date) -> date:
    return _mesi_indietro(giorno, -1) - timedelta(days=1)


class FinestraAndamento(QDialog):
    """Un dato alla volta, un periodo alla volta, avanti e indietro nel tempo."""

    giorno_scelto = Signal(str)

    def __init__(self, db, colori: dict, campo: str = "passi", parent=None):
        super().__init__(parent)
        self.db = db
        self.c = colori
        self.campo = campo if campo in MISURE else "passi"
        self.ampiezza = db.leggi("andamento_ampiezza", "mese")
        if self.ampiezza not in AMPIEZZE:
            self.ampiezza = "mese"
        self.indietro = 0            # quanti periodi fa
        self.setWindowTitle("Andamento")
        self.setMinimumSize(880, 620)

        esterno = QVBoxLayout(self)
        esterno.setContentsMargins(20, 18, 20, 16)
        esterno.setSpacing(14)
        esterno.addLayout(self._testata())
        esterno.addWidget(self._scelta_misure())
        esterno.addWidget(self._riquadro_grafico(), 3)
        esterno.addWidget(self._riquadro_elenco(), 2)

        QShortcut(QKeySequence(Qt.Key_Left), self, lambda: self._sposta(1))
        QShortcut(QKeySequence(Qt.Key_Right), self, lambda: self._sposta(-1))
        self.aggiorna()

    # ------------------------------------------------------------ struttura
    def _testata(self) -> QHBoxLayout:
        self.et_titolo = QLabel("")
        self.et_titolo.setObjectName("Sezione")
        self.et_periodo = QLabel("")
        self.et_periodo.setObjectName("NotaScheda")
        testi = QVBoxLayout()
        testi.setContentsMargins(0, 0, 0, 0); testi.setSpacing(2)
        testi.addWidget(self.et_titolo); testi.addWidget(self.et_periodo)

        self.segmenti: dict[str, QPushButton] = {}
        fila_amp = QHBoxLayout()
        fila_amp.setSpacing(6)
        for chiave, nome in AMPIEZZE.items():
            b = QPushButton(nome)
            b.setObjectName("Segmento")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=chiave: self._cambia_ampiezza(k))
            self.segmenti[chiave] = b
            fila_amp.addWidget(b)

        self.b_indietro = QPushButton("‹")
        self.b_indietro.setToolTip("Periodo precedente  (←)")
        self.b_avanti = QPushButton("›")
        self.b_avanti.setToolTip("Periodo successivo  (→)")
        for b, passo in ((self.b_indietro, 1), (self.b_avanti, -1)):
            b.setObjectName("FrecciaGiorno")
            b.setFixedWidth(36)
            b.setMinimumHeight(36)
            b.clicked.connect(lambda _=False, p=passo: self._sposta(p))
        self.b_oggi = QPushButton("Oggi")
        self.b_oggi.setMinimumHeight(36)
        self.b_oggi.clicked.connect(lambda: self._vai_a(0))

        fila = QHBoxLayout()
        fila.setSpacing(8)
        fila.addLayout(testi, 1)
        fila.addLayout(fila_amp)
        fila.addSpacing(6)
        fila.addWidget(self.b_indietro)
        fila.addWidget(self.b_avanti)
        fila.addWidget(self.b_oggi)
        return fila

    def _scelta_misure(self) -> QWidget:
        riquadro = QWidget()
        lay = DisposizioneFluida(riquadro, 0, 6)
        self.pastiglie: dict[str, QPushButton] = {}
        for campo, (_, breve, _, _, _, _) in MISURE.items():
            b = QPushButton(breve)
            b.setObjectName("Segmento")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=campo: self._cambia_campo(k))
            self.pastiglie[campo] = b
            lay.addWidget(b)
        return riquadro

    def _riquadro_grafico(self) -> QWidget:
        from PySide6.QtWidgets import QFrame
        scheda = QFrame()
        scheda.setObjectName("SchedaModulo")
        lay = QVBoxLayout(scheda)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)
        self.et_grande = QLabel("—")
        self.et_grande.setObjectName("ValoreScheda")
        self.et_riassunto = etichetta("", "NotaScheda")
        self.et_riassunto.setWordWrap(True)
        lay.addWidget(self.et_grande)
        lay.addWidget(self.et_riassunto)
        self.grafico = GraficoBarre(self.c)
        self.grafico.setMinimumHeight(170)
        lay.addWidget(self.grafico, 1)
        return scheda

    def _riquadro_elenco(self) -> QWidget:
        from PySide6.QtWidgets import QFrame
        scheda = QFrame()
        scheda.setObjectName("SchedaModulo")
        lay = QVBoxLayout(scheda)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)
        intestazione = QLabel("GIORNO PER GIORNO")
        intestazione.setObjectName("EtichettaScheda")
        lay.addWidget(intestazione)
        self.tab = QTableWidget(0, 3)
        self.tab.setHorizontalHeaderLabels(["Giorno", "Valore", "Rispetto alla media"])
        self.tab.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tab.setSelectionBehavior(QTableWidget.SelectRows)
        self.tab.doubleClicked.connect(self._apri_giorno)
        h = self.tab.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        h.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        abilita_deselezione(self.tab)
        stile_tabella(self.tab)
        self.tab.setToolTip("Doppio clic su un giorno per scriverne i dati.")
        lay.addWidget(self.tab, 1)
        return scheda

    # -------------------------------------------------------------- comandi
    def _cambia_campo(self, campo: str) -> None:
        self.campo = campo
        self.aggiorna()

    def _cambia_ampiezza(self, chiave: str) -> None:
        self.ampiezza = chiave
        self.indietro = 0
        self.db.imposta("andamento_ampiezza", chiave)
        self.aggiorna()

    def _sposta(self, passi: int) -> None:
        self._vai_a(max(0, self.indietro + passi))

    def _vai_a(self, indietro: int) -> None:
        self.indietro = max(0, indietro)
        self.aggiorna()

    def _apri_giorno(self) -> None:
        righe = self.tab.selectionModel().selectedRows()
        if not righe:
            return
        giorno = self.tab.item(righe[0].row(), 0).data(Qt.UserRole)
        if giorno:
            self.giorno_scelto.emit(giorno)

    # ------------------------------------------------------------- periodo
    def _intervallo(self) -> tuple[date, date, str]:
        """(dal, al, come si chiama) del periodo visibile."""
        oggi = date.today()
        if self.ampiezza == "settimana":
            lunedi = oggi - timedelta(days=oggi.weekday() + 7 * self.indietro)
            domenica = lunedi + timedelta(days=6)
            if lunedi.month == domenica.month:
                nome = (f"{lunedi.day}–{domenica.day} {MESI_BREVI[lunedi.month - 1]} "
                        f"{domenica.year}")
            else:
                nome = (f"{lunedi.day} {MESI_BREVI[lunedi.month - 1]} – "
                        f"{domenica.day} {MESI_BREVI[domenica.month - 1]} {domenica.year}")
            return lunedi, domenica, nome
        if self.ampiezza == "mese":
            primo = _mesi_indietro(oggi, self.indietro)
            return primo, _fine_mese(primo), f"{MESI[primo.month - 1]} {primo.year}"
        if self.ampiezza == "trimestre":
            ultimo = _mesi_indietro(oggi, 3 * self.indietro)
            primo = _mesi_indietro(ultimo, 2)
            return (primo, _fine_mese(ultimo),
                    f"{MESI_BREVI[primo.month - 1]}–{MESI_BREVI[ultimo.month - 1]} "
                    f"{ultimo.year}")
        anno = oggi.year - self.indietro
        return date(anno, 1, 1), date(anno, 12, 31), str(anno)

    def _gruppi(self, dal: date, al: date):
        """Le colonne del grafico: giorni, settimane o mesi secondo l'ampiezza."""
        if self.ampiezza in ("settimana", "mese"):
            giorno = dal
            while giorno <= al:
                yield giorno.strftime("%d"), [giorno.isoformat()]
                giorno += timedelta(days=1)
        elif self.ampiezza == "trimestre":
            inizio = dal - timedelta(days=dal.weekday())
            while inizio <= al:
                giorni = [(inizio + timedelta(days=i)).isoformat() for i in range(7)]
                yield f"{inizio.day}/{inizio.month}", [g for g in giorni
                                                       if dal.isoformat() <= g <= al.isoformat()]
                inizio += timedelta(days=7)
        else:
            for mese in range(1, 13):
                primo = date(dal.year, mese, 1)
                giorni = []
                giorno = primo
                while giorno.month == mese:
                    giorni.append(giorno.isoformat())
                    giorno += timedelta(days=1)
                yield MESI_BREVI[mese - 1], giorni

    # ----------------------------------------------------------------- dati
    def _testo(self, valore: float) -> str:
        _, _, _, unita, decimali, _ = MISURE[self.campo]
        if self.campo == "sonno":
            return durata(int(valore))
        return f"{numero(valore, decimali)} {unita}".strip()

    def aggiorna(self) -> None:
        nome, _, tinta, unita, decimali, modo = MISURE[self.campo]
        colore = tinta or self.c["accento"]
        for campo, b in self.pastiglie.items():
            b.setChecked(campo == self.campo)
        for chiave, b in self.segmenti.items():
            b.setChecked(chiave == self.ampiezza)

        dal, al, nome_periodo = self._intervallo()
        self.et_titolo.setText(nome)
        self.et_periodo.setText(nome_periodo)
        self.b_avanti.setEnabled(self.indietro > 0)
        self.b_oggi.setEnabled(self.indietro > 0)

        valori = dict(self.db.serie_salute(self.campo, dal.isoformat(), al.isoformat()))

        # ------------------------------------------------------- il grafico
        dati, etichette_vuote = [], 0
        for etic, giorni in self._gruppi(dal, al):
            presenti = [valori[g] for g in giorni if g in valori]
            if not presenti:
                valore = None
            elif modo == "somma" and len(giorni) > 1:
                valore = sum(presenti)
            else:
                valore = media(presenti)
            # con tanti giorni le etichette si diradano, se no si accavallano
            mostra = etic if (len(giorni) > 1 or etichette_vuote % 3 == 0) else ""
            etichette_vuote += 1
            dati.append((mostra, [valore]))
        self.grafico.formato = (
            (lambda v: durata(int(v)) if v else "0")
            if self.campo == "sonno" else (lambda v: numero(v, decimali)))
        self.grafico.evidenzia_ultima = self.indietro == 0
        self.grafico.riferimento = self._obiettivo()
        self.grafico.imposta_dati(dati, [(nome.lower(), colore)])

        # ------------------------------------------------------ il riassunto
        serie = list(valori.values())
        if not serie:
            self.et_grande.setText("—")
            self.et_riassunto.setText(
                f"Nessun dato di {nome.lower()} in questo periodo. "
                "Le frecce ‹ › scorrono i periodi precedenti.")
        else:
            principale = sum(serie) if modo == "somma" else media(serie)
            self.et_grande.setText(self._testo(principale))
            giorni_totali = (al - dal).days + 1
            pezzi = [("totale" if modo == "somma" else "media") + " del periodo",
                     f"min {self._testo(min(serie))}",
                     f"max {self._testo(max(serie))}",
                     f"{len(serie)} giorni su {giorni_totali} con dati"]
            if modo == "somma":
                pezzi.insert(1, f"media {self._testo(media(serie))} al giorno")
            self.et_riassunto.setText("  ·  ".join(pezzi))

        # --------------------------------------------------------- l'elenco
        riferimento = media(serie) if serie else 0.0
        giorni_ordinati = sorted(valori.items(), reverse=True)
        self.tab.setRowCount(len(giorni_ordinati))
        for i, (giorno, valore) in enumerate(giorni_ordinati):
            cella = QTableWidgetItem(data_it(giorno))
            cella.setData(Qt.UserRole, giorno)
            self.tab.setItem(i, 0, cella)
            v = QTableWidgetItem(self._testo(valore))
            v.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.tab.setItem(i, 1, v)
            scostamento = valore - riferimento
            segno = "+" if scostamento >= 0 else "−"
            testo = ("in media" if abs(scostamento) < (riferimento * 0.02 + 0.01)
                     else f"{segno}{self._testo(abs(scostamento))}")
            s = QTableWidgetItem(testo)
            s.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.tab.setItem(i, 2, s)

    def _obiettivo(self) -> float | None:
        """La linea tratteggiata, dove un obiettivo esiste davvero."""
        from .punteggi import PREDEFINITI
        if self.campo in ("passi", "sonno", "acqua"):
            chiave = f"obiettivo_{self.campo}"
            valore = self.db.leggi_num(chiave, PREDEFINITI[chiave])
            # su somme di più giorni la riga del giorno non significa niente
            return valore if self.ampiezza in ("settimana", "mese") else None
        return None
