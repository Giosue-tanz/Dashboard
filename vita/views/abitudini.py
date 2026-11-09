"""Abitudini: la griglia dei giorni, un clic per segnare."""
from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QMenu, QMessageBox, QPushButton,
                               QSizePolicy, QWidget)

from ..componenti import (NavigatorePeriodo, RigaMisura, SceltaPeriodo,
                          etichetta)
from ..dialoghi import DialogoAbitudine
from ..grafici import GraficoBarre
from ..icone_nav import icona
from ..tema import trasparente
from ..utils import GIORNI_CORTI, data_it, media, numero, ultimi_giorni
from . import VistaSezioni


class RigaAbitudine(QFrame):
    """Riga dell'elenco: il nome si riscrive sul posto, i comandi sono in vista."""

    rinominata = Signal(int, str)
    modifica_chiesta = Signal(int)
    menu_chiesto = Signal(int, object)

    def __init__(self, abitudine, colori: dict, parent=None):
        super().__init__(parent)
        self.id = int(abitudine["id"])
        self.nome_salvato = abitudine["nome"]
        attiva = bool(abitudine["attiva"])
        self.setObjectName("RigaAbitudine")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAttribute(Qt.WA_Hover, True)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 7, 8, 7)
        lay.setSpacing(9)

        punto = QLabel()
        punto.setFixedSize(10, 10)
        punto.setStyleSheet(
            f"background: {abitudine['colore'] if attiva else colori['griglia']};"
            " border-radius: 5px;")
        lay.addWidget(punto, 0, Qt.AlignVCenter)

        self.campo = QLineEdit(abitudine["nome"])
        self.campo.setObjectName("NomeAbitudine")
        self.campo.setToolTip("Scrivi qui per rinominare, Invio per confermare")
        self.campo.setMinimumWidth(70)
        if not attiva:
            self.campo.setStyleSheet(f"color: {colori['testo2']};")
        self.campo.editingFinished.connect(self._conferma)
        lay.addWidget(self.campo, 1)

        nota = QLabel(f"{abitudine['obiettivo']}×/sett" if attiva else "in pausa")
        nota.setObjectName("NotaScheda")
        nota.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lay.addWidget(nota, 0, Qt.AlignVCenter)

        b_modifica = self._bottone("matita", colori,
                                   "Modifica colore, obiettivo e area")
        b_modifica.clicked.connect(lambda: self.modifica_chiesta.emit(self.id))
        lay.addWidget(b_modifica, 0, Qt.AlignVCenter)

        self.b_menu = self._bottone("punti", colori, "Rinomina, pausa, elimina")
        self.b_menu.clicked.connect(
            lambda: self.menu_chiesto.emit(
                self.id, self.b_menu.mapToGlobal(self.b_menu.rect().bottomLeft())))
        lay.addWidget(self.b_menu, 0, Qt.AlignVCenter)

    @staticmethod
    def _bottone(nome: str, colori: dict, suggerimento: str) -> QPushButton:
        b = QPushButton()
        b.setObjectName("IconaRiga")
        b.setIcon(icona(nome, colori["testo2"], colori["testo"]))
        b.setIconSize(QSize(18, 18))
        b.setFixedSize(28, 28)
        b.setCursor(Qt.PointingHandCursor)
        b.setToolTip(suggerimento)
        return b

    def in_modifica(self) -> bool:
        return self.campo.hasFocus()

    def _conferma(self) -> None:
        nome = self.campo.text().strip()
        if not nome:
            self.campo.setText(self.nome_salvato)
            return
        if nome == self.nome_salvato:
            return
        self.nome_salvato = nome
        self.campo.setText(nome)
        self.rinominata.emit(self.id, nome)


class VistaAbitudini(VistaSezioni):
    titolo = "Abitudini"
    sottotitolo = "Le cose che vuoi fare spesso, segnate con un clic"
    nome_nuovo = "+  Nuova abitudine"
    chiave_vista = "abitudini"

    versione_layout = 2
    SEZIONI = {
        "griglia": "Griglia dei giorni",
        "elenco": "Le tue abitudini",
        "serie": "Come stai andando",
        "andamento": "Costanza nel tempo",
    }
    DISPOSIZIONE = [["griglia"], ["elenco", "serie", "andamento"]]
    ALTEZZE_PREDEFINITE = (0.52, 0.48)
    # quante colonne di giorni tiene la griglia: per esteso nel menu,
    # accorciato sulla pastiglia
    GIORNI_GRIGLIA = {"7": "7 giorni", "14": "14 giorni", "21": "21 giorni",
                      "30": "30 giorni", "60": "60 giorni"}
    GIORNI_GRIGLIA_CORTI = {"7": "7 g", "14": "14 g", "21": "21 g",
                            "30": "30 g", "60": "60 g"}
    PERIODI_SEZIONE = {
    }

    def crea_sezioni(self) -> None:
        self.riquadro, self.griglia = self._griglia()
        # la stessa pastiglia stretta della costanza in Salute: qui il periodo
        # è una durata — quante colonne di giorni — non un arco da sfogliare
        self.periodo_griglia = SceltaPeriodo(
            self.GIORNI_GRIGLIA, self.db.leggi("griglia_giorni", "14"),
            self.c, self.GIORNI_GRIGLIA_CORTI)
        self.periodo_griglia.scelto.connect(
            lambda v: (self.db.imposta("griglia_giorni", v),
                       self._aggiorna_griglia()))
        self.aggiungi("griglia", self.scorrevole(self.riquadro),
                      comando=self.periodo_griglia)

        self.righe: dict[int, RigaAbitudine] = {}
        self.cont_elenco, self.lay_elenco = self.colonna(7)
        self.area_elenco = self.aggiungi("elenco", self.scorrevole(self.cont_elenco))

        self.cont_serie, self.lay_serie = self.colonna(10)
        self.aggiungi("serie", self.scorrevole(self.cont_serie))

        self.nav_andamento = NavigatorePeriodo(self.c, "settimane")
        self.nav_andamento.cambiato.connect(self._aggiorna_andamento)
        self.g_andamento = GraficoBarre(self.c)
        self.g_andamento.formato = lambda v: f"{v:.0f}%"
        self.g_andamento.evidenzia_ultima = True
        self.nav_andamento.scorri_con_rotella(self.g_andamento)
        self.aggiungi("andamento", self.g_andamento,
                      comando=self.nav_andamento)

        self.grafici = [self.g_andamento]

    def _griglia(self) -> tuple[QWidget, QGridLayout]:
        riquadro = QWidget()
        riquadro.setObjectName("ContenutoSezione")
        griglia = QGridLayout(riquadro)
        griglia.setContentsMargins(0, 0, 0, 0)
        griglia.setHorizontalSpacing(4)
        griglia.setVerticalSpacing(6)
        return riquadro, griglia

    # ------------------------------------------------------------- comandi
    def nuovo(self) -> None:
        dlg = DialogoAbitudine(parent=self)
        if dlg.exec():
            self.db.salva_abitudine(dlg.dati())
            self._ricarica()

    def _modifica(self, id_: int) -> None:
        voce = self.db.uno("SELECT * FROM abitudini WHERE id=?", (id_,))
        if voce is None:
            return
        dlg = DialogoAbitudine(voce, parent=self)
        if dlg.exec():
            self.db.salva_abitudine(dlg.dati())
            self._ricarica()

    def _rinomina(self, id_: int, nome: str) -> None:
        """Il nome riscritto nell'elenco: si aggiorna tutto tranne l'elenco
        stesso, che ha già il testo giusto e il cursore dentro."""
        self.db.rinomina_abitudine(id_, nome)
        self._aggiorna_griglia()
        self._aggiorna_serie()

    def _pausa(self, id_: int, attiva: bool) -> None:
        self.db.attiva_abitudine(id_, attiva)
        self._ricarica()

    def _elimina(self, id_: int, nome: str) -> None:
        segni = self.db.segni_abitudine(id_)
        avviso = (f"Elimino «{nome}»?" if not segni else
                  f"Elimino «{nome}» e i {segni} giorni già segnati?")
        risposta = QMessageBox.warning(
            self, "Elimina abitudine",
            avviso + "\n\nSe vuoi solo smettere di seguirla, mettila in pausa:"
                     " resta nello storico.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if risposta != QMessageBox.Yes:
            return
        self.db.elimina("abitudini", id_)
        self.db.esegui("DELETE FROM registro WHERE abitudine_id=?", (id_,))
        self._ricarica()

    def _menu_abitudine(self, id_: int, punto) -> None:
        voce = self.db.uno("SELECT * FROM abitudini WHERE id=?", (id_,))
        if voce is None:
            return
        attiva = bool(voce["attiva"])
        menu = QMenu(self)
        menu.addAction("Rinomina", lambda: self._metti_a_fuoco(id_))
        menu.addAction("Modifica…", lambda: self._modifica(id_))
        menu.addSeparator()
        menu.addAction("Riattiva" if not attiva else "Metti in pausa",
                       lambda: self._pausa(id_, not attiva))
        menu.addAction("Elimina", lambda: self._elimina(id_, voce["nome"]))
        menu.exec(punto)

    def _metti_a_fuoco(self, id_: int) -> None:
        """Porta il cursore nel nome dell'abitudine dentro l'elenco."""
        self.azioni["elenco"].setChecked(True)
        riga = self.righe.get(id_)
        if riga is None:
            return
        self.area_elenco.ensureWidgetVisible(riga, 0, 30)
        riga.campo.setFocus(Qt.ShortcutFocusReason)
        riga.campo.selectAll()

    def _commuta(self, giorno: str, id_: int) -> None:
        self.db.commuta_abitudine(giorno, id_)
        self._ricarica()

    def _ricarica(self) -> None:
        self.aggiorna()
        self.dati_cambiati.emit()

    # ---------------------------------------------------------------- dati
    def aggiorna(self) -> None:
        self._aggiorna_griglia()
        self._aggiorna_elenco()
        self._aggiorna_serie()
        self._aggiorna_andamento()

    def _aggiorna_griglia(self) -> None:
        while self.griglia.count():
            w = self.griglia.takeAt(0).widget()
            if w is not None:
                w.hide(); w.setParent(None); w.deleteLater()

        abitudini = self.db.abitudini()
        if not abitudini:
            self.griglia.addWidget(etichetta(
                "Nessuna abitudine. Usa «+ Nuova abitudine» in alto a destra.",
                "NotaScheda"), 0, 0)
            return

        giorni = ultimi_giorni(int(self.periodo_griglia.valore))
        fatte = self.db.registro(giorni[0], giorni[-1])
        oggi = date.today().isoformat()

        for colonna, giorno in enumerate(giorni, start=1):
            d = date.fromisoformat(giorno)
            testa = QLabel(f"{GIORNI_CORTI[d.weekday()]}\n{d.day}")
            testa.setObjectName("NotaScheda")
            testa.setAlignment(Qt.AlignCenter)
            if giorno == oggi:
                testa.setStyleSheet(f"color: {self.c['testo']}; font-weight: 700;")
            self.griglia.addWidget(testa, 0, colonna)
        self.griglia.addWidget(QLabel(""), 0, len(giorni) + 1)

        for riga_, a in enumerate(abitudini, start=1):
            nome = QPushButton(a["nome"])
            nome.setObjectName("NomeGriglia")
            nome.setCursor(Qt.PointingHandCursor)
            nome.setToolTip(f"Modifica «{a['nome']}»")
            nome.clicked.connect(lambda _=False, id_=a["id"]: self._modifica(id_))
            nome.setContextMenuPolicy(Qt.CustomContextMenu)
            nome.customContextMenuRequested.connect(
                lambda punto, id_=a["id"], w=nome: self._menu_abitudine(
                    id_, w.mapToGlobal(punto)))
            self.griglia.addWidget(nome, riga_, 0)

            quante = 0
            for colonna, giorno in enumerate(giorni, start=1):
                segnata = (giorno, a["id"]) in fatte
                quante += 1 if segnata else 0
                cella = QPushButton()
                cella.setFixedHeight(22)
                cella.setMinimumWidth(18)
                cella.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                cella.setCursor(Qt.PointingHandCursor)
                cella.setToolTip(f"{a['nome']} · {data_it(giorno)}")
                bordo = (f"border: 1.5px solid {self.c['testo2']};"
                         if giorno == oggi else "border: none;")
                sfondo = a["colore"] if segnata else self.c["griglia"]
                cella.setStyleSheet(
                    f"QPushButton {{ background: {sfondo}; {bordo} border-radius: 6px; }}"
                    f"QPushButton:hover {{ background: "
                    f"{a['colore'] if segnata else trasparente(a['colore'], 0.45)}; }}")
                cella.clicked.connect(
                    lambda _=False, g=giorno, id_=a["id"]: self._commuta(g, id_))
                self.griglia.addWidget(cella, riga_, colonna)

            totale = QLabel(f"{quante}/{len(giorni)}")
            totale.setObjectName("NotaScheda")
            totale.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.griglia.addWidget(totale, riga_, len(giorni) + 1)

        self.griglia.setColumnStretch(0, 0)
        self.griglia.setRowStretch(len(abitudini) + 1, 1)
        self.contenitore.sezioni["griglia"].imposta_nota(
            f"{len(abitudini)} abitudini · clic per segnare")

    def _aggiorna_elenco(self) -> None:
        if any(r.in_modifica() for r in self.righe.values()):
            return                      # c'è il cursore in un nome: non lo tolgo
        self.svuota(self.lay_elenco)
        self.righe = {}
        abitudini = self.db.abitudini(solo_attive=False)
        for a in abitudini:
            riga_ = RigaAbitudine(a, self.c)
            riga_.rinominata.connect(self._rinomina)
            riga_.modifica_chiesta.connect(self._modifica)
            riga_.menu_chiesto.connect(self._menu_abitudine)
            self.righe[riga_.id] = riga_
            self.lay_elenco.addWidget(riga_)
        if not abitudini:
            self.lay_elenco.addWidget(etichetta(
                "Nessuna abitudine. Usa «+ Nuova abitudine» in alto a destra.",
                "NotaScheda"))
        self.lay_elenco.addStretch(1)
        self.contenitore.sezioni["elenco"].imposta_nota(
            "rinomina sul posto")

    def _aggiorna_serie(self) -> None:
        self.svuota(self.lay_serie)
        abitudini = self.db.abitudini()
        oggi = date.today()
        lunedi = oggi - timedelta(days=oggi.weekday())
        fatte = self.db.registro(lunedi.isoformat(), oggi.isoformat())
        for a in abitudini:
            questa = sum(1 for (g, id_) in fatte if id_ == a["id"])
            serie = self.db.serie_abitudine(a["id"])
            quota = int(questa / a["obiettivo"] * 100) if a["obiettivo"] else 0
            nota = f"{serie} giorni di fila" if serie else "nessuna serie in corso"
            self.lay_serie.addWidget(RigaMisura(
                self.c, "", a["nome"], nota, f"{questa}/{a['obiettivo']}",
                "questa settimana", quota, a["colore"]))
        if not abitudini:
            self.lay_serie.addWidget(etichetta("Niente da mostrare.", "NotaScheda"))
        self.lay_serie.addStretch(1)

    def _aggiorna_andamento(self) -> None:
        """Quanto degli obiettivi hai centrato, una barra per finestra.

        Gli obiettivi delle abitudini sono settimanali: in «settimane» una
        barra è una settimana ed è il conto giusto. In «giorni» e in «mesi»
        la quota si rapporta a quanto di una settimana sta nella finestra,
        se no un giorno solo sembrerebbe sempre un disastro.
        """
        abitudini = self.db.abitudini()
        obiettivo_settimana = sum(a["obiettivo"] for a in abitudini) or 1
        finestre = self.nav_andamento.finestre()
        dati, valori = [], []
        for nome, dal, al in finestre:
            quanti = (date.fromisoformat(al) - date.fromisoformat(dal)).days + 1
            obiettivo = obiettivo_settimana * quanti / 7
            fatte = self.db.registro(dal, al)
            quota = min(100.0, len(fatte) / obiettivo * 100) if obiettivo else 0.0
            dati.append((nome, [quota]))
            valori.append(quota)
        self.g_andamento.riferimento = 100
        self.g_andamento.evidenziata = self.nav_andamento.indice_adesso()
        self.g_andamento.imposta_dati(dati, [("costanza", self.c["accento"])])
        self.contenitore.sezioni["andamento"].imposta_nota(
            f"media {numero(media(valori), 0)}% degli obiettivi")
