"""Viste modulari dell'applicazione.

Ogni vista è un QWidget indipendente che riceve il database e la palette,
espone `aggiorna()` e segnala le modifiche con `dati_cambiati`.

`VistaSezioni` aggiunge quello che in Finance fa il cruscotto: riquadri che si
trascinano, si ridimensionano con i divisori, si nascondono dal menu e si
ricordano la disposizione. Qui ce l'hanno tutte le pagine.
"""
from __future__ import annotations

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QMenu, QPushButton, QScrollArea, QVBoxLayout,
                               QWidget)

from ..sezioni import ContenitoreSezioni, Sezione


class VistaBase(QWidget):
    dati_cambiati = Signal()
    area_richiesta = Signal(str)      # «portami alla pagina …»

    titolo = "Vista"
    sottotitolo = ""
    nome_nuovo = ""          # testo del pulsante in alto a destra; vuoto = assente
    # un pulsante in risalto promette che qualcosa succede: se l'azione non è
    # disponibile la vista lo dice qui e il pulsante resta discreto
    nuovo_in_risalto = True
    nota_nuovo = ""          # suggerimento del pulsante in alto a destra

    def __init__(self, db, colori: dict, fonte=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.c = colori
        self.fonte = fonte
        self.grafici: list = []
        self.azioni_intestazione: list[QWidget] = []
        self.costruisci()

    # da sovrascrivere
    def costruisci(self) -> None:
        ...

    def aggiorna(self) -> None:
        ...

    def nuovo(self) -> None:
        """Azione del pulsante «+» in alto a destra."""

    def aggiorna_tema(self, colori: dict) -> None:
        self.c = colori
        for g in self.grafici:
            if hasattr(g, "aggiorna_tema"):
                g.aggiorna_tema(colori)
        self.aggiorna()

    def area_scorrevole(self) -> tuple[QScrollArea, QVBoxLayout]:
        esterno = QVBoxLayout(self)
        esterno.setContentsMargins(0, 0, 0, 0)
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.NoFrame)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        interno = QWidget()
        lay = QVBoxLayout(interno)
        lay.setContentsMargins(2, 2, 6, 10)
        lay.setSpacing(14)
        area.setWidget(interno)
        esterno.addWidget(area)
        return area, lay


class VistaSezioni(VistaBase):
    """Vista fatta di riquadri componibili, come il cruscotto di Finance."""

    chiave_vista = "vista"
    # da alzare quando cambiano i riquadri: le disposizioni salvate con la
    # versione precedente non valgono più e si riparte da quella predefinita
    versione_layout = 1
    SEZIONI: dict[str, str] = {}
    DISPOSIZIONE: list[list[str]] = []
    PERIODI_SEZIONE: dict[str, tuple[dict, str]] = {}
    ALTEZZE_PREDEFINITE: tuple[float, ...] = ()
    # quote di larghezza riga per riga: senza, le colonne si dividono in parti uguali
    LARGHEZZE_PREDEFINITE: tuple[tuple[float, ...], ...] = ()
    # riquadri che alla prima apertura restano chiusi, finché non servono
    NASCOSTE_PREDEFINITE: tuple[str, ...] = ()

    def costruisci(self) -> None:
        self._pronto = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 6, 6)
        lay.setSpacing(8)
        self.contenitore = ContenitoreSezioni()
        self._menu_sezioni()
        lay.addWidget(self.contenitore, 1)
        self.crea_sezioni()
        self._ripristina()
        self.contenitore.disposizione_cambiata.connect(self._salva)
        self._pronto = True

    # da sovrascrivere
    def crea_sezioni(self) -> None:
        ...

    # ------------------------------------------------------------- riquadri
    def _menu_sezioni(self) -> None:
        self.b_sezioni = QPushButton("Riquadri")
        self.b_sezioni.setToolTip(
            "Mostra o nascondi i riquadri e ripristina la disposizione.\n\n"
            "Trascina un riquadro dal titolo per spostarlo, anche su una riga nuova.\n"
            "I divisori fra i riquadri ne regolano le dimensioni.\n"
            "Il testo accanto al titolo apre i periodi; «⋯» gli altri comandi.")
        self.menu_sezioni = QMenu(self)
        self.azioni: dict[str, QAction] = {}
        for chiave, nome in self.SEZIONI.items():
            a = QAction(nome.capitalize() if nome.isupper() else nome,
                        self, checkable=True, checked=True)
            a.toggled.connect(lambda visibile, k=chiave: self._mostra(k, visibile))
            self.menu_sezioni.addAction(a)
            self.azioni[chiave] = a
        self.menu_sezioni.addSeparator()
        self.menu_sezioni.addAction("Ripristina disposizione predefinita",
                                    self.ripristina_predefinita)
        self.b_sezioni.setMenu(self.menu_sezioni)
        self.azioni_intestazione = [self.b_sezioni]

    def aggiungi(self, chiave: str, contenuto: QWidget, stile: str = "Sezione") -> QWidget:
        sezione = Sezione(chiave, self.SEZIONI.get(chiave, chiave), contenuto, stile)
        sezione.chiusura_richiesta.connect(lambda k: self.azioni[k].setChecked(False))
        sezione.periodo_richiesto.connect(self._menu_periodo)
        sezione.menu_richiesto.connect(self._menu_sezione)
        sezione.imposta_periodo(self._nome_periodo(chiave))
        self.contenitore.registra(sezione)
        return contenuto

    def scorrevole(self, contenuto: QWidget) -> QScrollArea:
        """Mette un contenuto dentro un riquadro che scorre."""
        area = QScrollArea()
        area.setObjectName("ContenutoSezione")
        area.viewport().setObjectName("ContenutoSezione")
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.NoFrame)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        area.setWidget(contenuto)
        area.setMinimumHeight(60)
        return area

    @staticmethod
    def colonna(spaziatura: int = 9) -> tuple[QWidget, QVBoxLayout]:
        contenuto = QWidget()
        contenuto.setObjectName("ContenutoSezione")
        lay = QVBoxLayout(contenuto)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(spaziatura)
        return contenuto, lay

    @staticmethod
    def svuota(layout) -> None:
        while layout.count():
            voce = layout.takeAt(0)
            w = voce.widget()
            if w is not None:
                # nascondere prima di staccare: un widget senza genitore e
                # ancora visibile diventa una finestrella per conto suo
                w.hide()
                w.setParent(None)
                w.deleteLater()

    # -------------------------------------------------------------- periodi
    def periodo(self, chiave: str) -> str:
        if chiave not in self.PERIODI_SEZIONE:
            return ""
        voci, predefinito = self.PERIODI_SEZIONE[chiave]
        scelto = self.db.leggi(f"periodo_{self.chiave_vista}_{chiave}", predefinito)
        return scelto if scelto in voci else predefinito

    def _nome_periodo(self, chiave: str) -> str:
        if chiave not in self.PERIODI_SEZIONE:
            return ""
        voci, _ = self.PERIODI_SEZIONE[chiave]
        return voci[self.periodo(chiave)].lower()

    def _menu_periodo(self, chiave: str, punto) -> None:
        if chiave not in self.PERIODI_SEZIONE:
            return
        voci, _ = self.PERIODI_SEZIONE[chiave]
        corrente = self.periodo(chiave)
        menu = QMenu(self)
        for valore, testo in voci.items():
            azione = menu.addAction(testo)
            azione.setCheckable(True)
            azione.setChecked(valore == corrente)
            azione.triggered.connect(
                lambda _=False, k=chiave, v=valore: self._imposta_periodo(k, v))
        menu.exec(punto)

    def _imposta_periodo(self, chiave: str, valore: str) -> None:
        self.db.imposta(f"periodo_{self.chiave_vista}_{chiave}", valore)
        self.contenitore.sezioni[chiave].imposta_periodo(self._nome_periodo(chiave))
        self.aggiorna()

    def _menu_sezione(self, chiave: str, punto) -> None:
        menu = QMenu(self)
        if chiave in self.PERIODI_SEZIONE:
            voci, _ = self.PERIODI_SEZIONE[chiave]
            corrente = self.periodo(chiave)
            sotto = menu.addMenu("Periodo")
            for valore, testo in voci.items():
                azione = sotto.addAction(testo)
                azione.setCheckable(True)
                azione.setChecked(valore == corrente)
                azione.triggered.connect(
                    lambda _=False, k=chiave, v=valore: self._imposta_periodo(k, v))
            menu.addSeparator()
        menu.addAction("Nascondi questo riquadro",
                       lambda: self.azioni[chiave].setChecked(False))
        menu.addAction("Ripristina disposizione", self.ripristina_predefinita)
        menu.exec(punto)

    # --------------------------------------------------------- disposizione
    @classmethod
    def chiave_layout(cls) -> str:
        if cls.versione_layout > 1:
            return f"layout_{cls.chiave_vista}_v{cls.versione_layout}"
        return f"layout_{cls.chiave_vista}"

    @classmethod
    def impostazioni_usate(cls) -> dict[str, set[str] | None]:
        """Le impostazioni che questa vista legge davvero, con i valori che
        accetta (`None` = qualsiasi).

        Serve a ripulire l'archivio: alzando `versione_layout`, o togliendo un
        riquadro, le vecchie righe resterebbero lì per sempre.
        """
        usate: dict[str, set[str] | None] = {cls.chiave_layout(): None}
        for sezione, (voci, _) in cls.PERIODI_SEZIONE.items():
            usate[f"periodo_{cls.chiave_vista}_{sezione}"] = set(voci)
        return usate

    def _chiave_layout(self) -> str:
        return self.chiave_layout()

    def _ripristina(self) -> None:
        stato = self.db.leggi(self._chiave_layout(), "")
        if not stato or not self.contenitore.ripristina_stato(stato):
            self.contenitore.applica_disposizione(self.DISPOSIZIONE)
            for chiave in self.NASCOSTE_PREDEFINITE:
                self.contenitore.mostra_sezione(chiave, False)
            # alla prima apertura le righe partono dalle proporzioni previste
            QTimer.singleShot(0, self._dimensioni_predefinite)
        for chiave, azione in self.azioni.items():
            sezione = self.contenitore.sezioni.get(chiave)
            if sezione is None:
                continue
            azione.blockSignals(True)
            azione.setChecked(not sezione.isHidden())
            azione.blockSignals(False)

    def _salva(self) -> None:
        if getattr(self, "_pronto", False):
            self.db.imposta(self._chiave_layout(), self.contenitore.stato())

    def _mostra(self, chiave: str, visibile: bool) -> None:
        self.contenitore.mostra_sezione(chiave, visibile)
        if visibile:
            self.aggiorna()

    def ripristina_predefinita(self) -> None:
        for chiave, azione in self.azioni.items():
            acceso = chiave not in self.NASCOSTE_PREDEFINITE
            azione.blockSignals(True); azione.setChecked(acceso)
            azione.blockSignals(False)
        for sezione in self.contenitore.sezioni.values():
            sezione.show()
        self.contenitore.applica_disposizione(self.DISPOSIZIONE)
        for chiave in self.NASCOSTE_PREDEFINITE:
            self.contenitore.mostra_sezione(chiave, False)
        QTimer.singleShot(0, self._dimensioni_predefinite)
        self.aggiorna()

    def _dimensioni_predefinite(self) -> None:
        altezza = max(430, self.contenitore.height())
        quote = self.ALTEZZE_PREDEFINITE or tuple(
            [1 / max(1, len(self.DISPOSIZIONE))] * len(self.DISPOSIZIONE))
        self.contenitore.verticale.setSizes([int(altezza * q) for q in quote])
        for i in range(self.contenitore.verticale.count()):
            r = self.contenitore.verticale.widget(i)
            if not r.count():
                continue
            larghe = (self.LARGHEZZE_PREDEFINITE[i]
                      if i < len(self.LARGHEZZE_PREDEFINITE) else ())
            if len(larghe) == r.count():
                r.setSizes([max(1, int(r.width() * q)) for q in larghe])
            else:
                r.setSizes([r.width() // r.count()] * r.count())
        self._salva()
