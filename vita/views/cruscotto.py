"""Home: tutte le aree in un colpo d'occhio.

La chiave interna resta «cruscotto»: e' quella con cui la disposizione
dei riquadri e' salvata nell'archivio, e rinominarla sposterebbe i
riquadri di chi aggiorna.
"""
from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import QEvent, QObject, QTimer, Qt, Signal
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import (QHBoxLayout, QHeaderView, QLabel, QMenu,
                               QMessageBox, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from ..banda import DISPONIBILE, cerca_braccialetto, condiviso
from ..componenti import (COLORE_BATTITO, AnelloEtichettato, AzioniRiga,
                          EtichettaACapo, EtichettaAlta, LegendaMisure,
                          NavigatorePeriodo, RigaMisura, SceltaPeriodo,
                          SelezioneSemplice, abilita_deselezione,
                          dati_battito, etichetta, faccia, righe_indicatori,
                          separatore, separatore_verticale, stile_tabella)
from ..db import AREE
from ..dialoghi import DialogoEsame, DialogoProgetto, DialogoScadenza
from ..grafici import (Anello, GraficoBarre, GraficoIntervalli,
                       GraficoLinea, MappaCalore)
from ..punteggi import PREDEFINITI
from ..riquadri import RiquadroAttivita, SceltaRiquadri
from .. import catalogo
from ..tema import colore_area, luminosita, trasparente
from ..tess import Accensione, Motore
from .emozioni import MISURE as MISURE_EMOTIVE
from ..utils import (data_it, data_lunga, durata, euro, giorni, media,
                     mese_corrente, numero, relativa, settimana_corrente,
                     ultimi_giorni, voto)
from . import VistaSezioni


def _quota_battito(valore: float) -> int:
    """Più il battito a riposo è basso, più la barra è piena (45-85 bpm)."""
    if not valore:
        return 0
    return int(max(0.0, min(100.0, (85 - valore) / 40 * 100)))


class VistaCruscotto(VistaSezioni):
    titolo = "Home"
    sottotitolo = "Com'è messa la giornata, in tutte le aree"
    nome_nuovo = ""
    chiave_vista = "cruscotto"
    tema_cambiato = Signal(str)

    SEZIONI = {
        "oggi": "Oggi",
        "emotivo": "Andamento emotivo",
        "salute": "Salute",
        "carriera": "Carriera",
        "accademica": "Accademica",
        "abitudini": "Abitudini",
        "battito": "Battito",
        "indicatori": "Indicatori",
        "finanza": "Finanza",
        "impegni": "Impegni",
        "emozioni": "Emozioni",
    }
    versione_layout = 9
    # Come si legge una giornata: prima com'è andata (anello, salute, costanza),
    # poi come si sta muovendo (umore e soldi, i due andamenti che vogliono
    # larghezza), in fondo cosa resta da fare. Tess ha una pagina sua: qui
    # resta solo l'interruttore in testata.
    DISPOSIZIONE = [["oggi", "salute", "abitudini"],
                    ["battito", "indicatori", "emotivo"],
                    ["finanza", "carriera", "accademica", "emozioni", "impegni"]]
    ALTEZZE_PREDEFINITE = (0.30, 0.30, 0.40)
    # L'ultima riga non si divide in parti uguali. Finanza, Carriera e
    # Accademica sono elenchi di poche parole corte; Emozioni e Impegni sono
    # tabelle, e una tabella stretta non accorcia il testo: lo taglia. A un
    # quinto per uno, «Chiamare la terapeuta» diventava «Chiamar…» e la
    # colonna «Area» di Impegni finiva fuori dal bordo.
    LARGHEZZE_PREDEFINITE = ((0.30, 0.34, 0.36),
                             (0.34, 0.26, 0.40),
                             (0.155, 0.155, 0.17, 0.23, 0.29))
    # quanto indietro guarda il calendario delle abitudini: per esteso nel
    # menu, accorciato sulla pastiglia
    GIORNI_ABITUDINI = {"14": "14 giorni", "30": "30 giorni", "90": "90 giorni",
                        "180": "6 mesi", "365": "un anno"}
    GIORNI_ABITUDINI_CORTI = {"14": "14 g", "30": "30 g", "90": "90 g",
                              "180": "6 mesi", "365": "un anno"}
    PERIODI_SEZIONE = {
        "impegni": ({"30": "30 giorni", "90": "90 giorni", "365": "un anno",
                     "730": "due anni"}, "90"),
        "battito": ({"oggi": "oggi", "ieri": "ieri", "7": "7 giorni",
                     "14": "14 giorni", "30": "30 giorni"}, "oggi"),
        "indicatori": ({"7": "7 giorni", "30": "30 giorni", "90": "90 giorni",
                        "365": "un anno"}, "7"),
    }

    CHIAVE_PRESTITI = "cruscotto_prestiti"

    def _menu_sezioni(self) -> None:
        """Il menu «Riquadri», più la voce per prendere da altre pagine."""
        super()._menu_sezioni()
        # due segnaposto: le aree extra di attività si infilano sopra il
        # primo, i riquadri presi in prestito sopra il secondo — ognuno
        # resta raggruppato per conto suo, invece che mescolati alla rinfusa
        self.sep_attivita = self.menu_sezioni.insertSeparator(
            self.menu_sezioni.actions()[-2])
        self.sep_prestiti = self.menu_sezioni.insertSeparator(
            self.menu_sezioni.actions()[-2])
        self.menu_sezioni.addSeparator()
        self.menu_sezioni.addAction("Riquadri dalle altre pagine…",
                                    self.scegli_prestiti)
        # Un'altra area di attività: Carriera, Accademica, Salute, Finanza —
        # ognuna il suo riquadro, mai tutte mescolate in uno solo. Rifatto
        # ogni volta che si apre: dice solo le aree che non ci sono ancora.
        self.menu_attivita_extra = QMenu("Aggiungi un'altra area di attività…",
                                         self.menu_sezioni)
        self.menu_attivita_extra.aboutToShow.connect(self._popola_menu_attivita)
        self.menu_sezioni.addMenu(self.menu_attivita_extra)

    def crea_sezioni(self) -> None:
        # copia d'istanza: i riquadri presi in prestito si aggiungono qui, e
        # scrivere sull'attributo di classe li farebbe comparire a chiunque
        self.SEZIONI = dict(self.SEZIONI)
        # le pagine da cui si è preso qualcosa, costruite una volta sola
        self._viste_prestate: dict[str, object] = {}
        self.b_tema = QPushButton()
        self.b_tema.setObjectName("AzioneTestata")
        self.b_tema.setCursor(Qt.PointingHandCursor)
        self.b_tema.clicked.connect(self._commuta_tema)
        self._aggiorna_testo_tema()

        # Lo stesso bottone del tema, non un interruttore a parte: accende e
        # spegne il collegamento col braccialetto. Batteria e battito in
        # diretta restano nel loro riquadro di Salute, qui c'è solo il
        # collegamento. Acceso o spento si legge dal colore del testo —
        # neutro, non un semaforo rosso/verde che qui stonerebbe.
        # lo stesso braccialetto del riquadro in Salute: uno solo, così i
        # due comandi si accendono e si spengono insieme
        self.banda_home = condiviso()
        self.b_banda = QPushButton()
        self.b_banda.setObjectName("AzioneTestata")
        self.b_banda.setCursor(Qt.PointingHandCursor)
        self.b_banda.clicked.connect(self._tocca_banda)
        self.banda_home.stato.connect(self._stato_banda)
        self.banda_home.batteria.connect(self._batteria_banda)
        self._aggiorna_testo_banda()
        if not DISPONIBILE:
            # qui sì che non c'è proprio nulla da fare: niente Bluetooth di
            # sistema, e non cambia più finché non riparte l'app
            self.b_banda.setEnabled(False)
            self._aggiorna_testo_banda(
                "Su questo computer non c'è il Bluetooth di sistema.")
        elif not cerca_braccialetto():
            # non trovato *ora* non vuol dire mai: l'accoppiamento può
            # completarsi dopo l'avvio, o l'adattatore Bluetooth svegliarsi
            # un istante più tardi. Il bottone resta vivo — ci riprova
            # `accendi()` stesso al tocco, e dice lui se ancora non c'è.
            self._aggiorna_testo_banda(
                "Se non è ancora accoppiato, accoppialo dalle impostazioni "
                "Bluetooth del sistema.")

        self.azioni_intestazione = (
            [self.b_banda, self.b_tema] + self.azioni_intestazione)

        # ------------------------------------------------------------- oggi
        # L'anello si tinge dell'umore stesso — verde se la giornata va bene,
        # arancio o rosso se no — invece del verde fisso dell'accento: così
        # dice qualcosa anche prima di leggere il numero. Sotto, gli stessi
        # quattro numeri di prima ma in colonne divise da un filo, come la
        # riga degli indici in Salute: più grandi, e con un bordo fra l'uno
        # e l'altro invece che il vuoto a tenerli separati.
        contenuto, lay = self.colonna(10)
        self.anello_umore = Anello(self.c, self.c["accento"])
        # Più grande di prima: nella colonna stretta della Home ("oggi" è
        # un terzo della riga) il minimo di prima — 110px — era anche il
        # massimo che si vedeva mai, perché il tetto di allora (190px) non
        # si raggiungeva mai a quella larghezza. L'anello è `Anello`, e
        # disegna un cerchio grande quanto il lato più corto del suo
        # spazio: qui il collo di bottiglia è la larghezza della colonna,
        # non l'altezza, quindi serve più margine su entrambe.
        self.anello_umore.setMinimumHeight(150)
        # un tetto, non solo un minimo: senza, in un riquadro alto l'anello
        # si gonfiava a occupare tutto lo spazio che avanzava, e i quattro
        # numeri sotto restavano spinti in fondo con un vuoto enorme sopra
        self.anello_umore.setMaximumHeight(260)
        # Niente `Qt.AlignHCenter` qui: un'allineatura fa sì che il layout
        # dia al widget solo la sua dimensione minima invece di farlo
        # crescere a riempire la colonna — è il motivo per cui alzare
        # minimo e massimo, prima, non cambiava niente: il collo di
        # bottiglia non era l'altezza concessa, era che il cerchio non si
        # allargava mai oltre i suoi 92px di default. `Anello` disegna già
        # il cerchio centrato dentro tutto lo spazio che gli arriva.
        lay.addWidget(self.anello_umore, 1)
        lay.addWidget(separatore())
        self.riquadro_oggi = QWidget()
        self.riquadro_oggi.setObjectName("ContenutoSezione")
        self.lay_oggi = QHBoxLayout(self.riquadro_oggi)
        self.lay_oggi.setContentsMargins(0, 4, 0, 2)
        self.lay_oggi.setSpacing(0)
        lay.addWidget(self.riquadro_oggi)
        # Non solo oggi: la rotella del mouse (o due dita sul trackpad) sopra
        # il riquadro sfoglia i giorni indietro, uno per volta — com'è già
        # la rotella sui grafici, giù nel passato e su verso il presente.
        # «Oggi» accanto al titolo compare solo quando ti sei allontanato,
        # ed è la strada rapida per tornare indietro.
        self._scarto_oggi = 0
        self._contenuto_oggi = contenuto
        self._contenuto_oggi.installEventFilter(self)
        self._contenuto_oggi.setToolTip(
            "Scorri con la rotella (o due dita sul trackpad) per vedere un "
            "altro giorno.")
        # Un contenitore attorno al bottone, non il bottone da solo come
        # comando: `Intestazione.aggancia_comando` chiama `.show()` sul
        # comando ogni volta che la riga si rifà (resize, cambio tema…), e
        # lo farebbe ricomparire anche quando deve restare nascosto. Dentro
        # un contenitore sempre «mostrato», il bottone può restare nascosto
        # per conto suo — lo stesso trucco di «Oggi» dentro `NavigatorePeriodo`.
        self._comando_oggi = QWidget()
        _lay_comando_oggi = QHBoxLayout(self._comando_oggi)
        _lay_comando_oggi.setContentsMargins(0, 0, 0, 0)
        # Non la scritta «Oggi»: il titolo del riquadro è già «Oggi», e con
        # un bottone uguale accanto se ne leggevano due insieme. Una
        # freccina che torna indietro dice la stessa cosa senza ripetersi.
        self.b_oggi_torna = QPushButton("↺")
        self.b_oggi_torna.setObjectName("NavOggi")
        self.b_oggi_torna.setCursor(Qt.PointingHandCursor)
        self.b_oggi_torna.setFocusPolicy(Qt.NoFocus)
        self.b_oggi_torna.setToolTip("Torna a oggi")
        self.b_oggi_torna.clicked.connect(self._torna_a_oggi)
        self.b_oggi_torna.hide()
        _lay_comando_oggi.addWidget(self.b_oggi_torna)
        self.aggiungi("oggi", contenuto, comando=self._comando_oggi)

        # --------------------------------------------------------- emotivo
        # Prima il grafico mostrava solo umore ed energia, scelti una volta
        # per tutte nel codice: stress e lucidità, che la pagina Emozioni
        # misura lo stesso, qui non si vedevano mai. Ora ci sono tutte e
        # quattro, e la legenda sotto è il comando per scegliere quali
        # vedere — ci clicchi sopra una voce e quella linea sparisce dal
        # grafico, ricicchi e torna. La scelta si ricorda da una sessione
        # all'altra, come il periodo.
        self.nav_emotivo = NavigatorePeriodo(self.c, "settimane", tutto=True)
        self.nav_emotivo.cambiato.connect(self._aggiorna_emotivo)
        self.g_emotivo = GraficoLinea(self.c)
        self.g_emotivo.formato = lambda v: numero(v, 1)
        self.g_emotivo.minimo_forzato = 0
        self.g_emotivo.massimo_forzato = 10
        # niente legenda muta disegnata dentro il grafico: quella viva, che
        # si tocca, sta sopra — dirlo due volte non serviva
        self.g_emotivo.mostra_legenda = False
        # una linea sola, senza i pallini su ogni giorno: con quattro serie
        # che si incrociano i puntini si accavallano, ed è più pulita una
        # curva morbida — il suggerimento al passaggio del mouse resta
        self.g_emotivo.mostra_punti = False
        self.nav_emotivo.scorri_con_rotella(self.g_emotivo)
        contenuto, lay = self.colonna(6)
        salvate = self.db.leggi("cruscotto_emotivo_misure", "")
        chiavi_valide = {m[0] for m in MISURE_EMOTIVE}
        attive = ({k for k in salvate.split(",") if k in chiavi_valide}
                 if salvate else chiavi_valide) or chiavi_valide
        self.legenda_emotivo = LegendaMisure(
            self.c, [(k, n, col) for k, n, col in MISURE_EMOTIVE], attive)
        self.legenda_emotivo.cambiata.connect(self._cambia_misure_emotivo)
        # sopra il grafico, non sotto: è la prima cosa che si legge, e in
        # cima somiglia di più alla legenda che c'era prima dentro il disegno
        lay.addWidget(self.legenda_emotivo)
        lay.addWidget(self.g_emotivo, 1)
        self.aggiungi("emotivo", contenuto, comando=self.nav_emotivo)

        # ---------------------------------------------------------- salute
        contenuto, lay = self.colonna(10)
        self.anello_passi = Anello(self.c, self.c["accento"])
        self.anello_passi.setMinimumHeight(96)
        self.anello_passi.setCursor(Qt.PointingHandCursor)
        self.anello_passi.setToolTip("Doppio clic per aprire Salute.")
        self.anello_passi.mouseDoubleClickEvent = (
            lambda _ev: self.area_richiesta.emit("salute"))
        lay.addWidget(self.anello_passi, 1)
        fila = QHBoxLayout()
        fila.setContentsMargins(0, 0, 0, 0)
        fila.setSpacing(10)
        self.cerchietti = {
            "battito": AnelloEtichettato(self.c, "Battito", "#ff5a5a"),
            "sonno": AnelloEtichettato(self.c, "Sonno", "#3d7bfd"),
            "allenamenti": AnelloEtichettato(self.c, "Allenamenti",
                                             self.c["accento"]),
        }
        for cerchietto in self.cerchietti.values():
            fila.addWidget(cerchietto, 1)
        lay.addLayout(fila)
        self.aggiungi("salute", contenuto)

        # -------------------------------------------------------- carriera
        self.cont_carriera, self.lay_carriera = self.colonna(9)
        # «+», matita, cestino sulla riga del titolo: come in Emozioni e
        # Impegni, non più solo il doppio clic che non si vede. Le righe
        # non stanno in una tabella (sono `RigaMisura` in colonna), quindi
        # la scelta la tiene `SelezioneSemplice`, che si finge una tabella
        # giusto quanto basta per `AzioniRiga`.
        self.riga_scelta_carriera = SelezioneSemplice()
        self.azioni_carriera = AzioniRiga(
            self.c, self.riga_scelta_carriera, "questo progetto",
            nuovo="Nuovo progetto")
        self.azioni_carriera.aggiunge.connect(self._nuovo_progetto_home)
        self.azioni_carriera.modifica.connect(self._modifica_progetto_home)
        self.azioni_carriera.elimina.connect(self._elimina_progetto_home)
        self.aggiungi("carriera", self.scorrevole(self.cont_carriera),
                      comando=self.azioni_carriera)

        # ------------------------------------------------------ accademica
        self.cont_accademica, self.lay_accademica = self.colonna(9)
        self.riga_scelta_accademica = SelezioneSemplice()
        self.azioni_accademica = AzioniRiga(
            self.c, self.riga_scelta_accademica, "questo esame",
            nuovo="Nuovo esame")
        self.azioni_accademica.aggiunge.connect(self._nuovo_esame_home)
        self.azioni_accademica.modifica.connect(self._modifica_esame_home)
        self.azioni_accademica.elimina.connect(self._elimina_esame_home)
        self.aggiungi("accademica", self.scorrevole(self.cont_accademica),
                      comando=self.azioni_accademica)

        # -------------------------------------------------------- emozioni
        # Le attività dell'area Emozioni. `RiquadroAttivita` legge
        # direttamente la tabella `scadenze` filtrata sull'area, quindi
        # quello che scrivi qui è subito vero anche nella pagina Emozioni e
        # per chi legge l'archivio da un altro posto — non serve nessun
        # collegamento in più perché restino allineati.
        #
        # Non è l'unica che si può avere: dal menu «Riquadri» si aggiungono
        # le stesse cose per Carriera, Accademica, Salute o Finanza — ognuna
        # un riquadro suo, mai uno che le mescola tutte.
        self.riquadri_attivita: dict[str, RiquadroAttivita] = {}
        self.riq_emozioni = self._crea_riquadro_attivita("emozioni")

        # ------------------------------------------------------- abitudini
        contenuto, lay = self.colonna(8)
        self.mappa = MappaCalore(self.c)
        self.mappa.etichette = False      # qui contano i quadretti, non le lettere
        self.mappa.giorno_scelto.connect(
            lambda _g: self.area_richiesta.emit("abitudini"))
        self.mappa.setCursor(Qt.PointingHandCursor)
        lay.addWidget(self.mappa, 1)
        # la stessa pastiglia stretta della costanza in Salute: un calendario
        # a quadretti è una durata, non un arco da sfogliare
        self.periodo_abitudini = SceltaPeriodo(
            self.GIORNI_ABITUDINI, self.db.leggi("cruscotto_abitudini", "30"),
            self.c, self.GIORNI_ABITUDINI_CORTI)
        self.periodo_abitudini.scelto.connect(
            lambda v: (self.db.imposta("cruscotto_abitudini", v),
                       self._aggiorna_abitudini()))
        self.aggiungi("abitudini", contenuto,
                      comando=self.periodo_abitudini)

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

        # --------------------------------------------------------- finanza
        contenuto, lay = self.colonna(8)
        self.et_saldo = QLabel("—")
        self.et_saldo.setObjectName("ValoreScheda")
        lay.addWidget(self.et_saldo)
        self.et_finanza = EtichettaACapo("")
        self.et_finanza.setObjectName("NotaScheda")
        lay.addWidget(self.et_finanza)
        self.nav_finanza = NavigatorePeriodo(self.c, "mesi")
        self.nav_finanza.cambiato.connect(self._aggiorna_finanza)
        self.g_finanza = GraficoBarre(self.c)
        self.g_finanza.formato = lambda v: euro(v).replace(",00", "")
        self.nav_finanza.scorri_con_rotella(self.g_finanza)
        lay.addWidget(self.g_finanza, 1)
        self.aggiungi("finanza", contenuto, comando=self.nav_finanza)

        # --------------------------------------------------------- impegni
        self.tab = QTableWidget(0, 4)
        self.tab.setHorizontalHeaderLabels(["Quando", "Cosa", "Area", "Fatta"])
        self.tab.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tab.setSelectionBehavior(QTableWidget.SelectRows)
        h = self.tab.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        abilita_deselezione(self.tab)
        stile_tabella(self.tab)
        self.tab.doubleClicked.connect(self._modifica_impegno)
        self.tab.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tab.customContextMenuRequested.connect(self._menu_impegno)
        self.azioni_impegni = AzioniRiga(self.c, self.tab, "questo impegno",
                                         nuovo="Aggiungi un impegno")
        self.azioni_impegni.aggiunge.connect(self.nuovo_impegno)
        self.azioni_impegni.modifica.connect(self._modifica_impegno)
        self.azioni_impegni.elimina.connect(self._elimina_impegno)
        self.aggiungi("impegni", self.tab, comando=self.azioni_impegni)

        # I riquadri presi in prestito dalle altre pagine, se ce n'erano.
        # Vanno registrati **adesso**, prima che la base ripristini la
        # disposizione salvata: se arrivassero dopo, il loro posto nella
        # griglia sarebbe già stato deciso senza di loro.
        for chiave in self._prestiti_salvati():
            self._presta(chiave)

        # Stesso discorso per le aree extra di attività: anche queste prima
        # che la base ripristini la disposizione, o resterebbero fuori.
        for area in self._attivita_extra_salvate():
            self._crea_riquadro_attivita(area)

        self.grafici = [self.g_emotivo, self.g_finanza, self.anello_umore,
                        self.anello_passi, self.mappa, self.legenda_emotivo,
                        *self.cerchietti.values()]

    # ------------------------------------------------- riquadri in prestito
    # Un riquadro di un'altra pagina mostrato qui **è quello vero**, non una
    # copia: si costruisce la pagina di origine (senza mostrarla mai) e le si
    # prende il riquadro già montato — grafico, comandi, menu dei periodi.
    # Così non c'è niente da tenere allineato: quello che si corregge nella
    # sua pagina è corretto anche qui, perché è lo stesso oggetto.
    def _prestiti_salvati(self) -> list[str]:
        grezzo = self.db.leggi(self.CHIAVE_PRESTITI, "")
        return [c for c in grezzo.split("|") if c]

    def _salva_prestiti(self) -> None:
        presi = [c for c in self.contenitore.sezioni if catalogo.e_prestito(c)]
        self.db.imposta(self.CHIAVE_PRESTITI, "|".join(presi))

    def _vista_prestata(self, pagina: str):
        """La pagina da cui prendere, costruita alla prima richiesta.

        Non viene mai mostrata: serve solo come officina dove i riquadri
        nascono già montati e già capaci di aggiornarsi da soli.
        """
        if pagina not in self._viste_prestate:
            vista = catalogo.classe(pagina)(self.db, self.c, self.fonte)
            vista.hide()
            self._viste_prestate[pagina] = vista
        return self._viste_prestate[pagina]

    def _presta(self, chiave: str) -> bool:
        pagina, riquadro = catalogo.spacchetta(chiave)
        if pagina not in catalogo.PAGINE or chiave in self.contenitore.sezioni:
            return False
        try:
            vista = self._vista_prestata(pagina)
        except Exception:        # noqa: BLE001 — una pagina rotta non rompe la Home
            return False
        sezione = vista.contenitore.sezioni.get(riquadro)
        if sezione is None:
            return False
        # chiave nuova: «salute» esiste già qui come riquadro nostro, e due
        # riquadri con lo stesso nome si scalzerebbero a vicenda
        sezione.chiave = chiave
        nome = vista.SEZIONI.get(riquadro, riquadro)
        self.SEZIONI[chiave] = (f"{nome.capitalize() if nome.isupper() else nome}"
                                f"  ·  {catalogo.titolo(pagina)}")
        self.contenitore.registra(sezione)
        azione = QAction(self.SEZIONI[chiave], self, checkable=True, checked=True)
        azione.toggled.connect(lambda visibile, k=chiave: self._mostra(k, visibile))
        self.menu_sezioni.insertAction(self.sep_prestiti, azione)
        self.azioni[chiave] = azione
        return True

    def _restituisci(self, chiave: str) -> None:
        sezione = self.contenitore.sezioni.pop(chiave, None)
        if sezione is not None:
            sezione.hide()
            sezione.setParent(None)
        azione = self.azioni.pop(chiave, None)
        if azione is not None:
            self.menu_sezioni.removeAction(azione)
        self.SEZIONI.pop(chiave, None)

    def scegli_prestiti(self) -> None:
        """La finestra con tutti i riquadri delle altre pagine."""
        prima = {c for c in self.contenitore.sezioni if catalogo.e_prestito(c)}
        dialogo = SceltaRiquadri(prima, parent=self)
        if not dialogo.exec():
            return
        dopo = dialogo.scelti()
        for chiave in prima - dopo:
            self._restituisci(chiave)
        nuovi = [c for c in sorted(dopo - prima) if self._presta(c)]
        if nuovi:
            self.contenitore.aggiungi_in_fondo(nuovi)
        self._salva_prestiti()
        self._salva()
        self.aggiorna()

    # ---------------------------------------------------------------- Tess
    def _tocca_tess(self, acceso: bool) -> None:
        """L'interruttore accende e spegne il motore dell'AI locale.

        La chat vive nella sua pagina: qui c'è solo l'interruttore, perché
        accenderla da dove si guardano i numeri è comodo.
        """
        if not acceso:
            self.motore_tess.spegni()
            self._nota_tess(False)
            return
        self._nota_tess(True, "accendo")
        # Si riparte dal piu' svelto, come dalla pagina di Tess.
        # Il nome si risolve **qui**, nel filo della finestra: dentro
        # Accensione l'archivio SQLite non e' utilizzabile, e l'eccezione
        # ucciderebbe il filo lasciando l'interruttore a caricare per sempre.
        self.db.imposta("tess_modello", "")
        self.accensione_tess = Accensione(self.motore_tess, self,
                                          modello=self.motore_tess.modello())
        self.accensione_tess.fase.connect(
            lambda quale: self._nota_tess(True, "accendo"
                                          if quale == "motore" else "carico"))
        self.accensione_tess.pronta.connect(self._tess_accesa)
        self.accensione_tess.start()

    def _tess_accesa(self, riuscita: bool, errore: str) -> None:
        if not riuscita:
            self.interruttore_tess.imposta(False)
            self._nota_tess(False, errore)
            return
        self._nota_tess(True)
        self.area_richiesta.emit("tess")      # la chat è di là

    def _nota_tess(self, pronta: bool, messaggio: str = "") -> None:
        if messaggio == "accendo":
            nota = "Sto accendendo il motore…"
        elif messaggio == "carico":
            nota = "Carico il modello nella scheda video: qualche secondo."
        elif messaggio:
            nota = f"Non sono riuscito ad accendere Tess. {messaggio}"
        elif pronta:
            nota = ("Tess è in ascolto: la chat è nella sua pagina.\n"
                    "Spegni per liberare la memoria della scheda video.")
        else:
            nota = ("Accende la tua AI locale, poi apre la sua pagina.\n"
                    "Finché non la accendi non parte nessun motore e non si "
                    "occupa memoria.")
        for w in (self.comando_tess, self.et_tess, self.interruttore_tess):
            w.setToolTip(nota)

    # ---------------------------------------------------------------- tema
    def _commuta_tema(self) -> None:
        nuovo = "chiaro" if self.db.leggi("tema", "scuro") == "scuro" else "scuro"
        self.db.imposta("tema", nuovo)
        self._aggiorna_testo_tema(nuovo)
        self.tema_cambiato.emit(nuovo)

    def _aggiorna_testo_tema(self, tema: str = "") -> None:
        t = tema or self.db.leggi("tema", "scuro")
        if t == "scuro":
            self.b_tema.setText("☀️  Chiaro")
            self.b_tema.setToolTip("Passa al tema chiaro (Ctrl+T)")
        else:
            self.b_tema.setText("🌙  Scuro")
            self.b_tema.setToolTip("Passa al tema scuro (Ctrl+T)")

    def aggiorna_tema(self, colori: dict) -> None:
        super().aggiorna_tema(colori)
        self._aggiorna_testo_tema()
        self._aggiorna_testo_banda()

    # ------------------------------------------------------------ braccialetto
    def _tocca_banda(self) -> None:
        if self.banda_home.acceso:
            self.banda_home.spegni()
            self._aggiorna_testo_banda("Spento.")
        elif self.banda_home.accendi():
            self._aggiorna_testo_banda()
        # se accendi() non parte nemmeno, ha già emesso lui lo stato con il
        # motivo (niente Bluetooth, non accoppiato…): non lo si sovrascrive

    def _stato_banda(self, codice: str, frase: str) -> None:
        self._aggiorna_testo_banda(frase)

    def _batteria_banda(self, livello: int, carica: int) -> None:
        self._aggiorna_testo_banda(
            f"Batteria {livello}%" + (" in carica" if carica else ""))

    def _aggiorna_testo_banda(self, nota: str = "") -> None:
        """Acceso o spento si deve vedere, non solo intuire: la stessa
        scritta con l'orologio, ma da collegato diventa una pastiglia tinta
        — niente rosso/verde da semaforo, ma un bottone «premuto» invece
        che spento è inequivocabile."""
        acceso = self.banda_home.acceso
        self.b_banda.setText("⌚  Braccialetto")
        if acceso:
            self.b_banda.setStyleSheet(
                "QPushButton#AzioneTestata {"
                f"background: {trasparente(self.c['accento'], 0.24)};"
                f"color: {self.c['accento']};}}"
                "QPushButton#AzioneTestata:hover {"
                f"background: {trasparente(self.c['accento'], 0.34)};}}")
        else:
            self.b_banda.setStyleSheet("")
        base = ("Braccialetto collegato: tocca per spegnerlo." if acceso else
                "Braccialetto spento: tocca per collegarlo.\n"
                "Batteria e battito in diretta sono nel riquadro di Salute.")
        self.b_banda.setToolTip(f"{base}\n{nota}" if nota else base)

    def _allinea_tess(self) -> None:
        pass

    # ---------------------------------------------------------------- dati
    def aggiorna(self) -> None:
        self._aggiorna_oggi()
        self._aggiorna_emotivo()
        self._aggiorna_salute()
        self._aggiorna_battito()
        self._aggiorna_indicatori()
        self._aggiorna_carriera()
        self._aggiorna_accademica()
        self._aggiorna_emozioni()
        self._aggiorna_abitudini()
        self._aggiorna_finanza()
        self._aggiorna_impegni()
        self._aggiorna_prestati()

    def _aggiorna_prestati(self) -> None:
        """Fa aggiornare le pagine da cui abbiamo preso qualcosa.

        I riquadri in prestito sono quelli veri, e si riempiono dal metodo
        `aggiorna()` della loro pagina: senza chiamarlo resterebbero fermi
        ai dati del momento in cui sono stati costruiti. Una pagina che si
        rompe non deve portarsi dietro la Home.
        """
        for pagina, vista in list(self._viste_prestate.items()):
            try:
                vista.aggiorna()
            except Exception:    # noqa: BLE001
                pass

    def _numero(self, valore: str, nota: str, colore: str) -> QWidget:
        """Una colonna: il numero grande sopra, cos'è sotto — come in Salute."""
        cella = QWidget()
        cella.setObjectName("ContenutoSezione")
        colonna = QVBoxLayout(cella)
        colonna.setContentsMargins(0, 0, 0, 0)
        colonna.setSpacing(1)
        v = QLabel(valore)
        v.setObjectName("ValoreRiga")
        v.setAlignment(Qt.AlignCenter)
        v.setStyleSheet(f"color: {colore if valore != '—' else self.c['testo2']};")
        n = etichetta(nota, "NotaScheda")
        n.setAlignment(Qt.AlignCenter)
        colonna.addWidget(v)
        colonna.addWidget(n)
        return cella

    def _colore_umore(self, valore: float) -> str:
        """Lo stesso verso di colori della pagina Emozioni: più l'umore è
        alto, più verso il verde; più è basso, più verso il rosso."""
        if valore >= 7.5:
            return self.c["entrata"]
        if valore >= 6:
            return "#8bbf6a"
        if valore >= 4.5:
            return self.c["attenzione"]
        if valore >= 3:
            return "#f7913a"
        return self.c["uscita"]

    def eventFilter(self, oggetto, evento) -> bool:
        if (evento.type() == QEvent.Wheel
                and oggetto is getattr(self, "_contenuto_oggi", None)):
            self._scorri_oggi(evento)
            return True
        return super().eventFilter(oggetto, evento)

    def _scorri_oggi(self, evento) -> None:
        """Rotella giù: un giorno indietro. Su: un giorno avanti, fino a oggi."""
        passi = evento.angleDelta().y()
        evento.accept()
        if not passi:
            return
        nuovo = max(0, self._scarto_oggi + (-1 if passi > 0 else 1))
        if nuovo == self._scarto_oggi:
            return
        self._scarto_oggi = nuovo
        self._aggiorna_oggi()

    def _torna_a_oggi(self) -> None:
        if self._scarto_oggi:
            self._scarto_oggi = 0
            self._aggiorna_oggi()

    def _aggiorna_oggi(self) -> None:
        while self.lay_oggi.count():
            w = self.lay_oggi.takeAt(0).widget()
            if w is not None:
                w.hide(); w.setParent(None); w.deleteLater()
        giorno = (date.today() - timedelta(days=self._scarto_oggi)).isoformat()
        self.b_oggi_torna.setVisible(bool(self._scarto_oggi))
        medie = self.db.medie_periodo(giorno, giorno)
        if medie["n"]:
            umore = medie["umore"]
            self.anello_umore.imposta(umore / 10, voto(umore),
                                      f"umore {faccia(umore)}",
                                      colore=self._colore_umore(umore))
        else:
            self.anello_umore.imposta(0, "—", "nessuna voce",
                                      colore=self.c["griglia"])
        salute = self.db.salute_giorno(giorno)
        colonne = [
            self._numero(durata(salute["sonno"]) if salute and salute["sonno"]
                        else "—", "sonno", "#6c8cff"),
            self._numero(numero(salute["passi"], 0)
                        if salute and salute["passi"] else "—",
                        "passi", self.c["accento"]),
            self._numero(durata(self.db.minuti_studio(giorno, giorno)),
                        "studio", "#b07cff"),
            self._numero(durata(self.db.minuti_lavoro(giorno, giorno)),
                        "lavoro", "#6c8cff"),
        ]
        for posto, cella in enumerate(colonne):
            if posto:
                self.lay_oggi.addWidget(separatore_verticale())
            self.lay_oggi.addWidget(cella, 1)
        self.contenitore.sezioni["oggi"].imposta_nota(
            f"{data_lunga(giorno)} · {medie['n']} voci")

    def _cambia_misure_emotivo(self) -> None:
        self.db.imposta("cruscotto_emotivo_misure",
                        ",".join(sorted(self.legenda_emotivo.attive())))
        self._aggiorna_emotivo()

    def _aggiorna_emotivo(self) -> None:
        dal, al = self.nav_emotivo.esteso()
        righe = self.db.medie_giorno(dal, al)
        if len(righe) < 2:
            self.g_emotivo.vuoto = (
                f"Niente scritto {self.nav_emotivo.nome_esteso()}."
                if not righe else
                "Un giorno solo: per disegnare una linea ce ne vogliono due.")
            self.g_emotivo.imposta_serie([])
            self.contenitore.sezioni["emotivo"].imposta_nota(
                "" if not righe else "un giorno scritto")
            return
        def punti(campo):
            return [(data_it(r["data"])[:5], float(r[campo])) for r in righe]
        attive = self.legenda_emotivo.attive()
        self.g_emotivo.imposta_serie([
            (nome, punti(chiave), colore or self.c["accento"])
            for chiave, nome, colore in MISURE_EMOTIVE if chiave in attive])
        valori = [float(r["umore"]) for r in righe]
        self.contenitore.sezioni["emotivo"].imposta_nota(
            f"umore medio {numero(media(valori), 1)} · {len(righe)} giorni scritti")

    def _aggiorna_salute(self) -> None:
        """Un anello grande per i passi di oggi, tre piccoli per il resto."""
        oggi = date.today().isoformat()
        r = self.db.salute_giorno(oggi)
        obiettivo = self.db.leggi_num("obiettivo_passi", PREDEFINITI["obiettivo_passi"])
        passi = int(r["passi"]) if r else 0
        quota = passi / obiettivo if obiettivo else 0
        self.anello_passi.imposta(quota, numero(passi, 0) if passi else "—",
                                  "passi" if passi else "nessun dato oggi")
        self.anello_passi.setToolTip(
            f"{numero(passi, 0)} passi oggi · {quota * 100:.0f}% dell'obiettivo "
            f"({numero(obiettivo, 0)})\n\nDoppio clic per aprire Salute."
            if passi else "Oggi non ci sono ancora passi.\n\n"
                          "Doppio clic per aprire Salute.")

        settimana = ultimi_giorni(7)
        dati = self.db.giorni_salute(settimana[0], settimana[-1])
        battiti = [float(x["battito"]) for x in dati.values() if x["battito"]]
        sonni = [float(x["sonno"]) for x in dati.values() if x["sonno"]]
        dal, al = settimana_corrente()
        allenamenti = len(self.db.allenamenti(dal, al))
        obiettivo_all = self.db.leggi_num("obiettivo_allenamenti",
                                          PREDEFINITI["obiettivo_allenamenti"])
        obiettivo_sonno = self.db.leggi_num("obiettivo_sonno",
                                            PREDEFINITI["obiettivo_sonno"])

        self.cerchietti["battito"].imposta(
            _quota_battito(media(battiti)) / 100 if battiti else 0,
            f"{numero(media(battiti), 0)}" if battiti else "—",
            f"Battito a riposo: media {numero(media(battiti), 0)} bpm "
            f"negli ultimi 7 giorni" if battiti
            else "Nessun battito registrato negli ultimi 7 giorni")
        self.cerchietti["sonno"].imposta(
            media(sonni) / obiettivo_sonno if sonni and obiettivo_sonno else 0,
            durata(media(sonni)) if sonni else "—",
            f"Sonno: media {durata(media(sonni))} su {len(sonni)} notti "
            f"(obiettivo {durata(obiettivo_sonno)})" if sonni
            else "Nessuna notte registrata negli ultimi 7 giorni")
        self.cerchietti["allenamenti"].imposta(
            allenamenti / obiettivo_all if obiettivo_all else 0,
            f"{allenamenti}/{obiettivo_all:.0f}",
            f"Allenamenti: {allenamenti} su {obiettivo_all:.0f} questa settimana")

        self.contenitore.sezioni["salute"].imposta_nota(
            f"oggi · obiettivo {numero(obiettivo, 0)} passi")

    def _aggiorna_battito(self) -> None:
        """Lo stesso riquadro di Salute, qui in piccolo."""
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
                "nessuna misura dal braccialetto")

    def _aggiorna_indicatori(self) -> None:
        self.svuota(self.lay_ind)
        quanti = int(self.periodo("indicatori"))
        righe = righe_indicatori(self.db, self.c, quanti)
        for _campo, misura in righe:
            self.lay_ind.addWidget(misura)
        if not righe:
            self.lay_ind.addWidget(etichetta(
                "Battito, variabilità, stress e acqua: li scrivi in Salute → "
                "«Inserimento dati», o li porta il braccialetto.", "NotaScheda"))
        self.lay_ind.addStretch(1)

    def _segna_scelta(self, righe: dict, scelto: int | None) -> None:
        """Il fondo tinto sulla riga scelta — altrimenti su cosa agiranno
        la matita e il cestino resterebbe invisibile."""
        for id_, riga in righe.items():
            riga.setStyleSheet(
                f"background: {trasparente(self.c['accento'], 0.16)};"
                " border-radius: 10px;" if id_ == scelto else "")

    def _riga_cliccabile(self, riga, id_: int, selezione: "SelezioneSemplice",
                         righe: dict, doppio_clic) -> None:
        """Clic per scegliere (accende matita e cestino), doppio clic per
        aprire subito la modifica — lo stesso gesto che ha già Accademica
        nella sua pagina, qui anche visibile."""
        riga.setCursor(Qt.PointingHandCursor)
        riga.setToolTip("Clic per scegliere, doppio clic per modificare.")

        def premuto(_ev, id_=id_):
            selezione.scegli(id_)
            self._segna_scelta(righe, id_)
        riga.mousePressEvent = premuto
        riga.mouseDoubleClickEvent = lambda _ev, id_=id_: doppio_clic(id_)

    def _aggiorna_carriera(self) -> None:
        self.svuota(self.lay_carriera)
        self.riga_scelta_carriera.scegli(None)
        self._righe_carriera: dict[int, RigaMisura] = {}
        progetti = [p for p in self.db.progetti() if p["stato"] in ("corso", "pausa")]
        if not progetti:
            self.lay_carriera.addWidget(etichetta(
                "Nessun progetto in corso.", "NotaScheda"))
        for p in progetti[:6]:
            nota = p["cliente"] or p["tipo"]
            if p["scadenza"]:
                nota = f"{nota} · entro {data_it(p['scadenza'])}"
            if p["stato"] == "pausa":
                nota = f"{nota} · in pausa"
            riga = RigaMisura(
                self.c, "", p["nome"], nota, f"{p['avanzamento']}%",
                euro(p["compenso"]) if p["compenso"] else "", p["avanzamento"],
                p["colore"])
            self._riga_cliccabile(riga, p["id"], self.riga_scelta_carriera,
                                 self._righe_carriera, self._apri_progetto_home)
            self._righe_carriera[p["id"]] = riga
            self.lay_carriera.addWidget(riga)
        self.lay_carriera.addStretch(1)
        dal, al = settimana_corrente()
        minuti = self.db.minuti_lavoro(dal, al)
        dal_m, al_m = mese_corrente()
        incassi = self.db.totale_incassi(dal_m, al_m)
        self.contenitore.sezioni["carriera"].imposta_nota(
            f"{durata(minuti)} questa settimana · {euro(incassi)} questo mese")

    def _aggiorna_accademica(self) -> None:
        self.svuota(self.lay_accademica)
        self.riga_scelta_accademica.scegli(None)
        self._righe_accademica: dict[int, RigaMisura] = {}
        esami = [e for e in self.db.esami() if e["stato"] != "superato"]
        esami.sort(key=lambda e: (e["data_esame"] == "", e["data_esame"]))
        if not esami:
            self.lay_accademica.addWidget(etichetta(
                "Nessun esame in programma.", "NotaScheda"))
        for e in esami[:6]:
            nota = f"{e['cfu']} CFU"
            valore = data_it(e["data_esame"]) if e["data_esame"] else "da fissare"
            riga = RigaMisura(
                self.c, "", e["nome"], nota, valore, f"{e['avanzamento']}%",
                e["avanzamento"], "#35c4d7")
            self._riga_cliccabile(riga, e["id"], self.riga_scelta_accademica,
                                 self._righe_accademica, self._apri_esame_home)
            self._righe_accademica[e["id"]] = riga
            self.lay_accademica.addWidget(riga)
        self.lay_accademica.addStretch(1)
        # Niente più ore di studio qui: quel numero si legge in Accademica,
        # questo riquadro resta sul libretto — a che punto sono gli esami.
        r = self.db.riepilogo_libretto()
        self.contenitore.sezioni["accademica"].imposta_nota(
            f"CFU {r['cfu']} · media {numero(r['media'], 1)}" if r["n"] else
            "Nessun esame nel libretto")

    # ------------------------------------------------------- i progetti
    # Stessa tabella «progetti» della pagina Carriera: un progetto scritto
    # qui, o corretto qui, è lo stesso progetto di là.
    def _apri_progetto_home(self, id_: int) -> None:
        """Doppio clic su una riga: sceglila e apri subito la modifica —
        il gesto che c'era già, ora con la matita accanto a dirlo."""
        self.riga_scelta_carriera.scegli(id_)
        self._segna_scelta(self._righe_carriera, id_)
        self._modifica_progetto_home()

    def _nuovo_progetto_home(self) -> None:
        dialogo = DialogoProgetto(parent=self)
        if dialogo.exec():
            self.db.salva_progetto(dialogo.dati())
            self.aggiorna()

    def _modifica_progetto_home(self) -> None:
        id_ = self.riga_scelta_carriera.scelto()
        if id_ is None:
            return self._nuovo_progetto_home()
        voce = self.db.uno("SELECT * FROM progetti WHERE id=?", (id_,))
        if voce is None:
            return
        dialogo = DialogoProgetto(voce, parent=self)
        if dialogo.exec():
            self.db.salva_progetto(dialogo.dati())
            self.aggiorna()

    def _elimina_progetto_home(self) -> None:
        id_ = self.riga_scelta_carriera.scelto()
        if id_ is None:
            return
        voce = self.db.uno("SELECT * FROM progetti WHERE id=?", (id_,))
        if voce is None:
            return
        if QMessageBox.question(
                self, "Eliminare?",
                f"Vuoi eliminare «{voce['nome']}», con le ore e gli "
                "incassi che gli sono attaccati?",
                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        self.db.elimina("progetti", id_)
        self.aggiorna()

    # ---------------------------------------------------------- gli esami
    # Stessa tabella «esami» della pagina Accademica: niente di doppio.
    def _apri_esame_home(self, id_: int) -> None:
        self.riga_scelta_accademica.scegli(id_)
        self._segna_scelta(self._righe_accademica, id_)
        self._modifica_esame_home()

    def _nuovo_esame_home(self) -> None:
        dialogo = DialogoEsame(parent=self)
        if dialogo.exec():
            self.db.salva_esame(dialogo.dati())
            self.aggiorna()

    def _modifica_esame_home(self) -> None:
        id_ = self.riga_scelta_accademica.scelto()
        if id_ is None:
            return self._nuovo_esame_home()
        voce = self.db.uno("SELECT * FROM esami WHERE id=?", (id_,))
        if voce is None:
            return
        dialogo = DialogoEsame(voce, parent=self)
        if dialogo.exec():
            self.db.salva_esame(dialogo.dati())
            self.aggiorna()

    def _elimina_esame_home(self) -> None:
        id_ = self.riga_scelta_accademica.scelto()
        if id_ is None:
            return
        voce = self.db.uno("SELECT * FROM esami WHERE id=?", (id_,))
        if voce is None:
            return
        if QMessageBox.question(
                self, "Eliminare?", f"Vuoi eliminare «{voce['nome']}»?",
                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        self.db.elimina("esami", id_)
        self.aggiorna()

    # ---------------------------------------------------------- attività
    CHIAVE_ATTIVITA_EXTRA = "cruscotto_attivita_extra"

    @staticmethod
    def _chiave_attivita(area: str) -> str:
        # «emozioni» tiene il suo nome di sempre — è quello con cui la
        # disposizione salvata la trova già; le aree aggiunte dopo vanno
        # sotto un prefisso, per non rischiare di scontrarsi con nient'altro.
        return "emozioni" if area == "emozioni" else f"attivita_{area}"

    def _crea_riquadro_attivita(self, area: str) -> RiquadroAttivita:
        """Un riquadro «Attività» per una sola area. Non mescola mai aree
        diverse: è il motivo per cui esiste invece di un'unica tabella con
        tutto dentro, come Impegni."""
        riquadro = RiquadroAttivita(self.db, self.c, area)
        riquadro.cambiato.connect(self.aggiorna)
        chiave = self._chiave_attivita(area)
        self.SEZIONI[chiave] = ("Emozioni" if area == "emozioni" else
                                f"Attività · {AREE.get(area, area)}")
        self.riquadri_attivita[area] = riquadro
        self.aggiungi(chiave, riquadro, comando=riquadro.azioni)
        if area != "emozioni":
            # «emozioni» ha già la sua voce nel menu fin dall'inizio (sta
            # nel SEZIONI di classe); le aree aggiunte dopo si registrano
            # da sole, come fa `_presta` per i riquadri in prestito.
            azione = QAction(self.SEZIONI[chiave], self, checkable=True,
                             checked=True)
            azione.toggled.connect(
                lambda visibile, k=chiave: self._mostra(k, visibile))
            self.menu_sezioni.insertAction(self.sep_attivita, azione)
            self.azioni[chiave] = azione
        return riquadro

    def _attivita_extra_salvate(self) -> list[str]:
        grezzo = self.db.leggi(self.CHIAVE_ATTIVITA_EXTRA, "")
        return [a for a in grezzo.split("|") if a and a != "emozioni"]

    def _salva_attivita_extra(self) -> None:
        extra = [a for a in self.riquadri_attivita if a != "emozioni"]
        self.db.imposta(self.CHIAVE_ATTIVITA_EXTRA, "|".join(extra))

    def _popola_menu_attivita(self) -> None:
        self.menu_attivita_extra.clear()
        restano = [a for a in AREE if a not in self.riquadri_attivita]
        if not restano:
            azione = self.menu_attivita_extra.addAction(
                "Ci sono già tutte le aree")
            azione.setEnabled(False)
            return
        for area in restano:
            self.menu_attivita_extra.addAction(
                AREE[area], lambda a=area: self.aggiungi_area_attivita(a))

    def aggiungi_area_attivita(self, area: str) -> None:
        """Chiamato dal menu «Riquadri»: un'altra area, un riquadro suo."""
        if area in self.riquadri_attivita or area not in AREE:
            return
        self._crea_riquadro_attivita(area)
        self.contenitore.aggiungi_in_fondo([self._chiave_attivita(area)])
        self._salva_attivita_extra()
        self._salva()
        self.aggiorna()

    def _aggiorna_emozioni(self) -> None:
        """Il nome è storico (c'era solo Emozioni, all'inizio): aggiorna
        tutte le aree di attività che ci sono adesso, non solo quella."""
        for area, riquadro in self.riquadri_attivita.items():
            self.contenitore.sezioni[self._chiave_attivita(area)].imposta_nota(
                riquadro.nota())

    def _aggiorna_abitudini(self) -> None:
        quanti = int(self.periodo_abitudini.valore)
        # si parte da un lunedì: così le righe sono piene e la griglia è dritta
        oggi = date.today()
        inizio = oggi - timedelta(days=quanti - 1)
        inizio -= timedelta(days=inizio.weekday())
        elenco = [(inizio + timedelta(days=i)).isoformat()
                  for i in range((oggi - inizio).days + 1)]
        abitudini = self.db.abitudini()
        fatte = self.db.registro(elenco[0], elenco[-1])
        totale_giorno = max(1, len(abitudini))
        dati, suggerimenti = {}, {}
        for giorno in elenco:
            quante = sum(1 for (g, _) in fatte if g == giorno)
            if quante:
                dati[giorno] = (quante / totale_giorno, self.c["accento"])
            suggerimenti[giorno] = (f"{data_it(giorno)} — {quante} su "
                                    f"{totale_giorno} abitudini")
        self.mappa.imposta_dati(elenco, dati, suggerimenti)
        righe = []
        for a in abitudini:
            serie = self.db.serie_abitudine(a["id"])
            righe.append(f"{a['nome']}: {serie} giorni di fila" if serie
                         else f"{a['nome']}: nessuna serie")
        self.mappa.setToolTip(
            ("\n".join(righe) if righe else "Nessuna abitudine impostata.")
            + "\n\nPiù il quadretto è pieno, più abitudini hai segnato quel "
              "giorno. Clicca per aprire Abitudini.")
        segnate = len(fatte)
        giorni_pieni = len(dati)
        self.contenitore.sezioni["abitudini"].imposta_nota(
            f"{segnate} segni in {len(elenco)} giorni · {giorni_pieni} giornate "
            f"con almeno un segno")

    def _aggiorna_finanza(self) -> None:
        if self.fonte is None:
            return
        dal, al = mese_corrente()
        entrate, uscite = self.fonte.totali_periodo(dal, al)
        self.et_saldo.setText(euro(self.fonte.saldo()))
        self.et_finanza.setText(
            f"entrate {euro(entrate)} · uscite {euro(uscite)} · fonte {self.fonte.nome}")
        dati = []
        for nome, da, a in self.nav_finanza.finestre():
            e, u = self.fonte.totali_periodo(da, a)
            dati.append((nome, [e, u]))
        self.g_finanza.evidenziata = self.nav_finanza.indice_adesso()
        self.g_finanza.imposta_dati(
            dati, [("entrate", self.c["entrata"]), ("uscite", self.c["uscita"])])
        risparmio = entrate - uscite
        self.contenitore.sezioni["finanza"].imposta_nota(
            f"risparmio del mese {euro(risparmio)}")

    # ---------------------------------------------------- gli impegni
    # Nella tabella finiscono tre cose diverse — scadenze, esami e consegne
    # di progetti — e ognuna si corregge nella sua finestra. La riga si
    # ricorda da dove viene, così modificarla ed eliminarla sanno dove andare.
    def _impegno_scelto(self) -> tuple[str, int] | None:
        righe = self.tab.selectionModel().selectedRows()
        if not righe:
            return None
        return self.tab.item(righe[0].row(), 0).data(Qt.UserRole)

    def nuovo_impegno(self) -> None:
        """Un impegno scritto da qui. L'area si sceglie nella finestra.

        Finisce nella stessa tabella delle scadenze di Carriera, Accademica
        ed Emozioni: scritto qui, compare anche nella pagina della sua area.
        """
        dialogo = DialogoScadenza(area="emozioni", parent=self)
        if dialogo.exec():
            self.db.salva_scadenza(dialogo.dati())
            self.aggiorna()

    def _modifica_impegno(self) -> None:
        scelto = self._impegno_scelto()
        if scelto is None:
            return self.nuovo_impegno()
        specie, id_ = scelto
        tabella = {"scadenza": "scadenze", "esame": "esami",
                   "progetto": "progetti"}[specie]
        voce = self.db.uno(f"SELECT * FROM {tabella} WHERE id=?", (id_,))
        if voce is None:
            return
        if specie == "scadenza":
            dlg = DialogoScadenza(voce, parent=self)
            salva = self.db.salva_scadenza
        elif specie == "esame":
            dlg = DialogoEsame(voce, parent=self)
            salva = self.db.salva_esame
        else:
            dlg = DialogoProgetto(voce, parent=self)
            salva = self.db.salva_progetto
        if dlg.exec():
            salva(dlg.dati())
            self.aggiorna()

    def _elimina_impegno(self) -> None:
        scelto = self._impegno_scelto()
        if scelto is None:
            return
        specie, id_ = scelto
        tabella = {"scadenza": "scadenze", "esame": "esami",
                   "progetto": "progetti"}[specie]
        nomi = {"scadenza": "questa scadenza", "esame": "questo esame",
                "progetto": "questo progetto, con le ore e gli incassi che "
                            "gli sono attaccati"}
        if QMessageBox.question(
                self, "Eliminare?", f"Vuoi eliminare {nomi[specie]}?",
                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        self.db.elimina(tabella, id_)
        self.aggiorna()

    def _menu_impegno(self, punto) -> None:
        scelto = self._impegno_scelto()
        menu = QMenu(self)
        menu.addAction("Nuovo impegno", self.nuovo_impegno)
        if scelto is None:
            menu.exec(self.tab.viewport().mapToGlobal(punto))
            return
        menu.addSeparator()
        menu.addAction("Modifica", self._modifica_impegno)
        if scelto[0] == "scadenza":
            voce = self.db.uno("SELECT fatta FROM scadenze WHERE id=?",
                               (scelto[1],))
            gia = bool(voce and voce["fatta"])
            menu.addAction("Rimetti da fare" if gia else "Segna come fatta",
                           lambda: (
                self.db.esegui("UPDATE scadenze SET fatta=? WHERE id=?",
                               (0 if gia else 1, scelto[1])), self.aggiorna()))
        menu.addAction("Elimina", self._elimina_impegno)
        menu.exec(self.tab.viewport().mapToGlobal(punto))

    def _aggiorna_impegni(self) -> None:
        """Tutto quello che ha un giorno, da qualunque riquadro venga.

        Questa tabella è il calendario di tutte le aree messe insieme: gli
        impegni scritti qui, le attività dei riquadri di Emozioni,
        Accademica e Carriera, gli esami con l'appello fissato e i progetti
        con una consegna. Il riquadro di provenienza resta il posto dove si
        gestiscono — qui si vede solo *quando* cadono.

        Due regole, e sono quelle che prima mancavano:

        * conta la **data**, non lo stato. Un progetto ancora «idea» con la
          consegna domani è un impegno di domani come tutti gli altri;
          prima entravano solo quelli «in corso» o «in pausa», e la
          consegna spariva proprio dal posto che doveva ricordarla.
        * quello che resta da fare si vede sempre, anche se è in ritardo di
          mesi; quello già fatto solo se è di questo periodo — se no la
          tabella si riempie di esami del 2024 che non servono a nessuno.
        """
        quanti = int(self.periodo("impegni"))
        oggi = date.today()
        limite = (oggi + timedelta(days=quanti)).isoformat()
        inizio = (oggi - timedelta(days=quanti)).isoformat()

        def dentro(giorno: str, fatta: bool) -> bool:
            if not giorno or giorno > limite:
                # senza data non è un impegno a scadenza: resta nel suo
                # riquadro, che è il posto delle cose da fare senza un giorno
                return False
            return not fatta or giorno >= inizio

        scadenze = [s for s in self.db.scadenze("", limite, solo_aperte=False,
                                                limite=60)
                    if dentro(s["data"], bool(s["fatta"]))]
        esami = [e for e in self.db.esami()
                 if dentro(e["data_esame"], e["stato"] == "superato")]
        progetti = [p for p in self.db.progetti()
                    if dentro(p["scadenza"], p["stato"] == "fatto")]
        voci = [(s["data"], s["titolo"], AREE.get(s["area"], s["area"]),
                 ("scadenza", s["id"]), bool(s["fatta"])) for s in scadenze]
        voci += [(e["data_esame"], f"Esame di {e['nome']}", "Accademica",
                  ("esame", e["id"]), e["stato"] == "superato") for e in esami]
        voci += [(p["scadenza"], f"Consegna {p['nome']}", "Carriera",
                  ("progetto", p["id"]), p["stato"] == "fatto") for p in progetti]
        voci.sort(key=lambda v: (v[4], v[0]))      # da fare sopra, poi per data

        self.tab.setRowCount(len(voci))
        for i, (giorno, titolo, area, da_dove, fatta) in enumerate(voci):
            cella = QTableWidgetItem(relativa(giorno))
            cella.setData(Qt.UserRole, da_dove)
            cella.setToolTip(f"{data_it(giorno)}\nDoppio clic per modificarlo")
            # il rosso dei ritardi vale solo per quello che resta da fare
            if fatta:
                pass
            elif giorno <= oggi.isoformat():
                cella.setForeground(QColor(self.c["uscita"]))
            elif giorno <= (oggi + timedelta(days=7)).isoformat():
                cella.setForeground(QColor(self.c["attenzione"]))
            self.tab.setItem(i, 0, cella)
            self.tab.setItem(i, 1, QTableWidgetItem(titolo))
            self.tab.setItem(i, 2, QTableWidgetItem(area))
            self.tab.setItem(i, 3, QTableWidgetItem("sì" if fatta else "—"))
        self.azioni_impegni.rivedi()
        aperte = sum(1 for v in voci if not v[4])
        self.contenitore.sezioni["impegni"].imposta_nota(
            f"{aperte} da fare · {len(voci) - aperte} svolte")
