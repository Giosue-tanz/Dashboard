"""Carriera: progetti, ore lavorate e quanto rendono davvero."""
from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QHeaderView, QLabel, QMenu,
                               QProgressBar, QPushButton, QScrollArea,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from ..componenti import (NavigatorePeriodo, abilita_deselezione, etichetta,
                          riga, stile_tabella)
from ..db import STATI_PROGETTO
from ..dialoghi import DialogoIncasso, DialogoLavoro, DialogoProgetto, DialogoScadenza
from ..grafici import GraficoBarre, GraficoCiambella
from ..utils import (data_it, durata, euro, media, numero, ore, relativa,
                     anno_corrente, mese_corrente)
from . import VistaSezioni


class SchedaProgetto(QFrame):
    """Il cartellino di un progetto dentro la lavagna."""

    scelto = Signal(int)
    menu = Signal(int, object)

    def __init__(self, progetto, colori: dict, nota: str = "", parent=None):
        super().__init__(parent)
        self.id = progetto["id"]
        self.setObjectName("Cartellino")
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(
            f"#Cartellino {{ background: {colori['pannello2']};"
            f" border: 1px solid {colori['bordo']}; border-radius: 10px; }}"
            f"#Cartellino:hover {{ border-color: {progetto['colore']}; }}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(11, 9, 11, 10)
        lay.setSpacing(5)

        titolo = QLabel(progetto["nome"])
        titolo.setObjectName("TitoloRiga")
        titolo.setWordWrap(True)
        lay.addWidget(titolo)

        sotto = QLabel(nota)
        sotto.setObjectName("NotaScheda")
        sotto.setWordWrap(True)
        lay.addWidget(sotto)

        if progetto["stato"] != "idea":
            barra = QProgressBar()
            barra.setRange(0, 100)
            barra.setValue(int(progetto["avanzamento"]))
            barra.setTextVisible(False)
            barra.setFixedHeight(5)
            barra.setStyleSheet(
                f"QProgressBar {{ background: {colori['griglia']}; border: none;"
                f" border-radius: 3px; }}"
                f"QProgressBar::chunk {{ background: {progetto['colore']};"
                f" border-radius: 3px; }}")
            lay.addWidget(barra)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.RightButton:
            self.menu.emit(self.id, ev.globalPosition().toPoint())
        elif ev.button() == Qt.LeftButton:
            self.scelto.emit(self.id)


class VistaCarriera(VistaSezioni):
    titolo = "Carriera"
    sottotitolo = "Lavori, progetti personali e quanto rendono"
    nome_nuovo = "+  Nuovo progetto"
    chiave_vista = "carriera"

    SEZIONI = {
        "lavagna": "Progetti",
        "ore": "Ore di lavoro",
        "soldi": "Da dove arrivano i soldi",
        "registro": "Ore registrate",
        "incassi": "Incassi",
        "scadenze": "Scadenze",
    }
    DISPOSIZIONE = [["lavagna"], ["ore", "soldi"], ["registro", "incassi", "scadenze"]]
    ALTEZZE_PREDEFINITE = (0.40, 0.30, 0.30)
    PERIODI_SEZIONE = {
        "soldi": ({"mese": "Mese corrente", "tre_mesi": "Ultimi 3 mesi",
                   "anno": "Anno corrente", "anno_scorso": "Anno scorso",
                   "tutto": "Tutto"}, "anno"),
        "registro": ({"30": "30 giorni", "90": "90 giorni", "180": "6 mesi",
                      "365": "un anno", "730": "due anni"}, "30"),
        "incassi": ({"30": "30 giorni", "90": "90 giorni", "180": "6 mesi",
                     "365": "un anno", "730": "due anni"}, "90"),
    }

    def crea_sezioni(self) -> None:
        self.b_ore = QPushButton("Registra ore")
        self.b_ore.clicked.connect(self.registra_ore)
        self.b_incasso = QPushButton("Registra incasso")
        self.b_incasso.clicked.connect(self.registra_incasso)
        self.azioni_intestazione = [self.b_ore, self.b_incasso] + self.azioni_intestazione

        # ---------------------------------------------------------- lavagna
        self.lavagna = QWidget()
        self.lavagna.setObjectName("ContenutoSezione")
        self.lay_lavagna = QHBoxLayout(self.lavagna)
        self.lay_lavagna.setContentsMargins(0, 0, 0, 0)
        self.lay_lavagna.setSpacing(11)
        self.colonne: dict[str, QVBoxLayout] = {}
        for chiave, nome in STATI_PROGETTO.items():
            contenitore = QWidget()
            contenitore.setObjectName("ContenutoSezione")
            lay = QVBoxLayout(contenitore)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(8)
            testata = QLabel(nome.upper())
            testata.setObjectName("EtichettaScheda")
            lay.addWidget(testata)
            corpo = QWidget()
            corpo.setObjectName("ContenutoSezione")
            lay_corpo = QVBoxLayout(corpo)
            lay_corpo.setContentsMargins(0, 0, 0, 0)
            lay_corpo.setSpacing(8)
            area = QScrollArea()
            area.setObjectName("ContenutoSezione")
            area.viewport().setObjectName("ContenutoSezione")
            area.setWidgetResizable(True)
            area.setFrameShape(QScrollArea.NoFrame)
            area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            area.setWidget(corpo)
            lay.addWidget(area, 1)
            self.colonne[chiave] = lay_corpo
            self.lay_lavagna.addWidget(contenitore, 1)
        self.aggiungi("lavagna", self.lavagna)

        # -------------------------------------------------------------- ore
        contenuto, lay = self.colonna(8)
        self.et_ore = QLabel("—")
        self.et_ore.setObjectName("ValoreScheda")
        self.et_tariffa = QLabel("—")
        self.et_tariffa.setStyleSheet(
            f"color: {self.c['entrata']}; font-size: 16px; font-weight: 700;")
        lay.addLayout(riga(self.et_ore, None, self.et_tariffa))
        self.et_ore_nota = etichetta("", "NotaScheda")
        lay.addWidget(self.et_ore_nota)
        self.g_ore = GraficoBarre(self.c)
        self.g_ore.formato = lambda v: ore(v, 0)
        self.g_ore.evidenzia_ultima = True
        # giorno per giorno, settimana per settimana o mese per mese: lo
        # stesso comando dei passi e delle ore di studio, sulla riga del titolo
        self.nav_ore = NavigatorePeriodo(self.c, "settimane")
        self.nav_ore.cambiato.connect(self._aggiorna_ore)
        self.nav_ore.scorri_con_rotella(self.g_ore)
        lay.addWidget(self.g_ore, 1)
        self.aggiungi("ore", contenuto, comando=self.nav_ore)

        # ------------------------------------------------------------ soldi
        self.g_soldi = GraficoCiambella(self.c)
        self.g_soldi.formato = lambda v: euro(v)
        self.aggiungi("soldi", self.g_soldi)

        # --------------------------------------------------------- registro
        self.tab_ore = QTableWidget(0, 4)
        self.tab_ore.setHorizontalHeaderLabels(["Data", "Progetto", "Durata", "Su cosa"])
        self._prepara_tabella(self.tab_ore, (0, 1, 2), stretch=3)
        self.tab_ore.doubleClicked.connect(self._modifica_ore)
        self.tab_ore.customContextMenuRequested.connect(
            lambda punto: self._menu_tabella(self.tab_ore, "lavoro", punto))
        self.aggiungi("registro", self.tab_ore)

        self.tab_incassi = QTableWidget(0, 4)
        self.tab_incassi.setHorizontalHeaderLabels(
            ["Data", "Progetto", "Importo", "Descrizione"])
        self._prepara_tabella(self.tab_incassi, (0, 1, 2), stretch=3)
        self.tab_incassi.doubleClicked.connect(self._modifica_incasso)
        self.tab_incassi.customContextMenuRequested.connect(
            lambda punto: self._menu_tabella(self.tab_incassi, "incassi", punto))
        self.aggiungi("incassi", self.tab_incassi)

        self.tab_scadenze = QTableWidget(0, 3)
        self.tab_scadenze.setHorizontalHeaderLabels(["Quando", "Cosa", "Fatta"])
        self._prepara_tabella(self.tab_scadenze, (0, 2), stretch=1)
        self.tab_scadenze.doubleClicked.connect(self._modifica_scadenza)
        self.tab_scadenze.customContextMenuRequested.connect(
            lambda punto: self._menu_tabella(self.tab_scadenze, "scadenze", punto))
        self.aggiungi("scadenze", self.tab_scadenze)

        self.grafici = [self.g_ore, self.g_soldi]

    def _prepara_tabella(self, tab, contenuti, stretch: int) -> None:
        tab.setEditTriggers(QTableWidget.NoEditTriggers)
        tab.setSelectionBehavior(QTableWidget.SelectRows)
        tab.setContextMenuPolicy(Qt.CustomContextMenu)
        h = tab.horizontalHeader()
        for colonna in contenuti:
            h.setSectionResizeMode(colonna, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(stretch, QHeaderView.Stretch)
        abilita_deselezione(tab)
        stile_tabella(tab)

    # ------------------------------------------------------------- comandi
    def nuovo(self) -> None:
        dlg = DialogoProgetto(parent=self)
        if dlg.exec():
            self.db.salva_progetto(dlg.dati())
            self._ricarica()

    def registra_ore(self, progetto_id: int | None = None) -> None:
        voce = {"progetto_id": progetto_id} if progetto_id else None
        dlg = DialogoLavoro(self.db.progetti(), voce, parent=self)
        if dlg.exec():
            d = dlg.dati()
            self.db.esegui(
                "INSERT INTO lavoro(data, progetto_id, minuti, note) VALUES(?,?,?,?)",
                (d["data"], d["progetto_id"], d["minuti"], d["note"]))
            self._ricarica()

    def registra_incasso(self, progetto_id: int | None = None) -> None:
        voce = {"progetto_id": progetto_id} if progetto_id else None
        self._apri_incasso(voce)

    def _apri_incasso(self, voce) -> None:
        """La finestra dell'incasso: salva anche l'entrata gemella in finanza."""
        collegabile = bool(getattr(self.fonte, "modificabile", False))
        dlg = DialogoIncasso(self.db.progetti(), voce,
                             self.db.categorie("entrata"), collegabile, parent=self)
        if not dlg.exec():
            return
        d = dlg.dati()
        self.db.aggiungi_categoria(d["categoria"], "entrata")
        self.db.salva_incasso(d)
        self._ricarica()

    def _ricarica(self) -> None:
        self.aggiorna()
        self.dati_cambiati.emit()

    def _modifica_progetto(self, id_: int) -> None:
        voce = self.db.uno("SELECT * FROM progetti WHERE id=?", (id_,))
        if voce is None:
            return
        dlg = DialogoProgetto(voce, parent=self)
        if dlg.exec():
            self.db.salva_progetto(dlg.dati())
            self._ricarica()

    def _menu_progetto(self, id_: int, punto) -> None:
        voce = self.db.uno("SELECT * FROM progetti WHERE id=?", (id_,))
        if voce is None:
            return
        menu = QMenu(self)
        menu.addAction("Modifica", lambda: self._modifica_progetto(id_))
        menu.addAction("Registra ore", lambda: self.registra_ore(id_))
        menu.addAction("Registra incasso", lambda: self.registra_incasso(id_))
        menu.addSeparator()
        sposta = menu.addMenu("Sposta in")
        for chiave, nome in STATI_PROGETTO.items():
            azione = sposta.addAction(nome)
            azione.setCheckable(True)
            azione.setChecked(chiave == voce["stato"])
            azione.triggered.connect(
                lambda _=False, k=chiave: self._sposta(id_, k))
        menu.addSeparator()
        menu.addAction("Elimina", lambda: (self.db.elimina("progetti", id_),
                                           self._ricarica()))
        menu.exec(punto)

    def _sposta(self, id_: int, stato: str) -> None:
        avanzamento = ", avanzamento=100" if stato == "fatto" else ""
        self.db.esegui(f"UPDATE progetti SET stato=?{avanzamento} WHERE id=?",
                       (stato, id_))
        self._ricarica()

    def _id_selezionato(self, tab):
        righe = tab.selectionModel().selectedRows()
        if not righe:
            return None
        return tab.item(righe[0].row(), 0).data(Qt.UserRole)

    def _modifica_ore(self) -> None:
        id_ = self._id_selezionato(self.tab_ore)
        voce = self.db.uno("SELECT * FROM lavoro WHERE id=?", (id_,)) if id_ else None
        if voce is None:
            return
        dlg = DialogoLavoro(self.db.progetti(), voce, parent=self)
        if dlg.exec():
            d = dlg.dati()
            self.db.esegui(
                "UPDATE lavoro SET data=?, progetto_id=?, minuti=?, note=? WHERE id=?",
                (d["data"], d["progetto_id"], d["minuti"], d["note"], id_))
            self._ricarica()

    def _modifica_incasso(self) -> None:
        id_ = self._id_selezionato(self.tab_incassi)
        voce = self.db.uno("SELECT * FROM incassi WHERE id=?", (id_,)) if id_ else None
        if voce is not None:
            self._apri_incasso(voce)

    def _modifica_scadenza(self) -> None:
        id_ = self._id_selezionato(self.tab_scadenze)
        voce = self.db.uno("SELECT * FROM scadenze WHERE id=?", (id_,)) if id_ else None
        if voce is None:
            return
        dlg = DialogoScadenza(voce, parent=self)
        if dlg.exec():
            self.db.salva_scadenza(dlg.dati())
            self._ricarica()

    def _menu_tabella(self, tab, tabella: str, punto) -> None:
        id_ = self._id_selezionato(tab)
        if id_ is None:
            return
        menu = QMenu(self)
        modifica = {"lavoro": self._modifica_ore, "incassi": self._modifica_incasso,
                    "scadenze": self._modifica_scadenza}[tabella]
        menu.addAction("Modifica", modifica)
        if tabella == "incassi":
            voce = self.db.uno("SELECT * FROM incassi WHERE id=?", (id_,))
            collegato = bool(voce and voce["movimento_id"])
            if getattr(self.fonte, "modificabile", False):
                menu.addAction(
                    "Togli l'entrata in Finanza" if collegato
                    else "Registra anche fra le entrate di Finanza",
                    lambda: (self.db.collega_incasso(id_, not collegato),
                             self._ricarica()))
        if tabella == "scadenze":
            menu.addAction("Segna come fatta", lambda: (
                self.db.esegui("UPDATE scadenze SET fatta=1 WHERE id=?", (id_,)),
                self._ricarica()))
        menu.addAction("Elimina", lambda: (self.db.elimina(tabella, id_),
                                           self._ricarica()))
        menu.exec(tab.viewport().mapToGlobal(punto))

    # ---------------------------------------------------------------- dati
    def aggiorna(self) -> None:
        self._aggiorna_lavagna()
        self._aggiorna_ore()
        self._aggiorna_soldi()
        self._aggiorna_tabelle()

    def _aggiorna_lavagna(self) -> None:
        for lay in self.colonne.values():
            self.svuota(lay)
        conteggio = {k: 0 for k in STATI_PROGETTO}
        for p in self.db.progetti():
            conteggio[p["stato"]] = conteggio.get(p["stato"], 0) + 1
            pezzi = []
            if p["cliente"]:
                pezzi.append(p["cliente"])
            elif p["tipo"] != "personale":
                pezzi.append(p["tipo"])
            if p["compenso"]:
                pezzi.append(euro(p["compenso"]))
            minuti = self.db.minuti_lavoro("0001-01-01", "9999-12-31", p["id"])
            if minuti:
                pezzi.append(durata(minuti))
            if p["scadenza"]:
                pezzi.append(f"entro {data_it(p['scadenza'])}")
            scheda = SchedaProgetto(p, self.c, " · ".join(pezzi) or "nessun dettaglio")
            scheda.scelto.connect(self._modifica_progetto)
            scheda.menu.connect(self._menu_progetto)
            self.colonne[p["stato"]].addWidget(scheda)
        for chiave, lay in self.colonne.items():
            lay.addStretch(1)
        self.contenitore.sezioni["lavagna"].imposta_nota(
            " · ".join(f"{nome.lower()} {conteggio.get(k, 0)}"
                       for k, nome in STATI_PROGETTO.items()))

    def _aggiorna_ore(self) -> None:
        """Le ore di lavoro nel modo scelto: un giorno, una settimana o un
        mese per barra.

        Prima si potevano guardare solo a settimane: per sapere quanto avevi
        lavorato *martedì* bisognava andare nella tabella qui sotto.
        """
        finestre = self.nav_ore.finestre()
        dati, totali = [], []
        for nome_barra, dal, al in finestre:
            minuti = self.db.minuti_lavoro(dal, al)
            totali.append(minuti)
            dati.append((nome_barra, [float(minuti)]))
        self.g_ore.evidenziata = self.nav_ore.indice_adesso()
        self.g_ore.imposta_dati(dati, [("ore", "#6c8cff")])

        # il numero grande è quello del periodo in primo piano: in «giorni»
        # è **oggi**, non la domenica in fondo alla settimana
        dal, al = self.nav_ore.scelto()
        unita = {"giorni": "giorno", "settimane": "settimana",
                 "mesi": "mese"}[self.nav_ore.modo]
        self.et_ore.setText(durata(self.db.minuti_lavoro(dal, al)))
        self.et_ore_nota.setText(
            f"{self.nav_ore.nome_scelto()} · media {durata(media(totali))} "
            f"per {unita}")
        dal_anno, al_anno = anno_corrente()
        minuti_anno = self.db.minuti_lavoro(dal_anno, al_anno)
        incassi_anno = self.db.totale_incassi(dal_anno, al_anno)
        if minuti_anno:
            self.et_tariffa.setText(f"{euro(incassi_anno / (minuti_anno / 60))}/h")
            self.et_tariffa.setToolTip(
                f"{euro(incassi_anno)} incassati quest'anno divisi per "
                f"{ore(minuti_anno)} di lavoro registrate")
        else:
            self.et_tariffa.setText("—")
            self.et_tariffa.setToolTip("registra le ore per vedere la tariffa reale")
        self.contenitore.sezioni["ore"].imposta_nota(
            f"{len(finestre)} {self.nav_ore.modo}")

    def _aggiorna_soldi(self) -> None:
        periodo = self.periodo("soldi")
        if periodo == "mese":
            dal, al = mese_corrente()
        elif periodo == "anno":
            dal, al = anno_corrente()
        else:
            dal, al = "0001-01-01", "9999-12-31"
        voci = self.db.incassi_per_progetto(dal, al)
        totale = sum(v for _, v, _ in voci)
        self.g_soldi.imposta_dati([(nome, valore, colore) for nome, valore, colore in voci],
                                  euro(totale) if totale else "—", "incassati")
        self.contenitore.sezioni["soldi"].imposta_nota(
            f"{euro(totale)} in totale" if totale else "nessun incasso registrato")

    def _aggiorna_tabelle(self) -> None:
        giorni_ore = int(self.periodo("registro"))
        dal = (date.today() - timedelta(days=giorni_ore - 1)).isoformat()
        voci = self.db.lavoro(dal, date.today().isoformat(), limite=300)
        self.tab_ore.setRowCount(len(voci))
        for i, v in enumerate(voci):
            cella = QTableWidgetItem(relativa(v["data"]))
            cella.setData(Qt.UserRole, v["id"])
            self.tab_ore.setItem(i, 0, cella)
            self.tab_ore.setItem(i, 1, QTableWidgetItem(v["progetto"] or "—"))
            durata_cella = QTableWidgetItem(durata(v["minuti"]))
            durata_cella.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.tab_ore.setItem(i, 2, durata_cella)
            self.tab_ore.setItem(i, 3, QTableWidgetItem(v["note"]))
        self.contenitore.sezioni["registro"].imposta_nota(
            f"{durata(sum(v['minuti'] for v in voci))} in {giorni_ore} giorni")

        giorni_inc = int(self.periodo("incassi"))
        dal = (date.today() - timedelta(days=giorni_inc - 1)).isoformat()
        voci = self.db.incassi(dal, date.today().isoformat(), limite=300)
        self.tab_incassi.setRowCount(len(voci))
        for i, v in enumerate(voci):
            cella = QTableWidgetItem(relativa(v["data"]))
            cella.setData(Qt.UserRole, v["id"])
            self.tab_incassi.setItem(i, 0, cella)
            self.tab_incassi.setItem(i, 1, QTableWidgetItem(v["progetto"] or "—"))
            # «⇄» segna gli incassi che sono anche un'entrata di Finanza:
            # la categoria e lo stato del collegamento stanno nel suggerimento
            collegato = bool(v["movimento_id"])
            categoria = v["categoria"] or "Lavoro"
            importo = QTableWidgetItem(
                euro(v["importo"]) + ("  ⇄" if collegato else ""))
            importo.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            importo.setToolTip(
                f"{categoria} · anche fra le entrate di Finanza" if collegato
                else f"{categoria} · solo in Carriera")
            self.tab_incassi.setItem(i, 2, importo)
            self.tab_incassi.setItem(i, 3, QTableWidgetItem(v["descrizione"]))
        self.contenitore.sezioni["incassi"].imposta_nota(
            euro(sum(v["importo"] for v in voci)) + f" in {giorni_inc} giorni")

        scadenze = self.db.query(
            "SELECT * FROM scadenze WHERE area='carriera' ORDER BY fatta, data LIMIT 60")
        self.tab_scadenze.setRowCount(len(scadenze))
        for i, s in enumerate(scadenze):
            cella = QTableWidgetItem(relativa(s["data"]))
            cella.setData(Qt.UserRole, s["id"])
            cella.setToolTip(data_it(s["data"]))
            if not s["fatta"] and s["data"] <= date.today().isoformat():
                cella.setForeground(Qt.red)
            self.tab_scadenze.setItem(i, 0, cella)
            self.tab_scadenze.setItem(i, 1, QTableWidgetItem(s["titolo"]))
            self.tab_scadenze.setItem(i, 2, QTableWidgetItem("sì" if s["fatta"] else "—"))
        self.contenitore.sezioni["scadenze"].imposta_nota(
            f"{sum(1 for s in scadenze if not s['fatta'])} aperte")
