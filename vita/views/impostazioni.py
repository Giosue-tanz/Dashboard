"""Impostazioni: aspetto, obiettivi, sorgente della finanza, archivio."""
from __future__ import annotations

import csv
import os
import shutil
from datetime import datetime

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QDoubleSpinBox, QFileDialog,
                               QFormLayout, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QMessageBox, QPushButton, QScrollArea,
                               QSpinBox, QTabWidget, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from ..componenti import CampoDurata, Scheda, etichetta, riga, separatore, stile_tabella
from ..db import DATA_DIR
from ..fonti import PERCORSO_FINANCE, finance_presente
from ..punteggi import PREDEFINITI
from ..tema import ACCENTI, SCALE
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
        self.schede.addTab(self._aspetto(), "Aspetto")
        self.schede.addTab(self._obiettivi(), "Obiettivi")
        self.schede.addTab(self._scorrevole(self._finanza()), "Finanza")
        self.schede.addTab(self._dati(), "Dati e backup")

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
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(14)

        scheda = Scheda("Tema")
        self.gruppo_tema = QButtonGroup(self)
        fila = QHBoxLayout()
        fila.setSpacing(8)
        for chiave, nome in (("scuro", "Scuro"), ("chiaro", "Chiaro")):
            b = QPushButton(nome)
            b.setObjectName("Segmento")
            b.setCheckable(True)
            b.setChecked(self.db.leggi("tema", "scuro") == chiave)
            b.clicked.connect(lambda _=False, k=chiave: self._imposta_tema(k))
            self.gruppo_tema.addButton(b)
            fila.addWidget(b)
        fila.addStretch(1)
        scheda.aggiungi_layout(fila)
        scheda.aggiungi(etichetta("Ctrl+T cambia tema in qualsiasi momento.",
                                  "NotaScheda"))
        lay.addWidget(scheda)

        scheda = Scheda("Colore principale")
        griglia = QHBoxLayout()
        griglia.setSpacing(8)
        tema = self.db.leggi("tema", "scuro")
        for nome, tinte in ACCENTI.items():
            b = QPushButton(nome)
            b.setObjectName("Campione")
            colore = tinte["scuro" if tema == "scuro" else "chiaro"]
            b.setStyleSheet(f"background: {colore}; color: #0e1015; font-weight: 600;")
            b.clicked.connect(lambda _=False, k=nome: self._imposta_accento(k))
            griglia.addWidget(b)
        griglia.addStretch(1)
        scheda.aggiungi_layout(griglia)
        lay.addWidget(scheda)

        scheda = Scheda("Dimensione del testo")
        self.scala = QComboBox()
        self.scala.addItems(list(SCALE))
        self.scala.setCurrentText(self.db.leggi("scala", "normale"))
        self.scala.currentTextChanged.connect(self._imposta_scala)
        scheda.aggiungi(self.scala)
        lay.addWidget(scheda)

        lay.addStretch(1)
        return pagina

    def _imposta_tema(self, chiave: str) -> None:
        self.db.imposta("tema", chiave)
        self.tema_cambiato.emit(chiave)

    def _imposta_accento(self, nome: str) -> None:
        self.db.imposta("accento", nome)
        self.aspetto_cambiato.emit()

    def _imposta_scala(self, nome: str) -> None:
        self.db.imposta("scala", nome)
        self.aspetto_cambiato.emit()

    # ----------------------------------------------------------- obiettivi
    def _obiettivi(self) -> QWidget:
        pagina = QWidget()
        lay = QVBoxLayout(pagina)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(14)

        scheda = Scheda("Quanto ti sei dato da fare")
        modulo = QFormLayout()
        modulo.setSpacing(10)

        self.passi = QSpinBox(); self.passi.setRange(0, 100000)
        self.passi.setSingleStep(500); self.passi.setGroupSeparatorShown(True)
        self.passi.setValue(int(self.db.leggi_num("obiettivo_passi",
                                                  PREDEFINITI["obiettivo_passi"])))
        self.sonno = CampoDurata()
        self.sonno.imposta(int(self.db.leggi_num("obiettivo_sonno",
                                                 PREDEFINITI["obiettivo_sonno"])))
        self.allenamenti = QSpinBox(); self.allenamenti.setRange(0, 14)
        self.allenamenti.setValue(int(self.db.leggi_num(
            "obiettivo_allenamenti", PREDEFINITI["obiettivo_allenamenti"])))
        self.studio = CampoDurata()
        self.studio.imposta(int(self.db.leggi_num("obiettivo_studio",
                                                  PREDEFINITI["obiettivo_studio"])))
        self.acqua = QDoubleSpinBox(); self.acqua.setRange(0, 10)
        self.acqua.setSingleStep(0.25); self.acqua.setSuffix(" L")
        self.acqua.setValue(self.db.leggi_num("obiettivo_acqua",
                                              PREDEFINITI["obiettivo_acqua"]))
        self.cfu = QSpinBox(); self.cfu.setRange(0, 600)
        self.cfu.setValue(int(self.db.leggi_num("cfu_laurea", 180)))

        modulo.addRow("Passi al giorno", self.passi)
        modulo.addRow("Sonno a notte", self.sonno)
        modulo.addRow("Allenamenti a settimana", self.allenamenti)
        modulo.addRow("Studio a settimana", self.studio)
        modulo.addRow("Acqua al giorno", self.acqua)
        modulo.addRow("CFU della laurea", self.cfu)
        scheda.aggiungi_layout(modulo)

        salva = QPushButton("Salva obiettivi")
        salva.setObjectName("Primario")
        salva.clicked.connect(self._salva_obiettivi)
        scheda.aggiungi_layout(riga(None, salva))
        scheda.aggiungi(etichetta(
            "Gli obiettivi entrano negli indicatori in fondo alla barra e nelle "
            "linee tratteggiate dei grafici.", "NotaScheda"))
        lay.addWidget(scheda)
        lay.addStretch(1)
        return pagina

    def _salva_obiettivi(self) -> None:
        self.db.imposta("obiettivo_passi", self.passi.value())
        self.db.imposta("obiettivo_sonno", self.sonno.valore())
        self.db.imposta("obiettivo_allenamenti", self.allenamenti.value())
        self.db.imposta("obiettivo_studio", self.studio.valore())
        self.db.imposta("obiettivo_acqua", self.acqua.value())
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

        scheda = Scheda("Categorie dei movimenti")
        scheda.aggiungi(etichetta(
            "Due elenchi distinti: uno per le entrate, uno per le uscite. "
            "Valgono per i movimenti di Finanza e per gli incassi di Carriera.",
            "NotaScheda"))
        self.tab_categorie = QTableWidget(0, 2)
        self.tab_categorie.setHorizontalHeaderLabels(["Categoria", "Tipo"])
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
        scheda.aggiungi(etichetta(
            "Togliere una categoria non tocca i movimenti già scritti: sparisce "
            "solo dall'elenco che si propone.", "NotaScheda"))
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
        lay.addStretch(1)
        return pagina

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

    def _aggiungi_categoria(self) -> None:
        nome = self.nome_categoria.text().strip()
        if not nome:
            return
        self.db.aggiungi_categoria(nome, self.tipo_categoria.currentText())
        self.nome_categoria.clear()
        self.aggiorna()

    def _togli_categoria(self) -> None:
        righe = self.tab_categorie.selectionModel().selectedRows()
        if not righe:
            return
        cella = self.tab_categorie.item(righe[0].row(), 0)
        nome, tipo = cella.text(), cella.data(Qt.UserRole)
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
            "Il Galaxy Fit2 non consegna lo storico al PC: via Bluetooth si può "
            "leggere solo il battito mentre il braccialetto sta misurando "
            "(strumenti/battito_bluetooth.py).", "NotaScheda")
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
        self.tab_categorie.setRowCount(len(categorie))
        for i, (nome, tipo) in enumerate(categorie):
            cella = QTableWidgetItem(nome)
            cella.setData(Qt.UserRole, tipo)
            self.tab_categorie.setItem(i, 0, cella)
            self.tab_categorie.setItem(i, 1, QTableWidgetItem(tipo))

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
        self.et_archivio.setText(
            f"Archivio: {self.db.percorso}  ({numero(dimensione, 0)} kB)\n"
            f"Backup automatici: {self.db.cartella_backup()}\n"
            "I dati stanno fuori dalla cartella del codice: aggiornare l'app non "
            "li tocca mai.")
        conteggi = self.db.conteggi()
        self.et_conteggi.setText("   ·   ".join(
            f"{nome} {quanti}" for nome, quanti in conteggi.items() if quanti))
        backup = sorted(os.listdir(self.db.cartella_backup())) \
            if os.path.isdir(self.db.cartella_backup()) else []
        if backup:
            self.et_backup.setText(f"{len(backup)} backup · ultimo: {backup[-1]}")
