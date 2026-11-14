"""Impostazioni: aspetto, obiettivi, sorgente della finanza, archivio."""
from __future__ import annotations

import csv
import os
import shutil
from datetime import date, datetime

from PySide6.QtCore import QObject, Qt, QTime, Signal
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDoubleSpinBox,
                               QFileDialog, QFormLayout, QHBoxLayout, QHeaderView,
                               QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
                               QPushButton, QScrollArea, QSpinBox, QTabWidget,
                               QTableWidget, QTableWidgetItem, QTimeEdit,
                               QVBoxLayout, QWidget)

from ..componenti import (CampoData, CampoDurata, DisposizioneFluida,
                          EtichettaACapo, Interruttore, Scheda, etichetta,
                          riga, separatore, stile_tabella)
from ..db import DATA_DIR
from .. import blocco, salvataggio
from ..fonti import (PERCORSO_FINANCE, finance_presente,
                     porta_dentro_finance)
from ..icone_categorie import (ICONA_PREDEFINITA, SelettoreIcona,
                               etichetta_categoria, solo_nome)
from ..punteggi import PREDEFINITI
from ..tema import SCALE
from ..utils import durata, euro, numero
from . import VistaBase


class VistaImpostazioni(VistaBase):
    titolo = "Impostazioni"
    sottotitolo = "Aspetto, obiettivi, archivio"
    nome_nuovo = ""

    tema_cambiato = Signal(str)
    aspetto_cambiato = Signal()
    fonte_cambiata = Signal()

    def costruisci(self) -> None:
        esterno = QVBoxLayout(self)
        esterno.setContentsMargins(0, 0, 0, 0)
        self.schede = QTabWidget()
        esterno.addWidget(self.schede)
        self.schede.addTab(self._scorrevole(self._aspetto()), "Aspetto")
        self.schede.addTab(self._scorrevole(self._obiettivi()), "Obiettivi")
        self.schede.addTab(self._scorrevole(self._finanza()), "Finanza")
        self.schede.addTab(self._scorrevole(self._tess()), "Tess")
        self.schede.addTab(self._scorrevole(self._sicurezza()), "Sicurezza")
        self.schede.addTab(self._scorrevole(self._dati()), "Dati e backup")

    @staticmethod
    def _scorrevole(pagina: QWidget) -> QScrollArea:
        """Una scheda lunga scorre, invece di schiacciare le tabelle."""
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.NoFrame)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        area.setWidget(pagina)
        return area

    # ------------------------------------------------------------- aspetto
    def _aspetto(self) -> QWidget:
        pagina = QWidget()
        lay = QVBoxLayout(pagina)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(18)

        scheda = Scheda("Tema")
        self.gruppo_tema = QButtonGroup(self)
        fila = QHBoxLayout()
        fila.setSpacing(10)
        tema_attuale = self.db.leggi("tema", "scuro")
        for chiave, icona, nome in (("scuro", "🌙", "Scuro"), ("chiaro", "☀️", "Chiaro")):
            b = QPushButton(f"{icona}  {nome}")
            b.setObjectName("Segmento")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setMinimumHeight(42)
            b.setMinimumWidth(140)
            b.setChecked(tema_attuale == chiave)
            b.clicked.connect(lambda _=False, k=chiave: self._imposta_tema(k))
            self.gruppo_tema.addButton(b)
            fila.addWidget(b)
        fila.addStretch(1)
        scheda.aggiungi_layout(fila)
        nota = EtichettaACapo(
            "Scorciatoia: Ctrl+T cambia tema in qualsiasi momento da ogni schermata.\n"
            "I colori invece non si scelgono: ogni area ha il suo — rosso "
            "Emozioni, blu Carriera, viola Accademica, turchese Salute, "
            "verde Finanza, rosa Tess — e il resto della pagina è fatto per "
            "andarci d'accordo.")
        nota.setObjectName("NotaScheda")
        scheda.aggiungi(nota)
        lay.addWidget(scheda)

        scheda = Scheda("Dimensione del testo")
        fila_scala = QHBoxLayout()
        fila_scala.setSpacing(12)
        self.scala = QComboBox()
        self.scala.addItems(list(SCALE))
        self.scala.setFixedWidth(240)
        self.scala.setMinimumHeight(38)
        self.scala.setCurrentText(self.db.leggi("scala", "normale"))
        self.scala.currentTextChanged.connect(self._imposta_scala)
        fila_scala.addWidget(self.scala)
        fila_scala.addStretch(1)
        scheda.aggiungi_layout(fila_scala)
        spiega = EtichettaACapo(
            "Adatta proporzionalmente tutti i testi, i grafici e i comandi "
            "dell'interfaccia allo schermo (compatta 90%, normale 100%, grande 115%, molto grande 130%).")
        spiega.setObjectName("NotaScheda")
        scheda.aggiungi(spiega)
        lay.addWidget(scheda)

        lay.addStretch(1)
        return pagina

    def _imposta_tema(self, chiave: str) -> None:
        self.db.imposta("tema", chiave)
        self.tema_cambiato.emit(chiave)

    def _imposta_scala(self, nome: str) -> None:
        self.db.imposta("scala", nome)
        self.aspetto_cambiato.emit()

    # ----------------------------------------------------------- obiettivi
    def _obiettivi(self) -> QWidget:
        pagina = QWidget()
        lay = QVBoxLayout(pagina)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(18)

        # 1. Salute e Benessere
        scheda_salute = Scheda("Salute e benessere")
        modulo_salute = QFormLayout()
        modulo_salute.setHorizontalSpacing(24)
        modulo_salute.setVerticalSpacing(12)
        modulo_salute.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.passi = QSpinBox(); self.passi.setRange(0, 100000)
        self.passi.setSingleStep(500); self.passi.setGroupSeparatorShown(True)
        self.passi.setSuffix(" passi")
        self.passi.setFixedWidth(220); self.passi.setMinimumHeight(36)
        self.passi.setValue(int(self.db.leggi_num("obiettivo_passi",
                                                  PREDEFINITI["obiettivo_passi"])))

        self.sonno = CampoDurata()
        self.sonno.imposta(int(self.db.leggi_num("obiettivo_sonno",
                                                 PREDEFINITI["obiettivo_sonno"])))

        self.acqua = QDoubleSpinBox(); self.acqua.setRange(0, 10)
        self.acqua.setSingleStep(0.25); self.acqua.setSuffix(" L")
        self.acqua.setFixedWidth(220); self.acqua.setMinimumHeight(36)
        self.acqua.setValue(self.db.leggi_num("obiettivo_acqua",
                                              PREDEFINITI["obiettivo_acqua"]))

        self.allenamenti = QSpinBox(); self.allenamenti.setRange(0, 14)
        self.allenamenti.setSuffix(" sessioni")
        self.allenamenti.setFixedWidth(220); self.allenamenti.setMinimumHeight(36)
        self.allenamenti.setValue(int(self.db.leggi_num(
            "obiettivo_allenamenti", PREDEFINITI["obiettivo_allenamenti"])))

        # Non è un obiettivo, è una misura — ma è l'unica che non cambia mai,
        # e scriverla ogni giorno nell'inserimento dati sarebbe assurdo. Serve
        # agli indici della composizione: BMI, FMI e FFMI sono tutti e tre un
        # peso diviso l'altezza al quadrato, e senza non si calcolano.
        self.altezza = QSpinBox(); self.altezza.setRange(0, 250)
        self.altezza.setSuffix(" cm")
        self.altezza.setFixedWidth(220); self.altezza.setMinimumHeight(36)
        self.altezza.setValue(int(self.db.leggi_num("altezza", 0)))
        self.altezza.setToolTip(
            "Serve per BMI, FMI e FFMI nel riquadro «Composizione» di Salute.\n"
            "A zero quegli indici non si mostrano.")

        modulo_salute.addRow("Passi al giorno", self.passi)
        modulo_salute.addRow("Sonno a notte", self.sonno)
        modulo_salute.addRow("Acqua al giorno", self.acqua)
        modulo_salute.addRow("Allenamenti a settimana", self.allenamenti)
        modulo_salute.addRow("Altezza", self.altezza)
        scheda_salute.aggiungi_layout(modulo_salute)
        lay.addWidget(scheda_salute)

        # 2. Studio e Università
        scheda_studio = Scheda("Studio e università")
        modulo_studio = QFormLayout()
        modulo_studio.setHorizontalSpacing(24)
        modulo_studio.setVerticalSpacing(12)
        modulo_studio.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.studio = CampoDurata()
        self.studio.imposta(int(self.db.leggi_num("obiettivo_studio",
                                                  PREDEFINITI["obiettivo_studio"])))

        self.cfu = QSpinBox(); self.cfu.setRange(0, 600)
        self.cfu.setSuffix(" CFU")
        self.cfu.setFixedWidth(220); self.cfu.setMinimumHeight(36)
        self.cfu.setValue(int(self.db.leggi_num("cfu_laurea", 180)))

        modulo_studio.addRow("Studio a settimana", self.studio)
        modulo_studio.addRow("CFU della laurea", self.cfu)
        scheda_studio.aggiungi_layout(modulo_studio)
        lay.addWidget(scheda_studio)

        # Barra di salvataggio
        fila_salva = QHBoxLayout()
        fila_salva.setSpacing(12)
        salva = QPushButton("Salva obiettivi")
        salva.setObjectName("Primario")
        salva.setMinimumHeight(38)
        salva.setMinimumWidth(160)
        salva.clicked.connect(self._salva_obiettivi)
        fila_salva.addWidget(salva)
        nota_salva = etichetta(
            "Gli obiettivi entrano negli indicatori in fondo alla barra e nelle "
            "linee tratteggiate dei grafici.", "NotaScheda")
        fila_salva.addWidget(nota_salva, 1)
        lay.addLayout(fila_salva)

        lay.addStretch(1)
        return pagina

    def _salva_obiettivi(self) -> None:
        self.db.imposta("obiettivo_passi", self.passi.value())
        self.db.imposta("obiettivo_sonno", self.sonno.valore())
        self.db.imposta("obiettivo_allenamenti", self.allenamenti.value())
        self.db.imposta("obiettivo_studio", self.studio.valore())
        self.db.imposta("obiettivo_acqua", self.acqua.value())
        self.db.imposta("altezza", self.altezza.value())
        self.db.imposta("cfu_laurea", self.cfu.value())
        self.dati_cambiati.emit()
        QMessageBox.information(self, "Obiettivi", "Obiettivi salvati.")

    # -------------------------------------------------------------- finanza
    def _finanza(self) -> QWidget:
        pagina = QWidget()
        lay = QVBoxLayout(pagina)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(14)

        scheda = Scheda("Da dove arrivano i movimenti")
        self.fonte_scelta = QComboBox()
        self.fonte_scelta.addItem("Automatica (Finance se c'è)", "auto")
        self.fonte_scelta.addItem("Archivio di Finance (sola lettura)", "finance")
        self.fonte_scelta.addItem("Archivio interno", "locale")
        indice = self.fonte_scelta.findData(self.db.leggi("fonte_finanza", "auto"))
        self.fonte_scelta.setCurrentIndex(max(0, indice))
        self.fonte_scelta.currentIndexChanged.connect(self._cambia_fonte)
        scheda.aggiungi(self.fonte_scelta)

        self.percorso_finance = QLineEdit(
            self.db.leggi("percorso_finance", PERCORSO_FINANCE))
        sfoglia = QPushButton("Sfoglia…")
        sfoglia.clicked.connect(self._scegli_archivio_finance)
        scheda.aggiungi_layout(riga(QLabel("Archivio di Finance"),
                                    self.percorso_finance, sfoglia))
        self.stato_finance = etichetta("", "NotaScheda")
        scheda.aggiungi(self.stato_finance)

        self.avvio_finance = QLineEdit(self.db.leggi("avvio_finance", ""))
        self.avvio_finance.setPlaceholderText("…/Finance/avvia.sh")
        sfoglia2 = QPushButton("Sfoglia…")
        sfoglia2.clicked.connect(self._scegli_avvio_finance)
        scheda.aggiungi_layout(riga(QLabel("Avviatore di Finance"),
                                    self.avvio_finance, sfoglia2))
        salva = QPushButton("Salva")
        salva.setObjectName("Primario")
        salva.clicked.connect(self._salva_finanza)
        scheda.aggiungi_layout(riga(None, salva))
        lay.addWidget(scheda)

        scheda = Scheda("Porta dentro Finance")
        nota_porta = EtichettaACapo(
            "Copia qui dentro tutto quello che c'è in Finance: conti, "
            "categorie, movimenti, budget, obiettivi e ricorrenti. "
            "L'archivio di Finance non si tocca — si apre in sola lettura — e "
            "si può rilanciare quante volte vuoi: quello che è già entrato "
            "non entra due volte.\n"
            "Finito, la finanza di Dashboard vive da sola e i movimenti si "
            "scrivono qui, senza aprire più l'altra app.")
        nota_porta.setObjectName("NotaScheda")
        scheda.aggiungi(nota_porta)
        self.b_porta_finance = QPushButton("Porta dentro tutto")
        self.b_porta_finance.setObjectName("Primario")
        self.b_porta_finance.clicked.connect(self._porta_dentro_finance)
        self.esito_porta = EtichettaACapo("")
        self.esito_porta.setObjectName("NotaScheda")
        scheda.aggiungi_layout(riga(None, self.b_porta_finance))
        scheda.aggiungi(self.esito_porta)
        lay.addWidget(scheda)

        scheda = Scheda("Categorie dei movimenti")
        scheda.aggiungi(etichetta(
            "Due elenchi distinti: uno per le entrate, uno per le uscite. "
            "Valgono per i movimenti di Finanza e per gli incassi di Carriera.",
            "NotaScheda"))
        self.tab_categorie = QTableWidget(0, 2)
        self.tab_categorie.setHorizontalHeaderLabels(["Categoria", "Tipo"])
        self.tab_categorie.doubleClicked.connect(self._scegli_icona_categoria)
        self.tab_categorie.setToolTip(
            "Doppio clic su una categoria per cambiarle l'icona.")
        self.tab_categorie.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tab_categorie.setSelectionBehavior(QTableWidget.SelectRows)
        intestazione = self.tab_categorie.horizontalHeader()
        intestazione.setSectionResizeMode(0, QHeaderView.Stretch)
        intestazione.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tab_categorie.setMinimumHeight(190)
        self.tab_categorie.setMaximumHeight(240)
        stile_tabella(self.tab_categorie, 30)
        scheda.aggiungi(self.tab_categorie)
        self.nome_categoria = QLineEdit()
        self.nome_categoria.setPlaceholderText("nome della categoria")
        self.nome_categoria.returnPressed.connect(self._aggiungi_categoria)
        self.tipo_categoria = QComboBox()
        self.tipo_categoria.addItems(["uscita", "entrata"])
        aggiungi_cat = QPushButton("Aggiungi")
        aggiungi_cat.clicked.connect(self._aggiungi_categoria)
        togli_cat = QPushButton("Togli")
        togli_cat.clicked.connect(self._togli_categoria)
        scheda.aggiungi_layout(riga(self.nome_categoria, self.tipo_categoria,
                                    aggiungi_cat, togli_cat))
        scheda.aggiungi(EtichettaACapo(
            "L'icona la propone il nome — «Benzina» arriva con la pompa — ed è "
            "lo stesso catalogo dell'app Finance, così la stessa categoria ha "
            "la stessa faccia di qua e di là. Doppio clic su una riga per "
            "sceglierne un'altra fra 174.\n"
            "Togliere una categoria non tocca i movimenti già scritti: sparisce "
            "solo dall'elenco che si propone."))
        lay.addWidget(scheda)

        scheda = Scheda("Budget mensili (archivio interno)")
        self.tab_budget = QTableWidget(0, 2)
        self.tab_budget.setHorizontalHeaderLabels(["Categoria", "Al mese"])
        self.tab_budget.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tab_budget.setSelectionBehavior(QTableWidget.SelectRows)
        self.tab_budget.horizontalHeader().setStretchLastSection(True)
        self.tab_budget.setMinimumHeight(150)
        self.tab_budget.setMaximumHeight(190)
        stile_tabella(self.tab_budget, 30)
        scheda.aggiungi(self.tab_budget)
        self.categoria_budget = QLineEdit()
        self.categoria_budget.setPlaceholderText("categoria")
        self.importo_budget = QDoubleSpinBox()
        self.importo_budget.setRange(0, 999999); self.importo_budget.setSuffix(" €")
        aggiungi = QPushButton("Aggiungi o aggiorna")
        aggiungi.clicked.connect(self._salva_budget)
        togli = QPushButton("Togli")
        togli.clicked.connect(self._togli_budget)
        scheda.aggiungi_layout(riga(self.categoria_budget, self.importo_budget,
                                    aggiungi, togli))
        lay.addWidget(scheda)

        scheda = Scheda("I conti")
        nota_conti = EtichettaACapo(
            "Dove passa il denaro: contante, carta, conto corrente. Il saldo "
            "di un conto è quello di partenza più quello che ci è entrato "
            "meno quello che ne è uscito.\n"
            "Rinominare un conto se li porta dietro i suoi movimenti; "
            "toglierlo no: quei movimenti restano, senza conto.")
        nota_conti.setObjectName("NotaScheda")
        scheda.aggiungi(nota_conti)
        self.tab_conti = QTableWidget(0, 3)
        self.tab_conti.setHorizontalHeaderLabels(["Conto", "Di partenza", "Saldo"])
        self.tab_conti.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tab_conti.setSelectionBehavior(QTableWidget.SelectRows)
        self.tab_conti.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Stretch)
        self.tab_conti.setMinimumHeight(130)
        self.tab_conti.setMaximumHeight(180)
        stile_tabella(self.tab_conti, 30)
        scheda.aggiungi(self.tab_conti)
        self.nome_conto = QLineEdit()
        self.nome_conto.setPlaceholderText("nome del conto")
        self.iniziale_conto = QDoubleSpinBox()
        self.iniziale_conto.setRange(-999999, 999999)
        self.iniziale_conto.setSuffix(" €")
        self.iniziale_conto.setToolTip("Quanto c'era prima del primo movimento")
        aggiungi_conto = QPushButton("Aggiungi o aggiorna")
        aggiungi_conto.clicked.connect(self._salva_conto)
        togli_conto = QPushButton("Togli")
        togli_conto.clicked.connect(self._togli_conto)
        scheda.aggiungi_layout(riga(self.nome_conto, self.iniziale_conto,
                                    aggiungi_conto, togli_conto))
        lay.addWidget(scheda)

        scheda = Scheda("Movimenti che tornano da soli")
        nota_ric = EtichettaACapo(
            "Affitto, abbonamenti, stipendio: si scrivono da sé quando arriva "
            "il giorno, all'apertura di Dashboard. Quelli già scritti non "
            "tornano: se ne cancelli uno a mano resta cancellato.")
        nota_ric.setObjectName("NotaScheda")
        scheda.aggiungi(nota_ric)
        self.tab_ricorrenti = QTableWidget(0, 4)
        self.tab_ricorrenti.setHorizontalHeaderLabels(
            ["Cosa", "Quanto", "Ogni", "Dal"])
        self.tab_ricorrenti.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tab_ricorrenti.setSelectionBehavior(QTableWidget.SelectRows)
        self.tab_ricorrenti.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Stretch)
        self.tab_ricorrenti.setMinimumHeight(120)
        self.tab_ricorrenti.setMaximumHeight(170)
        stile_tabella(self.tab_ricorrenti, 30)
        scheda.aggiungi(self.tab_ricorrenti)
        self.desc_ric = QLineEdit()
        self.desc_ric.setPlaceholderText("es. Affitto")
        self.importo_ric = QDoubleSpinBox()
        self.importo_ric.setRange(0, 999999); self.importo_ric.setSuffix(" €")
        self.tipo_ric = QComboBox(); self.tipo_ric.addItems(["uscita", "entrata"])
        self.categoria_ric = QLineEdit()
        self.categoria_ric.setPlaceholderText("categoria")
        self.frequenza_ric = QComboBox()
        self.frequenza_ric.addItems(["mensile", "settimanale", "annuale"])
        self.inizio_ric = CampoData("", "dal…")
        aggiungi_ric = QPushButton("Aggiungi")
        aggiungi_ric.clicked.connect(self._salva_ricorrente)
        togli_ric = QPushButton("Togli")
        togli_ric.clicked.connect(self._togli_ricorrente)
        scheda.aggiungi_layout(riga(self.desc_ric, self.importo_ric,
                                    self.tipo_ric, self.categoria_ric))
        scheda.aggiungi_layout(riga(self.frequenza_ric, self.inizio_ric,
                                    aggiungi_ric, togli_ric))
        lay.addWidget(scheda)
        lay.addStretch(1)
        return pagina

    # ------------------------------------------------------------- conti
    def _conto_scelto(self):
        righe = self.tab_conti.selectionModel().selectedRows()
        if not righe:
            return None
        return self.tab_conti.item(righe[0].row(), 0).data(Qt.UserRole)

    def _salva_conto(self) -> None:
        """Un conto nuovo, o il saldo di partenza di uno che c'è già."""
        nome = self.nome_conto.text().strip()
        if not nome:
            return
        riga_ = self.db.uno("SELECT id FROM conti WHERE nome=?", (nome,))
        self.db.salva_conto({"id": riga_["id"] if riga_ else None, "nome": nome,
                             "saldo_iniziale": self.iniziale_conto.value(),
                             "tipo": "Conto corrente"})
        self.nome_conto.clear()
        self.iniziale_conto.setValue(0)
        self.fonte_cambiata.emit()
        self.aggiorna()

    def _togli_conto(self) -> None:
        id_ = self._conto_scelto()
        if id_ is None:
            return
        self.db.elimina_conto(int(id_))
        self.fonte_cambiata.emit()
        self.aggiorna()

    # -------------------------------------------------------- ricorrenti
    def _salva_ricorrente(self) -> None:
        descrizione = self.desc_ric.text().strip()
        if not descrizione or self.importo_ric.value() <= 0:
            return
        self.db.salva_ricorrente({
            "descrizione": descrizione, "tipo": self.tipo_ric.currentText(),
            "importo": self.importo_ric.value(),
            "categoria": self.categoria_ric.text().strip() or "Altro",
            "frequenza": self.frequenza_ric.currentText(),
            "inizio": self.inizio_ric.valore() or date.today().isoformat()})
        self.db.genera_ricorrenti()
        self.desc_ric.clear(); self.importo_ric.setValue(0)
        self.categoria_ric.clear()
        self.fonte_cambiata.emit()
        self.aggiorna()

    def _togli_ricorrente(self) -> None:
        righe = self.tab_ricorrenti.selectionModel().selectedRows()
        if not righe:
            return
        id_ = self.tab_ricorrenti.item(righe[0].row(), 0).data(Qt.UserRole)
        if id_ is not None:
            self.db.elimina("ricorrenti", int(id_))
            self.aggiorna()

    def _cambia_fonte(self) -> None:
        self.db.imposta("fonte_finanza", self.fonte_scelta.currentData())
        self.fonte_cambiata.emit()
        self.aggiorna()

    def _scegli_archivio_finance(self) -> None:
        percorso, _ = QFileDialog.getOpenFileName(
            self, "Archivio di Finance", os.path.dirname(PERCORSO_FINANCE),
            "Archivi SQLite (*.db);;Tutti i file (*)")
        if percorso:
            self.percorso_finance.setText(percorso)

    def _scegli_avvio_finance(self) -> None:
        percorso, _ = QFileDialog.getOpenFileName(
            self, "Avviatore di Finance", os.path.expanduser("~"),
            "Script (*.sh);;Tutti i file (*)")
        if percorso:
            self.avvio_finance.setText(percorso)

    def _salva_finanza(self) -> None:
        self.db.imposta("percorso_finance", self.percorso_finance.text().strip())
        self.db.imposta("avvio_finance", self.avvio_finance.text().strip())
        self.fonte_cambiata.emit()
        self.aggiorna()

    def _porta_dentro_finance(self) -> None:
        """Tutto l'archivio di Finance dentro quello di Dashboard."""
        percorso = self.percorso_finance.text().strip() or PERCORSO_FINANCE
        if not finance_presente(percorso):
            self.esito_porta.setText(f"Non trovo nessun archivio in {percorso}.")
            return
        if QMessageBox.question(
                self, "Portare dentro Finance?",
                f"Copio dentro Dashboard tutto quello che c'è in:\n{percorso}\n\n"
                "L'archivio di Finance non viene toccato. Dopo, la sorgente "
                "della finanza passa all'archivio interno, che è quello che "
                "rende i movimenti modificabili da qui.",
                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        entrati = porta_dentro_finance(self.db, percorso)
        quanti = ", ".join(f"{n} {nome}" for nome, n in entrati.items() if n)
        self.db.imposta("fonte_finanza", "locale")
        indice = self.fonte_scelta.findData("locale")
        if indice >= 0:
            self.fonte_scelta.blockSignals(True)
            self.fonte_scelta.setCurrentIndex(indice)
            self.fonte_scelta.blockSignals(False)
        self.esito_porta.setText(
            f"Portati dentro: {quanti}." if quanti else
            "Era già dentro tutto: non è entrato niente di nuovo.")
        self.fonte_cambiata.emit()
        self.aggiorna()

    def _aggiungi_categoria(self) -> None:
        nome = self.nome_categoria.text().strip()
        if not nome:
            return
        self.db.aggiungi_categoria(nome, self.tipo_categoria.currentText())
        self.nome_categoria.clear()
        self.aggiorna()

    def _scegli_icona_categoria(self) -> None:
        """Il catalogo delle icone per la categoria scelta."""
        righe = self.tab_categorie.selectionModel().selectedRows()
        if not righe:
            return
        cella = self.tab_categorie.item(righe[0].row(), 0)
        nome = solo_nome(cella.text())
        tipo = cella.data(Qt.UserRole)
        corrente = self.db.icone_categorie().get(nome, ICONA_PREDEFINITA)
        dlg = SelettoreIcona(corrente, self)
        if dlg.exec():
            self.db.imposta_icona_categoria(nome, tipo, dlg.scelta)
            self.fonte_cambiata.emit()
            self.aggiorna()

    def _togli_categoria(self) -> None:
        righe = self.tab_categorie.selectionModel().selectedRows()
        if not righe:
            return
        cella = self.tab_categorie.item(righe[0].row(), 0)
        nome, tipo = solo_nome(cella.text()), cella.data(Qt.UserRole)
        self.db.togli_categoria(nome, tipo)
        self.aggiorna()

    def _salva_budget(self) -> None:
        nome = self.categoria_budget.text().strip()
        if not nome:
            return
        self.db.salva_budget(nome, self.importo_budget.value())
        self.categoria_budget.clear()
        self.importo_budget.setValue(0)
        self.dati_cambiati.emit()
        self.aggiorna()

    def _togli_budget(self) -> None:
        righe = self.tab_budget.selectionModel().selectedRows()
        if not righe:
            return
        id_ = self.tab_budget.item(righe[0].row(), 0).data(Qt.UserRole)
        self.db.elimina("budget", id_)
        self.dati_cambiati.emit()
        self.aggiorna()

    # ----------------------------------------------------------------- dati
    # ------------------------------------------------------------ Tess
    def _tess(self) -> QWidget:
        """Come deve comportarsi Tess, e che cosa le si lascia vedere."""
        from ..tess import AREE_CONTESTO, LUNGHEZZE, TONI, aree_scelte

        pagina = QWidget()
        lay = QVBoxLayout(pagina)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(14)

        scheda = Scheda()
        # il titolo me lo faccio io: accanto ci va l'interruttore
        testa = QHBoxLayout()
        testa.setSpacing(10)
        titolo = etichetta("Come parla", "Sezione")
        self.tess_solo_mie = Interruttore(
            self.c, self.db.leggi("tess_solo_mie", "0") == "1")
        self.tess_solo_mie.setToolTip(
            "Acceso, a Tess arriva soltanto quello che scrivi tu qui sotto:\n"
            "nome, tono, lunghezza e le righe sui dati restano fuori.")
        et_solo = etichetta("solo le mie istruzioni", "NotaScheda")
        et_solo.setToolTip(self.tess_solo_mie.toolTip())
        self.tess_solo_mie.cambiato.connect(self._commuta_solo_mie)
        testa.addWidget(titolo)
        testa.addStretch(1)
        testa.addWidget(et_solo)
        testa.addWidget(self.tess_solo_mie)
        scheda.aggiungi_layout(testa)
        modulo = QFormLayout()
        modulo.setHorizontalSpacing(14)
        modulo.setVerticalSpacing(10)
        self.tess_nome = QLineEdit(self.db.leggi("tess_nome", "Tess"))
        self.tess_nome.setPlaceholderText("Tess")
        self.tess_tono = QComboBox()
        self.tess_tono.addItems(list(TONI))
        self.tess_tono.setCurrentText(self.db.leggi("tess_tono", "asciutta"))
        self.tess_lunghezza = QComboBox()
        self.tess_lunghezza.addItems(list(LUNGHEZZE))
        self.tess_lunghezza.setCurrentText(self.db.leggi("tess_lunghezza", "normali"))
        for campo in (self.tess_nome, self.tess_tono, self.tess_lunghezza):
            campo.setMinimumHeight(38)
            campo.setMaximumWidth(320)      # i campi corti non si allargano
        self.et_tono = QLabel("Tono")
        self.et_risposte = QLabel("Risposte")
        modulo.addRow("Nome", self.tess_nome)
        modulo.addRow(self.et_tono, self.tess_tono)
        modulo.addRow(self.et_risposte, self.tess_lunghezza)
        scheda.aggiungi_layout(modulo)
        self.et_stile_spento = etichetta(
            "A Tess arriva soltanto quello che scrivi in «Istruzioni tue»: "
            "nome, tono, lunghezza e le righe sui dati restano fuori. "
            "Quello che le serve sapere glielo scrivi tu.", "NotaScheda")
        self.et_stile_spento.setWordWrap(True)
        scheda.aggiungi(self.et_stile_spento)
        lay.addWidget(scheda)

        scheda = Scheda("Istruzioni tue")
        self.tess_istruzioni = QPlainTextEdit(self.db.leggi("tess_istruzioni", ""))
        self.tess_istruzioni.setObjectName("CampoDiario")
        self.tess_istruzioni.setPlaceholderText(
            "Per esempio: «dammi sempre un consiglio pratico alla fine», "
            "«non parlarmi di soldi se non te lo chiedo», «scrivimi in inglese»…")
        self.tess_istruzioni.setMinimumHeight(96)
        scheda.aggiungi(self.tess_istruzioni)
        nota = etichetta("Queste valgono più di tutte le altre: Tess le riceve "
                         "a ogni domanda, prima dei tuoi dati.", "NotaScheda")
        nota.setWordWrap(True)
        scheda.aggiungi(nota)
        lay.addWidget(scheda)

        scheda = Scheda("Che cosa può vedere")
        self.tess_aree: dict[str, QCheckBox] = {}
        scelte = aree_scelte(self.db)
        nomi = {"salute": "Salute", "punteggi": "Punteggi", "accademica": "Università",
                "carriera": "Lavoro e progetti", "abitudini": "Abitudini",
                "finanza": "Finanza", "scadenze": "Scadenze"}
        caselle = DisposizioneFluida(spaziatura=14)
        for chiave in AREE_CONTESTO:
            casella = QCheckBox(nomi.get(chiave, chiave))
            casella.setChecked(chiave in scelte)
            self.tess_aree[chiave] = casella
            caselle.addWidget(casella)
        scheda.aggiungi_layout(caselle)
        nota = etichetta(
            "Il riassunto che Tess riceve contiene solo numeri: medie, "
            "conteggi, scadenze. Il testo del diario non esce mai di qui, "
            "qualunque casella sia accesa. L'interruttore «dati» nella sua "
            "pagina spegne tutto il riassunto in un colpo.", "NotaScheda")
        nota.setWordWrap(True)
        scheda.aggiungi(nota)
        lay.addWidget(scheda)

        scheda = Scheda("Come la sentirà")
        self.tess_anteprima = etichetta("", "NotaScheda")
        self.tess_anteprima.setWordWrap(True)
        self.tess_anteprima.setTextInteractionFlags(Qt.TextSelectableByMouse)
        scheda.aggiungi(self.tess_anteprima)
        b_salva = QPushButton("Salva")
        b_salva.setObjectName("Primario")
        b_salva.clicked.connect(self._salva_tess)
        b_pulisci = QPushButton("Torna com'era")
        b_pulisci.clicked.connect(self._azzera_tess)
        scheda.aggiungi_layout(riga(b_salva, b_pulisci, None))
        lay.addWidget(scheda)
        self._stato_stile()
        self._anteprima_tess()
        for campo in (self.tess_tono, self.tess_lunghezza):
            campo.currentTextChanged.connect(lambda _=None: self._anteprima_tess(True))
        self.tess_nome.textChanged.connect(lambda _=None: self._anteprima_tess(True))
        self.tess_istruzioni.textChanged.connect(
            lambda: self._anteprima_tess(True))

        lay.addStretch(1)
        return pagina

    def _commuta_solo_mie(self, acceso: bool) -> None:
        self.db.imposta("tess_solo_mie", "1" if acceso else "0")
        self._stato_stile()
        self._anteprima_tess(True)

    def _stato_stile(self) -> None:
        """Con «solo le mie» acceso, tono e lunghezza si spengono a vista."""
        acceso = self.tess_solo_mie.acceso()
        for campo in (self.tess_tono, self.tess_lunghezza,
                      self.et_tono, self.et_risposte):
            campo.setEnabled(not acceso)
        self.et_stile_spento.setVisible(acceso)

    def _anteprima_tess(self, provvisoria: bool = False) -> None:
        """Mostra le istruzioni che Tess riceverà, anche prima di salvarle.

        Le mette insieme la stessa funzione che le manda davvero: un'anteprima
        che se le componesse per conto suo prima o poi direbbe un'altra cosa.
        """
        from ..tess import componi_istruzioni, istruzioni
        if not provvisoria:
            self.tess_anteprima.setText(istruzioni(self.db))
            return
        self.tess_anteprima.setText(componi_istruzioni(
            self.tess_nome.text(),
            self.tess_istruzioni.toPlainText(),
            self.tess_tono.currentText(),
            self.tess_lunghezza.currentText(),
            self.tess_solo_mie.acceso()))

    def _salva_tess(self) -> None:
        self.db.imposta("tess_nome", self.tess_nome.text().strip() or "Tess")
        self.db.imposta("tess_tono", self.tess_tono.currentText())
        self.db.imposta("tess_lunghezza", self.tess_lunghezza.currentText())
        self.db.imposta("tess_istruzioni",
                        self.tess_istruzioni.toPlainText().strip())
        self.db.imposta("tess_solo_mie",
                        "1" if self.tess_solo_mie.acceso() else "0")
        self.db.imposta("tess_aree", ",".join(
            c for c, casella in self.tess_aree.items() if casella.isChecked()))
        self._anteprima_tess()

    def _azzera_tess(self) -> None:
        for chiave in ("tess_nome", "tess_tono", "tess_lunghezza",
                       "tess_istruzioni", "tess_aree", "tess_solo_mie"):
            self.db.esegui("DELETE FROM impostazioni WHERE chiave=?", (chiave,))
        self.tess_nome.setText("Tess")
        self.tess_tono.setCurrentText("asciutta")
        self.tess_lunghezza.setCurrentText("normali")
        self.tess_istruzioni.setPlainText("")
        self.tess_solo_mie.imposta(False)
        self._stato_stile()
        for casella in self.tess_aree.values():
            casella.setChecked(True)
        self._anteprima_tess()

    # ------------------------------------------------------- sicurezza
    def _sicurezza(self) -> QWidget:
        pagina = QWidget()
        lay = QVBoxLayout(pagina)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(18)

        scheda = Scheda("Password d'ingresso")
        
        # Banner di stato elegante con badge
        riga_stato = QHBoxLayout()
        riga_stato.setSpacing(12)
        self.badge_blocco = QLabel()
        self.et_blocco = etichetta("", "NotaScheda")
        self.et_blocco.setWordWrap(True)
        riga_stato.addWidget(self.badge_blocco)
        riga_stato.addWidget(self.et_blocco, 1)
        scheda.aggiungi_layout(riga_stato)

        modulo = QFormLayout()
        modulo.setHorizontalSpacing(24)
        modulo.setVerticalSpacing(12)
        modulo.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.pw_attuale = QLineEdit()
        self.pw_nuova = QLineEdit()
        self.pw_ripeti = QLineEdit()
        for campo, invito in ((self.pw_attuale, "serve per cambiarla o toglierla"),
                              (self.pw_nuova, "almeno quattro caratteri"),
                              (self.pw_ripeti, "la stessa, per sicurezza")):
            campo.setEchoMode(QLineEdit.Password)
            campo.setPlaceholderText(invito)
            campo.setMinimumHeight(38)
            campo.setFixedWidth(280)

        # l'etichetta la tengo per nome: va nascosta insieme al campo
        self.et_pw_attuale = QLabel("Password di adesso")
        modulo.addRow(self.et_pw_attuale, self.pw_attuale)
        modulo.addRow("Nuova password", self.pw_nuova)
        modulo.addRow("Ripetila", self.pw_ripeti)
        scheda.aggiungi_layout(modulo)

        fila_azioni = QHBoxLayout()
        fila_azioni.setSpacing(10)
        self.b_blocco = QPushButton("Attiva la password")
        self.b_blocco.setObjectName("Primario")
        self.b_blocco.setMinimumHeight(38)
        self.b_blocco.setMinimumWidth(160)
        self.b_blocco.clicked.connect(self._salva_password)
        self.b_sblocco = QPushButton("Togli la password")
        self.b_sblocco.setMinimumHeight(38)
        self.b_sblocco.setMinimumWidth(150)
        self.b_sblocco.clicked.connect(self._togli_password)
        fila_azioni.addWidget(self.b_blocco)
        fila_azioni.addWidget(self.b_sblocco)
        fila_azioni.addStretch(1)
        scheda.aggiungi_layout(fila_azioni)
        lay.addWidget(scheda)

        scheda_info = Scheda("Che cosa protegge davvero")
        nota = etichetta(
            "È una porta, non una cassaforte: impedisce di aprire la "
            "Dashboard, ma l'archivio resta un file leggibile da altri "
            "programmi (`~/.local/share/Vita/vita.db`). Contro chi si siede al "
            "tuo posto va benissimo; contro chi si porta via il portatile "
            "serve cifrare il disco, che è mestiere del sistema.\n\n"
            "La password non viene salvata: se ne conserva solo l'impronta "
            "(PBKDF2, 240.000 giri, con sale). Se la dimentichi si toglie da "
            "terminale, la riga è scritta in cima a vita/blocco.py.",
            "NotaScheda")
        nota.setWordWrap(True)
        scheda_info.aggiungi(nota)
        lay.addWidget(scheda_info)

        lay.addStretch(1)
        self._stato_blocco()
        return pagina

    def _stato_blocco(self) -> None:
        acceso = blocco.attivo(self.db)
        if acceso:
            self.badge_blocco.setText("🔒  PROTETTA")
            self.badge_blocco.setStyleSheet(
                "background: rgba(22, 196, 127, 0.16); color: #16c47f;"
                " font-weight: 700; border-radius: 11px; padding: 4px 10px; font-size: 11px;")
            self.et_blocco.setText("La password è attiva: all'avvio la Dashboard la richiede.")
        else:
            self.badge_blocco.setText("🔓  NESSUNA PASSWORD")
            self.badge_blocco.setStyleSheet(
                "background: rgba(154, 160, 172, 0.16); color: #9aa0ac;"
                " font-weight: 700; border-radius: 11px; padding: 4px 10px; font-size: 11px;")
            self.et_blocco.setText("Nessuna password impostata: l'applicazione si apre subito.")
        self.pw_attuale.setVisible(acceso)
        self.et_pw_attuale.setVisible(acceso)
        self.b_blocco.setText("Cambia la password" if acceso
                              else "Attiva la password")
        self.b_sblocco.setVisible(acceso)
        for campo in (self.pw_attuale, self.pw_nuova, self.pw_ripeti):
            campo.clear()

    def _salva_password(self) -> None:
        if blocco.attivo(self.db) and not blocco.verifica(self.db,
                                                          self.pw_attuale.text()):
            QMessageBox.warning(self, "Password", "La password di adesso non è quella.")
            return
        nuova = self.pw_nuova.text()
        if len(nuova) < 4:
            QMessageBox.warning(self, "Password",
                                "Scegline una di almeno quattro caratteri.")
            return
        if nuova != self.pw_ripeti.text():
            QMessageBox.warning(self, "Password", "Le due password non coincidono.")
            return
        blocco.imposta(self.db, nuova)
        self._stato_blocco()
        QMessageBox.information(
            self, "Password",
            "Fatta. Dalla prossima apertura la Dashboard te la chiederà.")

    def _togli_password(self) -> None:
        if not blocco.verifica(self.db, self.pw_attuale.text()):
            QMessageBox.warning(self, "Password", "La password di adesso non è quella.")
            return
        blocco.imposta(self.db, "")
        self._stato_blocco()

    def _dati(self) -> QWidget:
        pagina = QWidget()
        lay = QVBoxLayout(pagina)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(14)

        scheda = Scheda("Archivio")
        self.et_archivio = etichetta("", "NotaScheda")
        self.et_archivio.setWordWrap(True)
        self.et_archivio.setTextInteractionFlags(Qt.TextSelectableByMouse)
        scheda.aggiungi(self.et_archivio)
        self.et_conteggi = etichetta("", "NotaScheda")
        self.et_conteggi.setWordWrap(True)
        scheda.aggiungi(self.et_conteggi)
        lay.addWidget(scheda)

        scheda = Scheda("Backup")
        b_backup = QPushButton("Fai un backup adesso")
        b_backup.setObjectName("Primario")
        b_backup.clicked.connect(self._backup)
        b_cartella = QPushButton("Backup in un'altra cartella…")
        b_cartella.clicked.connect(self._backup_altrove)
        b_ripristina = QPushButton("Ripristina da un backup…")
        b_ripristina.clicked.connect(self._ripristina)
        scheda.aggiungi_layout(riga(b_backup, b_cartella, b_ripristina, None))
        self.et_backup = etichetta("", "NotaScheda")
        self.et_backup.setWordWrap(True)
        scheda.aggiungi(self.et_backup)
        lay.addWidget(scheda)

        scheda = Scheda("Salvataggio automatico")
        self.cartella_salvataggio = QLineEdit(
            self.db.leggi("cartella_salvataggio", ""))
        self.cartella_salvataggio.setPlaceholderText(
            "la chiavetta o il disco esterno — per esempio /run/media/giosue/VITA")
        self.cartella_salvataggio.setMinimumHeight(38)
        b_scegli = QPushButton("Scegli…")
        b_scegli.clicked.connect(self._scegli_cartella_salvataggio)
        scheda.aggiungi_layout(riga(self.cartella_salvataggio, b_scegli))

        self.ora_salvataggio = QTimeEdit()
        self.ora_salvataggio.setDisplayFormat("HH:mm")
        self.ora_salvataggio.setButtonSymbols(QTimeEdit.NoButtons)
        self.ora_salvataggio.setMinimumHeight(38)
        self.ora_salvataggio.setFixedWidth(78)
        ora = self.db.leggi("ora_salvataggio", salvataggio.ORA_PREDEFINITA)
        self.ora_salvataggio.setTime(QTime.fromString(ora, "HH:mm"))
        self.ora_salvataggio.timeChanged.connect(self._ora_salvataggio)
        self.auto_salvataggio = Interruttore(self.c, salvataggio.acceso())
        self.auto_salvataggio.cambiato.connect(self._commuta_salvataggio)
        b_adesso = QPushButton("Salva adesso")
        b_adesso.setObjectName("Primario")
        b_adesso.clicked.connect(self._salva_adesso)
        scheda.aggiungi_layout(riga(
            etichetta("Ogni sera alle", "TitoloRiga"), self.ora_salvataggio,
            self.auto_salvataggio, None, b_adesso))
        self.et_auto = etichetta("", "NotaScheda")
        self.et_auto.setWordWrap(True)
        scheda.aggiungi(self.et_auto)
        nota = etichetta(
            "Copia l'archivio della Dashboard e quello di Finance. Se la "
            "chiavetta non è infilata non succede niente di male: lo scrive "
            "qui sotto e riprova la sera dopo. Restano le ultime quattordici "
            "copie più la prima di ogni mese.", "NotaScheda")
        nota.setWordWrap(True)
        scheda.aggiungi(nota)
        lay.addWidget(scheda)
        self._stato_salvataggio()

        scheda = Scheda("Importazione da Samsung Health")
        b_importa = QPushButton("Importa un'esportazione…")
        b_importa.setObjectName("Primario")
        b_importa.clicked.connect(self._importa_salute)
        scheda.aggiungi_layout(riga(b_importa, None))
        nota = etichetta(
            "Sul telefono: Samsung Health → Impostazioni → «Scarica dati "
            "personali». Porta sul PC la cartella (o lo zip) e scegli qui: "
            "Dashboard legge passi, sonno con le fasi, battito, peso, acqua e "
            "allenamenti.\n"
            "Il Galaxy Fit2 resta la via lunga: il braccialetto parla col PC "
            "(batteria, ora, battito in diretta) ma lo storico non lo consegna, "
            "perché il telefono lo svuota prima. L'esportazione qui sopra è "
            "l'unico modo completo.", "NotaScheda")
        nota.setWordWrap(True)
        scheda.aggiungi(nota)
        lay.addWidget(scheda)

        scheda = Scheda("Esportazione")
        b_csv = QPushButton("Esporta tutto in CSV…")
        b_csv.clicked.connect(self._esporta)
        scheda.aggiungi_layout(riga(b_csv, None))
        scheda.aggiungi(etichetta(
            "Una cartella con un file per tabella: diario, salute, allenamenti, "
            "progetti, ore, incassi, esami, studio, percorsi, scadenze, movimenti.",
            "NotaScheda"))
        lay.addWidget(scheda)
        lay.addStretch(1)
        return pagina

    def _scegli_cartella_salvataggio(self) -> None:
        cartella = QFileDialog.getExistingDirectory(
            self, "Dove salvare ogni sera",
            self.cartella_salvataggio.text() or "/run/media")
        if cartella:
            self.cartella_salvataggio.setText(cartella)
            self.db.imposta("cartella_salvataggio", cartella)
            self._stato_salvataggio()

    def _ora_salvataggio(self) -> None:
        ora = self.ora_salvataggio.time().toString("HH:mm")
        self.db.imposta("ora_salvataggio", ora)
        if salvataggio.acceso():          # già acceso: si riscrive col nuovo orario
            salvataggio.installa(ora)
        self._stato_salvataggio()

    def _commuta_salvataggio(self, acceso: bool) -> None:
        if acceso:
            if not self.cartella_salvataggio.text().strip():
                self.auto_salvataggio.imposta(False)
                QMessageBox.information(
                    self, "Salvataggio",
                    "Prima scegli la cartella: la chiavetta o il disco dove "
                    "finiranno le copie.")
                return
            self.db.imposta("cartella_salvataggio",
                            self.cartella_salvataggio.text().strip())
            salvataggio.installa(self.ora_salvataggio.time().toString("HH:mm"))
        else:
            salvataggio.disinstalla()
        self._stato_salvataggio()

    def _salva_adesso(self) -> None:
        cartella = self.cartella_salvataggio.text().strip()
        self.db.imposta("cartella_salvataggio", cartella)
        riuscito, racconto = salvataggio.salva(cartella, self.db, parlato=False)
        self.db.imposta("ultimo_salvataggio_esito",
                        ("fatto · " if riuscito else "") + racconto)
        if riuscito:
            self.db.imposta("ultimo_salvataggio",
                            datetime.now().isoformat(timespec="minutes"))
        self._stato_salvataggio()

    def _stato_salvataggio(self) -> None:
        ultimo = self.db.leggi("ultimo_salvataggio", "")
        esito = self.db.leggi("ultimo_salvataggio_esito", "")
        pezzi = []
        if salvataggio.acceso():
            prossimo = salvataggio.prossimo_giro()
            pezzi.append(f"acceso · prossimo giro {prossimo}" if prossimo
                         else "acceso")
        if ultimo:
            quando = datetime.fromisoformat(ultimo).strftime("%d/%m alle %H:%M")
            pezzi.append(f"ultimo salvataggio {quando}")
        if esito:
            pezzi.append(esito)
        self.et_auto.setText("  ·  ".join(pezzi) or "non è ancora stato fatto nessun "
                             "salvataggio automatico")

    def _importa_salute(self) -> None:
        from ..dialoghi import DialogoImporta
        dialogo = DialogoImporta(self.db, colori=self.c, parent=self)
        dialogo.exec()
        if dialogo.importati:
            self.dati_cambiati.emit()
            self.aggiorna()

    def _backup(self) -> None:
        percorso = self.db.backup(self.db.cartella_backup())
        self.et_backup.setText(f"Salvato in {percorso}")
        self.aggiorna()

    def _backup_altrove(self) -> None:
        cartella = QFileDialog.getExistingDirectory(
            self, "Dove salvare il backup", os.path.expanduser("~"))
        if cartella:
            percorso = self.db.backup(cartella)
            self.et_backup.setText(f"Salvato in {percorso}")

    def _ripristina(self) -> None:
        percorso, _ = QFileDialog.getOpenFileName(
            self, "Backup da ripristinare", self.db.cartella_backup(),
            "Archivi (*.db);;Tutti i file (*)")
        if not percorso:
            return
        risposta = QMessageBox.warning(
            self, "Ripristino",
            "L'archivio attuale verrà sostituito da quello scelto.\n\n"
            "Prima del ripristino viene fatta una copia di sicurezza "
            "dell'archivio attuale. Procedere?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if risposta != QMessageBox.Yes:
            return
        self.db.backup(self.db.cartella_backup())
        self.db.conn.commit()
        shutil.copy2(percorso, self.db.percorso)
        QMessageBox.information(
            self, "Ripristino",
            "Archivio ripristinato. Chiudi e riapri Dashboard per vedere i dati.")

    def _esporta(self) -> None:
        cartella = QFileDialog.getExistingDirectory(
            self, "Dove esportare", os.path.expanduser("~"))
        if not cartella:
            return
        destinazione = os.path.join(
            cartella, f"vita-csv-{datetime.now():%Y%m%d-%H%M%S}")
        os.makedirs(destinazione, exist_ok=True)
        tabelle = ("voci", "salute", "allenamenti", "progetti", "lavoro", "incassi",
                   "esami", "studio", "percorsi", "scadenze", "abitudini",
                   "registro", "movimenti", "budget", "obiettivi")
        scritti = 0
        for tabella in tabelle:
            righe = self.db.query(f"SELECT * FROM {tabella}")
            if not righe:
                continue
            with open(os.path.join(destinazione, f"{tabella}.csv"), "w",
                      newline="", encoding="utf-8") as f:
                scrittore = csv.writer(f, delimiter=";")
                scrittore.writerow(righe[0].keys())
                for r in righe:
                    scrittore.writerow(list(r))
            scritti += 1
        QMessageBox.information(
            self, "Esportazione",
            f"Scritti {scritti} file in:\n{destinazione}")

    # ---------------------------------------------------------------- stato
    def aggiorna(self) -> None:
        percorso = self.percorso_finance.text().strip() or PERCORSO_FINANCE
        if finance_presente(percorso):
            self.stato_finance.setText(f"Trovato: {percorso}")
        else:
            self.stato_finance.setText(
                f"Non trovato in {percorso} — uso l'archivio interno.")

        categorie = [(nome, tipo) for tipo in ("entrata", "uscita")
                     for nome in self.db.categorie(tipo)]
        icone = self.db.icone_categorie()
        self.tab_categorie.setRowCount(len(categorie))
        for i, (nome, tipo) in enumerate(categorie):
            cella = QTableWidgetItem(etichetta_categoria(nome, icone.get(nome)))
            cella.setData(Qt.UserRole, tipo)
            self.tab_categorie.setItem(i, 0, cella)
            self.tab_categorie.setItem(i, 1, QTableWidgetItem(tipo))

        conti = self.db.conti()
        self.tab_conti.setRowCount(len(conti))
        for i, c in enumerate(conti):
            cella = QTableWidgetItem(c["nome"])
            cella.setData(Qt.UserRole, c["id"])
            self.tab_conti.setItem(i, 0, cella)
            for colonna, valore in ((1, c["saldo_iniziale"]), (2, c["saldo"])):
                v = QTableWidgetItem(euro(valore))
                v.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.tab_conti.setItem(i, colonna, v)

        ricorrenti = self.db.ricorrenti()
        self.tab_ricorrenti.setRowCount(len(ricorrenti))
        for i, r in enumerate(ricorrenti):
            cella = QTableWidgetItem(r["descrizione"])
            cella.setData(Qt.UserRole, r["id"])
            self.tab_ricorrenti.setItem(i, 0, cella)
            importo = QTableWidgetItem(
                ("+" if r["tipo"] == "entrata" else "−") + euro(r["importo"]))
            importo.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.tab_ricorrenti.setItem(i, 1, importo)
            self.tab_ricorrenti.setItem(i, 2, QTableWidgetItem(r["frequenza"]))
            self.tab_ricorrenti.setItem(i, 3, QTableWidgetItem(r["inizio"]))

        voci = self.db.budget()
        self.tab_budget.setRowCount(len(voci))
        for i, b in enumerate(voci):
            cella = QTableWidgetItem(b["categoria"])
            cella.setData(Qt.UserRole, b["id"])
            self.tab_budget.setItem(i, 0, cella)
            importo = QTableWidgetItem(euro(b["mensile"]))
            importo.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.tab_budget.setItem(i, 1, importo)

        dimensione = os.path.getsize(self.db.percorso) / 1024 if os.path.exists(
            self.db.percorso) else 0
        tolte = len(getattr(self.db, "impostazioni_tolte", []))
        pulizia = (f"  ·  {tolte} non servivano più e sono state tolte all'avvio"
                   if tolte else "")
        self.et_archivio.setText(
            f"Archivio: {self.db.percorso}  ({numero(dimensione, 0)} kB)\n"
            f"Backup automatici: {self.db.cartella_backup()}\n"
            f"Impostazioni memorizzate: {self.db.quante_impostazioni()}{pulizia}\n"
            "I dati stanno fuori dalla cartella del codice: aggiornare l'app non "
            "li tocca mai.")
        conteggi = self.db.conteggi()
        self.et_conteggi.setText("   ·   ".join(
            f"{nome} {quanti}" for nome, quanti in conteggi.items() if quanti))
        backup = sorted(os.listdir(self.db.cartella_backup())) \
            if os.path.isdir(self.db.cartella_backup()) else []
        if backup:
            self.et_backup.setText(f"{len(backup)} backup · ultimo: {backup[-1]}")
