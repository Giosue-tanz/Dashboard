"""Accademica: il libretto, le ore di studio e quello che vuoi imparare."""
from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QHeaderView, QLabel, QMenu, QPushButton,
                               QTableWidget, QTableWidgetItem, QVBoxLayout)

from ..componenti import (NavigatorePeriodo, RigaMisura,
                          abilita_deselezione, etichetta, riga,
                          stile_tabella)
from ..db import STATI_ESAME
from ..dialoghi import DialogoEsame, DialogoPercorso, DialogoScadenza, DialogoStudio
from ..grafici import GraficoBarre, GraficoCiambella
from ..punteggi import PREDEFINITI
from ..tema import AREE
from ..utils import (data_it, durata, media, numero, ore, relativa,
                     settimana_corrente)
from . import VistaSezioni


class VistaAccademica(VistaSezioni):
    titolo = "Accademica"
    sottotitolo = "Il libretto, lo studio e i percorsi che ti sei dato"
    nome_nuovo = "+  Nuovo esame"
    chiave_vista = "accademica"

    SEZIONI = {
        "libretto": "Libretto",
        "imparare": "Da imparare",
        "studio": "Ore di studio",
        "materie": "Studio per materia",
        "scadenze": "Scadenze",
        "registro": "Sessioni di studio",
    }
    DISPOSIZIONE = [["libretto", "imparare"], ["studio", "materie"],
                    ["scadenze", "registro"]]
    ALTEZZE_PREDEFINITE = (0.40, 0.30, 0.30)
    PERIODI_SEZIONE = {
        "materie": ({"30": "30 giorni", "90": "90 giorni", "180": "6 mesi",
                     "365": "un anno", "730": "due anni"}, "30"),
        "registro": ({"30": "30 giorni", "90": "90 giorni", "180": "6 mesi",
                      "365": "un anno", "730": "due anni"}, "30"),
    }

    def crea_sezioni(self) -> None:
        self.b_studio = QPushButton("Registra studio")
        self.b_studio.clicked.connect(self.registra_studio)
        self.b_percorso = QPushButton("Nuovo percorso")
        self.b_percorso.clicked.connect(self.nuovo_percorso)
        self.azioni_intestazione = [self.b_studio, self.b_percorso] + self.azioni_intestazione

        # --------------------------------------------------------- libretto
        self.tab_esami = QTableWidget(0, 5)
        self.tab_esami.setHorizontalHeaderLabels(
            ["Materia", "CFU", "Anno", "Stato", "Voto"])
        self._prepara(self.tab_esami, stretch=0, contenuti=(1, 2, 3, 4))
        self.tab_esami.doubleClicked.connect(self._modifica_esame)
        self.tab_esami.customContextMenuRequested.connect(
            lambda punto: self._menu(self.tab_esami, "esami", punto))
        self.aggiungi("libretto", self.tab_esami)

        # --------------------------------------------------------- imparare
        self.cont_percorsi, self.lay_percorsi = self.colonna(10)
        self.aggiungi("imparare", self.scorrevole(self.cont_percorsi))

        # ----------------------------------------------------------- studio
        contenuto, lay = self.colonna(8)
        self.et_studio = QLabel("—")
        self.et_studio.setObjectName("ValoreScheda")
        self.et_scarto = QLabel("")
        self.et_scarto.setStyleSheet(
            f"color: {self.c['entrata']}; font-size: 15px; font-weight: 700;")
        lay.addLayout(riga(self.et_studio, None, self.et_scarto))
        self.et_studio_nota = etichetta("", "NotaScheda")
        lay.addWidget(self.et_studio_nota)

        # giorni, settimane o mesi, avanti e indietro: lo stesso comando che
        # sta nei riquadri di Salute
        self.nav_studio = NavigatorePeriodo(self.c, "settimane")
        self.nav_studio.cambiato.connect(self._aggiorna_studio)
        lay.addWidget(self.nav_studio)

        self.g_studio = GraficoBarre(self.c)
        self.g_studio.formato = lambda v: ore(v, 0)
        self.g_studio.evidenzia_ultima = True
        self.nav_studio.scorri_con_rotella(self.g_studio)
        lay.addWidget(self.g_studio, 1)
        self.aggiungi("studio", contenuto)

        # ---------------------------------------------------------- materie
        self.g_materie = GraficoCiambella(self.c)
        self.g_materie.formato = lambda v: durata(v)
        self.aggiungi("materie", self.g_materie)

        # --------------------------------------------------------- scadenze
        self.tab_scadenze = QTableWidget(0, 3)
        self.tab_scadenze.setHorizontalHeaderLabels(["Quando", "Cosa", "Fatta"])
        self._prepara(self.tab_scadenze, stretch=1, contenuti=(0, 2))
        self.tab_scadenze.doubleClicked.connect(self._modifica_scadenza)
        self.tab_scadenze.customContextMenuRequested.connect(
            lambda punto: self._menu(self.tab_scadenze, "scadenze", punto))
        self.aggiungi("scadenze", self.tab_scadenze)

        # --------------------------------------------------------- registro
        self.tab_studio = QTableWidget(0, 4)
        self.tab_studio.setHorizontalHeaderLabels(
            ["Data", "Materia", "Durata", "Argomento"])
        self._prepara(self.tab_studio, stretch=3, contenuti=(0, 1, 2))
        self.tab_studio.doubleClicked.connect(self._modifica_studio)
        self.tab_studio.customContextMenuRequested.connect(
            lambda punto: self._menu(self.tab_studio, "studio", punto))
        self.aggiungi("registro", self.tab_studio)

        self.grafici = [self.g_studio, self.g_materie]

    def _prepara(self, tab, stretch: int, contenuti) -> None:
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
        dlg = DialogoEsame(parent=self)
        if dlg.exec():
            self.db.salva_esame(dlg.dati())
            self._ricarica()

    def nuovo_percorso(self) -> None:
        dlg = DialogoPercorso(parent=self)
        if dlg.exec():
            self.db.salva_percorso(dlg.dati())
            self._ricarica()

    def registra_studio(self) -> None:
        dlg = DialogoStudio(self._materie(), parent=self)
        if dlg.exec():
            d = dlg.dati()
            self.db.esegui(
                "INSERT INTO studio(data, materia, minuti, argomento) VALUES(?,?,?,?)",
                (d["data"], d["materia"], d["minuti"], d["argomento"]))
            self._ricarica()

    def _materie(self) -> list[str]:
        nomi = [r["nome"] for r in self.db.esami()]
        viste = [m for m, _ in self.db.studio_per_materia("0001-01-01", "9999-12-31")]
        for m in viste:
            if m not in nomi and m != "senza materia":
                nomi.append(m)
        return nomi

    def _ricarica(self) -> None:
        self.aggiorna()
        self.dati_cambiati.emit()

    def _id(self, tab):
        righe = tab.selectionModel().selectedRows()
        if not righe:
            return None
        return tab.item(righe[0].row(), 0).data(Qt.UserRole)

    def _modifica_esame(self) -> None:
        self._apri_esame(self._id(self.tab_esami))

    def _apri_esame(self, id_) -> None:
        voce = self.db.uno("SELECT * FROM esami WHERE id=?", (id_,)) if id_ else None
        if voce is None:
            return
        dlg = DialogoEsame(voce, parent=self)
        if dlg.exec():
            self.db.salva_esame(dlg.dati())
            self._ricarica()

    def _modifica_studio(self) -> None:
        id_ = self._id(self.tab_studio)
        voce = self.db.uno("SELECT * FROM studio WHERE id=?", (id_,)) if id_ else None
        if voce is None:
            return
        dlg = DialogoStudio(self._materie(), voce, parent=self)
        if dlg.exec():
            d = dlg.dati()
            self.db.esegui(
                "UPDATE studio SET data=?, materia=?, minuti=?, argomento=? WHERE id=?",
                (d["data"], d["materia"], d["minuti"], d["argomento"], id_))
            self._ricarica()

    def _modifica_scadenza(self) -> None:
        id_ = self._id(self.tab_scadenze)
        voce = self.db.uno("SELECT * FROM scadenze WHERE id=?", (id_,)) if id_ else None
        if voce is None:
            dlg = DialogoScadenza(area="accademica", parent=self)
        else:
            dlg = DialogoScadenza(voce, parent=self)
        if dlg.exec():
            self.db.salva_scadenza(dlg.dati())
            self._ricarica()

    def _menu(self, tab, tabella: str, punto) -> None:
        id_ = self._id(tab)
        if id_ is None:
            return
        menu = QMenu(self)
        modifica = {"esami": self._modifica_esame, "studio": self._modifica_studio,
                    "scadenze": self._modifica_scadenza}[tabella]
        menu.addAction("Modifica", modifica)
        if tabella == "scadenze":
            menu.addAction("Segna come fatta", lambda: (
                self.db.esegui("UPDATE scadenze SET fatta=1 WHERE id=?", (id_,)),
                self._ricarica()))
        if tabella == "esami":
            menu.addAction("Registra studio", self.registra_studio)
        menu.addAction("Elimina", lambda: (self.db.elimina(tabella, id_),
                                           self._ricarica()))
        menu.exec(tab.viewport().mapToGlobal(punto))

    def _modifica_percorso(self, id_: int) -> None:
        voce = self.db.uno("SELECT * FROM percorsi WHERE id=?", (id_,))
        if voce is None:
            return
        dlg = DialogoPercorso(voce, parent=self)
        if dlg.exec():
            self.db.salva_percorso(dlg.dati())
            self._ricarica()

    # ---------------------------------------------------------------- dati
    def aggiorna(self) -> None:
        self._aggiorna_libretto()
        self._aggiorna_imparare()
        self._aggiorna_studio()
        self._aggiorna_materie()
        self._aggiorna_tabelle()

    def _aggiorna_libretto(self) -> None:
        esami = self.db.esami()
        self.tab_esami.setRowCount(len(esami))
        for i, e in enumerate(esami):
            nome = QTableWidgetItem(e["nome"])
            nome.setData(Qt.UserRole, e["id"])
            self.tab_esami.setItem(i, 0, nome)
            cfu = QTableWidgetItem(str(e["cfu"]))
            cfu.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.tab_esami.setItem(i, 1, cfu)
            self.tab_esami.setItem(i, 2, QTableWidgetItem(f"{e['anno']}º"))
            if e["stato"] == "superato":
                stato = STATI_ESAME["superato"]
            elif e["stato"] == "corso":
                stato = f"preparazione {e['avanzamento']}%"
            else:
                stato = (f"previsto {data_it(e['data_esame'])}" if e["data_esame"]
                         else "previsto")
            self.tab_esami.setItem(i, 3, QTableWidgetItem(stato))
            if e["voto"]:
                testo = "30 e lode" if e["lode"] else str(e["voto"])
            else:
                testo = "—"
            voto_cella = QTableWidgetItem(testo)
            voto_cella.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.tab_esami.setItem(i, 4, voto_cella)
        r = self.db.riepilogo_libretto()
        totale_cfu = int(self.db.leggi_num("cfu_laurea", 180))
        if r["n"]:
            self.contenitore.sezioni["libretto"].imposta_nota(
                f"{r['n']} superati · CFU {r['cfu']}/{totale_cfu} · "
                f"media {numero(r['media'], 1)} · ponderata {numero(r['ponderata'], 1)} · "
                f"base di laurea {numero(r['base'], 0)}")
        else:
            self.contenitore.sezioni["libretto"].imposta_nota(
                f"{len(esami)} esami in programma")

    def _aggiorna_imparare(self) -> None:
        """Due elenchi: gli esami che restano e quello che vuoi imparare a parte."""
        self.svuota(self.lay_percorsi)
        da_dare = [e for e in self.db.esami() if e["stato"] != "superato"]
        percorsi = self.db.percorsi()

        if da_dare:
            self.lay_percorsi.addWidget(self._titolo_blocco("Esami da dare"))
        for e in da_dare:
            sotto = f"{e['anno']}º anno"
            if e["data_esame"]:
                sotto += f" · appello {data_it(e['data_esame'])}"
            if e["stato"] == "corso":
                nota = (f"in preparazione {e['avanzamento']}%" if e["avanzamento"]
                        else "in preparazione")
                colore = AREE["accademica"]
            else:
                nota = "previsto"
                colore = self.c["testo2"]
            riga = RigaMisura(self.c, "", e["nome"], sotto, f"{e['cfu']} CFU", nota,
                              e["avanzamento"], colore)
            riga.setCursor(Qt.PointingHandCursor)
            riga.setToolTip("Doppio clic per modificare l'esame.")
            riga.mouseDoubleClickEvent = (
                lambda _ev, id_=e["id"]: self._apri_esame(id_))
            self.lay_percorsi.addWidget(riga)

        if percorsi or da_dare:
            self.lay_percorsi.addWidget(self._titolo_blocco("Altro da imparare"))
        if not percorsi:
            self.lay_percorsi.addWidget(etichetta(
                "«Nuovo percorso» per segnare quello che vuoi imparare fuori dal "
                "libretto." if da_dare else
                "Niente ancora. «Nuovo percorso» per segnare cosa vuoi imparare.",
                "NotaScheda"))
        for p in percorsi:
            sotto = p["risorsa"] or p["categoria"]
            if p["stato"] != "attivo":
                sotto = f"{sotto} · {p['stato']}"
            misura = RigaMisura(self.c, "", p["nome"], sotto,
                                f"{p['avanzamento']}%", p["categoria"],
                                p["avanzamento"], p["colore"])
            misura.setCursor(Qt.PointingHandCursor)
            misura.setToolTip("Doppio clic per modificare il percorso.")
            misura.mouseDoubleClickEvent = (
                lambda _ev, id_=p["id"]: self._modifica_percorso(id_))
            self.lay_percorsi.addWidget(misura)

        cfu = sum(int(e["cfu"]) for e in da_dare)
        attivi = sum(1 for p in percorsi if p["stato"] == "attivo")
        pezzi = []
        if da_dare:
            pezzi.append(f"{len(da_dare)} esami · {cfu} CFU da dare")
        pezzi.append(f"{len(percorsi)} percorsi"
                     + (f" · {attivi} attivi" if percorsi else ""))
        self.contenitore.sezioni["imparare"].imposta_nota(" · ".join(pezzi))
        self.lay_percorsi.addStretch(1)

    @staticmethod
    def _titolo_blocco(testo: str):
        return etichetta(testo.upper(), "EtichettaScheda")

    def _aggiorna_studio(self) -> None:
        """Le ore di studio nel modo scelto: giorni, settimane o mesi."""
        finestre = self.nav_studio.finestre()
        totali = [self.db.minuti_studio(dal, al) for _e, dal, al in finestre]
        dati = [(etichetta_barra, [float(minuti)])
                for (etichetta_barra, _d, _a), minuti in zip(finestre, totali)]
        obiettivo = self.db.leggi_num("obiettivo_studio", PREDEFINITI["obiettivo_studio"])
        # l'obiettivo è settimanale: sugli altri modi va riportato in scala
        riferimento = {"giorni": obiettivo / 7, "settimane": obiettivo,
                       "mesi": obiettivo * 30 / 7}[self.nav_studio.modo]
        self.g_studio.riferimento = riferimento
        self.g_studio.imposta_dati(dati, [("studio", "#b07cff")])

        scelto = totali[-1] if totali else 0
        self.et_studio.setText(durata(scelto))
        precedenti = media(totali[:-1]) if len(totali) > 1 else 0
        scostamento = scelto - precedenti
        segno = "+" if scostamento >= 0 else "−"
        self.et_scarto.setText(f"{segno}{durata(abs(scostamento))}")
        self.et_scarto.setStyleSheet(
            f"color: {self.c['entrata'] if scostamento >= 0 else self.c['uscita']};"
            f" font-size: 15px; font-weight: 700;")
        self.et_studio_nota.setText(
            f"obiettivo {durata(riferimento)} · "
            f"media delle altre {durata(precedenti)}")
        quanti = len(finestre)
        self.contenitore.sezioni["studio"].imposta_nota(
            f"{quanti} {self.nav_studio.modo}")

    def _aggiorna_materie(self) -> None:
        quanti = int(self.periodo("materie"))
        dal = (date.today() - timedelta(days=quanti - 1)).isoformat()
        voci = self.db.studio_per_materia(dal, date.today().isoformat())[:9]
        totale = sum(m for _, m in voci)
        from ..tema import PALETTE_GRAFICI
        self.g_materie.imposta_dati(
            [(nome, float(minuti), PALETTE_GRAFICI[i % len(PALETTE_GRAFICI)])
             for i, (nome, minuti) in enumerate(voci)],
            durata(totale) if totale else "—", "studiate")
        self.contenitore.sezioni["materie"].imposta_nota(
            f"{durata(totale)} in {quanti} giorni")

    def _aggiorna_tabelle(self) -> None:
        scadenze = self.db.query(
            "SELECT * FROM scadenze WHERE area='accademica' ORDER BY fatta, data LIMIT 60")
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

        quanti = int(self.periodo("registro"))
        dal = (date.today() - timedelta(days=quanti - 1)).isoformat()
        voci = self.db.studio(dal, date.today().isoformat(), limite=300)
        self.tab_studio.setRowCount(len(voci))
        for i, v in enumerate(voci):
            cella = QTableWidgetItem(relativa(v["data"]))
            cella.setData(Qt.UserRole, v["id"])
            self.tab_studio.setItem(i, 0, cella)
            self.tab_studio.setItem(i, 1, QTableWidgetItem(v["materia"] or "—"))
            durata_cella = QTableWidgetItem(durata(v["minuti"]))
            durata_cella.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.tab_studio.setItem(i, 2, durata_cella)
            self.tab_studio.setItem(i, 3, QTableWidgetItem(v["argomento"]))
        self.contenitore.sezioni["registro"].imposta_nota(
            f"{durata(sum(v['minuti'] for v in voci))} in {quanti} giorni")
