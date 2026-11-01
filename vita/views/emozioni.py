"""Emozioni: il diario e il controllo di come sta andando l'umore.

Le voci si scrivono nella finestra «Scrivi voce»: la apre il pulsante in alto
a destra, il riquadro «Voce di oggi», un giorno del calendario dell'umore o
una riga dell'elenco. La pagina, così, mostra soltanto quello che è già
scritto.
"""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QHBoxLayout, QHeaderView, QLabel, QMenu,
                               QProgressBar, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from ..componenti import (DisposizioneFluida, EtichettaACapo, EtichettaAlta,
                          abilita_deselezione, etichetta, faccia,
                          pillola, stile_tabella)
from ..dialoghi import DialogoVoce
from ..grafici import GraficoCiambella, GraficoLinea, MappaCalore
from ..utils import (PERIODI, data_it, data_lunga, giorni, intervallo, media,
                     numero, relativa, voto)
from . import VistaSezioni

# Le quattro misure di una voce, con la tinta che le accompagna in tutta
# l'app; l'umore prende il colore principale scelto nelle impostazioni.
MISURE = (("umore", "Umore", ""), ("energia", "Energia", "#35c4d7"),
          ("stress", "Stress", "#f7913a"), ("lucidita", "Lucidità", "#b07cff"))


def _barra_voto(colori: dict, nome: str, valore: float, colore: str) -> QWidget:
    """Riga compatta: il nome, la barra piena fino al voto e il voto."""
    contenuto = QWidget()
    contenuto.setObjectName("ContenutoSezione")
    lay = QHBoxLayout(contenuto)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(10)
    nome_et = etichetta(nome, "TitoloRiga")
    nome_et.setFixedWidth(64)
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
    valore_et.setStyleSheet(f"color: {colore}; font-weight: 700;")
    valore_et.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    valore_et.setFixedWidth(30)
    lay.addWidget(nome_et)
    lay.addWidget(barra, 1)
    lay.addWidget(valore_et)
    return contenuto


class VistaEmozioni(VistaSezioni):
    titolo = "Emozioni"
    sottotitolo = "Il diario e il controllo di come stai"
    nome_nuovo = "+  Scrivi voce"
    chiave_vista = "emozioni"
    versione_layout = 2

    SEZIONI = {
        "oggi": "Voce di oggi",
        "calendario": "Calendario dell'umore",
        "andamento": "Andamento",
        "frequenze": "Emozioni più frequenti",
        "correlazioni": "Cosa ti muove l'umore",
        "elenco": "Le tue voci",
    }
    DISPOSIZIONE = [["oggi", "calendario"], ["andamento", "frequenze"],
                    ["correlazioni", "elenco"]]
    ALTEZZE_PREDEFINITE = (0.34, 0.31, 0.35)
    PERIODI_SEZIONE = {
        "calendario": ({"trenta": "Ultimi 30 giorni", "tre_mesi": "Ultimi 3 mesi",
                        "sei_mesi": "Ultimi 6 mesi", "anno": "Anno corrente",
                        "anno_scorso": "Anno scorso"}, "trenta"),
        "andamento": (PERIODI, "trenta"),
        "frequenze": (PERIODI, "trenta"),
        "correlazioni": ({"tre_mesi": "Ultimi 3 mesi", "anno": "Anno corrente",
                          "tutto": "Tutto"}, "tre_mesi"),
        "elenco": (PERIODI, "trenta"),
    }

    def crea_sezioni(self) -> None:
        self.cont_oggi, self.lay_oggi = self.colonna(10)
        self.aggiungi("oggi", self.scorrevole(self.cont_oggi))

        self.mappa = MappaCalore(self.c)
        self.mappa.giorno_scelto.connect(self._apri_giorno)
        self.mappa.setToolTip("Clicca un giorno per scrivere o rileggere la sua voce.")
        self.aggiungi("calendario", self.mappa)

        self.g_andamento = GraficoLinea(self.c)
        self.g_andamento.formato = lambda v: numero(v, 1)
        self.g_andamento.minimo_forzato = 0
        self.g_andamento.massimo_forzato = 10
        self.aggiungi("andamento", self.g_andamento)

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

        self.grafici = [self.g_andamento, self.g_frequenze, self.mappa]

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
            grande = etichetta(voto(medie["umore"]), "ValoreScheda")
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
            et_nota = etichetta(nota, "NotaScheda")
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

    def _aggiorna_andamento(self) -> None:
        dal, al = intervallo(self.periodo("andamento"))
        righe = self.db.medie_giorno(dal, al)
        if not righe:
            self.g_andamento.imposta_serie([])
            return
        def punti(campo):
            return [(data_it(r["data"])[:5], float(r[campo])) for r in righe]
        self.g_andamento.imposta_serie([
            ("umore", punti("umore"), self.c["accento"]),
            ("energia", punti("energia"), "#35c4d7"),
            ("stress", punti("stress"), "#f7913a"),
        ])

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

        def confronta(nome: str, campo: str, condizione):
            """Due medie a confronto; i giorni senza quel dato restano fuori.

            La condizione può rispondere `None`: vuol dire «di quel giorno non
            so niente», e un giorno senza dato non è un giorno in cui la cosa
            non è successa.
            """
            dentro, fuori = [], []
            for g, r in medie.items():
                esito = condizione(g)
                if esito is None:
                    continue
                (dentro if esito else fuori).append(float(r[campo]))
            if len(dentro) < 3 or len(fuori) < 3:
                return None
            return nome, campo, media(dentro) - media(fuori), len(dentro)

        def misura(campo: str):
            """Valore di salute del giorno, oppure None se non è stato registrato."""
            def leggi(g):
                valore = float(salute[g][campo]) if g in salute else 0.0
                return valore or None
            return leggi

        sonno, passi = misura("sonno"), misura("passi")

        def soglia(leggi, prova):
            return lambda g: None if leggi(g) is None else prova(leggi(g))

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
        ]
        prove = [p for p in prove if p and abs(p[2]) >= 0.25]
        prove.sort(key=lambda p: -abs(p[2]))
        if not prove:
            self.lay_corr.addWidget(etichetta(
                "Nessuno scostamento degno di nota in questo periodo.", "NotaScheda"))
            self.lay_corr.addStretch(1)
            return

        for nome, chiave, scostamento, quanti in prove:
            buono = scostamento > 0 if chiave != "stress" else scostamento < 0
            colore = self.c["entrata"] if buono else self.c["uscita"]
            segno = "+" if scostamento > 0 else "−"
            testo = QLabel(
                f"{nome}  <span style='color:{colore}; font-weight:700'>"
                f"{chiave} {segno}{numero(abs(scostamento), 1)}</span>"
                f" <span style='color:{self.c['testo2']}'>· {quanti} giorni</span>")
            testo.setTextFormat(Qt.RichText)
            testo.setWordWrap(True)
            self.lay_corr.addWidget(testo)
        nota = etichetta("Sono confronti fra medie, non cause: dicono dove guardare.",
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
