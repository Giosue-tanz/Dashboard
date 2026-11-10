"""Finanza: lo stesso cruscotto dell'app Finance, dentro Dashboard.

I dati arrivano dall'archivio di Finance (in sola lettura) quando è installato,
altrimenti dall'archivio interno, dove i movimenti si inseriscono qui dentro.
"""
from __future__ import annotations

import os
from datetime import date

from PySide6.QtCore import QProcess, Qt
from PySide6.QtWidgets import (QHeaderView, QMenu, QPushButton, QTableWidget,
                               QTableWidgetItem)

from ..componenti import (ContenutoStat, NavigatorePeriodo, RigaMisura,
                          abilita_deselezione, etichetta, stile_tabella)
from ..dialoghi import DialogoMovimento, DialogoObiettivo
from ..grafici import GraficoBarre, GraficoCiambella, GraficoLinea
from ..icone_categorie import etichetta_categoria
from ..tema import PALETTE_GRAFICI
from ..utils import (FINESTRE, PERIODI, anno_corrente, data_it, euro,
                     intervallo, intervallo_precedente, mese_corrente,
                     relativa)
from . import VistaSezioni

ICONE_CONTO = {"Conto corrente": "🏦", "Contanti": "💵", "Carta prepagata": "💳",
               "Risparmio": "🐷", "Investimenti": "📈", "Altro": "👛"}


class VistaFinanza(VistaSezioni):
    titolo = "Finanza"
    sottotitolo = "Quanto entra, quanto esce, quanto resta"
    chiave_vista = "finanza"
    versione_layout = 2        # i riquadri sono quelli del cruscotto di Finance

    SEZIONI = {
        "saldo": "SALDO TOTALE",
        "entrate": "ENTRATE",
        "uscite": "USCITE",
        "risparmio": "RISPARMIO",
        "andamento": "Andamento del saldo",
        "ripartizione": "Uscite per categoria",
        "conti": "Saldo dei conti",
        "mensili": "Entrate e uscite",
        "budget": "Budget",
        "ultimi": "Ultimi movimenti",
        "obiettivi": "Obiettivi di risparmio",
    }
    DISPOSIZIONE = [["saldo", "entrate", "uscite", "risparmio"],
                    ["andamento", "ripartizione"],
                    ["conti", "mensili", "budget"],
                    ["ultimi"]]
    ALTEZZE_PREDEFINITE = (0.19, 0.30, 0.28, 0.23)
    PERIODI_SEZIONE = {
        "entrate": (PERIODI, "mese"),
        "uscite": (PERIODI, "mese"),
        "risparmio": (PERIODI, "mese"),
        "ripartizione": (PERIODI, "mese"),
        "ultimi": (PERIODI, "trenta"),
        "budget": ({"mese": "Mese corrente", "mese_scorso": "Mese scorso"}, "mese"),
    }

    def crea_sezioni(self) -> None:
        self.b_obiettivo = QPushButton("Nuovo obiettivo")
        self.b_obiettivo.clicked.connect(self.nuovo_obiettivo)
        self.b_finance = QPushButton("Apri Finance")
        self.b_finance.setToolTip("Apre l'app Finance, dove i movimenti si scrivono.")
        self.b_finance.clicked.connect(self._apri_finance)
        # «Apri Finance» per ultimo: in sola lettura prende il posto (e il verde)
        # che altrove è del pulsante «+ Nuovo movimento», in fondo a destra
        self.azioni_intestazione = ([self.b_obiettivo] + self.azioni_intestazione
                                    + [self.b_finance])
        self._aggiorna_azioni()

        # ---------------------------------------------------- i quattro dati
        self.stat: dict[str, ContenutoStat] = {}
        for chiave, colore in (("saldo", self.c["accento"]),
                               ("entrate", self.c["entrata"]),
                               ("uscite", self.c["uscita"]),
                               ("risparmio", self.c["attenzione"])):
            contenuto = ContenutoStat(self.c, colore)
            self.stat[chiave] = contenuto
            self.aggiungi(chiave, contenuto, "EtichettaScheda")

        # ------------------------------------------------------------ grafici
        self.nav_saldo = NavigatorePeriodo(self.c, "mesi", tutto=True)
        self.nav_saldo.cambiato.connect(self._aggiorna_andamento)
        self.g_saldo = GraficoLinea(self.c)
        self.g_saldo.formato = lambda v: euro(v).replace(",00", "")
        self.g_saldo.setMinimumHeight(70)
        self.nav_saldo.scorri_con_rotella(self.g_saldo)
        self.aggiungi("andamento", self.g_saldo, comando=self.nav_saldo)

        self.g_torta = GraficoCiambella(self.c)
        self.g_torta.formato = lambda v: euro(v)
        self.g_torta.setMinimumHeight(70)
        self.aggiungi("ripartizione", self.g_torta)

        self.nav_barre = NavigatorePeriodo(self.c, "mesi")
        self.nav_barre.cambiato.connect(self._aggiorna_mensili)
        self.g_barre = GraficoBarre(self.c)
        self.g_barre.formato = lambda v: euro(v).replace(",00", "")
        self.g_barre.setMinimumHeight(70)
        self.nav_barre.scorri_con_rotella(self.g_barre)
        self.aggiungi("mensili", self.g_barre, comando=self.nav_barre)

        # ------------------------------------------------------- elenchi
        self.cont_conti, self.lay_conti = self.colonna(9)
        self.aggiungi("conti", self.scorrevole(self.cont_conti))

        self.cont_budget, self.lay_budget = self.colonna(9)
        self.aggiungi("budget", self.scorrevole(self.cont_budget))

        self.cont_obiettivi, self.lay_obiettivi = self.colonna(9)
        self.aggiungi("obiettivi", self.scorrevole(self.cont_obiettivi))

        # ----------------------------------------------------- movimenti
        self.tab = QTableWidget(0, 5)
        self.tab.setHorizontalHeaderLabels(
            ["Data", "Categoria", "Descrizione", "Conto", "Importo"])
        self.tab.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tab.setSelectionBehavior(QTableWidget.SelectRows)
        self.tab.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tab.customContextMenuRequested.connect(self._menu_movimento)
        self.tab.doubleClicked.connect(self._modifica_movimento)
        self.tab.setMinimumHeight(60)
        h = self.tab.horizontalHeader()
        for colonna in (0, 1, 3, 4):
            h.setSectionResizeMode(colonna, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.Stretch)
        abilita_deselezione(self.tab)
        stile_tabella(self.tab)
        self.aggiungi("ultimi", self.tab)

        self.grafici = [self.g_saldo, self.g_torta, self.g_barre]

    # ------------------------------------------------------------- comandi
    @property
    def nuovo_in_risalto(self) -> bool:
        """Con l'archivio di Finance i movimenti qui non si scrivono."""
        return bool(self.fonte and self.fonte.modificabile)

    @property
    def nome_nuovo(self) -> str:
        """Il pulsante esiste solo se c'è un archivio in cui scrivere.

        Quando i dati arrivano da Finance il posto giusto per un movimento è
        Finance: lì porta il pulsante in risalto, e «Nuovo movimento» sparisce.
        """
        return "+  Nuovo movimento" if self.nuovo_in_risalto else ""

    def _aggiorna_azioni(self) -> None:
        """Il verde va sul pulsante che serve davvero in questo momento."""
        risalto = not self.nuovo_in_risalto
        if bool(self.b_finance.property("risalto")) == risalto:
            return
        self.b_finance.setProperty("risalto", risalto)
        self.b_finance.setObjectName("Primario" if risalto else "AzioneTestata")
        self.b_finance.style().unpolish(self.b_finance)
        self.b_finance.style().polish(self.b_finance)

    @property
    def nota_nuovo(self) -> str:
        if self.nuovo_in_risalto:
            return "Registra un movimento nell'archivio di Dashboard."
        return ("I movimenti arrivano dall'app Finance e qui sono in sola "
                "lettura: si inseriscono là.\nPer tenerli in Dashboard cambia "
                "sorgente in Impostazioni → Finanza.")

    def nuovo(self) -> None:
        if not self.fonte.modificabile:
            self._avviso_sola_lettura()
            return
        dlg = self._dialogo_movimento()
        if dlg.exec():
            self._salva_movimento(dlg.dati())

    def nuovo_obiettivo(self) -> None:
        if not self.fonte.modificabile:
            self._avviso_sola_lettura()
            return
        dlg = DialogoObiettivo(parent=self)
        if dlg.exec():
            self.db.salva_obiettivo(dlg.dati())
            self.azioni["obiettivi"].setChecked(True)
            self._ricarica()

    def _categorie(self) -> dict[str, list[str]]:
        """Un elenco per tipo: le categorie salvate più quelle già usate.

        Entrate e uscite hanno elenchi distinti — «Lavoro» non ha senso fra le
        spese, «Bollette» non ne ha fra le entrate.
        """
        elenchi = {}
        for tipo in ("entrata", "uscita"):
            salvate = self.db.categorie(tipo)
            viste = [c for c, _ in self.fonte.per_categoria(
                tipo, "0001-01-01", "9999-12-31")]
            elenchi[tipo] = salvate + sorted(set(viste) - set(salvate))
        return elenchi

    def _dialogo_movimento(self, voce=None):
        """La finestra del movimento, con sotto mano categorie, conti e tinte."""
        tinte = {r["nome"]: r["colore"] for r in
                 self.db.query("SELECT nome, colore FROM categorie WHERE colore<>''")}
        conti = [r["nome"] for r in self.db.conti()]
        return DialogoMovimento(self._categorie(), voce, parent=self,
                                conti=conti, colori=self.c, tinte=tinte,
                                icone=self.db.icone_categorie())

    def _salva_movimento(self, d: dict) -> None:
        """Salva il movimento e tiene categorie e conto per la prossima volta."""
        self.db.aggiungi_categoria(d["categoria"], d["tipo"])
        for extra in self.db.altre_categorie(d.get("categorie")):
            self.db.aggiungi_categoria(extra, d["tipo"])
        conto = (d.get("conto") or "").strip()
        if conto and not self.db.valore(
                "SELECT COUNT(*) FROM conti WHERE nome=?", (conto,)):
            self.db.salva_conto({"nome": conto, "saldo_iniziale": 0.0,
                                 "tipo": "Conto corrente"})
        self.db.salva_movimento(d)
        self._ricarica()

    def _avviso_sola_lettura(self) -> None:
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(
            self, "Archivio di Finance",
            "Questi dati arrivano dall'app Finance e qui sono in sola lettura.\n\n"
            "Inseriscili in Finance: Dashboard li rilegge al prossimo "
            "aggiornamento (Ctrl+R).\n\nPer tenere i movimenti qui dentro, cambia "
            "la sorgente in Impostazioni → Finanza.")

    def _apri_finance(self) -> None:
        from PySide6.QtWidgets import QMessageBox
        candidati = [self.db.leggi("avvio_finance", "")]
        casa = os.path.expanduser("~")
        candidati += [os.path.join(casa, p, "Finance", "avvia.sh") for p in
                      ("Scrivania/WORK", "Scrivania", "Desktop", "Progetti", "")]
        for percorso in candidati:
            if percorso and os.path.exists(percorso):
                QProcess.startDetached(percorso, [])
                self.db.imposta("avvio_finance", percorso)
                return
        QMessageBox.information(
            self, "Finance", "Non trovo l'avviatore di Finance.\n\n"
            "Indica il percorso di «avvia.sh» in Impostazioni → Finanza.")

    def _ricarica(self) -> None:
        self.aggiorna()
        self.dati_cambiati.emit()

    def _id_movimento(self):
        righe = self.tab.selectionModel().selectedRows()
        if not righe:
            return None
        return self.tab.item(righe[0].row(), 0).data(Qt.UserRole)

    def _modifica_movimento(self) -> None:
        if not self.fonte.modificabile:
            self._avviso_sola_lettura()
            return
        id_ = self._id_movimento()
        voce = self.db.uno("SELECT * FROM movimenti WHERE id=?", (id_,)) if id_ else None
        if voce is None:
            return
        dlg = self._dialogo_movimento(voce)
        if dlg.exec():
            self._salva_movimento(dlg.dati())

    def _menu_movimento(self, punto) -> None:
        id_ = self._id_movimento()
        if id_ is None or not self.fonte.modificabile:
            return
        menu = QMenu(self)
        menu.addAction("Modifica", self._modifica_movimento)
        menu.addAction("Elimina", lambda: (self.db.elimina("movimenti", id_),
                                           self._ricarica()))
        menu.exec(self.tab.viewport().mapToGlobal(punto))

    def _modifica_obiettivo(self, id_: int) -> None:
        if not self.fonte.modificabile:
            self._avviso_sola_lettura()
            return
        voce = self.db.uno("SELECT * FROM obiettivi WHERE id=?", (id_,))
        if voce is None:
            return
        dlg = DialogoObiettivo(voce, parent=self)
        if dlg.exec():
            self.db.salva_obiettivo(dlg.dati())
            self._ricarica()

    # ---------------------------------------------------------------- dati
    def aggiorna(self) -> None:
        self._aggiorna_azioni()
        self.b_finance.setVisible(not self.fonte.modificabile)
        self.b_obiettivo.setVisible(self.fonte.modificabile)
        self._aggiorna_stat()
        self._aggiorna_andamento()
        self._aggiorna_ripartizione()
        self._aggiorna_conti()
        self._aggiorna_mensili()
        self._aggiorna_budget()
        self._aggiorna_obiettivi()
        self._aggiorna_movimenti()

    def _serie_mensile(self, quanti: int = 12) -> list[tuple[str, float, float]]:
        return self.fonte.serie_mensile(quanti)

    def _aggiorna_stat(self) -> None:
        serie = self._serie_mensile(12)
        saldo = self.fonte.saldo()
        self.stat["saldo"].imposta(
            euro(saldo), f"fonte: {self.fonte.nome}",
            [self.fonte.saldo_alla_data(f"{m}-28") for m, _, _ in serie])

        for chiave in ("entrate", "uscite", "risparmio"):
            periodo = self.periodo(chiave)
            dal, al = intervallo(periodo)
            entrate, uscite = self.fonte.totali_periodo(dal, al)
            prima_dal, prima_al = intervallo_precedente(periodo)
            p_entrate, p_uscite = self.fonte.totali_periodo(prima_dal, prima_al)
            if chiave == "entrate":
                valore, prima = entrate, p_entrate
                serie_valori = [e for _, e, _ in serie]
            elif chiave == "uscite":
                valore, prima = uscite, p_uscite
                serie_valori = [u for _, _, u in serie]
            else:
                valore, prima = entrate - uscite, p_entrate - p_uscite
                serie_valori = [e - u for _, e, u in serie]
            if prima:
                scarto = (valore - prima) / abs(prima) * 100
                nota = f"{'+' if scarto >= 0 else '−'}{abs(scarto):.0f}% sul periodo prima"
            elif chiave == "risparmio" and entrate:
                nota = f"{(entrate - uscite) / entrate * 100:.0f}% di quanto è entrato"
            else:
                nota = "nessun confronto"
            self.stat[chiave].imposta(euro(valore), nota, serie_valori)

    def _aggiorna_andamento(self) -> None:
        """Quanto c'era in cassa alla fine di ogni finestra."""
        oggi = date.today().isoformat()
        punti = [(nome, self.fonte.saldo_alla_data(min(al, oggi)))
                 for nome, _dal, al in self.nav_saldo.finestre()
                 if _dal <= oggi]        # il saldo di un mese che non c'è ancora
        self.g_saldo.imposta_dati(punti, self.c["accento"], "saldo")
        self.contenitore.sezioni["andamento"].imposta_nota(
            f"{len(punti)} letture" if len(punti) > 1 else "")

    def _aggiorna_ripartizione(self) -> None:
        dal, al = intervallo(self.periodo("ripartizione"))
        voci = self.fonte.per_categoria("uscita", dal, al)[:10]
        totale = sum(v for _, v in voci)
        icone = self.db.icone_categorie()
        tinte = {r["nome"]: r["colore"] for r in self.db.query(
            "SELECT nome, colore FROM categorie WHERE colore<>''")}
        self.g_torta.imposta_dati(
            [(etichetta_categoria(nome, icone.get(nome)), valore,
              tinte.get(nome) or PALETTE_GRAFICI[i % len(PALETTE_GRAFICI)])
             for i, (nome, valore) in enumerate(voci)],
            euro(totale) if totale else "—", "di uscite")

    def _aggiorna_conti(self) -> None:
        self.svuota(self.lay_conti)
        conti = self.fonte.conti() if hasattr(self.fonte, "conti") else []
        totale = sum(saldo for _, saldo in conti) or 1
        for nome, saldo in conti:
            quota = int(max(0.0, min(100.0, saldo / totale * 100)))
            self.lay_conti.addWidget(RigaMisura(
                self.c, ICONE_CONTO.get("Conto corrente", "🏦"), nome,
                "quota del totale", euro(saldo), f"{quota}%", quota,
                self.c["accento"] if saldo >= 0 else self.c["uscita"]))
        if not conti:
            self.lay_conti.addWidget(etichetta("Nessun conto.", "NotaScheda"))
        self.lay_conti.addStretch(1)
        self.contenitore.sezioni["conti"].imposta_nota(
            f"{len(conti)} conti" if len(conti) != 1 else "")

    def _aggiorna_mensili(self) -> None:
        """Entrate e uscite, una coppia di barre per finestra."""
        finestre = self.nav_barre.finestre()
        dati, risparmi = [], []
        for nome, dal, al in finestre:
            entrate, uscite = self.fonte.totali_periodo(dal, al)
            dati.append((nome, [entrate, uscite]))
            risparmi.append(entrate - uscite)
        self.g_barre.evidenziata = self.nav_barre.indice_adesso()
        self.g_barre.imposta_dati(
            dati, [("entrate", self.c["entrata"]), ("uscite", self.c["uscita"])])
        in_attivo = sum(1 for r in risparmi if r > 0)
        self.contenitore.sezioni["mensili"].imposta_nota(
            f"in attivo {in_attivo} volte su {len(risparmi)}" if risparmi else "")

    def _aggiorna_budget(self) -> None:
        self.svuota(self.lay_budget)
        voci = self.fonte.budget()
        if not voci:
            self.lay_budget.addWidget(etichetta(
                "Nessun budget impostato." if self.fonte.modificabile
                else "Nessun budget in Finance.", "NotaScheda"))
            self.lay_budget.addStretch(1)
            self.contenitore.sezioni["budget"].imposta_nota("")
            return
        sforati = 0
        for categoria, limite, speso in voci:
            quota = int(speso / limite * 100) if limite else 0
            colore = self.c["uscita"] if speso > limite > 0 else self.c["accento"]
            if speso > limite > 0:
                sforati += 1
            self.lay_budget.addWidget(RigaMisura(
                self.c, "", categoria, f"restano {euro(max(0.0, limite - speso))}",
                euro(speso), f"su {euro(limite)}", quota, colore))
        self.lay_budget.addStretch(1)
        self.contenitore.sezioni["budget"].imposta_nota(
            f"{sforati} sforati" if sforati else f"{len(voci)} categorie")

    def _aggiorna_obiettivi(self) -> None:
        self.svuota(self.lay_obiettivi)
        voci = self.fonte.obiettivi()
        if not voci:
            self.lay_obiettivi.addWidget(etichetta(
                "Nessun obiettivo di risparmio.", "NotaScheda"))
            self.lay_obiettivi.addStretch(1)
            return
        locali = ({r["nome"]: r["id"] for r in self.db.obiettivi()}
                  if self.fonte.modificabile else {})
        for nome, obiettivo, accantonato, scadenza in voci:
            quota = int(accantonato / obiettivo * 100) if obiettivo else 0
            nota = f"entro {data_it(scadenza)}" if scadenza else "senza scadenza"
            misura = RigaMisura(self.c, "", nome, nota, euro(accantonato),
                                f"su {euro(obiettivo)}", quota, self.c["accento"])
            if nome in locali:
                misura.setCursor(Qt.PointingHandCursor)
                misura.mouseDoubleClickEvent = (
                    lambda _ev, id_=locali[nome]: self._modifica_obiettivo(id_))
            self.lay_obiettivi.addWidget(misura)
        self.lay_obiettivi.addStretch(1)

    def _aggiorna_movimenti(self) -> None:
        dal, al = intervallo(self.periodo("ultimi"))
        if dal < "1900":
            dal, al = "", ""
        voci = self.fonte.movimenti(dal, al, limite=400)
        icone = self.db.icone_categorie()
        self.tab.setRowCount(len(voci))
        for i, m in enumerate(voci):
            cella = QTableWidgetItem(relativa(m["data"]))
            cella.setData(Qt.UserRole, m.get("id"))
            cella.setToolTip(data_it(m["data"]))
            self.tab.setItem(i, 0, cella)
            # la prima categoria è quella che possiede l'importo; le altre
            # si contano accanto, senza allungare la colonna
            altre = self.db.altre_categorie(m.get("categorie"))
            nome_cat = m.get("categoria", "")
            cella_cat = QTableWidgetItem(
                etichetta_categoria(nome_cat, icone.get(nome_cat))
                + (f"  +{len(altre)}" if altre else ""))
            if altre:
                cella_cat.setToolTip("anche: " + ", ".join(altre))
            self.tab.setItem(i, 1, cella_cat)
            self.tab.setItem(i, 2, QTableWidgetItem(m.get("descrizione", "")))
            self.tab.setItem(i, 3, QTableWidgetItem(m.get("conto", "") or "—"))
            entrata = m.get("tipo") == "entrata"
            importo = QTableWidgetItem(
                ("+" if entrata else "−") + euro(abs(float(m.get("importo", 0)))))
            importo.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            from PySide6.QtGui import QColor
            importo.setForeground(QColor(self.c["entrata"] if entrata
                                         else self.c["uscita"]))
            self.tab.setItem(i, 4, importo)
        nota = "" if self.fonte.modificabile else " · sola lettura"
        self.contenitore.sezioni["ultimi"].imposta_nota(
            f"{len(voci)} movimenti{nota}")
