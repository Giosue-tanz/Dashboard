"""Salute: attività, sonno, composizione corporea, allenamenti e costanza.

I dati si scrivono nella finestra «Inserimento dati», che si apre dal
pulsante in alto (o cliccando un giorno nella mappa della costanza).
"""
from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QGridLayout, QHBoxLayout, QHeaderView, QLabel,
                               QMenu, QPushButton, QTableWidget, QTableWidgetItem,
                               QWidget)

from ..braccialetto import RiquadroBraccialetto
from ..componenti import (COLORE_BATTITO, EtichettaACapo, EtichettaAlta,
                          NavigatorePeriodo, RigaMisura,
                          abilita_deselezione, binario, dati_battito,
                          etichetta, righe_indicatori, stile_tabella)
from ..andamento import FinestraAndamento
from ..dialoghi import (DialogoAllenamento, DialogoGiorno,
                        DialogoImporta)
from ..grafici import (Anello, BarraFasi, GraficoBarre, GraficoIntervalli,
                       GraficoLinea, MappaCalore)
from ..punteggi import PREDEFINITI
from ..utils import (data_it, durata, media, numero, relativa,
                     settimana_corrente, ultimi_giorni)
from . import VistaSezioni


class VistaSalute(VistaSezioni):
    titolo = "Salute"
    sottotitolo = "Attività, sonno e misure — i dati li metti tu"
    nome_nuovo = "+  Allenamento"

    chiave_vista = "salute"
    versione_layout = 5

    SEZIONI = {
        "oggi": "Oggi",
        "corpo": "Composizione",
        "costanza": "Costanza",
        "passi": "Passi",
        "sonno": "Sonno",
        "battito": "Battito",
        "indicatori": "Indicatori",
        "allenamenti": "Allenamenti",
        "peso": "Peso",
        "braccialetto": "Braccialetto",
    }
    DISPOSIZIONE = [["oggi", "corpo", "costanza"], ["passi", "sonno", "battito"],
                    ["indicatori", "allenamenti", "peso", "braccialetto"]]
    # la riga di mezzo tiene tre grafici con il loro navigatore: le serve
    # più aria delle altre
    ALTEZZE_PREDEFINITE = (0.31, 0.35, 0.34)
    LARGHEZZE_PREDEFINITE = ((), (0.34, 0.34, 0.32),
                             (0.24, 0.26, 0.22, 0.28))
    PERIODI_SEZIONE = {
        "peso": ({"30": "30 giorni", "90": "90 giorni", "180": "6 mesi",
                  "365": "un anno", "730": "due anni"}, "90"),
        "corpo": ({"30": "30 giorni", "90": "90 giorni", "180": "6 mesi",
                   "365": "un anno", "730": "due anni"}, "90"),
        "costanza": ({"2": "2 settimane", "4": "4 settimane", "8": "8 settimane",
                      "12": "12 settimane", "26": "6 mesi"}, "4"),
        "indicatori": ({"7": "7 giorni", "30": "30 giorni", "90": "90 giorni",
                        "365": "un anno"}, "7"),
        # il battito si guarda in due modi: le ore di una giornata, oppure
        # come è andato giorno per giorno
        "battito": ({"oggi": "oggi", "ieri": "ieri", "7": "7 giorni",
                     "14": "14 giorni", "30": "30 giorni",
                     "90": "90 giorni"}, "oggi"),
        "allenamenti": ({"7": "questa settimana", "30": "30 giorni",
                         "90": "90 giorni", "365": "un anno"}, "30"),
    }
    # ogni dato della costanza ha la sua tinta e il suo modo di dirsi
    COSTANZA = {
        "passi": ("Passi", "", "giorni camminati"),
        "sonno": ("Sonno", "#3d7bfd", "notti registrate"),
        "allenamenti": ("Allenamenti", "#ff9f45", "giorni di allenamento"),
    }

    def crea_sezioni(self) -> None:
        self.b_dati = QPushButton("Inserimento dati")
        self.b_dati.setToolTip(
            "Apre la finestra dove si scrivono passi, sonno, battito,\n"
            "peso e composizione corporea di un giorno.")
        self.b_dati.clicked.connect(lambda: self.apri_dati())
        self.b_andamento = QPushButton("Andamento")
        self.b_andamento.setToolTip(
            "Scorri i tuoi dati nel tempo: settimana, mese, trimestre, anno.\n"
            "Le frecce ‹ › tornano indietro un periodo alla volta.")
        self.b_andamento.clicked.connect(lambda: self.apri_andamento())
        self.b_importa = QPushButton("Importa dati…")
        self.b_importa.setToolTip(
            "Porta dentro Dashboard un'esportazione di Samsung Health\n"
            "(passi, sonno, battito, peso, allenamenti).")
        self.b_importa.clicked.connect(self.importa)
        self.azioni_intestazione = ([self.b_dati, self.b_andamento, self.b_importa]
                                   + self.azioni_intestazione)
        self.segnala_esportazioni()
        self.setAcceptDrops(True)      # si può lasciar cadere lo zip sulla pagina

        # ------------------------------------------------------------- oggi
        contenuto, lay = self.colonna(10)
        self.anello = Anello(self.c, self.c["accento"])
        self.anello.setMinimumHeight(120)
        lay.addWidget(self.anello, 1)
        self.riquadro_numeri = QWidget()
        self.riquadro_numeri.setObjectName("ContenutoSezione")
        self.lay_numeri = QGridLayout(self.riquadro_numeri)
        self.lay_numeri.setContentsMargins(0, 0, 0, 0)
        self.lay_numeri.setSpacing(6)
        lay.addWidget(self.riquadro_numeri)
        self.aggiungi("oggi", contenuto)

        # ------------------------------------------ composizione corporea
        contenuto, lay = self.colonna(8)
        self.et_peso = EtichettaAlta("—")
        self.et_peso.setObjectName("ValoreScheda")
        self.et_peso_nota = etichetta("", "NotaScheda")
        lay.addWidget(self.et_peso)
        lay.addWidget(self.et_peso_nota)
        self.barra_corpo = BarraFasi(self.c)
        lay.addWidget(self.barra_corpo)
        # compare solo quando manca qualcosa: le righe sotto dicono già tutto
        self.et_corpo_nota = EtichettaACapo("")
        self.et_corpo_nota.setObjectName("NotaScheda")
        self.et_corpo_nota.hide()
        lay.addWidget(self.et_corpo_nota)
        self.cont_corpo, self.lay_corpo = self.colonna(7)
        lay.addWidget(self.scorrevole(self.cont_corpo), 1)
        self.aggiungi("corpo", contenuto)

        # -------------------------------------------------------- costanza
        contenuto, lay = self.colonna(10)
        quale, self.pastiglie = binario(
            {k: nome for k, (nome, _, _) in self.COSTANZA.items()},
            next(iter(self.COSTANZA)), self._scegli_costanza)
        scelta = QHBoxLayout()
        scelta.setContentsMargins(0, 0, 0, 0)
        scelta.addWidget(quale)
        scelta.addStretch(1)
        lay.addLayout(scelta)

        self.mappa = MappaCalore(self.c)
        self.mappa.giorno_scelto.connect(self.apri_dati)
        self.mappa.setToolTip("Un quadretto per giorno: più è pieno, più sei andato "
                              "vicino all'obiettivo.\nClicca un giorno per scriverne "
                              "i dati.")
        lay.addWidget(self.mappa, 1)
        self.aggiungi("costanza", contenuto)

        # ------------------------------------------------------------ passi
        contenuto, lay = self.colonna(6)
        self.nav_passi = NavigatorePeriodo(self.c, "giorni")
        self.nav_passi.cambiato.connect(self._aggiorna_passi)
        lay.addWidget(self.nav_passi)
        self.g_passi = GraficoBarre(self.c)
        self.g_passi.formato = lambda v: numero(v, 0)
        self.g_passi.evidenzia_ultima = True
        self._apribile(self.g_passi, "passi")
        # la rotellina sul grafico scorre le settimane
        self.nav_passi.scorri_con_rotella(self.g_passi)
        lay.addWidget(self.g_passi, 1)
        self.aggiungi("passi", contenuto)

        # ------------------------------------------------------------ sonno
        contenuto, lay = self.colonna(8)
        self.et_sonno = EtichettaAlta("—")
        self.et_sonno.setObjectName("ValoreScheda")
        self.et_sonno_nota = etichetta("", "NotaScheda")
        # totale e nota sulla stessa riga: una riga in meno da far stare dentro
        self.et_sonno_nota.setAlignment(Qt.AlignRight | Qt.AlignBottom)
        testa = QHBoxLayout()
        testa.setSpacing(10)
        testa.addWidget(self.et_sonno)
        testa.addStretch(1)
        testa.addWidget(self.et_sonno_nota)
        lay.addLayout(testa)
        self.nav_sonno = NavigatorePeriodo(self.c, "giorni")
        self.nav_sonno.cambiato.connect(self._aggiorna_sonno)
        lay.addWidget(self.nav_sonno)
        self.fasi = BarraFasi(self.c)
        lay.addWidget(self.fasi)
        self.et_fasi = etichetta("", "NotaScheda")
        self.et_fasi.setWordWrap(True)
        lay.addWidget(self.et_fasi)
        self.g_sonno = GraficoBarre(self.c)
        self.g_sonno.formato = lambda v: durata(v)
        self.g_sonno.evidenzia_ultima = True
        self.g_sonno.setMinimumHeight(74)
        self._apribile(self.g_sonno, "sonno")
        self.nav_sonno.scorri_con_rotella(self.g_sonno)
        lay.addWidget(self.g_sonno, 1)
        # in poco spazio i pezzi si ritirano uno alla volta: meglio di un taglio
        self.lay_sonno = lay
        self.cont_sonno = contenuto
        self.sez_sonno = None       # arriva con aggiungi(), poco sotto
        contenuto.resizeEvent = lambda ev: self._adatta_sonno(
            ev.size().width(), ev.size().height())
        self.aggiungi("sonno", contenuto)
        self.sez_sonno = self.contenitore.sezioni["sonno"]

        # ---------------------------------------------------------- battito
        contenuto, lay = self.colonna(8)
        self.et_battito = EtichettaAlta("—")
        self.et_battito.setObjectName("ValoreScheda")
        self.et_battito_nota = etichetta("", "NotaScheda")
        self.et_battito_nota.setAlignment(Qt.AlignRight | Qt.AlignBottom)
        testa = QHBoxLayout()
        testa.setSpacing(10)
        testa.addWidget(self.et_battito)
        testa.addStretch(1)
        testa.addWidget(self.et_battito_nota)
        lay.addLayout(testa)
        self.g_battito = GraficoIntervalli(self.c, COLORE_BATTITO)
        self.g_battito.formato = lambda v: numero(v, 0)
        lay.addWidget(self.g_battito, 1)
        self.aggiungi("battito", contenuto)

        # ------------------------------------------------------- indicatori
        self.cont_ind, self.lay_ind = self.colonna(10)
        self.aggiungi("indicatori", self.scorrevole(self.cont_ind))

        # ------------------------------------------------------ allenamenti
        self.tab = QTableWidget(0, 5)
        self.tab.setHorizontalHeaderLabels(["Data", "Tipo", "Durata", "Distanza", "Kcal"])
        self.tab.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tab.setSelectionBehavior(QTableWidget.SelectRows)
        self.tab.doubleClicked.connect(self._modifica_allenamento)
        self.tab.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tab.customContextMenuRequested.connect(self._menu_allenamento)
        h = self.tab.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.Stretch)
        for colonna in (2, 3, 4):
            h.setSectionResizeMode(colonna, QHeaderView.ResizeToContents)
        abilita_deselezione(self.tab)
        stile_tabella(self.tab)
        self.aggiungi("allenamenti", self.tab)

        # ------------------------------------------------------------- peso
        self.g_peso = GraficoLinea(self.c)
        self.g_peso.formato = lambda v: numero(v, 1)
        self._apribile(self.g_peso, "peso")
        self.aggiungi("peso", self.g_peso)
        self._crea_braccialetto()

        self.grafici = [self.g_passi, self.g_sonno, self.g_peso, self.anello,
                        self.fasi, self.barra_corpo, self.mappa]

    # ------------------------------------------------------------- comandi
    def nuovo(self) -> None:
        dlg = DialogoAllenamento(parent=self)
        if dlg.exec():
            self.db.salva_allenamento(dlg.dati())
            self._dopo_salvataggio()

    def apri_andamento(self, campo: str = "passi") -> None:
        """Apre la finestra che scorre i dati passati, sul dato scelto."""
        finestra = FinestraAndamento(self.db, self.c, campo, parent=self)
        finestra.giorno_scelto.connect(self.apri_dati)
        finestra.exec()
        self.aggiorna()

    def _apribile(self, widget, campo: str) -> None:
        """Doppio clic su un grafico o una riga: si apre l'andamento di quel dato."""
        widget.setCursor(Qt.PointingHandCursor)
        widget.mouseDoubleClickEvent = (
            lambda _ev, c=campo: self.apri_andamento(c))

    def apri_dati(self, giorno: str = "") -> None:
        """Apre la finestra dei dati, eventualmente già sul giorno scelto."""
        dialogo = DialogoGiorno(self.db, self.c, giorno, parent=self)
        dialogo.salvato.connect(lambda _: self._dopo_salvataggio())
        dialogo.exec()

    def dragEnterEvent(self, evento):
        if evento.mimeData().hasUrls():
            evento.acceptProposedAction()

    def dropEvent(self, evento):
        for url in evento.mimeData().urls():
            if url.isLocalFile():
                evento.acceptProposedAction()
                self.importa(url.toLocalFile())
                return

    def importa(self, percorso: str = "") -> None:
        """Importa un'esportazione di Samsung Health scaricata dal telefono."""
        dialogo = DialogoImporta(self.db, percorso, self.c, parent=self)
        dialogo.exec()
        self.segnala_esportazioni()
        if dialogo.importati:
            self._dopo_salvataggio()

    def segnala_esportazioni(self) -> None:
        """Se in «Scaricati» c'è un'esportazione nuova, il pulsante lo dice."""
        from datetime import date as _date

        from ..importa import esportazioni_trovate
        try:
            trovate = esportazioni_trovate()
        except Exception:
            trovate = []
        ultima = self.db.leggi("ultima_importazione_quando", "")
        nuova = bool(trovate) and (not ultima or trovate[0][1] > float(ultima))
        if nuova:
            giorno = data_it(_date.fromtimestamp(trovate[0][1]).isoformat())
            self.b_importa.setText("Importa dati…  ●")
            self.b_importa.setStyleSheet(
                f"border-color: {self.c['accento']}; color: {self.c['accento']};")
            self.b_importa.setToolTip(
                f"Trovata un'esportazione di Samsung Health del {giorno}:\n"
                f"{trovate[0][0]}")
        else:
            self.b_importa.setText("Importa dati…")
            self.b_importa.setStyleSheet("")
            self.b_importa.setToolTip(
                "Porta dentro Dashboard un'esportazione di Samsung Health\n"
                "(passi, sonno, battito, peso, allenamenti).")

    def _dopo_salvataggio(self) -> None:
        self.aggiorna()
        self.dati_cambiati.emit()

    def _allenamento_scelto(self):
        righe = self.tab.selectionModel().selectedRows()
        if not righe:
            return None
        id_ = self.tab.item(righe[0].row(), 0).data(Qt.UserRole)
        return self.db.uno("SELECT * FROM allenamenti WHERE id=?", (id_,))

    def _modifica_allenamento(self) -> None:
        voce = self._allenamento_scelto()
        if voce is None:
            return
        dlg = DialogoAllenamento(voce, parent=self)
        if dlg.exec():
            self.db.salva_allenamento(dlg.dati())
            self._dopo_salvataggio()

    def _menu_allenamento(self, punto) -> None:
        voce = self._allenamento_scelto()
        if voce is None:
            return
        menu = QMenu(self)
        menu.addAction("Modifica", self._modifica_allenamento)
        menu.addAction("Elimina", lambda: (self.db.elimina("allenamenti", voce["id"]),
                                           self._dopo_salvataggio()))
        menu.exec(self.tab.viewport().mapToGlobal(punto))

    # ---------------------------------------------------------------- dati
    def aggiorna(self) -> None:
        self._aggiorna_oggi()
        self._aggiorna_corpo()
        self._aggiorna_costanza()
        self._aggiorna_passi()
        self._aggiorna_sonno()
        self._aggiorna_indicatori()
        self._aggiorna_allenamenti()
        self._aggiorna_battito()
        self._aggiorna_peso()

    def _numero(self, valore: str, nota: str, colore: str, colonna: int) -> None:
        v = QLabel(valore)
        v.setAlignment(Qt.AlignCenter)
        v.setStyleSheet(f"color: {colore}; font-size: 17px; font-weight: 700;")
        n = QLabel(nota)
        n.setObjectName("NotaScheda")
        n.setAlignment(Qt.AlignCenter)
        self.lay_numeri.addWidget(v, 0, colonna)
        self.lay_numeri.addWidget(n, 1, colonna)

    def _aggiorna_oggi(self) -> None:
        while self.lay_numeri.count():
            w = self.lay_numeri.takeAt(0).widget()
            if w is not None:
                w.hide(); w.setParent(None); w.deleteLater()
        oggi = date.today().isoformat()
        r = self.db.salute_giorno(oggi)
        obiettivo = self.db.leggi_num("obiettivo_passi", PREDEFINITI["obiettivo_passi"])
        passi = int(r["passi"]) if r else 0
        quota = passi / obiettivo if obiettivo else 0
        self.anello.imposta(quota, f"{quota * 100:.0f}%" if passi else "—",
                            "dell'obiettivo" if passi else "nessun dato")
        self._numero(numero(passi, 0) if passi else "—", "passi", self.c["accento"], 0)
        self._numero(numero(r["kcal"], 0) if r and r["kcal"] else "—",
                     "kcal attive", "#f7913a", 1)
        self._numero(numero(r["km"], 1) if r and r["km"] else "—", "km", "#35c4d7", 2)
        self.contenitore.sezioni["oggi"].imposta_nota(
            f"obiettivo {numero(obiettivo, 0)} passi")

    # --------------------------------------------- composizione corporea
    def _aggiorna_corpo(self) -> None:
        """Peso, com'è fatto e come si muove: grassa, muscolare, massa secca."""
        self.svuota(self.lay_corpo)
        quanti = int(self.periodo("corpo"))
        elenco = ultimi_giorni(quanti)
        dati = self.db.giorni_salute(elenco[0], elenco[-1])

        def serie(campo: str) -> list[tuple[str, float]]:
            return [(g, float(dati[g][campo])) for g in elenco
                    if g in dati and dati[g][campo]]

        pesi, grassi, muscoli = serie("peso"), serie("grasso"), serie("muscolo")
        if not pesi and not grassi and not muscoli:
            self.et_peso.setText("—")
            self.et_peso_nota.setText("nessuna misura in questo periodo")
            self.barra_corpo.imposta_dati([])
            self.barra_corpo.setToolTip("")
            self.et_corpo_nota.hide()
            self.lay_corpo.addWidget(etichetta(
                "Peso, massa grassa e massa muscolare si scrivono nella finestra "
                "«Inserimento dati».", "NotaScheda"))
            invito = QPushButton("Inserimento dati")
            invito.clicked.connect(lambda: self.apri_dati())
            self.lay_corpo.addWidget(invito)
            self.lay_corpo.addStretch(1)
            return

        peso = pesi[-1][1] if pesi else 0.0
        grasso = grassi[-1][1] if grassi else 0.0
        muscolo = muscoli[-1][1] if muscoli else 0.0
        kg_grassa = peso * grasso / 100
        kg_muscolo = peso * muscolo / 100
        secca = peso - kg_grassa

        def variazione(valori, unita: str) -> str:
            if len(valori) < 2:
                return "unica misura"
            scostamento = valori[-1][1] - valori[0][1]
            segno = "+" if scostamento > 0 else "−"
            return f"{segno}{numero(abs(scostamento), 1)} {unita} in {quanti} giorni"

        ultima = (pesi or grassi or muscoli)[-1][0]
        self.et_peso.setText(f"{numero(peso, 1)} kg" if peso else f"{numero(grasso, 1)} %")
        if pesi:
            coda = (f" · min {numero(min(v for _, v in pesi), 1)} · "
                    f"max {numero(max(v for _, v in pesi), 1)} kg"
                    if len(pesi) > 1 else "")
            self.et_peso_nota.setText(
                f"{relativa(ultima)} · {variazione(pesi, 'kg')}{coda}")
        else:
            self.et_peso_nota.setText(relativa(ultima))

        # la barra: com'è diviso il peso, non quanto pesa
        if peso and (grasso or muscolo):
            resto = max(0.0, peso - kg_grassa - kg_muscolo)
            fette = [("grassa", kg_grassa, "#f7913a"),
                     ("muscolare", kg_muscolo, "#6c8cff"),
                     ("resto", resto, self.c["griglia"])]
            self.barra_corpo.imposta_dati([f for f in fette if f[1] > 0])
            self.barra_corpo.setToolTip("   ·   ".join(
                f"massa {n}: {numero(v, 1)} kg" for n, v, _ in fette if v > 0))
            self.et_corpo_nota.hide()
        else:
            self.barra_corpo.imposta_dati([("peso", max(peso, 1.0), self.c["accento"])])
            self.barra_corpo.setToolTip("")
            self.et_corpo_nota.setText(
                "senza massa grassa il peso resta un numero solo: scrivila in "
                "«Inserimento dati».")
            self.et_corpo_nota.show()

        if grassi:
            riga_corpo = RigaMisura(
                self.c, "◍", "Massa grassa",
                f"{numero(kg_grassa, 1)} kg del peso" if peso else "percentuale",
                f"{numero(grasso, 1)} %", variazione(grassi, "punti"),
                int(grasso), "#f7913a")
            self._apribile(riga_corpo, "grasso")
            self.lay_corpo.addWidget(riga_corpo)
        if muscoli:
            riga_corpo = RigaMisura(
                self.c, "⟡", "Massa muscolare",
                f"{numero(kg_muscolo, 1)} kg del peso" if peso else "percentuale",
                f"{numero(muscolo, 1)} %", variazione(muscoli, "punti"),
                int(muscolo), "#6c8cff")
            self._apribile(riga_corpo, "muscolo")
            self.lay_corpo.addWidget(riga_corpo)
        if pesi and grassi:
            riga_corpo = RigaMisura(
                self.c, "◆", "Massa secca", "il peso meno la massa grassa",
                f"{numero(secca, 1)} kg", f"{numero(100 - grasso, 1)} % del peso",
                int(100 - grasso), self.c["accento"])
            self._apribile(riga_corpo, "peso")
            self.lay_corpo.addWidget(riga_corpo)
        self.lay_corpo.addStretch(1)

    # ------------------------------------------------------------ costanza
    def dato_costanza(self) -> str:
        """Quale dato mostra la mappa: passi, sonno o allenamenti."""
        scelto = self.db.leggi("costanza_dato", "passi")
        return scelto if scelto in self.COSTANZA else "passi"

    def _scegli_costanza(self, chiave: str) -> None:
        self.db.imposta("costanza_dato", chiave)
        self._aggiorna_costanza()

    def _aggiorna_costanza(self) -> None:
        """Un quadretto per giorno: quanto spesso ci sei stato davvero."""
        dato = self.dato_costanza()
        for chiave, b in self.pastiglie.items():
            b.setChecked(chiave == dato)
        nome, tinta, cosa = self.COSTANZA[dato]
        colore = tinta or self.c["accento"]

        settimane = int(self.periodo("costanza"))
        oggi = date.today()
        inizio = oggi - timedelta(days=oggi.weekday() + 7 * (settimane - 1))
        elenco = [(inizio + timedelta(days=i)).isoformat()
                  for i in range((oggi - inizio).days + 1)]

        valori: dict[str, float] = {}
        if dato == "allenamenti":
            obiettivo = 45.0
            for a in self.db.allenamenti(elenco[0], elenco[-1]):
                valori[a["data"]] = valori.get(a["data"], 0.0) + float(a["minuti"])
        else:
            obiettivo = self.db.leggi_num(f"obiettivo_{dato}",
                                          PREDEFINITI[f"obiettivo_{dato}"])
            valori.update(dict(self.db.serie_salute(dato, elenco[0], elenco[-1])))

        def misura(valore: float) -> str:
            return (f"{numero(valore, 0)} passi" if dato == "passi"
                    else durata(int(valore)))

        self.mappa.imposta_dati(
            elenco,
            {g: (min(1.0, v / obiettivo) if obiettivo else 1.0, colore)
             for g, v in valori.items()},
            {g: f"{data_it(g)} · {misura(v)}" for g, v in valori.items()})

        # ------------------------------------------------- il riassunto sotto
        raggiunti = sum(1 for v in valori.values() if v >= obiettivo)
        serie = migliore = 0
        for giorno in elenco:
            if valori.get(giorno, 0) >= obiettivo:
                serie += 1
                migliore = max(migliore, serie)
            else:
                serie = 0
        attuale = 0
        for giorno in reversed(elenco):
            if valori.get(giorno, 0) >= obiettivo:
                attuale += 1
            elif giorno != oggi.isoformat():   # oggi non è ancora finito
                break

        quota = round(raggiunti / len(elenco) * 100) if elenco else 0
        if not valori:
            riassunto = f"nessun dato di {nome.lower()}"
        else:
            riassunto = (f"{raggiunti}/{len(elenco)} centrati · "
                         f"media {misura(media(list(valori.values())))}")
            if attuale > 1:
                riassunto += f" · serie di {attuale}"
        self.mappa.setToolTip(
            f"{cosa.capitalize()}: {len(valori)} giorni su {len(elenco)}.\n"
            f"Obiettivo raggiunto {raggiunti} volte ({quota}%), "
            f"meglio {migliore} di fila.\n"
            "Più il quadretto è pieno, più sei andato vicino all'obiettivo: "
            "clicca un giorno per scriverne i dati.")
        self.contenitore.sezioni["costanza"].imposta_nota(riassunto)

    def _aggiorna_passi(self) -> None:
        """I passi nel modo scelto: un giorno per barra, o una settimana, o un mese."""
        finestre = self.nav_passi.finestre()
        giornaliero = self.db.leggi_num("obiettivo_passi",
                                        PREDEFINITI["obiettivo_passi"])
        barre, valori = [], []
        for etichetta_barra, dal, al in finestre:
            giorni_dentro = self.db.giorni_salute(dal, al)
            somma = sum(float(r["passi"]) for r in giorni_dentro.values() if r["passi"])
            con_dati = any(r["passi"] for r in giorni_dentro.values())
            barre.append((etichetta_barra, [somma if con_dati else None]))
            if con_dati:
                valori.append(somma)
        # l'obiettivo è al giorno: su settimane e mesi va moltiplicato
        quanti_giorni = {"giorni": 1, "settimane": 7, "mesi": 30}[self.nav_passi.modo]
        self.g_passi.riferimento = giornaliero * quanti_giorni
        self.g_passi.imposta_dati(barre, [("passi", self.c["accento"])])
        raggiunti = sum(1 for v in valori if v >= self.g_passi.riferimento)
        self.contenitore.sezioni["passi"].imposta_nota(
            f"media {numero(media(valori), 0)} · obiettivo raggiunto "
            f"{raggiunti} volte su {len(valori)}"
            if valori else "nessun dato")

    def _crea_braccialetto(self) -> None:
        """Il riquadro del braccialetto: non si collega finché non glielo dici."""
        self.riquadro_banda = RiquadroBraccialetto(self.db, self.c)
        self.riquadro_banda.dati_cambiati.connect(self.dati_cambiati)
        self.aggiungi("braccialetto", self.riquadro_banda)

    def _adatta_sonno(self, larghezza: int, altezza: int) -> None:
        """In poco spazio il riquadro si sfoltisce invece di tagliarsi.

        Le soglie non sono numeri fissi: si ricavano da quanto chiedono i
        pezzi, così valgono anche con il testo ingrandito. In verticale se ne
        va prima la legenda delle fasi, poi la barra; il totale e il grafico
        restano sempre. In orizzontale sparisce la nota accanto al totale.
        """
        def alto(widget) -> int:
            # la barra delle fasi ha un'altezza fissa e nessun suggerimento
            return max(widget.sizeHint().height(), widget.minimumHeight(), 0)

        self.et_sonno_nota.setVisible(
            larghezza >= self.et_sonno.sizeHint().width() + 10
            + self.et_sonno_nota.sizeHint().width())
        spazio = self.lay_sonno.spacing()
        serve = alto(self.et_sonno) + spazio + self.g_sonno.minimumHeight()
        # sotto al totale più il grafico non si scende: i divisori si fermano
        # prima, invece di tagliare le barre. La misura si prende qui, non alla
        # costruzione: prima che il tema sia applicato i caratteri sono altri
        if self.sez_sonno is not None and self.cont_sonno.minimumHeight() != serve:
            chrome = max(0, self.sez_sonno.height() - altezza)
            self.cont_sonno.setMinimumHeight(serve)
            self.sez_sonno.setMinimumHeight(serve + chrome)
        for widget in (self.fasi, self.et_fasi):
            serve += alto(widget) + spazio
            widget.setVisible(altezza >= serve)

    def _aggiorna_sonno(self) -> None:
        """Il sonno nel modo scelto. Le fasi sono sempre quelle di una notte:
        l'ultima con dati dentro l'intervallo che stai guardando."""
        finestre = self.nav_sonno.finestre()
        dal, al = finestre[0][1], finestre[-1][2]
        dati = self.db.giorni_salute(dal, al)
        scelto_dal, scelto_al = self.nav_sonno.scelto()
        notti = [r for g, r in sorted(dati.items())
                 if scelto_dal <= g <= scelto_al and r["sonno"]]
        ultimo = notti[-1] if notti else None
        tutte = [float(r["sonno"]) for r in dati.values() if r["sonno"]]

        if ultimo is None:
            self.et_sonno.setText("—")
            self.et_sonno_nota.setText("nessuna notte registrata")
            self.fasi.imposta_dati([])
            self.et_fasi.setText("")
            self._barre_sonno(finestre, dati)
            return

        totale = int(ultimo["sonno"])
        if self.nav_sonno.modo == "giorni":
            grande, nota_quando = totale, relativa(ultimo["data"])
        else:
            # su settimane e mesi il numero grande è la media per notte
            dentro = [float(r["sonno"]) for g, r in dati.items()
                      if scelto_dal <= g <= scelto_al and r["sonno"]]
            grande = int(media(dentro))
            nota_quando = f"media di {len(dentro)} notti"
        self.et_sonno.setText(durata(grande))
        scostamento = grande - media(tutte)
        segno = "+" if scostamento >= 0 else "−"
        self.et_sonno_nota.setText(
            f"{nota_quando} · {segno}{durata(abs(scostamento))} sulla media")

        dettagliate = (int(ultimo["sonno_profondo"]) + int(ultimo["sonno_rem"])
                       + int(ultimo["sonno_sveglio"]))
        if not dettagliate:
            # senza fasi registrate non si finge di conoscerle
            self.fasi.imposta_dati([("sonno", float(totale), "#6c8cff")])
            self.et_fasi.setText("fasi non registrate per questa notte")
            self.et_fasi.setTextFormat(Qt.PlainText)
            self._barre_sonno(finestre, dati)
            return
        leggero = max(0, totale - int(ultimo["sonno_profondo"])
                      - int(ultimo["sonno_rem"]) - int(ultimo["sonno_sveglio"]))
        self.fasi.imposta_dati([
            ("profondo", float(ultimo["sonno_profondo"]), "#6c8cff"),
            ("leggero", float(leggero), "#35c4d7"),
            ("REM", float(ultimo["sonno_rem"]), "#b07cff"),
            ("sveglio", float(ultimo["sonno_sveglio"]), self.c["griglia"]),
        ])
        pezzi = [("profondo", ultimo["sonno_profondo"], "#6c8cff"),
                 ("leggero", leggero, "#35c4d7"),
                 ("REM", ultimo["sonno_rem"], "#b07cff"),
                 ("sveglio", ultimo["sonno_sveglio"], self.c["testo2"])]
        legenda = "   ".join(
            f"<span style='color:{col}'>●</span> {nome} {durata(v)}"
            for nome, v, col in pezzi if v) or "fasi non registrate"
        if self.nav_sonno.modo != "giorni":
            legenda += f"   <span style='color:{self.c['testo2']}'>" \
                       f"(notte del {data_it(ultimo['data'])[:5]})</span>"
        self.et_fasi.setText(legenda)
        self.et_fasi.setTextFormat(Qt.RichText)
        self._barre_sonno(finestre, dati)

    def _barre_sonno(self, finestre, dati) -> None:
        """Le barre del sonno: una notte per barra, o la media di ogni
        settimana o mese."""
        self.g_sonno.riferimento = self.db.leggi_num(
            "obiettivo_sonno", PREDEFINITI["obiettivo_sonno"])
        barre, valori = [], []
        for etichetta_barra, dal, al in finestre:
            dentro = [float(r["sonno"]) for g, r in dati.items()
                      if dal <= g <= al and r["sonno"]]
            valore = media(dentro) if dentro else None
            barre.append((etichetta_barra, [valore]))
            if dentro:
                valori.extend(dentro)
        self.g_sonno.imposta_dati(barre, [("sonno", "#6c8cff")])
        self.contenitore.sezioni["sonno"].imposta_nota(
            f"media {durata(media(valori))} su {len(valori)} notti"
            if valori else "nessun dato")

    def _aggiorna_battito(self) -> None:
        """Il battito: le ore di una giornata, o come è andato giorno per giorno.

        Non si disegna una barra da zero: in un'ora il cuore sta fra un minimo
        e un massimo, e quello che conta è l'intervallo. Il puntino chiaro
        dentro la capsula è la media.
        """
        scelta = self.periodo("battito")
        dati, riposo, nota = dati_battito(self.db, scelta)
        self.g_battito.imposta_dati(dati)
        self.et_battito_nota.setText(nota)
        if riposo:
            self.et_battito.setText(str(riposo))
            self.et_battito.setStyleSheet(
                f"color: {COLORE_BATTITO}; font-weight: 700;")
            self.contenitore.sezioni["battito"].imposta_nota(
                "bpm a riposo" if scelta in ("oggi", "ieri")
                else "bpm a riposo, in media")
        else:
            self.et_battito.setText("—")
            self.et_battito.setStyleSheet("")
            self.contenitore.sezioni["battito"].imposta_nota(
                "il braccialetto non ha ancora dato misure")

    def _aggiorna_indicatori(self) -> None:
        self.svuota(self.lay_ind)
        quanti = int(self.periodo("indicatori"))
        righe = righe_indicatori(self.db, self.c, quanti)
        for campo, misura in righe:
            misura.setToolTip("Doppio clic per scorrere l'andamento di questo dato.")
            self._apribile(misura, campo)
            self.lay_ind.addWidget(misura)
        if not righe:
            self.lay_ind.addWidget(etichetta(
                "Battito, variabilità, stress e acqua si scrivono nella "
                "finestra «Inserimento dati», in alto — oppure li porta il "
                "braccialetto.", "NotaScheda"))
        self.lay_ind.addStretch(1)

    def _aggiorna_allenamenti(self) -> None:
        quanti = int(self.periodo("allenamenti"))
        elenco = ultimi_giorni(quanti)
        voci = self.db.allenamenti(elenco[0], elenco[-1])
        self.tab.setRowCount(len(voci))
        for i, a in enumerate(voci):
            cella = QTableWidgetItem(relativa(a["data"]))
            cella.setData(Qt.UserRole, a["id"])
            cella.setToolTip(data_it(a["data"]))
            self.tab.setItem(i, 0, cella)
            self.tab.setItem(i, 1, QTableWidgetItem(a["tipo"]))
            self.tab.setItem(i, 2, QTableWidgetItem(durata(a["minuti"])))
            self.tab.setItem(i, 3, QTableWidgetItem(
                f"{numero(a['km'], 1)} km" if a["km"] else "—"))
            self.tab.setItem(i, 4, QTableWidgetItem(
                numero(a["kcal"], 0) if a["kcal"] else "—"))
            for colonna in (2, 3, 4):
                self.tab.item(i, colonna).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        dal, al = settimana_corrente()
        questa = len(self.db.allenamenti(dal, al))
        obiettivo = self.db.leggi_num("obiettivo_allenamenti",
                                      PREDEFINITI["obiettivo_allenamenti"])
        minuti = sum(a["minuti"] for a in voci)
        self.contenitore.sezioni["allenamenti"].imposta_nota(
            f"{questa} su {obiettivo:.0f} questa settimana · {durata(minuti)} in totale")

    def _aggiorna_peso(self) -> None:
        quanti = int(self.periodo("peso"))
        elenco = ultimi_giorni(quanti)
        serie = self.db.serie_salute("peso", elenco[0], elenco[-1])
        self.g_peso.imposta_dati([(data_it(g)[:5], v) for g, v in serie],
                                 "#35c4d7", "peso")
        if len(serie) >= 2:
            scostamento = serie[-1][1] - serie[0][1]
            segno = "+" if scostamento > 0 else "−"
            self.contenitore.sezioni["peso"].imposta_nota(
                f"{numero(serie[-1][1], 1)} kg · {segno}{numero(abs(scostamento), 1)} "
                f"in {quanti} giorni")
        else:
            self.contenitore.sezioni["peso"].imposta_nota(f"{quanti} giorni")
