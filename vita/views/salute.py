"""Salute: attività, sonno, composizione corporea, allenamenti e costanza.

I dati si scrivono nella finestra «Inserimento dati», che si apre dal
pulsante in alto (o cliccando un giorno nella mappa della costanza).
"""
from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QGridLayout, QHBoxLayout, QHeaderView, QLabel,
                               QMenu, QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

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
    versione_layout = 7

    SEZIONI = {
        "oggi": "Oggi",
        "corpo": "Composizione",
        "costanza": "Costanza",
        "passi": "Passi",
        "sonno": "Sonno",
        "battito": "Battito",
        "indicatori": "Indicatori",
        "allenamenti": "Allenamenti",
        "braccialetto": "Braccialetto",
    }
    # Tre righe, tre domande, dall'immediato al lento:
    #   la giornata  — com'è andata oggi: movimento, riposo, cuore
    #   nel tempo    — come va la settimana: passi, costanza, indicatori
    #   il corpo     — peso e composizione, allenamenti, e chi li misura
    DISPOSIZIONE = [["oggi", "sonno", "battito"],
                    ["passi", "costanza", "indicatori"],
                    ["corpo", "allenamenti", "braccialetto"]]
    # l'ultima riga tiene la tabella e il braccialetto, che hanno più roba
    # dentro: un filo più alta delle altre due
    ALTEZZE_PREDEFINITE = (0.33, 0.32, 0.35)
    LARGHEZZE_PREDEFINITE = ((0.36, 0.34, 0.30), (0.34, 0.33, 0.33),
                             (0.38, 0.32, 0.30))
    PERIODI_SEZIONE = {
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
    # ogni dato della costanza ha il suo segno, la sua tinta e il suo modo
    # di dirsi: il segno sta sulla riga del titolo, il nome nel suggerimento
    # e nella nota accanto al titolo
    COSTANZA = {
        "passi": ("Passi", "", "giorni camminati", "👟"),
        "sonno": ("Sonno", "#3d7bfd", "notti registrate", "🌙"),
        "allenamenti": ("Allenamenti", "#ff9f45", "giorni di allenamento", "💪"),
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
        # L'anello dell'obiettivo a sinistra, i sei numeri della giornata a
        # destra: sopra quello che hai fatto (passi, calorie, distanza),
        # sotto quello che il corpo dice di sé (sonno, battito, stress).
        contenuto, lay = self.colonna(10)
        fila = QHBoxLayout()
        fila.setSpacing(14)
        self.anello = Anello(self.c, self.c["accento"])
        self.anello.setMinimumSize(104, 104)
        self._apribile(self.anello, "passi")
        fila.addWidget(self.anello, 2)
        self.riquadro_numeri = QWidget()
        self.riquadro_numeri.setObjectName("ContenutoSezione")
        self.lay_numeri = QGridLayout(self.riquadro_numeri)
        self.lay_numeri.setContentsMargins(0, 0, 0, 0)
        self.lay_numeri.setHorizontalSpacing(8)
        self.lay_numeri.setVerticalSpacing(12)
        for colonna in range(3):
            self.lay_numeri.setColumnStretch(colonna, 1)
        # i sei numeri stanno insieme al centro, non spiaccicati agli angoli
        fila.addWidget(self.riquadro_numeri, 5, Qt.AlignVCenter)
        lay.addLayout(fila, 1)
        self.aggiungi("oggi", contenuto)

        # ------------------------------------------ composizione corporea
        # Il peso, come si muove, e di che cosa è fatto. La curva sta qui
        # dentro invece che in un riquadro a parte: senza massa grassa la
        # composizione non ha niente da dire, e un riquadro con dentro un
        # numero solo e una barra finta non serviva a nessuno.
        contenuto, lay = self.colonna(7)
        self.et_peso = EtichettaAlta("—")
        self.et_peso.setObjectName("ValoreScheda")
        self.et_peso_scarto = etichetta("", "NotaScheda")
        self.et_peso_scarto.setAlignment(Qt.AlignRight | Qt.AlignBottom)
        testa = QHBoxLayout()
        testa.setSpacing(10)
        testa.addWidget(self.et_peso)
        testa.addStretch(1)
        testa.addWidget(self.et_peso_scarto)
        lay.addLayout(testa)
        self.et_peso_nota = EtichettaACapo("")
        self.et_peso_nota.setObjectName("NotaScheda")
        lay.addWidget(self.et_peso_nota)

        self.g_peso = GraficoLinea(self.c)
        self.g_peso.formato = lambda v: numero(v, 1)
        self.g_peso.setMinimumHeight(78)
        self._apribile(self.g_peso, "peso")
        lay.addWidget(self.g_peso, 1)

        self.barra_corpo = BarraFasi(self.c)
        lay.addWidget(self.barra_corpo)
        # la legenda dei pezzi, come quella delle fasi del sonno
        self.et_corpo_nota = EtichettaACapo("")
        self.et_corpo_nota.setObjectName("NotaScheda")
        lay.addWidget(self.et_corpo_nota)
        self.cont_corpo, self.lay_corpo = self.colonna(7)
        self.area_corpo = self.scorrevole(self.cont_corpo)
        lay.addWidget(self.area_corpo, 1)
        self.aggiungi("corpo", contenuto)

        # -------------------------------------------------------- costanza
        contenuto, lay = self.colonna(10)
        self.quale_costanza, self.pastiglie = binario(
            {k: segno for k, (_, _, _, segno) in self.COSTANZA.items()},
            next(iter(self.COSTANZA)), self._scegli_costanza,
            {k: nome for k, (nome, _, _, _) in self.COSTANZA.items()})
        self.mappa = MappaCalore(self.c)
        self.mappa.giorno_scelto.connect(self.apri_dati)
        self.mappa.setToolTip("Un quadretto per giorno: più è pieno, più sei andato "
                              "vicino all'obiettivo.\nClicca un giorno per scriverne "
                              "i dati.")
        lay.addWidget(self.mappa, 1)
        # il riassunto sta sotto la mappa, non accanto al titolo: lassù ci
        # sono già i tre segni e il periodo, e la riga non basterebbe per tutti
        self.et_costanza = etichetta("", "NotaScheda")
        self.et_costanza.setAlignment(Qt.AlignCenter)
        self.et_costanza.setWordWrap(True)
        lay.addWidget(self.et_costanza)
        self.aggiungi("costanza", contenuto, comando=self.quale_costanza)

        # ------------------------------------------------------------ passi
        contenuto, lay = self.colonna(6)
        # il navigatore sta sulla riga del titolo, non qui dentro: quei
        # quaranta pixel sono altezza che il grafico si tiene
        self.nav_passi = NavigatorePeriodo(self.c, "giorni")
        self.nav_passi.cambiato.connect(self._aggiorna_passi)
        # il numero grande è quello del giorno che stai guardando — oggi,
        # se oggi è nella finestra: come nel riquadro del sonno
        self.et_passi = EtichettaAlta("—")
        self.et_passi.setObjectName("ValoreScheda")
        self.et_passi_nota = etichetta("", "NotaScheda")
        self.et_passi_nota.setAlignment(Qt.AlignRight | Qt.AlignBottom)
        testa_passi = QHBoxLayout()
        testa_passi.setSpacing(10)
        testa_passi.addWidget(self.et_passi)
        testa_passi.addStretch(1)
        testa_passi.addWidget(self.et_passi_nota)
        lay.addLayout(testa_passi)
        self.g_passi = GraficoBarre(self.c)
        self.g_passi.formato = lambda v: numero(v, 0)
        self.g_passi.evidenzia_ultima = True
        self._apribile(self.g_passi, "passi")
        # la rotellina sul grafico scorre le settimane
        self.nav_passi.scorri_con_rotella(self.g_passi)
        lay.addWidget(self.g_passi, 1)
        self.aggiungi("passi", contenuto, comando=self.nav_passi)

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
        self.aggiungi("sonno", contenuto, comando=self.nav_sonno)
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

    def _numero(self, campo: str, valore: str, nota: str, colore: str,
                riga: int, colonna: int, spiega: str = "") -> None:
        """Un numero della giornata: grande e colorato, con sotto cos'è."""
        cella = QWidget()
        cella.setObjectName("ContenutoSezione")
        dentro = QVBoxLayout(cella)
        dentro.setContentsMargins(0, 0, 0, 0)
        dentro.setSpacing(1)
        v = EtichettaAlta(valore)
        v.setObjectName("NumeroOggi")
        v.setAlignment(Qt.AlignCenter)
        # il colore qui, la misura nel foglio di stile: così cresce anche lui
        # quando ingrandisci il testo
        v.setStyleSheet(f"color: {colore if valore != '—' else self.c['testo2']};")
        # «bpm a riposo · 01/11» col testo grande non sta su una riga sola:
        # va a capo invece di farsi tagliare
        n = EtichettaACapo(nota)
        n.setObjectName("NotaScheda")
        n.setAlignment(Qt.AlignCenter)
        dentro.addWidget(v)
        dentro.addWidget(n)
        if campo:
            cella.setToolTip((spiega + "\n" if spiega else "")
                             + "Doppio clic per scorrere l'andamento di questo dato.")
            self._apribile(cella, campo)
        self.lay_numeri.addWidget(cella, riga, colonna)

    def _recente(self, dati: dict, elenco: list[str], campo: str) -> tuple[float, str]:
        """L'ultimo valore scritto per questo dato, e di che giorno è.

        Passi e calorie si contano oggi e basta. Sonno, battito e stress no:
        il braccialetto li consegna quando gli pare, e un trattino al posto
        del battito di ieri sera non dice niente a nessuno. Meglio il numero
        vero con scritto di quando è.
        """
        for giorno in reversed(elenco):
            riga = dati.get(giorno)
            if riga is not None and riga[campo]:
                return float(riga[campo]), giorno
        return 0.0, ""

    @staticmethod
    def _quando(giorno: str) -> str:
        """«ieri», o la data breve: sta accanto al nome del dato, dev'essere corta."""
        scarto = (date.today() - date.fromisoformat(giorno)).days
        return "ieri" if scarto == 1 else data_it(giorno)[:5]

    def _aggiorna_oggi(self) -> None:
        self.svuota(self.lay_numeri)
        oggi = date.today().isoformat()
        elenco = ultimi_giorni(7)
        dati = self.db.giorni_salute(elenco[0], elenco[-1])
        r = dati.get(oggi)
        obiettivo = self.db.leggi_num("obiettivo_passi", PREDEFINITI["obiettivo_passi"])
        passi = float(r["passi"]) if r and r["passi"] else 0.0
        quota = passi / obiettivo if obiettivo else 0
        self.anello.imposta(quota, f"{quota * 100:.0f}%" if passi else "—",
                            "dell'obiettivo" if passi else "nessun dato")

        # la riga di sopra: quello che hai fatto oggi, che oggi si conta
        for colonna, (campo, nota, colore, decimali) in enumerate(
                (("passi", "passi", self.c["accento"], 0),
                 ("kcal", "kcal attive", "#f7913a", 0),
                 ("km", "km", "#35c4d7", 1))):
            valore = float(r[campo]) if r and r[campo] else 0.0
            self._numero(campo, numero(valore, decimali) if valore else "—",
                         nota, colore, 0, colonna)

        # la riga di sotto: quello che il corpo dice di sé, anche di ieri
        for colonna, (campo, nota, colore, forma, spiega) in enumerate(
                (("sonno", "sonno", "#6c8cff", durata, "Quanto hai dormito"),
                 ("battito", "battito", COLORE_BATTITO, lambda v: numero(v, 0),
                  "Battito a riposo, in bpm"),
                 ("stress", "stress", "#f0b429", lambda v: numero(v, 0),
                  "Stress medio della giornata, da 0 a 100"))):
            valore, giorno = self._recente(dati, elenco, campo)
            quando = f"{nota} · {self._quando(giorno)}" if giorno and giorno != oggi \
                else nota
            self._numero(campo, forma(valore) if valore else "—",
                         quando, colore, 1, colonna, spiega)

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
        self.g_peso.imposta_dati([(data_it(g)[:5], v) for g, v in pesi],
                                 "#35c4d7", "peso")
        self.g_peso.setVisible(len(pesi) >= 2)
        if not pesi and not grassi and not muscoli:
            self.et_peso.setText("—")
            self.et_peso_scarto.setText("")
            self.et_peso_nota.setText("nessuna misura in questo periodo")
            self.barra_corpo.hide()
            self.et_corpo_nota.hide()
            self.lay_corpo.addWidget(etichetta(
                "Peso, massa grassa e massa muscolare si scrivono nella finestra "
                "«Inserimento dati».", "NotaScheda"))
            invito = QPushButton("Inserimento dati")
            invito.clicked.connect(lambda: self.apri_dati())
            self.lay_corpo.addWidget(invito)
            self.lay_corpo.addStretch(1)
            self.area_corpo.show()
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
        # quanto si è mosso, grande e colorato accanto al numero: è la cosa
        # che si guarda per prima
        if len(pesi) > 1:
            scostamento = pesi[-1][1] - pesi[0][1]
            segno = "+" if scostamento > 0 else "−"
            tinta = self.c["uscita"] if scostamento > 0 else self.c["entrata"]
            self.et_peso_scarto.setText(
                f"{segno}{numero(abs(scostamento), 1)} kg")
            self.et_peso_scarto.setStyleSheet(
                f"color: {tinta}; font-weight: 700;")
            self.et_peso_nota.setText(
                f"{relativa(ultima)} · in {quanti} giorni · "
                f"min {numero(min(v for _, v in pesi), 1)} · "
                f"max {numero(max(v for _, v in pesi), 1)} kg")
        else:
            self.et_peso_scarto.setText("")
            self.et_peso_nota.setText(relativa(ultima))

        # la barra: com'è diviso il peso, non quanto pesa. Senza massa grassa
        # non si disegna una barra finta — non c'è niente da dividere
        if peso and (grasso or muscolo):
            resto = max(0.0, peso - kg_grassa - kg_muscolo)
            fette = [("grassa", kg_grassa, "#f7913a"),
                     ("muscolare", kg_muscolo, "#6c8cff"),
                     ("resto", resto, self.c["griglia"])]
            vive = [f for f in fette if f[1] > 0]
            self.barra_corpo.imposta_dati(vive)
            self.barra_corpo.setToolTip("   ·   ".join(
                f"massa {n}: {numero(v, 1)} kg" for n, v, _ in vive))
            self.barra_corpo.show()
            self.et_corpo_nota.setText("   ".join(
                f"<span style='color:{col}'>●</span> {nome} {numero(v, 1)} kg"
                for nome, v, col in vive
                if nome != "resto" or v > 0.1))
            self.et_corpo_nota.setTextFormat(Qt.RichText)
            self.et_corpo_nota.show()
        else:
            self.barra_corpo.hide()
            self.et_corpo_nota.setTextFormat(Qt.PlainText)
            self.et_corpo_nota.setText(
                "senza massa grassa il peso resta un numero solo: scrivila in "
                "«Inserimento dati».")
            self.et_corpo_nota.show()

        righe = 0
        if grassi:
            righe += 1
            riga_corpo = RigaMisura(
                self.c, "◍", "Massa grassa",
                f"{numero(kg_grassa, 1)} kg del peso" if peso else "percentuale",
                f"{numero(grasso, 1)} %", variazione(grassi, "punti"),
                int(grasso), "#f7913a")
            self._apribile(riga_corpo, "grasso")
            self.lay_corpo.addWidget(riga_corpo)
        if muscoli:
            righe += 1
            riga_corpo = RigaMisura(
                self.c, "⟡", "Massa muscolare",
                f"{numero(kg_muscolo, 1)} kg del peso" if peso else "percentuale",
                f"{numero(muscolo, 1)} %", variazione(muscoli, "punti"),
                int(muscolo), "#6c8cff")
            self._apribile(riga_corpo, "muscolo")
            self.lay_corpo.addWidget(riga_corpo)
        if pesi and grassi:
            righe += 1
            riga_corpo = RigaMisura(
                self.c, "◆", "Massa secca", "il peso meno la massa grassa",
                f"{numero(secca, 1)} kg", f"{numero(100 - grasso, 1)} % del peso",
                int(100 - grasso), self.c["accento"])
            self._apribile(riga_corpo, "peso")
            self.lay_corpo.addWidget(riga_corpo)
        self.lay_corpo.addStretch(1)
        # senza righe l'area che scorre non serve: lo spazio va alla curva
        self.area_corpo.setVisible(righe > 0)

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
        nome, tinta, cosa, _segno = self.COSTANZA[dato]
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
            # il nome del dato lo dice il segno acceso là sopra: qui bastano
            # i numeri, e così la nota ci sta accanto al titolo
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
        self.et_costanza.setText(riassunto)

    def _aggiorna_passi(self) -> None:
        """I passi nel modo scelto: un giorno per barra, o una settimana, o un mese.

        Il numero grande è quello del periodo in primo piano: **oggi**, se
        oggi è nella finestra che stai guardando. Prima il riquadro diceva
        solo la media della settimana, e per sapere quanti passi avevi fatto
        oggi bisognava andarli a cercare nell'anello di «Oggi».
        """
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
        self.g_passi.evidenziata = self.nav_passi.indice_adesso()
        self.g_passi.imposta_dati(barre, [("passi", self.c["accento"])])

        dal, al = self.nav_passi.scelto()
        dentro = self.db.giorni_salute(dal, al)
        adesso = sum(float(r["passi"]) for r in dentro.values() if r["passi"])
        quota = adesso / self.g_passi.riferimento if self.g_passi.riferimento else 0
        self.et_passi.setText(numero(adesso, 0) if adesso else "—")
        self.et_passi_nota.setText(
            f"{self.nav_passi.nome_scelto()} · {quota * 100:.0f}% "
            f"dell'obiettivo" if adesso
            else f"{self.nav_passi.nome_scelto()} · nessun passo registrato")

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
            # chi va a capo si misura alla larghezza che ha davvero: il
            # suggerimento di un'etichetta a capo vale per una colonna
            # stretta, e la legenda delle fasi sembrava alta il doppio
            if isinstance(widget, QLabel) and widget.wordWrap():
                return widget.heightForWidth(max(1, larghezza))
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
        # Nel periodo scelto può non esserci niente: in «giorni» quel periodo
        # è l'ultimo giorno della settimana, che a metà settimana deve ancora
        # arrivare. Dire «nessuna notte registrata» sopra un grafico pieno di
        # notti è falso: si racconta l'ultima che c'è, dicendo di quando è.
        viste = [r for g, r in sorted(dati.items()) if r["sonno"]]
        ultimo = notti[-1] if notti else (viste[-1] if viste else None)
        tutte = [float(r["sonno"]) for r in dati.values() if r["sonno"]]

        if ultimo is None:
            # dire «nessuna notte registrata» suona come «mai»: qui vuol dire
            # solo che in questa finestra non ce ne sono
            self.et_sonno.setText("—")
            self.et_sonno_nota.setText(
                f"nessuna notte {self.nav_sonno.nome()}")
            self.fasi.imposta_dati([])
            self.et_fasi.setText("")
            self._barre_sonno(finestre, dati)
            return

        totale = int(ultimo["sonno"])
        if self.nav_sonno.modo == "giorni" or not notti:
            grande, nota_quando = totale, relativa(ultimo["data"])
        else:
            # su settimane e mesi il numero grande è la media per notte
            dentro = [float(r["sonno"]) for g, r in dati.items()
                      if scelto_dal <= g <= scelto_al and r["sonno"]]
            grande = int(media(dentro))
            nota_quando = f"media di {len(dentro)} notti"
        self.et_sonno.setText(durata(grande))
        scostamento = grande - media(tutte)
        # con una notte sola lo scarto dalla media è zero: scrivere «+— sulla
        # media» non è un'informazione, è un rumore
        if len(tutte) > 1 and abs(scostamento) >= 1:
            segno = "+" if scostamento >= 0 else "−"
            self.et_sonno_nota.setText(
                f"{nota_quando} · {segno}{durata(abs(scostamento))} sulla media")
        else:
            self.et_sonno_nota.setText(nota_quando)

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
        self.g_sonno.evidenziata = self.nav_sonno.indice_adesso()
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

