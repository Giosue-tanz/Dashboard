"""Salute: attività, sonno, composizione corporea, stress e costanza.

I dati si scrivono nella finestra «Inserimento dati», che si apre dal
pulsante in alto (o cliccando un giorno nella mappa della costanza).
"""
from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (QGridLayout, QHBoxLayout, QLabel, QMenu,
                               QMessageBox, QPushButton, QSizePolicy,
                               QVBoxLayout, QWidget)

from ..braccialetto import RiquadroBraccialetto
from ..componenti import (COLORE_BATTITO, EtichettaACapo, EtichettaAlta,
                          NavigatorePeriodo, SceltaPeriodo, binario,
                          dati_battito, etichetta, righe_indicatori,
                          separatore, separatore_verticale)
from ..tema import trasparente
from ..andamento import FinestraAndamento
from ..dialoghi import (DialogoAllenamento, DialogoGiorno,
                        DialogoImporta)
from ..grafici import (BarraFasi, GraficoBarre, GraficoIntervalli,
                       GraficoSonno, MappaCalore, Sparkline)
from ..punteggi import PREDEFINITI
from ..utils import (data_it, durata, giorni, media, minuti_notturni, minuti_ore,
                     numero, ore_minuti, relativa, ultimi_giorni)
from . import VistaSezioni


class VistaSalute(VistaSezioni):
    titolo = "Salute"
    sottotitolo = "Attività, sonno e misure — i dati li metti tu"
    nome_nuovo = "+  Allenamento"

    chiave_vista = "salute"
    versione_layout = 8

    SEZIONI = {
        "oggi": "Oggi",
        "corpo": "Composizione",
        "costanza": "Costanza",
        "passi": "Passi",
        "sonno": "Sonno",
        "battito": "Battito",
        "indicatori": "Indicatori",
        "stress": "Stress",
        "braccialetto": "Braccialetto",
    }
    # Tre righe, tre domande, dall'immediato al lento:
    #   la giornata  — com'è andata oggi: movimento, riposo, cuore
    #   nel tempo    — come va la settimana: passi, costanza, indicatori
    #   il corpo     — peso e composizione, stress, e chi li misura
    DISPOSIZIONE = [["oggi", "sonno", "battito"],
                    ["passi", "costanza", "indicatori"],
                    ["corpo", "stress", "braccialetto"]]
    # l'ultima riga tiene la composizione e il braccialetto, che hanno più
    # roba dentro: un filo più alta delle altre due
    ALTEZZE_PREDEFINITE = (0.33, 0.32, 0.35)
    LARGHEZZE_PREDEFINITE = ((0.36, 0.34, 0.30), (0.34, 0.33, 0.33),
                             (0.38, 0.32, 0.30))
    PERIODI_SEZIONE = {
        "indicatori": ({"7": "7 giorni", "30": "30 giorni", "90": "90 giorni",
                        "365": "un anno"}, "7"),
        # il battito si guarda in due modi: le ore di una giornata, oppure
        # come è andato giorno per giorno
        "battito": ({"oggi": "oggi", "ieri": "ieri", "7": "7 giorni",
                     "14": "14 giorni", "30": "30 giorni",
                     "90": "90 giorni"}, "oggi"),
    }
    # quanto indietro guarda il calendario della costanza: la scritta per
    # esteso sta nel menu, quella corta sulla pastiglia
    SETTIMANE_COSTANZA = {"2": "2 settimane", "4": "4 settimane",
                          "8": "8 settimane", "13": "3 mesi", "26": "6 mesi"}
    SETTIMANE_CORTE = {"2": "2 sett", "4": "4 sett", "8": "8 sett",
                       "13": "3 mesi", "26": "6 mesi"}
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
        # I passi grandi con la loro barra, e sotto gli altri cinque numeri
        # della giornata su una riga sola.
        #
        # Prima c'era un anello che si prendeva un terzo della larghezza per
        # dire una percentuale — un numero *ricavato* dai passi — mentre i
        # passi veri stavano in una casella piccola come le altre cinque. Con
        # un obiettivo solo da mostrare, una barra larga dice la stessa cosa
        # in un decimo dello spazio, e quello che avanza va ai numeri.
        contenuto, lay = self.colonna(10)
        testa = QHBoxLayout()
        testa.setSpacing(8)
        self.et_passi_oggi = EtichettaAlta("—")
        self.et_passi_oggi.setObjectName("NumeroGiornata")
        self._apribile(self.et_passi_oggi, "passi")
        self.et_passi_oggi.setToolTip(
            "Passi di oggi.\nDoppio clic per scorrere l'andamento.")
        self.et_passi_unita = etichetta("passi", "NotaScheda")
        self.et_passi_unita.setAlignment(Qt.AlignLeft | Qt.AlignBottom)
        self.et_passi_quota = etichetta("", "NotaScheda")
        self.et_passi_quota.setAlignment(Qt.AlignRight | Qt.AlignBottom)
        testa.addWidget(self.et_passi_oggi)
        testa.addWidget(self.et_passi_unita)
        testa.addStretch(1)
        testa.addWidget(self.et_passi_quota)
        lay.addLayout(testa)

        # la barra dell'obiettivo: fatto e quel che manca, due fette sole
        self.barra_passi = BarraFasi(self.c)
        self.barra_passi.setFixedHeight(9)
        self._apribile(self.barra_passi, "passi")
        lay.addWidget(self.barra_passi)

        # lo spazio che avanza sta fra la barra e la striscia dei numeri,
        # non fra la riga di separazione e i numeri: se no quella riga
        # restava orfana in cima a una fascia vuota
        lay.addStretch(1)
        lay.addWidget(separatore())
        self.riquadro_numeri = QWidget()
        self.riquadro_numeri.setObjectName("ContenutoSezione")
        self.lay_numeri = QGridLayout(self.riquadro_numeri)
        self.lay_numeri.setContentsMargins(0, 0, 0, 0)
        self.lay_numeri.setHorizontalSpacing(6)
        self.lay_numeri.setVerticalSpacing(12)
        for colonna in range(5):
            self.lay_numeri.setColumnStretch(colonna, 1)
        lay.addWidget(self.riquadro_numeri)
        self.aggiungi("oggi", contenuto)

        # ------------------------------------------ composizione corporea
        # Il peso, come si muove, e di che cosa è fatto. La curva sta qui
        # dentro invece che in un riquadro a parte: senza massa grassa la
        # composizione non ha niente da dire, e un riquadro con dentro un
        # numero solo e una barra finta non serviva a nessuno.
        contenuto, lay = self.colonna(7)
        self.nav_corpo = NavigatorePeriodo(self.c, "settimane", tutto=True)
        self.nav_corpo.cambiato.connect(self._aggiorna_corpo)
        # il numero grande e l'unità piccola accanto, non «75,5 kg» tutto
        # della stessa misura: a colpo d'occhio si legge il numero, e i
        # chili li sai già
        self.et_peso = EtichettaAlta("—")
        self.et_peso.setObjectName("ValoreScheda")
        self.et_peso_unita = etichetta("", "NotaScheda")
        self.et_peso_unita.setAlignment(Qt.AlignLeft | Qt.AlignBottom)
        self.et_peso_scarto = etichetta("", "NotaScheda")
        self.et_peso_scarto.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        testa = QHBoxLayout()
        testa.setSpacing(6)
        testa.addWidget(self.et_peso)
        testa.addWidget(self.et_peso_unita)
        testa.addStretch(1)
        testa.addWidget(self.et_peso_scarto)
        lay.addLayout(testa)
        # «2 giorni fa · 3 misure» stava qui sotto: quando è stata l'ultima
        # pesata e quante ce ne sono dietro la curva sono cose che si
        # guardano una volta, non a ogni occhiata — e intanto tenevano una
        # riga fissa fra il peso e il disegno. Sono passate nel suggerimento
        # della curva, insieme al minimo e al massimo del periodo.

        # La curva nuda: nessun asse, nessuna griglia, nessun riempimento
        # sotto. Di un peso che si muove di mezzo chilo le tacche non
        # dicevano niente che non dica già «74,1–75,6» nel suggerimento, e
        # rubavano il margine sinistro a tutto il riquadro.
        self.g_peso = Sparkline(self.c)
        self.g_peso.punto_finale = True
        # lo spazio che avanza se lo prende la curva, invece di spargersi
        # come aria fra una riga e l'altra: `Sparkline` nasce con un'altezza
        # fissa da miniatura, qui è il disegno principale del riquadro
        self.g_peso.setMinimumHeight(58)
        self.g_peso.setMaximumHeight(16777215)
        self.g_peso.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._apribile(self.g_peso, "peso")
        lay.addWidget(self.g_peso, 1)

        # qui dentro ci va solo l'invito a scrivere la prima misura, quando
        # l'archivio è vuoto: le parti del peso stanno nella riga in fondo
        self.cont_corpo, self.lay_corpo = self.colonna(6)
        lay.addWidget(self.cont_corpo)

        # In fondo, una riga sola: il BMI e le parti del peso. Le parti
        # prima stavano su due righe loro, alte una ventina di pixel l'una,
        # per dire due numeri che in una colonna ci stanno uguali. FMI e
        # FFMI se ne sono andati per far loro posto: erano gli stessi chili
        # del grasso e della magra, solo divisi per l'altezza al quadrato —
        # il BMI, che quella divisione la fa sul peso intero, resta.
        self.linea_indici = separatore()
        lay.addWidget(self.linea_indici)
        self.riga_indici = QWidget()
        self.riga_indici.setObjectName("ContenutoSezione")
        self.lay_indici = QHBoxLayout(self.riga_indici)
        self.lay_indici.setContentsMargins(0, 2, 0, 2)
        self.lay_indici.setSpacing(0)
        lay.addWidget(self.riga_indici)

        # Scrivere, correggere e cancellare una misura non stanno più su una
        # riga di icone in fondo: rubavano l'ultima striscia di riquadro a
        # quello che il riquadro deve dire, e comandi che si usano una volta
        # a settimana non meritano posto fisso. Vivono nel menu «⋯» del
        # titolo (vedi `voci_sezione`), che è il posto che l'app riserva
        # agli altri comandi, e nella finestra dell'andamento.
        self._ultima_corpo = ""
        self.nav_corpo.scorri_con_rotella(self.g_peso)
        self.aggiungi("corpo", contenuto, comando=self.nav_corpo)

        # -------------------------------------------------------- costanza
        contenuto, lay = self.colonna(10)
        self.quale_costanza, self.pastiglie = binario(
            {k: segno for k, (_, _, _, segno) in self.COSTANZA.items()},
            next(iter(self.COSTANZA)), self._scegli_costanza,
            {k: nome for k, (nome, _, _, _) in self.COSTANZA.items()})
        # Il periodo sta **prima** dei tre segni, sulla stessa riga: dice
        # quanto indietro si guarda, i segni dicono cosa. Qui le frecce non
        # servono — un calendario a quadretti è una durata, non un arco da
        # sfogliare — e una pastiglia stretta ci sta accanto ai simboli.
        self.periodo_costanza = SceltaPeriodo(
            self.SETTIMANE_COSTANZA, self.db.leggi("costanza_settimane", "8"),
            self.c, self.SETTIMANE_CORTE)
        self.periodo_costanza.scelto.connect(
            lambda v: (self.db.imposta("costanza_settimane", v),
                       self._aggiorna_costanza()))
        comando_costanza = QWidget()
        comando_costanza.setObjectName("ContenutoSezione")
        fila_comando = QHBoxLayout(comando_costanza)
        fila_comando.setContentsMargins(0, 0, 0, 0)
        fila_comando.setSpacing(6)
        fila_comando.addWidget(self.periodo_costanza)
        fila_comando.addWidget(self.quale_costanza)
        self.mappa = MappaCalore(self.c)
        self.mappa.giorno_scelto.connect(self._giorno_costanza)
        self.mappa.setToolTip(
            "Un quadretto per giorno: più è pieno, più sei andato vicino "
            "all'obiettivo.\nClicca un giorno per scriverne i dati — e con 💪 "
            "acceso, per aprire gli allenamenti\ndi quel giorno e correggerli.")
        lay.addWidget(self.mappa, 1)
        # il riassunto sta sotto la mappa, non accanto al titolo: lassù ci
        # sono già i tre segni e il periodo, e la riga non basterebbe per tutti
        self.et_costanza = etichetta("", "NotaScheda")
        self.et_costanza.setAlignment(Qt.AlignCenter)
        self.et_costanza.setWordWrap(True)
        lay.addWidget(self.et_costanza)
        self.aggiungi("costanza", contenuto, comando=comando_costanza)

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
        self.g_sonno = GraficoSonno(self.c)
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

        # ----------------------------------------------------------- stress
        # Due stress, e non sono la stessa cosa: quello che misura il
        # braccialetto dal battito (0-100, più basso è meglio) e quello che
        # senti tu, scritto in Emozioni. Il grande è il misurato; il sentito
        # sta nella riga sotto, perché quando i due non vanno d'accordo è
        # proprio quella la cosa interessante.
        contenuto, lay = self.colonna(6)
        self.nav_stress = NavigatorePeriodo(self.c, "giorni")
        self.nav_stress.cambiato.connect(self._aggiorna_stress)
        self.et_stress = EtichettaAlta("—")
        self.et_stress.setObjectName("ValoreScheda")
        self.et_stress_nota = etichetta("", "NotaScheda")
        self.et_stress_nota.setAlignment(Qt.AlignRight | Qt.AlignBottom)
        testa_stress = QHBoxLayout()
        testa_stress.setSpacing(10)
        testa_stress.addWidget(self.et_stress)
        testa_stress.addStretch(1)
        testa_stress.addWidget(self.et_stress_nota)
        lay.addLayout(testa_stress)
        self.g_stress = GraficoBarre(self.c)
        self.g_stress.formato = lambda v: numero(v, 0)
        self.g_stress.evidenzia_ultima = True
        self.g_stress.pallino_media = True
        self._apribile(self.g_stress, "stress")
        self.nav_stress.scorri_con_rotella(self.g_stress)
        lay.addWidget(self.g_stress, 1)
        self.aggiungi("stress", contenuto, comando=self.nav_stress)

        self._crea_braccialetto()

        self.grafici = [self.g_passi, self.g_sonno, self.g_peso, self.g_stress,
                        self.barra_passi, self.fasi, self.mappa]

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
        if finestra.cambiato:        # di là si cancella: anche le altre pagine
            self.dati_cambiati.emit()

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

    def _giorno_costanza(self, giorno: str) -> None:
        """Un quadretto cliccato: apre quello che quel quadretto racconta.

        Con 💪 acceso sono gli allenamenti: il quadretto apre quello del
        giorno, o ne comincia uno nuovo. È da qui che si correggono e si
        buttano via, da quando la tabella non sta più in pagina.
        """
        if self.dato_costanza() != "allenamenti":
            self.apri_dati(giorno)
            return
        fatti = list(self.db.allenamenti(giorno, giorno))
        if not fatti:
            self._apri_allenamento({"data": giorno})
            return
        menu = QMenu(self)
        for a in fatti:
            voce = menu.addMenu(f"{a['tipo']} · {durata(a['minuti'])}")
            voce.addAction("Modifica",
                           lambda _=False, v=a: self._apri_allenamento(v))
            voce.addAction("Elimina", lambda _=False, v=a: (
                self.db.elimina("allenamenti", v["id"]), self._dopo_salvataggio()))
        menu.addSeparator()
        menu.addAction("Aggiungine un altro",
                       lambda: self._apri_allenamento({"data": giorno}))
        menu.addAction("Scrivi i dati del giorno", lambda: self.apri_dati(giorno))
        menu.exec(QCursor.pos())

    def _apri_allenamento(self, voce) -> None:
        """La finestra di un allenamento, nuovo o già scritto."""
        dlg = DialogoAllenamento(voce, parent=self)
        if dlg.exec():
            self.db.salva_allenamento(dlg.dati())
            self._dopo_salvataggio()

    # ---------------------------------------------------------------- dati
    def aggiorna(self) -> None:
        self._aggiorna_oggi()
        self._aggiorna_corpo()
        self._aggiorna_costanza()
        self._aggiorna_passi()
        self._aggiorna_sonno()
        self._aggiorna_indicatori()
        self._aggiorna_stress()
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

        # i passi, grandi: sono il dato, non la percentuale che se ne ricava
        self.et_passi_oggi.setText(numero(passi, 0) if passi else "—")
        self.et_passi_oggi.setStyleSheet(
            f"color: {self.c['accento'] if passi else self.c['testo2']};")
        self.et_passi_quota.setText(
            f"{quota * 100:.0f}% di {numero(obiettivo, 0)}" if passi and obiettivo
            else ("nessun dato" if not passi else ""))
        # la barra: quello che hai fatto e quello che manca. Il fondo è un
        # grigio che si vede — con «griglia», sul tema scuro, una barra al
        # 5% sembrava rotta invece che appena cominciata
        fatto = min(passi, obiettivo) if obiettivo else passi
        manca = max(0.0, obiettivo - passi) if obiettivo else 0.0
        self.barra_passi.imposta_dati(
            [("fatti", fatto, self.c["accento"]),
             ("mancano", manca, self.c["pannello2"])])
        self.barra_passi.setToolTip(
            f"{numero(passi, 0)} passi su {numero(obiettivo, 0)}: "
            f"ne mancano {numero(manca, 0)}."
            if passi and manca else
            (f"Obiettivo raggiunto: {numero(passi, 0)} passi." if passi
             else "Nessun passo scritto oggi."))

        # gli altri cinque della giornata, su una riga sola. Le etichette
        # sono corte perché le colonne sono cinque: il nome per esteso sta
        # nel suggerimento, che è dove uno lo cerca.
        numeri = (("kcal", "kcal", "#f7913a", lambda v: numero(v, 0),
                   "Calorie attive bruciate oggi", True),
                  ("km", "km", "#35c4d7", lambda v: numero(v, 1),
                   "Distanza percorsa oggi", True),
                  ("sonno", "sonno", "#6c8cff", durata, "Quanto hai dormito", False),
                  ("battito", "battito", COLORE_BATTITO, lambda v: numero(v, 0),
                   "Battito a riposo, in bpm", False),
                  ("stress", "stress", "#f0b429", lambda v: numero(v, 0),
                   "Stress medio della giornata, da 0 a 100", False))
        for colonna, (campo, nota, colore, forma, spiega, solo_oggi) in enumerate(numeri):
            if solo_oggi:
                # passi, calorie e distanza si contano oggi e basta
                valore = float(r[campo]) if r and r[campo] else 0.0
                quando = nota
            else:
                # sonno, battito e stress il braccialetto li consegna quando
                # gli pare: meglio il numero vero, con scritto di quando è
                valore, giorno = self._recente(dati, elenco, campo)
                quando = (f"{nota} · {self._quando(giorno)}"
                          if giorno and giorno != oggi else nota)
            self._numero(campo, forma(valore) if valore else "—",
                         quando, colore, 0, colonna, spiega)

        self.contenitore.sezioni["oggi"].imposta_nota(
            f"obiettivo {numero(obiettivo, 0)} passi")

    # --------------------------------------------- composizione corporea
    def _aggiorna_corpo(self) -> None:
        """Peso, com'è fatto e come si muove: grassa, muscolare, massa secca."""
        self.svuota(self.lay_corpo)
        # la curva disegna ogni misura che c'è dentro la finestra: non si
        # media niente, il peso è un numero che hai scritto tu
        dal, al = self.nav_corpo.esteso()
        elenco = giorni(dal, al)
        quando = self.nav_corpo.nome_esteso()
        dati = self.db.giorni_salute(dal, al)

        def serie(campo: str) -> list[tuple[str, float]]:
            return [(g, float(dati[g][campo])) for g in elenco
                    if g in dati and dati[g][campo]]

        pesi, grassi, muscoli = serie("peso"), serie("grasso"), serie("muscolo")
        self.g_peso.imposta_dati([v for _, v in pesi], "#35c4d7")
        self.g_peso.setVisible(len(pesi) >= 2)
        if not pesi and not grassi and not muscoli:
            self.et_peso.setText("—")
            self.et_peso_unita.setText("")
            self.et_peso_scarto.setText("")
            self.g_peso.setToolTip("")
            self._ultima_corpo = ""
            self.linea_indici.hide()
            self.riga_indici.hide()
            self.lay_corpo.addWidget(etichetta(
                f"Nessuna misura in {quando}. Peso, massa grassa e massa "
                "muscolare si scrivono nella finestra «Inserimento dati».",
                "NotaScheda"))
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
            return f"{segno}{numero(abs(scostamento), 1)} {unita}"

        ultima = (pesi or grassi or muscoli)[-1][0]
        self.et_peso.setText(numero(peso, 1) if peso else numero(grasso, 1))
        self.et_peso_unita.setText("kg" if peso else "%")
        # quanto si è mosso, grande e colorato accanto al numero: è la cosa
        # che si guarda per prima
        if len(pesi) > 1:
            scostamento = pesi[-1][1] - pesi[0][1]
            segno = "+" if scostamento > 0 else "−"
            tinta = self.c["uscita"] if scostamento > 0 else self.c["entrata"]
            # una pastiglia, non una scritta colorata: è il modo in cui lo
            # dicono le schede di Samsung Health, e a colpo d'occhio si
            # legge prima il verso della freccia che il numero
            freccia = "↑" if scostamento > 0 else "↓"
            self.et_peso_scarto.setText(
                f"{freccia} {numero(abs(scostamento), 1)}")
            self.et_peso_scarto.setToolTip(
                f"{numero(abs(scostamento), 1)} kg "
                f"{'in più' if scostamento > 0 else 'in meno'} rispetto "
                f"alla prima misura di {quando}.")
            self.et_peso_scarto.setStyleSheet(
                f"color: {tinta}; background: {trasparente(tinta, 0.14)};"
                "border-radius: 9px; padding: 2px 9px;")
        else:
            self.et_peso_scarto.setText("")
            self.et_peso_scarto.setStyleSheet("")

        # tutto il racconto del periodo sta qui, sulla curva: quante misure,
        # quand'è l'ultima, da quanto a quanto
        quante = (f"{len(pesi)} misure" if len(pesi) > 1
                  else ("una misura sola" if pesi else "nessuna pesata"))
        estremi = (f"\nDa {numero(min(v for _, v in pesi), 1)} a "
                   f"{numero(max(v for _, v in pesi), 1)} kg."
                   if len(pesi) > 1 else "")
        self.g_peso.setToolTip(
            f"{quante} in {quando} · ultima {relativa(ultima)}.{estremi}\n"
            "Doppio clic per vederle tutte, una per riga.")

        self.cont_corpo.hide()        # l'invito serve solo ad archivio vuoto

        # La riga in fondo: il BMI e le parti del peso, una colonna per una.
        parti = []
        if grassi:
            parti.append(("grassa", "#f7913a", grasso, kg_grassa,
                          "grasso", variazione(grassi, "punti")))
        if muscoli:
            parti.append(("muscolare", "#6c8cff", muscolo, kg_muscolo,
                          "muscolo", variazione(muscoli, "punti")))
        if grassi:
            parti.append(("magra", self.c["accento"], 100 - grasso,
                          secca, "peso", "il peso meno la massa grassa"))
        self._indici(peso, parti)
        # su quale misura lavorano «correggi» e «cancella» del menu «⋯»
        self._ultima_corpo = ultima

    def voci_sezione(self, chiave: str, menu: QMenu) -> bool:
        """I comandi della composizione, nel menu «⋯» del suo titolo."""
        if chiave != "corpo":
            return False
        menu.addAction("Scrivi una misura…", lambda: self.apri_dati())
        quando = data_it(self._ultima_corpo) if self._ultima_corpo else ""
        correggi = menu.addAction(f"Correggi la misura del {quando}…" if quando
                                  else "Correggi l'ultima misura…")
        correggi.triggered.connect(lambda: self.apri_dati(self._ultima_corpo))
        cancella = menu.addAction(f"Cancella la misura del {quando}…" if quando
                                  else "Cancella l'ultima misura…")
        cancella.triggered.connect(self._cancella_composizione)
        for azione in (correggi, cancella):
            azione.setEnabled(bool(self._ultima_corpo))
        menu.addAction("Tutte le misure…",
                       lambda: self.apri_andamento("peso"))
        return True

    def _indici(self, peso: float, parti: list) -> None:
        """La riga in fondo: il BMI e le parti del peso, una colonna per una.

        Il BMI viene dall'altezza, le parti dalla bilancia: se l'altezza
        non c'è il BMI non si calcola, ma grassa e magra sì — e si mostrano
        lo stesso, con al posto del BMI la strada per scrivere l'altezza.
        """
        self.svuota(self.lay_indici)
        colonne: list[QWidget] = []
        altezza = self.db.leggi_num("altezza", 0) / 100      # in metri
        if peso and altezza > 0:
            colonne.append(self._indice(
                "BMI", numero(peso / (altezza * altezza), 1),
                self.c["testo"], "peso",
                "Il peso diviso l'altezza al quadrato: non sa dire se un "
                "chilo è grasso o muscolo, per quello ci sono le colonne "
                "accanto."))
        elif peso:
            colonne.append(self._invito_altezza())
        # in chili, non in percentuale: «3,0 kg» è una cosa che si può
        # soppesare, «4,0 %» va prima moltiplicata per il peso. La
        # percentuale, che è il numero che scrivi tu, resta nel suggerimento
        for nome, colore, percento, chili, campo, nota in parti:
            colonne.append(self._indice(
                nome, f"{numero(chili, 1)} kg" if chili
                else f"{numero(percento, 1)} %", colore, campo,
                f"{numero(percento, 1)} % del peso · {nota}" if chili
                else f"Senza il peso non si ricavano i chili · {nota}"))
        for posto, colonna in enumerate(colonne):
            if posto:
                self.lay_indici.addWidget(separatore_verticale())
            self.lay_indici.addWidget(colonna, 1)
        self.linea_indici.setVisible(bool(colonne))
        self.riga_indici.setVisible(bool(colonne))

    def _invito_altezza(self) -> QWidget:
        """Al posto del BMI, quando l'altezza non c'è ancora."""
        invito = QPushButton("altezza?")
        invito.setObjectName("Segmento")
        invito.setCursor(Qt.PointingHandCursor)
        invito.setToolTip(
            "Il BMI è il peso diviso l'altezza al quadrato: senza altezza "
            "non c'è niente da calcolare.\n"
            "Si scrive una volta sola, in Impostazioni → Obiettivi.")
        invito.clicked.connect(lambda: self.area_richiesta.emit("impostazioni"))
        return invito

    def _indice(self, sigla: str, valore: str, colore: str, campo: str,
                spiega: str) -> QWidget:
        """Una colonna: il numero grande, e sotto come si chiama."""
        indice = QWidget()
        indice.setObjectName("ContenutoSezione")
        colonna = QVBoxLayout(indice)
        colonna.setContentsMargins(0, 0, 0, 0)
        colonna.setSpacing(1)
        numeroso = QLabel(valore)
        numeroso.setObjectName("ValoreRiga")
        numeroso.setAlignment(Qt.AlignCenter)
        numeroso.setStyleSheet(f"color: {colore};")
        nome = etichetta(sigla, "NotaScheda")
        nome.setAlignment(Qt.AlignCenter)
        colonna.addWidget(numeroso)
        colonna.addWidget(nome)
        indice.setToolTip(f"{spiega}\nDoppio clic per vederne l'andamento."
                          if campo else spiega)
        if campo:
            self._apribile(indice, campo)
        return indice

    def _cancella_composizione(self) -> None:
        """Butta via la misura del giorno che il riquadro sta mostrando.

        Peso, massa grassa e massa muscolare di quel giorno se ne vanno
        insieme, perché insieme sono state scritte: è *quella pesata* che
        si cancella. Tutto il resto della giornata — passi, sonno, battito
        — non si tocca.
        """
        giorno = self._ultima_corpo
        riga = self.db.salute_giorno(giorno) if giorno else None
        if riga is None:
            return
        pezzi = []
        if riga["peso"]:
            pezzi.append(f"peso {numero(riga['peso'], 1)} kg")
        if riga["grasso"]:
            pezzi.append(f"massa grassa {numero(riga['grasso'], 1)} %")
        if riga["muscolo"]:
            pezzi.append(f"massa muscolare {numero(riga['muscolo'], 1)} %")
        if not pezzi:
            return
        if QMessageBox.question(
                self, "Cancellare la misura?",
                f"Misura del {data_it(giorno)}: {', '.join(pezzi)}.\n\n"
                "Sparisce dall'archivio e dalla curva. Gli altri dati di "
                "quel giorno — passi, sonno, battito — restano dove sono.",
                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        for campo in ("peso", "grasso", "muscolo"):
            self.db.cancella_misura(giorno, campo)
        self._dopo_salvataggio()

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

        # settimane piene, da lunedì: la griglia ha sette colonne fisse e un
        # periodo che comincia di mercoledì le sfalserebbe tutte
        settimane = int(self.periodo_costanza.valore)
        fine = date.today()
        fine += timedelta(days=6 - fine.weekday())        # fino a domenica
        inizio = fine - timedelta(weeks=settimane - 1, days=6)
        elenco = giorni(inizio.isoformat(), fine.isoformat())
        # la settimana in corso finisce di domenica, che deve ancora
        # arrivare: i conti si fanno sui giorni già passati
        oggi = date.today().isoformat()
        passati = [g for g in elenco if g <= oggi] or elenco

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
        raggiunti = sum(1 for g in passati if valori.get(g, 0) >= obiettivo)
        serie = migliore = 0
        for giorno in passati:
            if valori.get(giorno, 0) >= obiettivo:
                serie += 1
                migliore = max(migliore, serie)
            else:
                serie = 0
        attuale = 0
        for giorno in reversed(passati):
            if valori.get(giorno, 0) >= obiettivo:
                attuale += 1
            elif giorno != oggi:               # oggi non è ancora finito
                break

        quota = round(raggiunti / len(passati) * 100) if passati else 0
        if not valori:
            riassunto = f"nessun dato di {nome.lower()}"
        else:
            # il nome del dato lo dice il segno acceso là sopra: qui bastano
            # i numeri, e così la nota ci sta accanto al titolo
            riassunto = (f"{raggiunti}/{len(passati)} centrati · "
                         f"media {misura(media(list(valori.values())))}")
            if attuale > 1:
                riassunto += f" · serie di {attuale}"
        self.mappa.setToolTip(
            f"{cosa.capitalize()}: {len(valori)} giorni su {len(passati)}.\n"
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
            # senza fasi registrate non si finge di conoscerle, e non si
            # spende una riga a dirlo: lo spazio vuoto sotto la barra è già
            # abbastanza chiaro, e l'orario qui sotto conta di più
            self.fasi.imposta_dati([("sonno", float(totale), "#6c8cff")])
            self.et_fasi.setText("")
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
        """Una barra per notte, o per la media di una settimana o un mese:
        non più solo quante ore, ma da che ora a che ora.

        Con più notti in una barra sola (settimane, mesi) gli orari si
        mediano fra loro — e vanno messi prima sull'asse che comincia la
        sera (`minuti_notturni`): 23:40 e 01:07 sono vicini di un'ora e
        mezza nella stessa notte, non lontani ventidue ore, ed è ancorarli
        a un'ora fissa — non alla prima notte che capita in elenco — che fa
        venire la stessa media qualunque sia l'ordine dei giorni.
        """
        barre, valori = [], []
        for etichetta_barra, dal, al in finestre:
            dentro = [float(r["sonno"]) for g, r in dati.items()
                      if dal <= g <= al and r["sonno"]]
            if dentro:
                valori.extend(dentro)
            notti = [r for g, r in dati.items()
                     if dal <= g <= al and r["sonno"] and r["a_letto"] and r["sveglia"]]
            if not notti:
                barre.append((etichetta_barra, "", "", None))
                continue
            inizi = [minuti_notturni(ore_minuti(r["a_letto"])) for r in notti]
            fini = []
            for r, i in zip(notti, inizi):
                f = minuti_notturni(ore_minuti(r["sveglia"]))
                fini.append(f + 1440 if f <= i else f)
            inizio_medio, fine_media = media(inizi), media(fini)
            barre.append((etichetta_barra, minuti_ore(inizio_medio),
                         minuti_ore(fine_media), fine_media - inizio_medio))
        self.g_sonno.evidenziata = self.nav_sonno.indice_adesso()
        self.g_sonno.imposta_dati(barre, "#6c8cff")
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

    # Come li chiama il braccialetto: sotto 30 è basso, sopra 80 è tanto.
    LIVELLI_STRESS = ((30, "basso", "#16c47f"), (60, "normale", "#f0b429"),
                      (80, "alto", "#ff9f45"), (101, "molto alto", "#ff5a5a"))

    @classmethod
    def _livello_stress(cls, valore: float) -> tuple[str, str]:
        for soglia, nome, tinta in cls.LIVELLI_STRESS:
            if valore < soglia:
                return nome, tinta
        return cls.LIVELLI_STRESS[-1][1], cls.LIVELLI_STRESS[-1][2]

    def _aggiorna_stress(self) -> None:
        """Lo stress misurato dal braccialetto, giorno per giorno.

        Da 0 a 100, e qui più basso vuol dire meglio: è il contrario di
        quasi tutti gli altri grafici della pagina, per questo la barra ha
        il colore del livello invece di quello dell'accento.
        """
        finestre = self.nav_stress.finestre()
        barre, valori = [], []
        for nome_barra, dal, al in finestre:
            dentro = [v for _g, v in self.db.serie_salute("stress", dal, al) if v]
            quanto = media(dentro) if dentro else None
            barre.append((nome_barra, [quanto]))
            if quanto is not None:
                valori.append(quanto)
        self.g_stress.evidenziata = self.nav_stress.indice_adesso()
        tinta = self._livello_stress(valori[-1])[1] if valori else self.c["accento"]
        self.g_stress.imposta_dati(barre, [("stress", tinta)])

        dal, al = self.nav_stress.scelto()
        dentro = [v for _g, v in self.db.serie_salute("stress", dal, al) if v]
        adesso = media(dentro) if dentro else 0.0
        if adesso:
            nome, colore = self._livello_stress(adesso)
            self.et_stress.setText(numero(adesso, 0))
            self.et_stress.setStyleSheet(f"color: {colore}; font-weight: 700;")
            self.et_stress_nota.setText(f"{self.nav_stress.nome_scelto()} · {nome}")
        else:
            # niente in questa finestra: si dice l'ultima misura che c'è,
            # invece di un trattino che non spiega niente
            ultimo = self.db.uno(
                "SELECT data, stress FROM salute WHERE stress > 0 AND data <= ? "
                "ORDER BY data DESC LIMIT 1", (al,))
            if ultimo:
                nome, colore = self._livello_stress(float(ultimo["stress"]))
                self.et_stress.setText(numero(float(ultimo["stress"]), 0))
                self.et_stress.setStyleSheet(f"color: {colore}; font-weight: 700;")
                self.et_stress_nota.setText(
                    f"ultima misura · {relativa(ultimo['data'])} · {nome}")
            else:
                self.et_stress.setText("—")
                self.et_stress.setStyleSheet("")
                self.et_stress_nota.setText(
                    f"{self.nav_stress.nome_scelto()} · il braccialetto non ha "
                    "ancora misurato lo stress")

        self.contenitore.sezioni["stress"].imposta_nota(
            f"media {numero(media(valori), 0)} su {len(valori)} "
            f"{'giorni' if self.nav_stress.modo == 'giorni' else 'periodi'} misurati"
            if valori else "lo misura il braccialetto, dal battito")

