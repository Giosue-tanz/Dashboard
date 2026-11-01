"""Cruscotto: tutte le aree in un colpo d'occhio."""
from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QGridLayout, QHBoxLayout, QHeaderView, QLabel,
                               QPushButton, QTableWidget, QTableWidgetItem,
                               QWidget)

from ..componenti import (AnelloEtichettato, Interruttore, RigaMisura,
                          abilita_deselezione, etichetta, faccia,
                          stile_tabella)
from ..db import AREE
from ..grafici import Anello, GraficoBarre, GraficoLinea, MappaCalore
from ..punteggi import PREDEFINITI
from ..tess import Accensione, Motore
from ..utils import (PERIODI, data_it, data_lunga, durata, etichetta_mese, euro,
                     giorni, intervallo, media, mese_corrente, numero, relativa,
                     settimana_corrente, ultimi_giorni, voto)
from . import VistaSezioni


def _quota_battito(valore: float) -> int:
    """Più il battito a riposo è basso, più la barra è piena (45-85 bpm)."""
    if not valore:
        return 0
    return int(max(0.0, min(100.0, (85 - valore) / 40 * 100)))


class VistaCruscotto(VistaSezioni):
    titolo = "Cruscotto"
    sottotitolo = "Com'è messa la giornata, in tutte le aree"
    nome_nuovo = ""
    chiave_vista = "cruscotto"

    SEZIONI = {
        "oggi": "Oggi",
        "emotivo": "Andamento emotivo",
        "salute": "Salute",
        "carriera": "Carriera",
        "accademica": "Accademica",
        "abitudini": "Abitudini",
        "finanza": "Finanza",
        "impegni": "Prossimi impegni",
    }
    versione_layout = 5
    # Come si legge una giornata: prima com'è andata (anello, salute, costanza),
    # poi come si sta muovendo (umore e soldi, i due andamenti che vogliono
    # larghezza), in fondo cosa resta da fare. Tess ha una pagina sua: qui
    # resta solo l'interruttore in testata.
    DISPOSIZIONE = [["oggi", "salute", "abitudini"],
                    ["emotivo", "finanza"],
                    ["carriera", "accademica", "impegni"]]
    ALTEZZE_PREDEFINITE = (0.37, 0.31, 0.32)
    LARGHEZZE_PREDEFINITE = ((0.30, 0.34, 0.36),
                             (0.56, 0.44),
                             (0.35, 0.35, 0.30))
    PERIODI_SEZIONE = {
        "emotivo": (PERIODI, "trenta"),
        "abitudini": ({"14": "14 giorni", "30": "30 giorni", "90": "90 giorni",
                       "180": "6 mesi", "365": "un anno"}, "30"),
        "finanza": ({"6": "6 mesi", "12": "12 mesi", "24": "24 mesi",
                     "36": "36 mesi"}, "6"),
        "impegni": ({"30": "30 giorni", "90": "90 giorni", "365": "un anno",
                     "730": "due anni"}, "90"),
    }

    def crea_sezioni(self) -> None:
        self.motore_tess = Motore(self.db)
        self.comando_tess = QWidget()
        self.comando_tess.setObjectName("ComandoTestata")
        fila_tess = QHBoxLayout(self.comando_tess)
        fila_tess.setContentsMargins(4, 0, 10, 0)
        fila_tess.setSpacing(9)
        self.et_tess = QLabel("Tess")
        self.et_tess.setObjectName("NotaScheda")
        self.interruttore_tess = Interruttore(self.c)
        self.interruttore_tess.cambiato.connect(self._tocca_tess)
        fila_tess.addWidget(self.et_tess)
        fila_tess.addWidget(self.interruttore_tess)
        self._nota_tess(False)
        self.azioni_intestazione = [self.comando_tess] + self.azioni_intestazione

        # ------------------------------------------------------------- oggi
        contenuto, lay = self.colonna(10)
        self.anello_umore = Anello(self.c, self.c["accento"])
        self.anello_umore.setMinimumHeight(110)
        lay.addWidget(self.anello_umore, 1)
        self.riquadro_oggi = QWidget()
        self.riquadro_oggi.setObjectName("ContenutoSezione")
        self.lay_oggi = QGridLayout(self.riquadro_oggi)
        self.lay_oggi.setContentsMargins(0, 0, 0, 0)
        self.lay_oggi.setSpacing(6)
        lay.addWidget(self.riquadro_oggi)
        self.aggiungi("oggi", contenuto)

        # --------------------------------------------------------- emotivo
        self.g_emotivo = GraficoLinea(self.c)
        self.g_emotivo.formato = lambda v: numero(v, 1)
        self.g_emotivo.minimo_forzato = 0
        self.g_emotivo.massimo_forzato = 10
        self.aggiungi("emotivo", self.g_emotivo)

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
        self.aggiungi("carriera", self.scorrevole(self.cont_carriera))

        # ------------------------------------------------------ accademica
        self.cont_accademica, self.lay_accademica = self.colonna(9)
        self.aggiungi("accademica", self.scorrevole(self.cont_accademica))

        # ------------------------------------------------------- abitudini
        contenuto, lay = self.colonna(8)
        self.mappa = MappaCalore(self.c)
        self.mappa.etichette = False      # qui contano i quadretti, non le lettere
        self.mappa.giorno_scelto.connect(
            lambda _g: self.area_richiesta.emit("abitudini"))
        self.mappa.setCursor(Qt.PointingHandCursor)
        lay.addWidget(self.mappa, 1)
        self.aggiungi("abitudini", contenuto)

        # --------------------------------------------------------- finanza
        contenuto, lay = self.colonna(8)
        self.et_saldo = QLabel("—")
        self.et_saldo.setObjectName("ValoreScheda")
        lay.addWidget(self.et_saldo)
        self.et_finanza = etichetta("", "NotaScheda")
        lay.addWidget(self.et_finanza)
        self.g_finanza = GraficoBarre(self.c)
        self.g_finanza.formato = lambda v: euro(v).replace(",00", "")
        lay.addWidget(self.g_finanza, 1)
        self.aggiungi("finanza", contenuto)

        # --------------------------------------------------------- impegni
        self.tab = QTableWidget(0, 3)
        self.tab.setHorizontalHeaderLabels(["Quando", "Cosa", "Area"])
        self.tab.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tab.setSelectionBehavior(QTableWidget.SelectRows)
        h = self.tab.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        abilita_deselezione(self.tab)
        stile_tabella(self.tab)
        self.aggiungi("impegni", self.tab)

        self.grafici = [self.g_emotivo, self.g_finanza, self.anello_umore,
                        self.anello_passi, self.mappa,
                        *self.cerchietti.values(), self.interruttore_tess]

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
        self.accensione_tess = Accensione(self.motore_tess, self)
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

    def _allinea_tess(self) -> None:
        """L'interruttore dice come sta il motore, anche se l'hai acceso altrove."""
        if getattr(self, "accensione_tess", None) and self.accensione_tess.isRunning():
            return
        self.interruttore_tess.imposta(self.motore_tess.attiva())

    # ---------------------------------------------------------------- dati
    def aggiorna(self) -> None:
        self._allinea_tess()
        self._aggiorna_oggi()
        self._aggiorna_emotivo()
        self._aggiorna_salute()
        self._aggiorna_carriera()
        self._aggiorna_accademica()
        self._aggiorna_abitudini()
        self._aggiorna_finanza()
        self._aggiorna_impegni()

    def _numero(self, valore: str, nota: str, colore: str, colonna: int) -> None:
        v = QLabel(valore)
        v.setAlignment(Qt.AlignCenter)
        v.setStyleSheet(f"color: {colore}; font-size: 15px; font-weight: 700;")
        n = QLabel(nota)
        n.setObjectName("NotaScheda")
        n.setAlignment(Qt.AlignCenter)
        self.lay_oggi.addWidget(v, 0, colonna)
        self.lay_oggi.addWidget(n, 1, colonna)

    def _aggiorna_oggi(self) -> None:
        while self.lay_oggi.count():
            w = self.lay_oggi.takeAt(0).widget()
            if w is not None:
                w.hide(); w.setParent(None); w.deleteLater()
        oggi = date.today().isoformat()
        medie = self.db.medie_periodo(oggi, oggi)
        if medie["n"]:
            umore = medie["umore"]
            self.anello_umore.imposta(umore / 10, voto(umore),
                                      f"umore {faccia(umore)}")
        else:
            self.anello_umore.imposta(0, "—", "nessuna voce")
        salute = self.db.salute_giorno(oggi)
        self._numero(durata(salute["sonno"]) if salute and salute["sonno"] else "—",
                     "sonno", "#6c8cff", 0)
        self._numero(numero(salute["passi"], 0) if salute and salute["passi"] else "—",
                     "passi", self.c["accento"], 1)
        self._numero(durata(self.db.minuti_studio(oggi, oggi)), "studio", "#b07cff", 2)
        self._numero(durata(self.db.minuti_lavoro(oggi, oggi)), "lavoro", "#6c8cff", 3)
        self.contenitore.sezioni["oggi"].imposta_nota(
            f"{data_lunga(oggi)} · {medie['n']} voci")

    def _aggiorna_emotivo(self) -> None:
        dal, al = intervallo(self.periodo("emotivo"))
        righe = self.db.medie_giorno(dal, al)
        if not righe:
            self.g_emotivo.imposta_serie([])
            self.contenitore.sezioni["emotivo"].imposta_nota("")
            return
        def punti(campo):
            return [(data_it(r["data"])[:5], float(r[campo])) for r in righe]
        self.g_emotivo.imposta_serie([
            ("umore", punti("umore"), self.c["accento"]),
            ("energia", punti("energia"), "#35c4d7")])
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

    def _aggiorna_carriera(self) -> None:
        self.svuota(self.lay_carriera)
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
            self.lay_carriera.addWidget(RigaMisura(
                self.c, "", p["nome"], nota, f"{p['avanzamento']}%",
                euro(p["compenso"]) if p["compenso"] else "", p["avanzamento"],
                p["colore"]))
        self.lay_carriera.addStretch(1)
        dal, al = settimana_corrente()
        minuti = self.db.minuti_lavoro(dal, al)
        dal_m, al_m = mese_corrente()
        incassi = self.db.totale_incassi(dal_m, al_m)
        self.contenitore.sezioni["carriera"].imposta_nota(
            f"{durata(minuti)} questa settimana · {euro(incassi)} questo mese")

    def _aggiorna_accademica(self) -> None:
        self.svuota(self.lay_accademica)
        esami = [e for e in self.db.esami() if e["stato"] != "superato"]
        esami.sort(key=lambda e: (e["data_esame"] == "", e["data_esame"]))
        if not esami:
            self.lay_accademica.addWidget(etichetta(
                "Nessun esame in programma.", "NotaScheda"))
        for e in esami[:6]:
            nota = f"{e['cfu']} CFU"
            valore = data_it(e["data_esame"]) if e["data_esame"] else "da fissare"
            self.lay_accademica.addWidget(RigaMisura(
                self.c, "", e["nome"], nota, valore, f"{e['avanzamento']}%",
                e["avanzamento"], "#35c4d7"))
        self.lay_accademica.addStretch(1)
        r = self.db.riepilogo_libretto()
        dal, al = settimana_corrente()
        studio = self.db.minuti_studio(dal, al)
        self.contenitore.sezioni["accademica"].imposta_nota(
            f"CFU {r['cfu']} · media {numero(r['media'], 1)} · "
            f"{durata(studio)} di studio questa settimana" if r["n"] else
            f"{durata(studio)} di studio questa settimana")

    def _aggiorna_abitudini(self) -> None:
        quanti = int(self.periodo("abitudini"))
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
        mesi = int(self.periodo("finanza"))
        serie = self.fonte.serie_mensile(mesi)
        self.g_finanza.imposta_dati(
            [(etichetta_mese(m), [e, u]) for m, e, u in serie],
            [("entrate", self.c["entrata"]), ("uscite", self.c["uscita"])])
        risparmio = entrate - uscite
        self.contenitore.sezioni["finanza"].imposta_nota(
            f"risparmio del mese {euro(risparmio)}")

    def _aggiorna_impegni(self) -> None:
        quanti = int(self.periodo("impegni"))
        oggi = date.today()
        limite = (oggi + timedelta(days=quanti)).isoformat()
        scadenze = list(self.db.scadenze("", limite, solo_aperte=True, limite=40))
        esami = [e for e in self.db.esami()
                 if e["stato"] != "superato" and e["data_esame"] and
                 e["data_esame"] <= limite]
        progetti = [p for p in self.db.progetti()
                    if p["stato"] in ("corso", "pausa") and p["scadenza"] and
                    p["scadenza"] <= limite]
        voci = [(s["data"], s["titolo"], AREE.get(s["area"], s["area"]))
                for s in scadenze]
        voci += [(e["data_esame"], f"Esame di {e['nome']}", "Accademica") for e in esami]
        voci += [(p["scadenza"], f"Consegna {p['nome']}", "Carriera") for p in progetti]
        voci.sort(key=lambda v: v[0])

        self.tab.setRowCount(len(voci))
        for i, (giorno, titolo, area) in enumerate(voci):
            cella = QTableWidgetItem(relativa(giorno))
            cella.setToolTip(data_it(giorno))
            if giorno <= oggi.isoformat():
                cella.setForeground(QColor(self.c["uscita"]))
            elif giorno <= (oggi + timedelta(days=7)).isoformat():
                cella.setForeground(QColor(self.c["attenzione"]))
            self.tab.setItem(i, 0, cella)
            self.tab.setItem(i, 1, QTableWidgetItem(titolo))
            self.tab.setItem(i, 2, QTableWidgetItem(area))
        self.contenitore.sezioni["impegni"].imposta_nota(
            f"{len(voci)} nei prossimi {quanti} giorni")
