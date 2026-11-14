"""Emozioni: il diario e il controllo di come sta andando l'umore.

Le voci si scrivono nella finestra «Scrivi voce»: la apre il pulsante in alto
a destra, il riquadro «Voce di oggi», un giorno del calendario dell'umore o
una riga dell'elenco. La pagina, così, mostra soltanto quello che è già
scritto.
"""
from __future__ import annotations

import statistics
from datetime import date

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QColor, QFontMetrics
from PySide6.QtWidgets import (QHBoxLayout, QHeaderView, QLabel, QMenu,
                               QProgressBar, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from ..componenti import (DisposizioneFluida, EtichettaACapo, EtichettaAlta,
                          LegendaMisure, NavigatorePeriodo,
                          abilita_deselezione, etichetta, faccia, pillola,
                          stile_tabella)
from ..dialoghi import DialogoVoce
from ..riquadri import RiquadroAttivita
from ..grafici import GraficoCiambella, GraficoLinea, MappaCalore
from ..utils import (PERIODI, data_it, data_lunga, giorni, intervallo, media,
                     minuti_notturni, numero, ore_minuti, relativa, voto)
from . import VistaSezioni

# Le quattro misure di una voce, con la tinta che le accompagna in tutta
# l'app; l'umore prende il colore principale scelto nelle impostazioni.
MISURE = (("umore", "Umore", ""), ("energia", "Energia", "#35c4d7"),
          ("stress", "Stress", "#f7913a"), ("lucidita", "Lucidità", "#b07cff"))


class _NomeMisura(QLabel):
    """Il nome di una misura, largo quanto la parola più lunga.

    Si rimisura quando cambia il foglio di stile, cioè quando cambi tema o
    dimensione del testo: con sessantaquattro pixel fissi, col testo molto
    grande, «Lucidità» restava tagliata.
    """

    def _adatta(self) -> None:
        self.ensurePolished()
        self.setFixedWidth(
            max(64, QFontMetrics(self.font()).horizontalAdvance("Lucidità") + 6))

    def showEvent(self, ev):
        super().showEvent(ev)
        self._adatta()

    def changeEvent(self, ev):
        super().changeEvent(ev)
        if ev.type() in (QEvent.StyleChange, QEvent.FontChange,
                         QEvent.ApplicationFontChange):
            self._adatta()


def _barra_voto(colori: dict, nome: str, valore: float, colore: str) -> QWidget:
    """Riga compatta: il nome, la barra piena fino al voto e il voto."""
    contenuto = QWidget()
    contenuto.setObjectName("ContenutoSezione")
    lay = QHBoxLayout(contenuto)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(10)
    # incolonnate tutte alla stessa misura, che segue il carattere
    nome_et = _NomeMisura(nome)
    nome_et.setObjectName("TitoloRiga")
    barra = QProgressBar()
    barra.setRange(0, 100)
    barra.setValue(int(max(0, min(100, round(valore * 10)))))
    barra.setTextVisible(False)
    barra.setFixedHeight(6)
    barra.setStyleSheet(
        f"QProgressBar {{ background: {colori['pannello2']}; border: none;"
        f" border-radius: 3px; }}"
        f"QProgressBar::chunk {{ background: {colore}; border-radius: 3px; }}")
    valore_et = etichetta(voto(valore))
    valore_et.setStyleSheet(f"color: {colore}; font-weight: 700; padding-right: 4px;")
    valore_et.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    valore_et.setFixedWidth(34)
    lay.addWidget(nome_et)
    lay.addWidget(barra, 1)
    lay.addWidget(valore_et)
    return contenuto


class VistaEmozioni(VistaSezioni):
    titolo = "Emozioni"
    sottotitolo = "Il diario e il controllo di come stai"
    nome_nuovo = "+  Scrivi voce"
    chiave_vista = "emozioni"
    versione_layout = 5

    SEZIONI = {
        "oggi": "Voce di oggi",
        "calendario": "Calendario dell'umore",
        "andamento": "Andamento",
        "frequenze": "Emozioni più frequenti",
        "correlazioni": "Cosa ti muove l'umore",
        "elenco": "Le tue voci",
        "attivita": "Attività",
    }
    # Lo stesso riquadro di Home — stessa classe, stessa tabella
    # `scadenze` filtrata sull'area — non una copia: scritta qui o di là è
    # la stessa voce, perché è lo stesso oggetto che la legge e la salva.
    DISPOSIZIONE = [["oggi", "calendario"], ["andamento", "frequenze"],
                    ["correlazioni", "elenco", "attivita"]]
    ALTEZZE_PREDEFINITE = (0.34, 0.31, 0.35)
    PERIODI_SEZIONE = {
        "calendario": ({"trenta": "Ultimi 30 giorni", "tre_mesi": "Ultimi 3 mesi",
                        "sei_mesi": "Ultimi 6 mesi", "anno": "Anno corrente",
                        "anno_scorso": "Anno scorso"}, "trenta"),
        "frequenze": (PERIODI, "trenta"),
        # anche a periodi corti: con due settimane i confronti sono fragili,
        # ma servono a vedere come stai andando *adesso*, non in media da
        # gennaio. Quanti giorni stanno dietro a ogni riga lo dice la riga.
        "correlazioni": ({"quattordici": "Ultimi 14 giorni",
                          "trenta": "Ultimi 30 giorni",
                          "tre_mesi": "Ultimi 3 mesi", "anno": "Anno corrente",
                          "tutto": "Tutto"}, "trenta"),
        "elenco": (PERIODI, "trenta"),
    }

    def crea_sezioni(self) -> None:
        self.cont_oggi, self.lay_oggi = self.colonna(10)
        self.lay_oggi.setContentsMargins(0, 0, 8, 0)
        self.aggiungi("oggi", self.scorrevole(self.cont_oggi))

        self.mappa = MappaCalore(self.c)
        self.mappa.giorno_scelto.connect(self._apri_giorno)
        self.mappa.setToolTip("Clicca un giorno per scrivere o rileggere la sua voce.")
        self.aggiungi("calendario", self.mappa)

        # Lo stesso grafico fatto per la Home: la legenda sopra, viva — ci
        # clicchi sopra una misura e sparisce dalla linea, ricicchi e torna
        # — e una curva morbida senza un pallino su ogni giorno, che con
        # quattro serie incrociate si accavallavano proprio dove si
        # toccano. Prima qui c'erano solo umore, energia e stress: la
        # lucidità, che la pagina misura lo stesso, non si vedeva mai.
        self.nav_andamento = NavigatorePeriodo(self.c, "giorni", tutto=True)
        self.nav_andamento.cambiato.connect(self._aggiorna_andamento)
        self.g_andamento = GraficoLinea(self.c)
        self.g_andamento.formato = lambda v: numero(v, 1)
        self.g_andamento.minimo_forzato = 0
        self.g_andamento.massimo_forzato = 10
        self.g_andamento.mostra_legenda = False
        self.g_andamento.mostra_punti = False
        self.nav_andamento.scorri_con_rotella(self.g_andamento)
        contenuto, lay = self.colonna(6)
        salvate = self.db.leggi("emozioni_andamento_misure", "")
        chiavi_valide = {m[0] for m in MISURE}
        attive = ({k for k in salvate.split(",") if k in chiavi_valide}
                 if salvate else chiavi_valide) or chiavi_valide
        self.legenda_andamento = LegendaMisure(
            self.c, [(k, n, col) for k, n, col in MISURE], attive)
        self.legenda_andamento.cambiata.connect(self._cambia_misure_andamento)
        lay.addWidget(self.legenda_andamento)
        lay.addWidget(self.g_andamento, 1)
        self.aggiungi("andamento", contenuto, comando=self.nav_andamento)

        self.g_frequenze = GraficoCiambella(self.c)
        self.g_frequenze.formato = lambda v: f"{v:.0f} volte"
        self.aggiungi("frequenze", self.g_frequenze)

        self.cont_corr, self.lay_corr = self.colonna(7)
        self.aggiungi("correlazioni", self.scorrevole(self.cont_corr))

        self.tab = QTableWidget(0, 5)
        self.tab.setHorizontalHeaderLabels(
            ["Data", "Umore", "Emozioni", "Diario", "Ora"])
        self.tab.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tab.setSelectionBehavior(QTableWidget.SelectRows)
        self.tab.doubleClicked.connect(self._modifica)
        self.tab.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tab.customContextMenuRequested.connect(self._menu_voce)
        h = self.tab.horizontalHeader()
        for colonna, modo in ((0, QHeaderView.ResizeToContents),
                              (1, QHeaderView.ResizeToContents),
                              (2, QHeaderView.ResizeToContents),
                              (3, QHeaderView.Stretch),
                              (4, QHeaderView.ResizeToContents)):
            h.setSectionResizeMode(colonna, modo)
        abilita_deselezione(self.tab)
        stile_tabella(self.tab)
        self.aggiungi("elenco", self.tab)

        # -------------------------------------------------------- attività
        self.riq_attivita = RiquadroAttivita(self.db, self.c, "emozioni")
        self.riq_attivita.cambiato.connect(self._dopo_salvataggio)
        self.aggiungi("attivita", self.riq_attivita,
                      comando=self.riq_attivita.azioni)

        self.grafici = [self.g_andamento, self.g_frequenze, self.mappa,
                        self.legenda_andamento]

    # ------------------------------------------------------------- comandi
    def nuovo(self) -> None:
        self.apri_voce()

    def apri_voce(self, voce=None, giorno: str = "") -> None:
        """Apre la finestra della voce: nuova, di un giorno o già scritta."""
        dialogo = DialogoVoce(self.db, self.c, voce, giorno, parent=self)
        dialogo.salvato.connect(self._dopo_salvataggio)
        dialogo.exec()

    def _dopo_salvataggio(self) -> None:
        self.aggiorna()
        self.dati_cambiati.emit()

    def _apri_giorno(self, giorno: str) -> None:
        self.apri_voce(giorno=giorno)

    def _voce_selezionata(self):
        righe = self.tab.selectionModel().selectedRows()
        if not righe:
            return None
        id_ = self.tab.item(righe[0].row(), 0).data(Qt.UserRole)
        return self.db.uno("SELECT * FROM voci WHERE id=?", (id_,))

    def _modifica(self) -> None:
        voce = self._voce_selezionata()
        if voce:
            self.apri_voce(voce)

    def _menu_voce(self, punto) -> None:
        voce = self._voce_selezionata()
        if voce is None:
            return
        menu = QMenu(self)
        menu.addAction("Modifica", self._modifica)
        menu.addAction("Elimina", lambda: self._elimina(voce["id"]))
        menu.exec(self.tab.viewport().mapToGlobal(punto))

    def _elimina(self, id_: int) -> None:
        self.db.elimina("voci", id_)
        self._dopo_salvataggio()

    # ---------------------------------------------------------------- dati
    def aggiorna(self) -> None:
        self._aggiorna_oggi()
        self._aggiorna_calendario()
        self._aggiorna_andamento()
        self._aggiorna_frequenze()
        self._aggiorna_correlazioni()
        self._aggiorna_elenco()
        self.contenitore.sezioni["attivita"].imposta_nota(
            self.riq_attivita.nota())

    def _aggiorna_oggi(self) -> None:
        """Come è andata oggi, in breve, e il pulsante per scrivere."""
        self.svuota(self.lay_oggi)
        oggi = date.today().isoformat()
        voci = self.db.voci(oggi, oggi)
        self.contenitore.sezioni["oggi"].imposta_nota(data_lunga(oggi))

        medie = {chiave: media([float(v[chiave]) for v in voci])
                 for chiave, _, _ in MISURE} if voci else {}
        colore = self._colore_umore(medie["umore"]) if voci else self.c["testo2"]

        simbolo = QLabel(faccia(medie["umore"]) if voci else "✎")
        simbolo.setStyleSheet(f"font-size: {27 if voci else 21}px;"
                              + ("" if voci else f" color: {self.c['testo2']};"))
        simbolo.setFixedWidth(34)
        simbolo.setAlignment(Qt.AlignCenter)
        if voci:
            ora = voci[0]["ora"]
            # non si lascia schiacciare: quando il riquadro è basso il voto
            # veniva tagliato a metà, e col testo grande anche la nota
            grande = EtichettaAlta(voto(medie["umore"]))
            grande.setObjectName("ValoreScheda")
            grande.setStyleSheet(f"color: {colore}; font-weight: 700;")
            nota = (f"umore · alle {ora}" if len(voci) == 1
                    else f"media di {len(voci)} voci · ultima alle {ora}")
        else:
            grande = EtichettaAlta("Nessuna voce, per ora")
            grande.setObjectName("Sezione")
            nota = ("Quattro cursori, le emozioni che riconosci e, se ti va, "
                    "due righe di diario.")
        testi = QVBoxLayout()
        testi.setContentsMargins(0, 0, 0, 0)
        testi.setSpacing(1)
        if voci:
            et_nota = EtichettaAlta(nota)
            et_nota.setObjectName("NotaScheda")
        else:
            # la frase d'invito va a capo: le serve l'altezza di tutte le righe
            et_nota = EtichettaACapo(nota)
            et_nota.setObjectName("NotaScheda")
        testi.addWidget(grande)
        testi.addWidget(et_nota)

        if voci:
            azione = QPushButton("Modifica la voce" if len(voci) == 1
                                 else "Modifica l'ultima")
        else:
            azione = QPushButton("+  Scrivi la voce")
            azione.setObjectName("Primario")
        azione.setMinimumHeight(34)
        azione.clicked.connect(
            lambda: self.apri_voce(voci[0]) if voci else self.apri_voce(giorno=oggi))
        testa = QHBoxLayout()
        testa.setSpacing(10)
        testa.addWidget(simbolo, 0, Qt.AlignTop)
        testa.addLayout(testi, 1)
        testa.addWidget(azione, 0, Qt.AlignTop)
        self.lay_oggi.addLayout(testa)

        if not voci:
            self.lay_oggi.addStretch(1)
            return

        for chiave, nome, tinta in MISURE:
            self.lay_oggi.addWidget(
                _barra_voto(self.c, nome, medie[chiave], tinta or self.c["accento"]))

        # le emozioni di tutte le voci di oggi, nell'ordine in cui le hai segnate
        segnate: list[str] = []
        for v in reversed(voci):
            for nome in (x.strip() for x in v["emozioni"].split(",")):
                if nome and nome not in segnate:
                    segnate.append(nome)
        if segnate:
            colori = self.db.colori_emozioni()
            riquadro = QWidget()
            riquadro.setObjectName("ContenutoSezione")
            fluida = DisposizioneFluida(riquadro, 0, 6)
            for nome in segnate:
                fluida.addWidget(
                    pillola(nome, colori.get(nome, self.c["accento"]), ""))
            self.lay_oggi.addWidget(riquadro)

        testo = (voci[0]["testo"] or "").strip()
        if testo:
            citazione = etichetta(testo, "CitazioneVoce")
            citazione.setWordWrap(True)
            self.lay_oggi.addWidget(citazione)
        self.lay_oggi.addStretch(1)

    def _colore_umore(self, valore: float) -> str:
        if valore >= 7.5:
            return self.c["entrata"]
        if valore >= 6:
            return "#8bbf6a"
        if valore >= 4.5:
            return self.c["attenzione"]
        if valore >= 3:
            return "#f7913a"
        return self.c["uscita"]

    def _aggiorna_calendario(self) -> None:
        dal, al = intervallo(self.periodo("calendario"))
        if dal < "1900":
            dal = self.db.prima_data()
        elenco = giorni(dal, al)
        medie = {r["data"]: r for r in self.db.medie_giorno(dal, al)}
        dati, suggerimenti = {}, {}
        for giorno in elenco:
            r = medie.get(giorno)
            if not r:
                suggerimenti[giorno] = f"{data_it(giorno)} — nessuna voce"
                continue
            u = float(r["umore"])
            dati[giorno] = (0.25 + 0.75 * (u / 10), self._colore_umore(u))
            suggerimenti[giorno] = (f"{data_it(giorno)} — umore {voto(u)}  "
                                    f"{faccia(u)}   ({r['n']} voci)")
        self.mappa.imposta_dati(elenco, dati, suggerimenti)

    def _cambia_misure_andamento(self) -> None:
        self.db.imposta("emozioni_andamento_misure",
                        ",".join(sorted(self.legenda_andamento.attive())))
        self._aggiorna_andamento()

    def _aggiorna_andamento(self) -> None:
        """Come sono andati umore, energia, stress e lucidità.

        Di norma un punto per giorno, con la media delle voci di quel giorno.
        Ma quando in tutta la finestra c'è **un giorno solo** con delle voci,
        una linea di un punto non dice niente: allora si scende dentro la
        giornata e si disegnano le voci una per una, **all'ora in cui le hai
        scritte** — se la mattina è andata diversa dalla sera, è lì che si
        vede. In tutti e due i casi si disegnano solo le misure accese
        nella legenda.
        """
        attive = self.legenda_andamento.attive()
        dal, al = self.nav_andamento.esteso()
        righe = self.db.medie_giorno(dal, al)
        sezione = self.contenitore.sezioni["andamento"]
        if len(righe) == 1:
            giorno = righe[0]["data"]
            voci = sorted(self.db.voci(giorno, giorno), key=lambda v: v["ora"])
            if len(voci) >= 2:
                def a_ore(campo):
                    return [(v["ora"][:5], float(v[campo])) for v in voci]
                self.g_andamento.imposta_serie([
                    (nome, a_ore(chiave), colore or self.c["accento"])
                    for chiave, nome, colore in MISURE if chiave in attive])
                sezione.imposta_nota(
                    f"{data_it(giorno)[:5]}, ora per ora · {len(voci)} voci")
                return
            sezione.imposta_nota(f"una voce sola, {relativa(giorno)}")
            self.g_andamento.vuoto = (
                f"Una voce sola, {relativa(giorno)}: per disegnare una linea "
                "ce ne vogliono almeno due.")
        else:
            sezione.imposta_nota(f"{len(righe)} giorni scritti" if righe else "")
            self.g_andamento.vuoto = (
                f"Niente scritto {self.nav_andamento.nome_esteso()}. "
                "«Scrivi voce», in alto, e comincia da oggi.")
        if not righe:
            self.g_andamento.imposta_serie([])
            return
        def punti(campo):
            return [(data_it(r["data"])[:5], float(r[campo])) for r in righe]
        self.g_andamento.imposta_serie([
            (nome, punti(chiave), colore or self.c["accento"])
            for chiave, nome, colore in MISURE if chiave in attive])

    def _aggiorna_frequenze(self) -> None:
        dal, al = intervallo(self.periodo("frequenze"))
        colori = self.db.colori_emozioni()
        frequenze = self.db.frequenza_emozioni(dal, al)[:9]
        totale = sum(v for _, v in frequenze)
        self.g_frequenze.imposta_dati(
            [(nome, float(n), colori.get(nome, self.c["accento"]))
             for nome, n in frequenze],
            str(totale), "segnate")

    def _aggiorna_correlazioni(self) -> None:
        self.svuota(self.lay_corr)
        dal, al = intervallo(self.periodo("correlazioni"))
        if dal < "1900":
            dal = self.db.prima_data()
        medie = {r["data"]: r for r in self.db.medie_giorno(dal, al)}
        if len(medie) < 6:
            self.lay_corr.addWidget(etichetta(
                "Servono almeno sei giorni di diario per confrontare qualcosa.",
                "NotaScheda"))
            self.lay_corr.addStretch(1)
            return

        salute = self.db.giorni_salute(dal, al)
        allenamenti = {r["data"] for r in self.db.allenamenti(dal, al)}
        lavoro: dict[str, int] = {}
        for r in self.db.lavoro(dal, al):
            lavoro[r["data"]] = lavoro.get(r["data"], 0) + r["minuti"]
        studio: dict[str, int] = {}
        for r in self.db.studio(dal, al):
            studio[r["data"]] = studio.get(r["data"], 0) + r["minuti"]
        # quante abitudini hai fatto, giorno per giorno: serve a confrontare
        # i giorni in cui ne hai fatte la metà o più con quelli in cui no
        totale_abitudini = len(self.db.abitudini())
        fatte_giorno: dict[str, int] = {}
        for g, _id in self.db.registro(dal, al):
            fatte_giorno[g] = fatte_giorno.get(g, 0) + 1

        def confronta(nome: str, campo: str, condizione):
            """Due medie a confronto; i giorni senza quel dato restano fuori.

            La condizione può rispondere `None`: vuol dire «di quel giorno non
            so niente», e un giorno senza dato non è un giorno in cui la cosa
            non è successa.

            Non basta più uno scostamento grande: deve esserlo **rispetto a
            quanto quella misura va già su e giù da sola**. Un salto di 1,5
            punti non dice niente se l'umore in quei giorni oscillava già di
            3 punti per conto suo — è dentro il rumore normale. Lo stesso
            salto, con un umore che di solito si muove di mezzo punto, è un
            segnale vero. Quel rapporto è lo scarto quadratico medio messo
            in comune fra i due gruppi (la stessa idea della «d di Cohen»,
            una misura classica per confrontare due gruppi che tenga conto
            di quanto variano): si richiede che sia di almeno 0,5 — una
            differenza di mezza deviazione standard, soglia comune per dire
            «non è solo rumore» senza pretendere la certezza di un test
            statistico vero, che con poche decine di giorni non si può fare.
            """
            dentro, fuori = [], []
            for g, r in medie.items():
                esito = condizione(g)
                if esito is None:
                    continue
                (dentro if esito else fuori).append(float(r[campo]))
            if len(dentro) < 3 or len(fuori) < 3:
                return None
            scostamento = media(dentro) - media(fuori)
            insieme = dentro + fuori
            spargimento = statistics.pstdev(insieme) if len(set(insieme)) > 1 else 0.0
            effetto = abs(scostamento) / spargimento if spargimento else (
                999.0 if abs(scostamento) >= 0.2 else 0.0)
            return (nome, campo, scostamento, len(dentro),
                    len(dentro) + len(fuori), effetto)

        def misura(campo: str):
            """Valore di salute del giorno, oppure None se non è stato registrato."""
            def leggi(g):
                valore = float(salute[g][campo]) if g in salute else 0.0
                return valore or None
            return leggi

        def orario(campo: str):
            """Minuti dalle 18 in poi (vedi `minuti_notturni`), o None se manca."""
            def leggi(g):
                testo = salute[g][campo] if g in salute else ""
                return minuti_notturni(ore_minuti(testo)) if testo else None
            return leggi

        sonno, passi = misura("sonno"), misura("passi")
        battito = misura("battito")
        acqua = misura("acqua")
        profondo = misura("sonno_profondo")
        a_letto = orario("a_letto")
        riposo_medio = media([battito(g) for g in medie if battito(g)])

        def soglia(leggi, prova):
            return lambda g: None if leggi(g) is None else prova(leggi(g))

        def weekend(g: str) -> bool:
            return date.fromisoformat(g).weekday() >= 5

        def sonno_profondo_alto(g: str) -> bool | None:
            tot, prof = sonno(g), profondo(g)
            if not tot or prof is None:
                return None
            return (prof / tot) >= 0.22

        prove = [
            confronta("Quando dormi meno di 6 ore", "umore",
                      soglia(sonno, lambda v: v < 360)),
            confronta("Quando dormi più di 7 ore e mezza", "energia",
                      soglia(sonno, lambda v: v >= 450)),
            confronta("Nei giorni in cui ti alleni", "umore",
                      lambda g: g in allenamenti),
            confronta("Quando cammini più di 8.000 passi", "umore",
                      soglia(passi, lambda v: v >= 8000)),
            confronta("Quando lavori più di 4 ore", "energia",
                      lambda g: lavoro.get(g, 0) > 240),
            confronta("Quando studi più di 3 ore", "stress",
                      lambda g: studio.get(g, 0) > 180),
            confronta("Quando il battito a riposo è più alto del solito",
                      "stress",
                      soglia(battito, lambda v: v > riposo_medio)
                      if riposo_medio else lambda g: None),
            confronta("Quando bevi almeno due litri d'acqua", "energia",
                      soglia(acqua, lambda v: v >= 2.0)),
            confronta("Quando vai a letto dopo mezzanotte", "umore",
                      soglia(a_letto, lambda v: v >= 1440)),
            confronta("Nel weekend", "umore", lambda g: weekend(g)),
            confronta("Quando fai almeno metà delle tue abitudini", "umore",
                      lambda g: fatte_giorno.get(g, 0) >= totale_abitudini / 2
                      if totale_abitudini else None),
            confronta("Quando il sonno profondo è più di un quinto del totale",
                      "energia", sonno_profondo_alto),
        ]
        # «tentate» sono i confronti che si potevano fare davvero; fra quelli
        # si tengono solo quelli che passano la soglia dell'effetto — vedi
        # `confronta` per perché non basta più un numero assoluto
        tentate = [p for p in prove if p]
        prove = [p for p in tentate if p[5] >= 0.5]
        prove.sort(key=lambda p: -p[5])
        if not prove:
            if not tentate:
                spiegazione = (
                    f"Con {len(medie)} giorni di diario qui dentro non c'è "
                    "ancora un confronto da fare: ogni riga vuole almeno tre "
                    "giorni da una parte e tre dall'altra (per esempio tre "
                    "notti corte e tre normali). Prova con un periodo più lungo.")
            else:
                massimo = max(p[5] for p in tentate)
                spiegazione = (
                    f"Niente di netto: su {len(medie)} giorni, anche la "
                    "differenza più marcata resta dentro quanto quella misura "
                    f"oscilla già da sola ({numero(massimo, 1)} volte il suo "
                    "scarto, contro la 0,5 che serve per contare qualcosa).")
            nota_vuota = etichetta(spiegazione, "NotaScheda")
            nota_vuota.setWordWrap(True)
            self.lay_corr.addWidget(nota_vuota)
            self.lay_corr.addStretch(1)
            return

        for nome, chiave, scostamento, quanti, su_quanti, effetto in prove:
            buono = scostamento > 0 if chiave != "stress" else scostamento < 0
            colore = self.c["entrata"] if buono else self.c["uscita"]
            segno = "+" if scostamento > 0 else "−"
            # «nettamente» da 0,8 in su (effetto grande), altrimenti solo
            # «si vede»: anche superata la soglia, la forza del segnale varia
            quanto = "nettamente" if effetto >= 0.8 else "si vede che"
            testo = QLabel(
                f"{nome}  <span style='color:{colore}; font-weight:700'>"
                f"{chiave} {segno}{numero(abs(scostamento), 1)}</span>"
                f" <span style='color:{self.c['testo2']}'>· {quanto} cambia · "
                f"{quanti} giorni su {su_quanti}</span>")
            testo.setTextFormat(Qt.RichText)
            testo.setWordWrap(True)
            self.lay_corr.addWidget(testo)
        nota = etichetta("Sono confronti fra medie, non cause: dicono dove "
                         "guardare. Restano solo quelli abbastanza netti da "
                         "distinguersi da come quella misura oscilla di suo, "
                         "non ogni scostamento che capita. Più corto è il "
                         "periodo, meno giorni stanno dietro a ogni riga.",
                         "NotaScheda")
        nota.setWordWrap(True)
        self.lay_corr.addWidget(nota)
        self.lay_corr.addStretch(1)

    def _aggiorna_elenco(self) -> None:
        dal, al = intervallo(self.periodo("elenco"))
        if dal < "1900":
            dal = ""
            al = ""
        voci = self.db.voci(dal, al, limite=400)
        self.tab.setRowCount(len(voci))
        for i, v in enumerate(voci):
            cella_data = QTableWidgetItem(relativa(v["data"]))
            cella_data.setData(Qt.UserRole, v["id"])
            cella_data.setToolTip(data_lunga(v["data"]))
            umore = QTableWidgetItem(f"{faccia(v['umore'])}  {voto(v['umore'])}")
            umore.setForeground(Qt.NoBrush)
            testo = (v["testo"] or "").replace("\n", " ")
            self.tab.setItem(i, 0, cella_data)
            self.tab.setItem(i, 1, umore)
            self.tab.setItem(i, 2, QTableWidgetItem(v["emozioni"]))
            self.tab.setItem(i, 3, QTableWidgetItem(testo))
            self.tab.setItem(i, 4, QTableWidgetItem(v["ora"]))

    def aggiorna_tema(self, colori: dict) -> None:
        super().aggiorna_tema(colori)
