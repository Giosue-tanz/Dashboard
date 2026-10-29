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

from ..componenti import RigaMisura, abilita_deselezione, etichetta, stile_tabella
from ..andamento import FinestraAndamento
from ..dialoghi import (DialogoAllenamento, DialogoGiorno,
                        DialogoImporta)
from ..grafici import (Anello, BarraFasi, GraficoBarre, GraficoLinea,
                       MappaCalore)
from ..punteggi import PREDEFINITI
from ..utils import (data_it, durata, media, numero, relativa,
                     settimana_corrente, ultimi_giorni)
from . import VistaSezioni


class VistaSalute(VistaSezioni):
    titolo = "Salute"
    sottotitolo = "Attività, sonno e misure — i dati li metti tu"
    nome_nuovo = "+  Allenamento"

    chiave_vista = "salute"
    versione_layout = 3

    SEZIONI = {
        "oggi": "Oggi",
        "corpo": "Composizione",
        "costanza": "Costanza",
        "passi": "Passi",
        "sonno": "Sonno",
        "indicatori": "Indicatori",
        "allenamenti": "Allenamenti",
        "peso": "Peso",
    }
    DISPOSIZIONE = [["oggi", "corpo", "costanza"], ["passi", "sonno"],
                    ["indicatori", "allenamenti", "peso"]]
    ALTEZZE_PREDEFINITE = (0.38, 0.29, 0.33)
    PERIODI_SEZIONE = {
        "passi": ({"7": "7 giorni", "14": "14 giorni", "30": "30 giorni",
                   "90": "90 giorni", "180": "6 mesi"}, "14"),
        "sonno": ({"7": "7 giorni", "14": "14 giorni", "30": "30 giorni",
                   "90": "90 giorni", "180": "6 mesi"}, "14"),
        "peso": ({"30": "30 giorni", "90": "90 giorni", "180": "6 mesi",
                  "365": "un anno", "730": "due anni"}, "90"),
        "corpo": ({"30": "30 giorni", "90": "90 giorni", "180": "6 mesi",
                   "365": "un anno", "730": "due anni"}, "90"),
        "costanza": ({"2": "2 settimane", "4": "4 settimane", "8": "8 settimane",
                      "12": "12 settimane", "26": "6 mesi"}, "4"),
        "indicatori": ({"7": "7 giorni", "30": "30 giorni", "90": "90 giorni",
                        "365": "un anno"}, "7"),
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
        self.et_peso = QLabel("—")
        self.et_peso.setObjectName("ValoreScheda")
        self.et_peso_nota = etichetta("", "NotaScheda")
        lay.addWidget(self.et_peso)
        lay.addWidget(self.et_peso_nota)
        self.barra_corpo = BarraFasi(self.c)
        lay.addWidget(self.barra_corpo)
        # compare solo quando manca qualcosa: le righe sotto dicono già tutto
        self.et_corpo_nota = etichetta("", "NotaScheda")
        self.et_corpo_nota.setWordWrap(True)
        self.et_corpo_nota.hide()
        lay.addWidget(self.et_corpo_nota)
        self.cont_corpo, self.lay_corpo = self.colonna(7)
        lay.addWidget(self.scorrevole(self.cont_corpo), 1)
        self.aggiungi("corpo", contenuto)

        # -------------------------------------------------------- costanza
        contenuto, lay = self.colonna(10)
        scelta = QHBoxLayout()
        scelta.setContentsMargins(0, 0, 0, 0)
        scelta.setSpacing(6)
        self.pastiglie: dict[str, QPushButton] = {}
        for chiave, (nome, _, _) in self.COSTANZA.items():
            b = QPushButton(nome)
            b.setObjectName("Segmento")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=chiave: self._scegli_costanza(k))
            self.pastiglie[chiave] = b
            scelta.addWidget(b)
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
        self.g_passi = GraficoBarre(self.c)
        self.g_passi.formato = lambda v: numero(v, 0)
        self.g_passi.evidenzia_ultima = True
        self._apribile(self.g_passi, "passi")
        self.aggiungi("passi", self.g_passi)

        # ------------------------------------------------------------ sonno
        contenuto, lay = self.colonna(8)
        self.et_sonno = QLabel("—")
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
        lay.addWidget(self.g_sonno, 1)
        # in poco spazio i pezzi si ritirano uno alla volta: meglio di un taglio
        self.lay_sonno = lay
        self.cont_sonno = contenuto
        self.sez_sonno = None       # arriva con aggiungi(), poco sotto
        contenuto.resizeEvent = lambda ev: self._adatta_sonno(
            ev.size().width(), ev.size().height())
        self.aggiungi("sonno", contenuto)
        self.sez_sonno = self.contenitore.sezioni["sonno"]

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
        self.contenitore.sezioni["oggi"].imposta_periodo(
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
        self.contenitore.sezioni["costanza"].imposta_periodo(
            f"{self._nome_periodo('costanza')} · {riassunto}")

    def _aggiorna_passi(self) -> None:
        quanti = int(self.periodo("passi"))
        elenco = ultimi_giorni(quanti)
        dati = self.db.giorni_salute(elenco[0], elenco[-1])
        self.g_passi.riferimento = self.db.leggi_num(
            "obiettivo_passi", PREDEFINITI["obiettivo_passi"])
        self.g_passi.imposta_dati(
            [(data_it(g)[:5], [float(dati[g]["passi"]) if g in dati and dati[g]["passi"]
                               else None])
             for g in elenco],
            [("passi", self.c["accento"])])
        valori = [float(dati[g]["passi"]) for g in elenco
                  if g in dati and dati[g]["passi"]]
        raggiunti = sum(1 for v in valori if v >= self.g_passi.riferimento)
        self.contenitore.sezioni["passi"].imposta_periodo(
            f"{quanti} giorni · {len(valori)} con dati · "
            f"media {numero(media(valori), 0)} · obiettivo raggiunto {raggiunti} volte"
            if valori else f"{quanti} giorni · nessun dato")

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
        quanti = int(self.periodo("sonno"))
        elenco = ultimi_giorni(quanti)
        dati = self.db.giorni_salute(elenco[0], elenco[-1])
        ultimo = None
        for g in reversed(elenco):
            if g in dati and dati[g]["sonno"]:
                ultimo = dati[g]
                break
        if ultimo is None:
            self.et_sonno.setText("—")
            self.et_sonno_nota.setText("nessuna notte registrata")
            self.fasi.imposta_dati([])
            self.et_fasi.setText("")
        else:
            totale = int(ultimo["sonno"])
            self.et_sonno.setText(durata(totale))
            medie = media([float(dati[g]["sonno"]) for g in elenco
                           if g in dati and dati[g]["sonno"]])
            scostamento = totale - medie
            segno = "+" if scostamento >= 0 else "−"
            self.et_sonno_nota.setText(
                f"{relativa(ultimo['data'])} · {segno}{durata(abs(scostamento))} "
                f"sulla media di {quanti} giorni")
            dettagliate = (int(ultimo["sonno_profondo"]) + int(ultimo["sonno_rem"])
                           + int(ultimo["sonno_sveglio"]))
            if not dettagliate:
                # senza fasi registrate non si finge di conoscerle
                self.fasi.imposta_dati([("sonno", float(totale), "#6c8cff")])
                self.et_fasi.setText("fasi non registrate per questa notte")
                self.et_fasi.setTextFormat(Qt.PlainText)
                self._barre_sonno(elenco, dati, quanti)
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
            self.et_fasi.setText("   ".join(
                f"<span style='color:{col}'>●</span> {nome} {durata(v)}"
                for nome, v, col in pezzi if v) or "fasi non registrate")
            self.et_fasi.setTextFormat(Qt.RichText)

        self._barre_sonno(elenco, dati, quanti)

    def _barre_sonno(self, elenco, dati, quanti: int) -> None:
        """Le barre delle ultime notti, sotto alla barra delle fasi."""
        self.g_sonno.riferimento = self.db.leggi_num(
            "obiettivo_sonno", PREDEFINITI["obiettivo_sonno"])
        self.g_sonno.imposta_dati(
            [(data_it(g)[:5], [float(dati[g]["sonno"]) if g in dati and dati[g]["sonno"]
                               else None])
             for g in elenco],
            [("sonno", "#6c8cff")])
        valori = [float(dati[g]["sonno"]) for g in elenco if g in dati and dati[g]["sonno"]]
        self.contenitore.sezioni["sonno"].imposta_periodo(
            f"media {durata(media(valori))} su {len(valori)} notti di {quanti} giorni"
            if valori else f"{quanti} giorni · nessun dato")

    def _aggiorna_indicatori(self) -> None:
        self.svuota(self.lay_ind)
        quanti = int(self.periodo("indicatori"))
        elenco = ultimi_giorni(quanti)
        dati = self.db.giorni_salute(elenco[0], elenco[-1])
        oggi = self.db.salute_giorno(date.today().isoformat())

        def valori(campo):
            return [float(r[campo]) for r in dati.values() if r[campo]]

        acqua_obiettivo = self.db.leggi_num("obiettivo_acqua", PREDEFINITI["obiettivo_acqua"])
        voci = [
            ("❤", "Battito a riposo", "battito", "bpm", "#ef5f5c", 0),
            ("〰", "Variabilità (HRV)", "hrv", "ms", self.c["accento"], 0),
            ("💧", "Acqua", "acqua", "L", "#6c8cff", acqua_obiettivo),
        ]
        presenti = 0
        for simbolo, nome, campo, unita, colore, obiettivo in voci:
            serie = valori(campo)
            if not serie and not (oggi and oggi[campo]):
                continue
            presenti += 1
            attuale = float(oggi[campo]) if oggi and oggi[campo] else (serie[-1] if serie else 0)
            decimali = 0 if campo in ("battito", "hrv") else 1
            if obiettivo:
                quota = int(min(100, attuale / obiettivo * 100))
            elif campo == "battito":
                quota = int(max(0.0, min(100.0, (85 - attuale) / 40 * 100)))
            elif campo == "hrv":
                quota = int(max(0.0, min(100.0, attuale / 80 * 100)))
            else:
                quota = int(min(100, (attuale / max(serie) * 100) if serie else 0))
            nota = (f"obiettivo {numero(obiettivo, 1)} {unita}" if obiettivo
                    else f"media {numero(media(serie), decimali)} {unita}" if serie else "")
            misura = RigaMisura(
                self.c, simbolo, nome, nota, f"{numero(attuale, decimali)} {unita}",
                f"{quanti} giorni", quota, colore)
            misura.setToolTip("Doppio clic per scorrere l'andamento di questo dato.")
            self._apribile(misura, campo)
            self.lay_ind.addWidget(misura)
        if not presenti:
            self.lay_ind.addWidget(etichetta(
                "Battito, variabilità e acqua si scrivono nella finestra "
                "«Inserimento dati», in alto.", "NotaScheda"))
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
        self.contenitore.sezioni["allenamenti"].imposta_periodo(
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
            self.contenitore.sezioni["peso"].imposta_periodo(
                f"{numero(serie[-1][1], 1)} kg · {segno}{numero(abs(scostamento), 1)} "
                f"in {quanti} giorni")
        else:
            self.contenitore.sezioni["peso"].imposta_periodo(f"{quanti} giorni")
