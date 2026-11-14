"""Riquadri interi, fatti per stare in più di una pagina.

In `componenti.py` ci sono i pezzi (un anello, una pastiglia, un
interruttore); qui ci sono i riquadri completi — tabella, comandi e lettura
dall'archivio insieme — che la Home e una pagina di area mostrano **uguali**.

Il motivo per cui esiste questo file: la stessa tabella delle attività era
stata scritta due volte, una in `views/cruscotto.py` e una in
`views/emozioni.py`, centotrenta righe l'una. Due copie della stessa cosa
divergono sempre: si corregge una colonna stretta di qua e resta stretta di
là. Qui ce n'è una sola, e chi la vuole se la prende.
"""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QHBoxLayout, QLabel, QMenu,
                               QMessageBox, QProgressBar, QPushButton,
                               QScrollArea, QSizePolicy, QVBoxLayout, QWidget)

from . import catalogo
from .componenti import AzioniRiga, SelezioneSemplice, etichetta
from .dialoghi import DialogoBase, DialogoScadenza
from .tema import colore_area, luminosita, trasparente
from .utils import data_it, relativa


class RigaAttivita(QWidget):
    """Una riga per un'attività: titolo, nota, tre opzioni di stato e barra.
    Identica a RigaMisura per dimensioni, margini e tipografia.
    """

    richiesta_stato = Signal(int, str)
    selezionata = Signal(int)
    doppio_clic = Signal(int)
    menu_richiesto = Signal(int, object)

    ALTEZZA_BARRA = 6

    STATI = (
        ("da_fare", "Da fare", 0),
        ("in_corso", "In corso", 50),
        ("completata", "Completata", 100),
    )

    def __init__(self, voce: dict, colori: dict, area: str = "emozioni", parent=None):
        super().__init__(parent)
        self.voce_id = int(voce["id"])
        self.c = colori
        self.area = area
        self._selezionata = False
        self.setObjectName("ContenutoSezione")
        self.setCursor(Qt.PointingHandCursor)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 2, 4, 3)
        lay.setSpacing(6)

        alto = QHBoxLayout()
        alto.setContentsMargins(0, 0, 0, 0)
        alto.setSpacing(8)

        sinistra = QVBoxLayout()
        sinistra.setContentsMargins(0, 0, 0, 0)
        sinistra.setSpacing(1)

        self.et_titolo = QLabel(voce["titolo"])
        self.et_titolo.setObjectName("TitoloRiga")

        oggi = date.today().isoformat()
        stato = voce.get("stato") or ("completata" if voce.get("fatta") else "da_fare")
        self._stato = stato

        # Senza data non è in ritardo: un «chiamare la terapeuta» senza
        # giorno fissato non è scaduto, è solo da fare. Il confronto
        # diretto direbbe di sì — una stringa vuota viene prima di
        # qualunque data — e la riga si colorerebbe di rosso per sempre.
        giorno = voce["data"] or ""
        scaduta = bool(giorno) and (stato != "completata") and (giorno <= oggi)
        colore_data = colore_area(self.area, luminosita(self.c["fondo"]) > 0.5) if scaduta else self.c["testo2"]
        testo_data = relativa(giorno) if giorno else "senza data"
        if voce.get("note"):
            testo_sotto = f"{testo_data} · {voce['note']}"
        else:
            testo_sotto = testo_data

        self.et_sotto = QLabel(testo_sotto)
        self.et_sotto.setObjectName("NotaScheda")
        if scaduta:
            self.et_sotto.setStyleSheet(f"color: {colore_data};")
        self.et_sotto.setToolTip(
            f"{data_it(giorno) if giorno else 'Nessuna data fissata'}\n"
            f"{voce.get('note', '')}".strip())

        for et in (self.et_titolo, self.et_sotto):
            et.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

        sinistra.addWidget(self.et_titolo)
        sinistra.addWidget(self.et_sotto)
        alto.addLayout(sinistra, 1)

        # Tre opzioni ben visibili nel widget (stile compatto e proporzionato)
        destra = QHBoxLayout()
        destra.setContentsMargins(0, 0, 0, 0)
        destra.setSpacing(2)
        destra.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.bottoni: dict[str, QPushButton] = {}

        for chiave, etichetta_b, _quota in self.STATI:
            b = QPushButton(etichetta_b)
            b.setCursor(Qt.PointingHandCursor)
            b.setFixedHeight(19)
            b.setFocusPolicy(Qt.NoFocus)
            b.clicked.connect(lambda _c=False, k=chiave: self.richiesta_stato.emit(self.voce_id, k))
            destra.addWidget(b)
            self.bottoni[chiave] = b

        alto.addLayout(destra, 0)
        lay.addLayout(alto)

        # Barra visiva come in Carriera (altezza 6px, raggio 5px)
        self.barra = QProgressBar()
        self.barra.setRange(0, 100)
        self.barra.setTextVisible(False)
        self.barra.setFixedHeight(self.ALTEZZA_BARRA)
        lay.addWidget(self.barra)

        self._aggiorna_visivo()

    def imposta_selezionata(self, sel: bool) -> None:
        self._selezionata = sel
        self._aggiorna_bordo()

    def _aggiorna_bordo(self) -> None:
        if self._selezionata:
            self.setStyleSheet(
                f"RigaAttivita {{ background: {trasparente(self.c['accento'], 0.16)};"
                " border-radius: 8px; }"
            )
        else:
            self.setStyleSheet(
                "RigaAttivita { background: transparent; border-radius: 8px; }"
                f"RigaAttivita:hover {{ background: {trasparente(self.c['accento'], 0.06)}; }}"
            )

    def _aggiorna_visivo(self) -> None:
        self._aggiorna_bordo()
        raggio = self.ALTEZZA_BARRA // 2 + 2
        for chiave, _testo, quota in self.STATI:
            b = self.bottoni[chiave]
            attivo = (chiave == self._stato)
            if chiave == "da_fare":
                colore = self.c["testo2"]
            elif chiave == "in_corso":
                colore = self.c["attenzione"]
            else:
                colore = self.c["entrata"]

            if attivo:
                b.setStyleSheet(
                    f"QPushButton {{ background: {trasparente(colore, 0.22)}; color: {colore};"
                    f" font-weight: 700; font-size: 9.5px; border: 1.2px solid {colore};"
                    f" border-radius: 9px; padding: 1px 6px; }}"
                )
                self.barra.setValue(quota)
                self.barra.setStyleSheet(
                    f"QProgressBar {{ background: {self.c['pannello2']}; border: none;"
                    f" border-radius: {raggio}px; }}"
                    f"QProgressBar::chunk {{ background: {colore}; border-radius: {raggio}px; }}"
                )
            else:
                b.setStyleSheet(
                    f"QPushButton {{ background: transparent; color: {trasparente(colore, 0.65)};"
                    f" font-weight: 500; font-size: 9.5px; border: 1px solid {trasparente(colore, 0.22)};"
                    f" border-radius: 9px; padding: 1px 6px; }}"
                    f"QPushButton:hover {{ background: {trasparente(colore, 0.12)}; color: {colore};"
                    f" border-color: {colore}; }}"
                )

    def mousePressEvent(self, ev) -> None:
        if ev.button() == Qt.LeftButton:
            self.selezionata.emit(self.voce_id)
        super().mousePressEvent(ev)

    def mouseDoubleClickEvent(self, ev) -> None:
        if ev.button() == Qt.LeftButton:
            self.doppio_clic.emit(self.voce_id)
        super().mouseDoubleClickEvent(ev)

    def contextMenuEvent(self, ev) -> None:
        self.menu_richiesto.emit(self.voce_id, ev.globalPos())


class RiquadroAttivita(QWidget):
    """Le cose da fare di una sola area: stile Carriera/Accademica con
    opzioni di stato ben visibili e barra visiva.
    """

    cambiato = Signal()

    def __init__(self, db, colori: dict, area: str = "emozioni",
                 cosa: str = "questo evento",
                 nuovo: str = "Nuovo evento", parent=None):
        super().__init__(parent)
        self.db = db
        self.c = colori
        self.area = area
        self._righe: dict[int, RigaAttivita] = {}
        self.setObjectName("ContenutoSezione")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.area_scorrimento = QScrollArea(self)
        self.area_scorrimento.setWidgetResizable(True)
        self.area_scorrimento.setFrameShape(QScrollArea.NoFrame)
        self.area_scorrimento.setObjectName("ContenutoSezione")
        self.area_scorrimento.viewport().setObjectName("ContenutoSezione")
        self.area_scorrimento.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.contenitore_righe = QWidget()
        self.contenitore_righe.setObjectName("ContenutoSezione")
        self.lay_righe = QVBoxLayout(self.contenitore_righe)
        self.lay_righe.setContentsMargins(0, 0, 0, 0)
        self.lay_righe.setSpacing(9)
        self.area_scorrimento.setWidget(self.contenitore_righe)
        lay.addWidget(self.area_scorrimento)

        # Selezione e comandi in testata
        self.selezione = SelezioneSemplice()
        self.azioni = AzioniRiga(colori, self.selezione, cosa, nuovo=nuovo)
        self.azioni.aggiunge.connect(self.nuova)
        self.azioni.modifica.connect(self.modifica)
        self.azioni.elimina.connect(self.elimina)

    def aggiorna_tema(self, colori: dict) -> None:
        self.c = colori
        self.azioni.aggiorna_tema(colori)
        self.aggiorna()

    def _scelta(self) -> int | None:
        return self.selezione.scelto()

    def _scegli_riga(self, id_: int) -> None:
        self.selezione.scegli(id_)
        for rid, r in self._righe.items():
            r.imposta_selezionata(rid == id_)

    def _voce(self, id_: int):
        return self.db.uno("SELECT * FROM scadenze WHERE id=?", (id_,))

    def nuova(self) -> None:
        dialogo = DialogoScadenza(area=self.area, parent=self, area_fissa=True)
        if dialogo.exec():
            self.db.salva_scadenza(dialogo.dati())
            self.cambiato.emit()

    def modifica(self) -> None:
        id_ = self._scelta()
        if id_ is None:
            return self.nuova()
        voce = self._voce(id_)
        if voce is None:
            return
        dialogo = DialogoScadenza(voce, parent=self, area_fissa=True)
        if dialogo.exec():
            self.db.salva_scadenza(dialogo.dati())
            self.cambiato.emit()

    def elimina(self) -> None:
        id_ = self._scelta()
        if id_ is None:
            return
        voce = self._voce(id_)
        if voce is None:
            return
        if QMessageBox.question(
                self, "Elimina",
                f"Elimino «{voce['titolo']}»?") != QMessageBox.Yes:
            return
        self.db.elimina("scadenze", id_)
        self.selezione.scegli(None)
        self.cambiato.emit()

    def segna_stato(self, id_: int, stato: str) -> None:
        fatta = 1 if stato == "completata" else 0
        self.db.esegui("UPDATE scadenze SET stato=?, fatta=? WHERE id=?",
                       (stato, fatta, id_))
        self.cambiato.emit()

    def _apri_menu_riga(self, id_: int, punto) -> None:
        self._scegli_riga(id_)
        voce = self._voce(id_)
        if voce is None:
            return
        menu = QMenu(self)
        menu.addAction("Nuovo evento", self.nuova)
        menu.addSeparator()
        menu.addAction("Modifica", self.modifica)
        menu.addSeparator()
        menu.addAction("Segna come Da fare", lambda: self.segna_stato(id_, "da_fare"))
        menu.addAction("Segna come In corso", lambda: self.segna_stato(id_, "in_corso"))
        menu.addAction("Segna come Completata", lambda: self.segna_stato(id_, "completata"))
        menu.addSeparator()
        menu.addAction("Elimina", self.elimina)
        menu.exec(punto)

    def aggiorna(self) -> tuple[int, int]:
        while self.lay_righe.count():
            item = self.lay_righe.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._righe.clear()
        self.selezione.scegli(None)

        # chi ha una data viene prima di chi non ce l'ha: `data=''` vale 1 e
        # va in fondo, se no le cose senza giorno — che non scadono mai —
        # starebbero in cima a quelle di domani
        voci = [dict(v) for v in self.db.query(
            "SELECT * FROM scadenze WHERE area=? ORDER BY "
            "(CASE stato WHEN 'in_corso' THEN 1 WHEN 'da_fare' THEN 2 ELSE 3 END), "
            "(data IS NULL OR data=''), data LIMIT 60",
            (self.area,))]

        if not voci:
            et = etichetta("Nessun impegno in programma.", "NotaScheda")
            self.lay_righe.addWidget(et)

        for d_voce in voci:
            r = RigaAttivita(d_voce, self.c, self.area, parent=self.contenitore_righe)
            r.richiesta_stato.connect(self.segna_stato)
            r.selezionata.connect(self._scegli_riga)
            r.doppio_clic.connect(lambda _id: self.modifica())
            r.menu_richiesto.connect(self._apri_menu_riga)
            self._righe[d_voce["id"]] = r
            self.lay_righe.addWidget(r)

        self.lay_righe.addStretch(1)
        self.azioni.rivedi()

        aperte = sum(1 for v in voci if (v.get("stato") != "completata" and not v.get("fatta")))
        svolte = len(voci) - aperte
        return aperte, svolte

    def nota(self) -> str:
        aperte, svolte = self.aggiorna()
        voci = [dict(v) for v in self.db.query("SELECT stato, fatta FROM scadenze WHERE area=?", (self.area,))]
        in_corso = sum(1 for v in voci if v.get("stato") == "in_corso")
        da_fare = sum(1 for v in voci if (v.get("stato") == "da_fare" or (not v.get("stato") and not v.get("fatta"))))
        pezzi = []
        if in_corso:
            pezzi.append(f"{in_corso} in corso")
        if da_fare:
            pezzi.append(f"{da_fare} da fare")
        pezzi.append(f"{svolte} svolte")
        return " · ".join(pezzi) if pezzi else "nessun impegno"


class SceltaRiquadri(DialogoBase):
    """Quali riquadri delle altre pagine mostrare in Home.

    Non duplica niente: ogni voce è il riquadro vero di quella pagina —
    stesso grafico, stessa tabella, stessi comandi — mostrato anche qui.
    Toglierlo dalla Home non lo toglie dalla sua pagina.

    I nomi arrivano da `catalogo`, che li legge dalla classe della vista
    senza costruirla: aprire questa finestra non accende nessuna pagina.
    """

    def __init__(self, scelti: set[str], parent=None):
        super().__init__("Riquadri dalle altre pagine", parent, larghezza=560,
                         nota="Spunta quelli che vuoi vedere anche in Home. "
                              "Restano dove sono: qui se ne mostra una copia "
                              "viva, non un duplicato.")
        self.caselle: dict[str, QCheckBox] = {}

        dentro = QWidget()
        dentro.setObjectName("ContenutoSezione")
        colonna = QVBoxLayout(dentro)
        colonna.setContentsMargins(2, 2, 10, 2)
        colonna.setSpacing(14)
        for pagina in catalogo.PAGINE:
            titolo = QLabel(catalogo.titolo(pagina))
            titolo.setObjectName("EtichettaScheda")
            colonna.addWidget(titolo)
            for riquadro, nome in catalogo.riquadri(pagina).items():
                chiave = catalogo.chiave_prestito(pagina, riquadro)
                casella = QCheckBox(nome.capitalize() if nome.isupper() else nome)
                casella.setChecked(chiave in scelti)
                colonna.addWidget(casella)
                self.caselle[chiave] = casella
        colonna.addStretch(1)

        area = QScrollArea()
        area.setObjectName("ContenutoSezione")
        area.viewport().setObjectName("ContenutoSezione")
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.NoFrame)
        area.setWidget(dentro)
        area.setMinimumHeight(380)
        # sotto la scheda dei campi, che qui resta vuota: le voci sono tante
        # e vogliono scorrere, non stare in un modulo
        self.scheda.hide()
        self.corpo.insertWidget(self.corpo.count() - 1, area, 1)
        self.b_salva.setText("Applica")

    def scelti(self) -> set[str]:
        return {c for c, casella in self.caselle.items() if casella.isChecked()}
