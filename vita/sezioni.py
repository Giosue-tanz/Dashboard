"""Sezioni trascinabili per i pannelli configurabili.

Ogni sezione è una scheda con una maniglia in alto: si prende e si porta dove
serve, anche in una riga nuova. Il contenitore gestisce righe e colonne con
divisori ridimensionabili e sa salvare e ricaricare l'intera disposizione.
"""
from __future__ import annotations

import json

from PySide6.QtCore import QEvent, QMimeData, QPoint, QRect, Qt, Signal
from PySide6.QtGui import QDrag, QFont, QFontMetrics, QPainter, QPixmap
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPushButton,
                               QSizePolicy, QSplitter, QVBoxLayout, QWidget)

MIME = "application/x-vita-sezione"
BORDO_RIGA = 18          # zona in cui il rilascio crea una riga nuova
LARGHEZZA_MINIMA = 150
LARGHEZZA_LIBERA = 16777215   # il massimo di Qt: «nessun limite»
FRECCIA_GIU = "\u25be"        # la punta che dice «qui si sceglie»
ALTEZZA_MINIMA = 108


class Intestazione(QWidget):
    """Barra pulita: titolo, periodo come testo discreto, comandi al passaggio.

    Tutta la barra è l'area di trascinamento, così non serve una maniglia fissa:
    gli unici elementi sempre visibili sono il titolo e il periodo.
    """

    chiusura_richiesta = Signal()
    periodo_richiesto = Signal(QPoint)
    menu_richiesto = Signal(QPoint)
    # «qui non ci sta»: il comando va rimesso sotto il titolo
    comando_fuori = Signal(bool)

    ALTEZZA_MINIMA = 24

    def __init__(self, titolo: str, stile: str = "Sezione", parent=None):
        super().__init__(parent)
        self.setCursor(Qt.OpenHandCursor)
        self.setFixedHeight(self.ALTEZZA_MINIMA)
        self._titolo_pieno = titolo
        self._nota_piena = ""
        self._periodo_pieno = ""
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        self.titolo = QLabel(titolo)
        self.titolo.setObjectName(stile)
        # la nota grigia: quello che il riquadro racconta di sé
        self.nota = QLabel("")
        self.nota.setObjectName("Periodo")
        self.nota.hide()
        # il periodo invece è un comando, e si vede che lo è: pastiglia a
        # destra, con la freccia. Prima era una scritta grigia come le altre,
        # in mezzo ai numeri, e nessuno capiva che ci si poteva cliccare.
        self.periodo = QPushButton("")
        self.periodo.setObjectName("Periodo")
        self.periodo.setCursor(Qt.PointingHandCursor)
        self.periodo.setFocusPolicy(Qt.NoFocus)
        self.periodo.setToolTip("Cambia il periodo mostrato")
        self.periodo.clicked.connect(
            lambda: self.periodo_richiesto.emit(
                self.periodo.mapToGlobal(QPoint(0, self.periodo.height() + 2))))
        self.periodo.hide()
        # I «⋯» non ci sono più. Erano tre puntini che comparivano al
        # passaggio del mouse e aprivano lo stesso menu del tasto destro: una
        # seconda strada per la stessa cosa, che rubava posto al comando del
        # riquadro — e il posto sulla riga del titolo è quello che serve al
        # navigatore dei periodi. Il menu resta sul tasto destro, e nascondere
        # i riquadri si fa dal pulsante «Riquadri» in testa alla pagina.

        lay.addWidget(self.titolo)
        lay.addWidget(self.nota)
        lay.addStretch(1)
        lay.addWidget(self.periodo)
        self.lay = lay
        # il comando del riquadro (il navigatore dei periodi), se ce l'ha:
        # sta qui sulla riga del titolo, e sono pixel che restano al grafico
        self.comando: QWidget | None = None
        self._comando_dentro = True
        self._sta_sistemando = False
        self._premuto: QPoint | None = None
        self._adatta_altezza()

    # -------------------------------------------------------------- comando
    def imposta_comando(self, widget: QWidget) -> None:
        """Mette un comando in fondo alla riga del titolo."""
        self.comando = widget
        self.aggancia_comando()

    def aggancia_comando(self) -> None:
        """(Ri)mette il comando nella barra, prima del periodo e dei «⋯»."""
        if self.comando is None:
            return
        self.lay.insertWidget(self.lay.indexOf(self.periodo), self.comando)
        self.comando.show()
        self._comando_dentro = True
        self._adatta_altezza()
        self._accorcia()

    def _spazio_comando(self) -> tuple[int, int]:
        """Quanto chiede il comando: (il minimo, il massimo)."""
        if self.comando is None:
            return 0, 0
        if hasattr(self.comando, "larghezza_necessaria"):
            return (self.comando.larghezza_necessaria(),
                    self.comando.spazio_massimo())
        largo = self.comando.sizeHint().width()
        return largo, largo

    # -------------------------------------------------------------- aspetto
    def _adatta_altezza(self) -> None:
        """L'altezza segue il carattere, non un numero fisso.

        Con il testo molto grande una barra alta 24 px tagliava le code delle
        lettere: la «g» di «Oggi», di «Progetti», di «Prossimi impegni».
        """
        pezzi = [self.titolo, self.nota, self.periodo]
        if self.comando is not None and self._comando_dentro:
            pezzi.append(self.comando)
        for widget in pezzi:
            widget.ensurePolished()
        alto = max(w.sizeHint().height() for w in pezzi)
        self.setFixedHeight(max(self.ALTEZZA_MINIMA, alto + 2))

    def _accorcia(self) -> None:
        """Divide lo spazio della barra: prima il titolo, poi il periodo, poi la nota.

        L'ordine è quello che conta: il titolo dice di che riquadro si tratta,
        il periodo è un comando e deve restare cliccabile, la nota è il
        racconto e può accorciarsi. Le misure si chiedono ai widget, non al
        carattere: il grassetto del foglio di stile occupa più di quanto dica
        la metrica, e il titolo finirebbe tagliato.
        """
        if self._sta_sistemando:
            # spostare il comando rimette in moto il layout: una volta sola
            return
        self._sta_sistemando = True
        try:
            self._sistema()
        finally:
            self._sta_sistemando = False

    def _sistema(self) -> None:
        spazio = max(0, self.width() - 8)
        for widget in (self.titolo, self.nota):
            widget.setMinimumWidth(0)
            widget.setMaximumWidth(LARGHEZZA_LIBERA)

        largo_titolo = self._misura(self.titolo, self._titolo_pieno)
        if largo_titolo > spazio:
            # non ci sta nemmeno il titolo: si accorcia lui, coi puntini
            testo = self.titolo.fontMetrics().elidedText(
                self._titolo_pieno, Qt.ElideRight, spazio)
            while len(testo) > 2 and self._misura(self.titolo, testo) > spazio:
                testo = testo[:-2] + "…"
            self.titolo.setFixedWidth(spazio)
            self.titolo.setToolTip(self._titolo_pieno)
            self.nota.setVisible(False)
            self.periodo.setVisible(False)
            self._posto_al_comando(0)
            return
        self.titolo.setToolTip("")
        # larghezza fissa: così nota e periodo non gli rubano spazio dal layout
        self.titolo.setFixedWidth(largo_titolo)
        resto = spazio - largo_titolo - 12
        # il comando viene prima della nota: la nota racconta, il comando si usa
        resto = self._posto_al_comando(resto)

        # la pastiglia del periodo, se questo riquadro ne ha uno
        if self._periodo_pieno:
            self.periodo.setText(f"{self._periodo_pieno}  {FRECCIA_GIU}")
            largo_periodo = self.periodo.sizeHint().width()
            self.periodo.setVisible(resto >= largo_periodo)
            if self.periodo.isVisible():
                resto -= largo_periodo + 10
        else:
            self.periodo.setVisible(False)

        if not self._nota_piena:
            self.nota.setVisible(False)
            return
        intera = self._misura(self.nota, self._nota_piena)
        # o ci sta tutta, o ne resta abbastanza da dire qualcosa: un moncone
        # come «6/28 centr…» non serve a nessuno, meglio niente. Dove c'è
        # anche un comando la nota la si vuole intera o niente: accanto a una
        # pastiglia un troncone è solo disordine
        intera_o_niente = self.comando is not None and self._comando_dentro
        if resto < (intera if intera_o_niente else min(intera, 70)):
            self.nota.setVisible(False)
            # non è persa: dove il comando le ha preso il posto, la nota si
            # legge passando sul titolo
            self.titolo.setToolTip(self._nota_piena)
            return
        self.nota.setVisible(True)
        testo = self.nota.fontMetrics().elidedText(
            self._nota_piena, Qt.ElideRight, resto)
        while len(testo) > 2 and self._misura(self.nota, testo) > resto:
            testo = testo[:-2] + "…"
        self.nota.setFixedWidth(min(resto, self.nota.sizeHint().width()))
        self.nota.setToolTip(self._nota_piena)

    def _posto_al_comando(self, resto: int) -> int:
        """Il comando ci sta accanto al titolo? Se no lo si manda sotto.

        La misura non dipende da dove sta adesso il comando — è sempre la
        larghezza che chiede — quindi la decisione non può oscillare fra una
        sistemata e l'altra.
        """
        if self.comando is None:
            return resto
        serve, pieno = self._spazio_comando()
        dentro = resto >= serve
        if dentro != self._comando_dentro:
            self._comando_dentro = dentro
            self.comando_fuori.emit(not dentro)
        if not dentro:
            return resto
        if hasattr(self.comando, "adatta_a"):
            self.comando.adatta_a(resto)
        # si riserva il massimo solo dove il massimo ci sta: così la nota non
        # si prende lo spazio che fra una scorsa e l'altra servirà a «Oggi»
        return resto - (pieno if resto >= pieno else serve) - 10

    def _misura(self, etichetta: QLabel, testo: str) -> int:
        """Scrive il testo e torna quanto spazio chiede davvero."""
        etichetta.setText(testo)
        return etichetta.sizeHint().width()

    def imposta_titolo(self, testo: str) -> None:
        self._titolo_pieno = testo
        self._accorcia()

    def imposta_nota(self, testo: str) -> None:
        """Il racconto grigio accanto al titolo."""
        self._nota_piena = testo
        self._accorcia()

    def imposta_periodo(self, testo: str) -> None:
        """Il periodo mostrato: diventa la pastiglia a destra."""
        self._periodo_pieno = testo
        self._accorcia()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._accorcia()

    def changeEvent(self, ev):
        super().changeEvent(ev)
        # il foglio di stile cambia (tema, dimensione del testo): rimisuro
        if ev.type() in (QEvent.StyleChange, QEvent.FontChange,
                         QEvent.ApplicationFontChange):
            self._adatta_altezza()
            self._accorcia()

    # ---------------------------------------------------------- interazione
    def _dentro(self, widget: QLabel, punto: QPoint) -> bool:
        return widget.isVisible() and widget.geometry().adjusted(
            -4, -6, 4, 6).contains(punto)

    def mousePressEvent(self, ev):
        punto = ev.position().toPoint()
        if ev.button() == Qt.RightButton:
            self.menu_richiesto.emit(self.mapToGlobal(punto))
            return
        if ev.button() != Qt.LeftButton:
            return
        if self._dentro(self.periodo, punto):
            self.periodo_richiesto.emit(
                self.periodo.mapToGlobal(QPoint(0, self.periodo.height())))
            return
        self._premuto = punto
        self.setCursor(Qt.ClosedHandCursor)

    def mouseReleaseEvent(self, _):
        self._premuto = None
        self.setCursor(Qt.OpenHandCursor)

    def mouseMoveEvent(self, ev):
        if self._premuto is None:
            return
        if (ev.position().toPoint() - self._premuto).manhattanLength() < 12:
            return
        sezione = self.parent()
        while sezione is not None and not isinstance(sezione, Sezione):
            sezione = sezione.parent()
        if sezione is None:
            return
        self._premuto = None
        self.setCursor(Qt.OpenHandCursor)

        dati = QMimeData()
        dati.setData(MIME, sezione.chiave.encode())
        trascina = QDrag(self)
        trascina.setMimeData(dati)
        anteprima = sezione.grab().scaledToWidth(
            min(320, sezione.width()), Qt.SmoothTransformation)
        ombra = QPixmap(anteprima.size())
        ombra.fill(Qt.transparent)
        pittore = QPainter(ombra)
        pittore.setOpacity(0.85)
        pittore.drawPixmap(0, 0, anteprima)
        pittore.end()
        trascina.setPixmap(ombra)
        trascina.setHotSpot(QPoint(40, 14))
        trascina.exec(Qt.MoveAction)


class Sezione(QFrame):
    """Scheda spostabile: intestazione trascinabile più contenuto."""

    chiusura_richiesta = Signal(str)
    periodo_richiesto = Signal(str, QPoint)
    menu_richiesto = Signal(str, QPoint)

    def __init__(self, chiave: str, titolo: str, contenuto: QWidget,
                 stile_titolo: str = "Sezione", comando: QWidget | None = None,
                 parent=None):
        super().__init__(parent)
        self.setObjectName("Scheda")
        self.chiave = chiave
        self.contenuto = contenuto
        self.setMinimumSize(LARGHEZZA_MINIMA, ALTEZZA_MINIMA)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 12)
        lay.setSpacing(8)
        self.intestazione = Intestazione(titolo, stile_titolo, self)
        self.intestazione.chiusura_richiesta.connect(
            lambda: self.chiusura_richiesta.emit(self.chiave))
        self.intestazione.periodo_richiesto.connect(
            lambda punto: self.periodo_richiesto.emit(self.chiave, punto))
        self.intestazione.menu_richiesto.connect(
            lambda punto: self.menu_richiesto.emit(self.chiave, punto))
        lay.addWidget(self.intestazione)

        # il posto di ripiego del comando: quando il riquadro è così stretto
        # che accanto al titolo non ci sta, torna qui sotto invece di tagliarsi
        self.riga_comando = QWidget(self)
        self.riga_comando.setObjectName("ContenutoSezione")
        ripiego = QHBoxLayout(self.riga_comando)
        ripiego.setContentsMargins(0, 0, 0, 0)
        ripiego.addStretch(1)
        self.riga_comando.hide()
        lay.addWidget(self.riga_comando)
        lay.addWidget(contenuto, 1)

        self.comando = comando
        if comando is not None:
            self.intestazione.comando_fuori.connect(self._sposta_comando)
            self.intestazione.imposta_comando(comando)

    # --------------------------------------------------------- il comando
    def _sposta_comando(self, fuori: bool) -> None:
        """Lo porta sotto il titolo, o se lo riprende quando torna il posto."""
        if self.comando is None:
            return
        if fuori:
            self.riga_comando.layout().addWidget(self.comando)
            self.riga_comando.show()
            self.intestazione._adatta_altezza()
        else:
            self.riga_comando.hide()
            self.intestazione.aggancia_comando()

    def imposta_nota(self, testo: str) -> None:
        self.intestazione.imposta_nota(testo)

    def imposta_periodo(self, testo: str) -> None:
        self.intestazione.imposta_periodo(testo)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        # i titoli restano tutti della stessa misura: la dà il foglio di stile
        if hasattr(self.contenuto, "adatta_dimensioni"):
            self.contenuto.adatta_dimensioni(self.contenuto.size())


class Indicatore(QFrame):
    """Linea luminosa che mostra dove finirà la sezione trascinata."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("IndicatoreRilascio")
        self.hide()

    def mostra(self, rettangolo: QRect) -> None:
        self.setGeometry(rettangolo)
        self.show()
        self.raise_()


class ContenitoreSezioni(QWidget):
    """Righe di sezioni affiancate, tutte ridimensionabili e riordinabili."""

    disposizione_cambiata = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.sezioni: dict[str, Sezione] = {}
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.verticale = QSplitter(Qt.Vertical)
        self.verticale.setHandleWidth(8)
        self.verticale.setChildrenCollapsible(True)
        self.verticale.splitterMoved.connect(
            lambda *_: self.disposizione_cambiata.emit())
        lay.addWidget(self.verticale)
        self.indicatore = Indicatore(self)

    # ------------------------------------------------------------ costruzione
    def registra(self, sezione: Sezione) -> None:
        self.sezioni[sezione.chiave] = sezione

    def _nuova_riga(self, indice: int = -1) -> QSplitter:
        riga = QSplitter(Qt.Horizontal)
        riga.setHandleWidth(8)
        riga.setChildrenCollapsible(True)
        riga.splitterMoved.connect(lambda *_: self.disposizione_cambiata.emit())
        if indice < 0 or indice >= self.verticale.count():
            self.verticale.addWidget(riga)
        else:
            self.verticale.insertWidget(indice, riga)
        return riga

    def applica_disposizione(self, righe: list[list[str]]) -> None:
        """Ricostruisce la griglia a partire dall'elenco di righe di chiavi."""
        for s in self.sezioni.values():
            s.hide()
            s.setParent(None)
        while self.verticale.count():
            vecchia = self.verticale.widget(0)
            vecchia.hide()
            vecchia.setParent(None)
            vecchia.deleteLater()

        for chiavi in righe:
            presenti = [k for k in chiavi if k in self.sezioni]
            if not presenti:
                continue
            riga = self._nuova_riga()
            for k in presenti:
                riga.addWidget(self.sezioni[k])
                self.sezioni[k].show()
        self._pulisci()

    def disposizione(self) -> list[list[str]]:
        righe = []
        for i in range(self.verticale.count()):
            riga = self.verticale.widget(i)
            if not isinstance(riga, QSplitter):
                continue
            chiavi = [riga.widget(j).chiave for j in range(riga.count())
                      if isinstance(riga.widget(j), Sezione)]
            if chiavi:
                righe.append(chiavi)
        return righe

    def stato(self) -> str:
        """Disposizione e dimensioni, pronte per essere salvate."""
        dati = {
            "righe": self.disposizione(),
            "verticale": self.verticale.sizes(),
            "orizzontali": [self.verticale.widget(i).sizes()
                            for i in range(self.verticale.count())
                            if isinstance(self.verticale.widget(i), QSplitter)],
            "nascoste": [k for k, s in self.sezioni.items() if s.isHidden()],
        }
        return json.dumps(dati)

    def ripristina_stato(self, testo: str) -> bool:
        try:
            dati = json.loads(testo)
            righe = [list(map(str, r)) for r in dati["righe"]]
        except Exception:
            return False
        note = {k for r in righe for k in r}
        mancanti = [k for k in self.sezioni if k not in note]
        if mancanti:
            righe.append(mancanti)
        self.applica_disposizione(righe)
        for k in dati.get("nascoste", []):
            if k in self.sezioni:
                self.sezioni[k].hide()
        self._pulisci()
        if dati.get("verticale"):
            self.verticale.setSizes(dati["verticale"])
        for i, dimensioni in enumerate(dati.get("orizzontali", [])):
            if i < self.verticale.count() and isinstance(self.verticale.widget(i), QSplitter):
                self.verticale.widget(i).setSizes(dimensioni)
        return True

    # --------------------------------------------------------------- rilascio
    def _righe(self) -> list[QSplitter]:
        return [self.verticale.widget(i) for i in range(self.verticale.count())
                if isinstance(self.verticale.widget(i), QSplitter)
                and not self.verticale.widget(i).isHidden()]

    def _bersaglio(self, punto: QPoint):
        """Dove finirebbe il rilascio: (riga, indice, crea_nuova_riga)."""
        righe = self._righe()
        if not righe:
            return None, 0, True
        for riga in righe:
            alto = riga.mapTo(self, QPoint(0, 0)).y()
            basso = alto + riga.height()
            if punto.y() < alto:
                return riga, 0, True
            if alto <= punto.y() <= basso:
                if punto.y() - alto < BORDO_RIGA:
                    return riga, 0, True
                if basso - punto.y() < BORDO_RIGA:
                    return riga, 1, True
                indice = riga.count()
                for j in range(riga.count()):
                    w = riga.widget(j)
                    if w.isHidden():
                        continue
                    centro = w.mapTo(self, QPoint(w.width() // 2, 0)).x()
                    if punto.x() < centro:
                        indice = j
                        break
                return riga, indice, False
        return righe[-1], 1, True

    def dragEnterEvent(self, ev):
        if ev.mimeData().hasFormat(MIME):
            ev.acceptProposedAction()

    def dragMoveEvent(self, ev):
        if not ev.mimeData().hasFormat(MIME):
            return
        ev.acceptProposedAction()
        riga, indice, nuova = self._bersaglio(ev.position().toPoint())
        if riga is None:
            self.indicatore.hide()
            return
        if nuova:
            y = riga.mapTo(self, QPoint(0, 0)).y()
            y = y - 4 if indice == 0 else y + riga.height() - 2
            self.indicatore.mostra(QRect(2, y, self.width() - 4, 5))
        else:
            if indice >= riga.count():
                ultimo = riga.widget(riga.count() - 1)
                x = ultimo.mapTo(self, QPoint(ultimo.width(), 0)).x()
            else:
                w = riga.widget(indice)
                x = w.mapTo(self, QPoint(0, 0)).x()
            y = riga.mapTo(self, QPoint(0, 0)).y()
            self.indicatore.mostra(QRect(x - 2, y + 2, 5, riga.height() - 4))

    def dragLeaveEvent(self, _):
        self.indicatore.hide()

    def dropEvent(self, ev):
        self.indicatore.hide()
        if not ev.mimeData().hasFormat(MIME):
            return
        chiave = bytes(ev.mimeData().data(MIME)).decode()
        sezione = self.sezioni.get(chiave)
        if sezione is None:
            return
        riga, indice, nuova = self._bersaglio(ev.position().toPoint())
        ev.acceptProposedAction()

        if nuova:
            posizione = self.verticale.indexOf(riga) + (0 if indice == 0 else 1) \
                if riga is not None else -1
            destinazione = self._nuova_riga(posizione)
            destinazione.addWidget(sezione)
        else:
            if riga.indexOf(sezione) == indice:
                return
            riga.insertWidget(indice, sezione)
        sezione.show()
        self._pulisci()
        self._distribuisci(riga if not nuova else None)
        self.disposizione_cambiata.emit()

    # --------------------------------------------------------------- utilità
    def _pulisci(self) -> None:
        """Elimina le righe rimaste senza sezioni."""
        for i in reversed(range(self.verticale.count())):
            w = self.verticale.widget(i)
            if isinstance(w, QSplitter) and w.count() == 0:
                w.hide()
                w.setParent(None)
                w.deleteLater()
            elif isinstance(w, QSplitter):
                w.setVisible(any(not w.widget(j).isHidden() for j in range(w.count())))

    def _distribuisci(self, riga: QSplitter | None) -> None:
        """Riparte lo spazio in modo che nessuna sezione resti a dimensione zero."""
        righe = [riga] if riga is not None else self._righe()
        for r in righe:
            if r is None or r.count() == 0:
                continue
            visibili = [j for j in range(r.count()) if not r.widget(j).isHidden()]
            if not visibili:
                continue
            quota = max(LARGHEZZA_MINIMA, r.width() // len(visibili))
            r.setSizes([quota if j in visibili else 0 for j in range(r.count())])
        altezze = self.verticale.sizes()
        if altezze and min(altezze) < ALTEZZA_MINIMA:
            totale = sum(altezze) or self.height()
            self.verticale.setSizes([max(ALTEZZA_MINIMA, totale // max(1, len(altezze)))
                                     for _ in altezze])

    def mostra_sezione(self, chiave: str, visibile: bool) -> None:
        sezione = self.sezioni.get(chiave)
        if sezione is None:
            return
        sezione.setVisible(visibile)
        self._pulisci()
        if visibile:
            riga = sezione.parent()
            while riga is not None and not isinstance(riga, QSplitter):
                riga = riga.parent()
            self._distribuisci(riga if riga is not self.verticale else None)
        self.disposizione_cambiata.emit()
