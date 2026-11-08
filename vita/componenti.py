"""Componenti riutilizzabili dell'interfaccia."""
from __future__ import annotations

from PySide6.QtCore import (QDate, QEasingCurve, QEvent, QModelIndex, QObject,
                            QPoint, QPointF, QRect, QRectF, QSize, Qt,
                            QVariantAnimation, Signal)
from PySide6.QtGui import (QColor, QFont, QFontMetrics, QKeySequence, QPainter,
                           QPainterPath, QPen, QShortcut)
from PySide6.QtWidgets import (QCheckBox, QDateEdit, QFrame, QHBoxLayout, QLabel,
                               QMenu,
                               QLayout, QProgressBar, QPushButton, QSizePolicy,
                               QSlider, QSpinBox, QVBoxLayout, QWidget)

from .grafici import Anello, Sparkline
from .tema import scurisci, su_colore as su_tinta, trasparente
from .utils import (MODI_PERIODO, QUANTI_PREDEFINITI, data_it, intervalli,
                    media, nome_intervallo, numero, ultimi_giorni)

FACCE = ["😖", "😣", "😕", "😐", "🙂", "😊", "😄", "🤩"]


def faccia(valore: float) -> str:
    """Il volto che corrisponde a un umore da 1 a 10."""
    indice = int(max(1.0, min(10.0, valore)) - 1) * len(FACCE) // 10
    return FACCE[min(len(FACCE) - 1, indice)]


# --------------------------------------------------------------- contenitori
class Scheda(QFrame):
    """Pannello arrotondato con titolo opzionale."""

    def __init__(self, titolo: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("Scheda")
        self.layout_v = QVBoxLayout(self)
        self.layout_v.setContentsMargins(16, 14, 16, 14)
        self.layout_v.setSpacing(10)
        if titolo:
            et = QLabel(titolo)
            et.setObjectName("Sezione")
            self.layout_v.addWidget(et)
            self.etichetta_titolo = et

    def aggiungi(self, widget: QWidget, stiramento: int = 0) -> QWidget:
        self.layout_v.addWidget(widget, stiramento)
        return widget

    def aggiungi_layout(self, layout) -> None:
        self.layout_v.addLayout(layout)


class EtichettaAlta(QLabel):
    """Etichetta che non si lascia schiacciare sotto la propria riga.

    I numeri grandi («74,1 kg», «7h») stanno in riquadri che possono farsi
    bassi: senza un minimo legato al carattere, con il testo molto grande la
    cifra veniva tagliata a metà. Il minimo si rifà da sé quando cambia il
    foglio di stile, cioè quando si cambia tema o dimensione del testo.
    """

    def _adatta(self) -> None:
        self.ensurePolished()
        self.setMinimumHeight(self.sizeHint().height())

    def showEvent(self, ev):
        super().showEvent(ev)
        self._adatta()

    def changeEvent(self, ev):
        super().changeEvent(ev)
        if ev.type() in (QEvent.StyleChange, QEvent.FontChange,
                         QEvent.ApplicationFontChange):
            self._adatta()


class EtichettaACapo(QLabel):
    """Etichetta che va a capo e si prende per davvero le righe che le servono.

    Un `QLabel` con `wordWrap` dentro un layout verticale chiede l'altezza di
    una riga sola e il resto lo nasconde: l'altezza giusta dipende dalla
    larghezza, e la larghezza si sa solo dopo. Qui si rimisura a ogni
    ridimensionamento.
    """

    def __init__(self, testo: str = "", parent=None):
        super().__init__(testo, parent)
        self.setWordWrap(True)

    def _adatta(self) -> None:
        if self.width() > 0:
            self.setMinimumHeight(self.heightForWidth(self.width()))

    def setText(self, testo: str) -> None:
        super().setText(testo)
        self._adatta()

    def showEvent(self, ev):
        super().showEvent(ev)
        self._adatta()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._adatta()


class DisposizioneFluida(QLayout):
    """Righe che vanno a capo da sole: serve alle etichette delle emozioni."""

    def __init__(self, parent=None, margine: int = 0, spaziatura: int = 6):
        super().__init__(parent)
        self.setContentsMargins(margine, margine, margine, margine)
        self._spazio = spaziatura
        self._voci: list = []

    def addItem(self, item):
        self._voci.append(item)

    def count(self):
        return len(self._voci)

    def itemAt(self, indice):
        return self._voci[indice] if 0 <= indice < len(self._voci) else None

    def takeAt(self, indice):
        return self._voci.pop(indice) if 0 <= indice < len(self._voci) else None

    def expandingDirections(self):
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, larghezza):
        return self._disponi(QRect(0, 0, larghezza, 0), prova=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._disponi(rect, prova=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        dimensione = QSize()
        for voce in self._voci:
            dimensione = dimensione.expandedTo(voce.minimumSize())
        m = self.contentsMargins()
        return dimensione + QSize(m.left() + m.right(), m.top() + m.bottom())

    def _disponi(self, rect: QRect, prova: bool) -> int:
        m = self.contentsMargins()
        area = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y, altezza_riga = area.x(), area.y(), 0
        for voce in self._voci:
            dimensione = voce.sizeHint()
            prossimo = x + dimensione.width() + self._spazio
            if prossimo - self._spazio > area.right() and altezza_riga > 0:
                x = area.x()
                y += altezza_riga + self._spazio
                prossimo = x + dimensione.width() + self._spazio
                altezza_riga = 0
            if not prova:
                voce.setGeometry(QRect(QPoint(x, y), dimensione))
            x = prossimo
            altezza_riga = max(altezza_riga, dimensione.height())
        return y + altezza_riga - rect.y() + m.bottom()


# ------------------------------------------------------------------- schede
class ContenutoStat(QWidget):
    """Valore grande, nota e sparkline: i testi si adattano allo spazio."""

    def __init__(self, colori: dict, colore_valore: str | None = None, parent=None):
        super().__init__(parent)
        self.c = colori
        self.setObjectName("ContenutoSezione")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)
        self.colore_valore = colore_valore or colori["testo"]
        self.valore = QLabel("—")
        self.valore.setObjectName("ValoreScheda")
        self.nota = QLabel("")
        self.nota.setObjectName("NotaScheda")
        self.nota.setWordWrap(True)
        self.spark = Sparkline(colori)
        self.spark.colore = colore_valore or colori["accento"]
        for w in (self.valore, self.nota, self.spark):
            lay.addWidget(w)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def imposta(self, valore: str, nota: str = "", serie: list | None = None) -> None:
        self.valore.setText(str(valore))
        self.nota.setText(nota)
        if serie is not None:
            self.spark.imposta_dati(serie)
        self.adatta_dimensioni(self.size())

    def aggiorna_tema(self, colori: dict) -> None:
        self.c = colori
        self.spark.aggiorna_tema(colori)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self.adatta_dimensioni(ev.size())

    def adatta_dimensioni(self, dimensione) -> None:
        larghezza = max(80, dimensione.width())
        altezza = max(50, dimensione.height())
        px = int(max(15, min(40, min(larghezza / 7.0, altezza / 2.6))))
        prova = QFont(self.valore.font())
        prova.setBold(True); prova.setPixelSize(px)
        while px > 13 and QFontMetrics(prova).horizontalAdvance(
                self.valore.text()) > larghezza - 6:
            px -= 1; prova.setPixelSize(px)
        self.valore.setStyleSheet(
            f"color: {self.colore_valore}; font-size: {px}px; font-weight: 700;")
        self.nota.setStyleSheet(f"color: {self.c['testo2']}; "
                                f"font-size: {max(10, min(14, int(px * 0.4)))}px;")
        self.nota.setVisible(altezza > 48)
        self.spark.setVisible(altezza > 92)
        self.spark.setFixedHeight(max(16, min(42, int(altezza * 0.2))))


class SchedaStat(Scheda):
    """Etichetta, valore grande, nota e sparkline dentro una scheda."""

    def __init__(self, etichetta_: str, colori: dict, colore: str | None = None, parent=None):
        super().__init__(parent=parent)
        self.layout_v.setSpacing(4)
        self.et = QLabel(etichetta_.upper())
        self.et.setObjectName("EtichettaScheda")
        self.contenuto = ContenutoStat(colori, colore)
        self.layout_v.addWidget(self.et)
        self.layout_v.addWidget(self.contenuto, 1)
        self.setMinimumHeight(110)

    def imposta(self, valore: str, nota: str = "", serie: list | None = None) -> None:
        self.contenuto.imposta(valore, nota, serie)


class AnelloEtichettato(QWidget):
    """Anello piccolo con il valore dentro e il nome sotto: un dato a colpo d'occhio."""

    def __init__(self, colori: dict, nome: str, colore: str = "", lato: int = 58,
                 parent=None):
        super().__init__(parent)
        self.setObjectName("ContenutoSezione")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(7)
        self.anello = Anello(colori, colore)
        self.anello.setFixedSize(lato, lato)
        lay.addWidget(self.anello, 0, Qt.AlignHCenter)
        self.et_nome = QLabel(nome)
        self.et_nome.setObjectName("NotaScheda")
        self.et_nome.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.et_nome)

    def imposta(self, quota: float, valore: str, suggerimento: str = "") -> None:
        self.anello.imposta(max(0.0, quota), valore, "")
        self.setToolTip(suggerimento)

    def aggiorna_tema(self, colori: dict) -> None:
        self.anello.aggiorna_tema(colori)


class RigaMisura(QWidget):
    """Riga con simbolo, due testi a sinistra, due a destra e barra sotto."""

    LATO = 30
    ALTEZZA_BARRA = 6

    def __init__(self, colori: dict, simbolo: str = "", titolo: str = "",
                 sottotitolo: str = "", valore: str = "", nota: str = "",
                 quota: int = 0, colore: str = "", parent=None):
        super().__init__(parent)
        self.c = colori
        self.setObjectName("ContenutoSezione")
        colore = colore or colori["accento"]
        self._titolo, self._sottotitolo = titolo, sottotitolo

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(7)
        alto = QHBoxLayout()
        alto.setContentsMargins(0, 0, 0, 0)
        alto.setSpacing(11)

        # senza simbolo non si lascia il buco: il testo parte da sinistra
        self.con_simbolo = bool(simbolo)
        self.simbolo = QLabel(simbolo)
        self.simbolo.setAlignment(Qt.AlignCenter)
        self.simbolo.setFixedSize(self.LATO, self.LATO)
        self.simbolo.setStyleSheet(
            f"background: {trasparente(colore, 0.16)};"
            f"border-radius: {self.LATO // 2}px; font-size: 15px;")
        if self.con_simbolo:
            alto.addWidget(self.simbolo, 0, Qt.AlignVCenter)
        else:
            self.simbolo.hide()

        self.et_titolo = QLabel(titolo)
        self.et_titolo.setObjectName("TitoloRiga")
        self.et_sotto = QLabel(sottotitolo)
        self.et_sotto.setObjectName("NotaScheda")
        for et in (self.et_titolo, self.et_sotto):
            et.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        sinistra = QVBoxLayout()
        sinistra.setContentsMargins(0, 0, 0, 0); sinistra.setSpacing(1)
        sinistra.addWidget(self.et_titolo); sinistra.addWidget(self.et_sotto)
        alto.addLayout(sinistra, 1)

        self.et_valore = QLabel(valore)
        self.et_valore.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.et_valore.setObjectName("ValoreRiga")
        self.et_valore.setStyleSheet(f"color: {colore};")
        self.et_nota = QLabel(nota)
        self.et_nota.setObjectName("NotaScheda")
        self.et_nota.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        destra = QVBoxLayout()
        destra.setContentsMargins(0, 0, 0, 0); destra.setSpacing(1)
        destra.addWidget(self.et_valore); destra.addWidget(self.et_nota)
        alto.addLayout(destra, 0)

        self.barra = QProgressBar()
        self.barra.setRange(0, 100)
        self.barra.setValue(max(0, min(100, int(quota))))
        self.barra.setTextVisible(False)
        self.barra.setFixedHeight(self.ALTEZZA_BARRA)
        raggio = self.ALTEZZA_BARRA // 2 + 2
        self.barra.setStyleSheet(
            f"QProgressBar {{ background: {colori['pannello2']}; border: none;"
            f" border-radius: {raggio}px; }}"
            f"QProgressBar::chunk {{ background: {colore}; border-radius: {raggio}px; }}")
        lay.addLayout(alto)
        lay.addWidget(self.barra)
        # senza un minimo le righe si schiacciano l'una sull'altra quando il
        # riquadro è basso: meglio farle scorrere
        self._adatta_altezza()

    def _adatta_altezza(self) -> None:
        """Il minimo segue il carattere, non un numero fisso.

        Con il testo molto grande le due righe di testo chiedono più dei 30 px
        del simbolo: tenendo il vecchio minimo, titolo e nota finivano
        tagliate a metà lettera.
        """
        for et in (self.et_titolo, self.et_sotto, self.et_valore, self.et_nota):
            et.ensurePolished()
        sinistra = (self.et_titolo.sizeHint().height()
                    + self.et_sotto.sizeHint().height() + 1)
        destra = (self.et_valore.sizeHint().height()
                  + self.et_nota.sizeHint().height() + 1)
        alto = max(self.LATO, sinistra, destra)
        self.setMinimumHeight(alto + self.ALTEZZA_BARRA + 9)

    def showEvent(self, ev):
        super().showEvent(ev)
        # una riga creata dopo l'avvio prende il foglio di stile solo qui:
        # misurarla nel costruttore darebbe l'altezza del carattere sbagliato
        self._adatta_altezza()

    def changeEvent(self, ev):
        super().changeEvent(ev)
        if ev.type() in (QEvent.StyleChange, QEvent.FontChange,
                         QEvent.ApplicationFontChange):
            self._adatta_altezza()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        occupato = (self.LATO + 26) if self.con_simbolo else 12
        spazio = max(40, self.width() - occupato
                     - max(self.et_valore.sizeHint().width(),
                           self.et_nota.sizeHint().width()))
        for et, testo in ((self.et_titolo, self._titolo),
                          (self.et_sotto, self._sottotitolo)):
            et.setText(QFontMetrics(et.font()).elidedText(testo, Qt.ElideRight, spazio))


# ------------------------------------------------------------------ ingressi
class CursoreVoto(QWidget):
    """Cursore da 1 a 10 con un decimale: umore, energia, stress, lucidità."""

    cambiato = Signal(float)

    def __init__(self, etichetta_: str, colori: dict, colore: str = "",
                 con_faccia: bool = False, parent=None):
        super().__init__(parent)
        self.c = colori
        self.colore = colore or colori["accento"]
        self.con_faccia = con_faccia
        self.setObjectName("ContenutoSezione")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(5)

        testa = QHBoxLayout()
        testa.setSpacing(8)
        self.et = QLabel(etichetta_)
        self.et.setObjectName("NotaScheda")
        self.et_valore = QLabel("5,0")
        self.et_valore.setStyleSheet(f"color: {self.colore}; font-weight: 700;")
        self.et_faccia = QLabel(faccia(5))
        self.et_faccia.setStyleSheet("font-size: 17px;")
        self.et_faccia.setVisible(con_faccia)
        testa.addWidget(self.et)
        testa.addStretch(1)
        testa.addWidget(self.et_faccia)
        testa.addWidget(self.et_valore)

        self.cursore = QSlider(Qt.Horizontal)
        self.cursore.setRange(10, 100)
        self.cursore.setSingleStep(1)
        self.cursore.setPageStep(5)
        self.cursore.setValue(50)
        self.cursore.valueChanged.connect(self._cambiato)
        self._stile_cursore()

        lay.addLayout(testa)
        lay.addWidget(self.cursore)

    def _stile_cursore(self) -> None:
        self.cursore.setStyleSheet(f"""
        QSlider::groove:horizontal {{
            height: 9px; border-radius: 5px; background: {self.c['pannello2']};
        }}
        QSlider::sub-page:horizontal {{
            height: 9px; border-radius: 5px; background: {self.colore};
        }}
        QSlider::handle:horizontal {{
            width: 18px; height: 18px; margin: -5px 0; border-radius: 10px;
            background: {self.colore}; border: 3px solid {self.c['pannello']};
        }}
        QSlider::handle:horizontal:hover {{ border-width: 2px; }}""")

    def _cambiato(self, valore: int) -> None:
        v = valore / 10
        self.et_valore.setText(f"{v:.1f}".replace(".", ","))
        if self.con_faccia:
            self.et_faccia.setText(faccia(v))
        self.cambiato.emit(v)

    def valore(self) -> float:
        return self.cursore.value() / 10

    def imposta(self, valore: float) -> None:
        self.cursore.setValue(int(round(max(1.0, min(10.0, valore)) * 10)))
        self._cambiato(self.cursore.value())

    def aggiorna_tema(self, colori: dict, colore: str = "") -> None:
        self.c = colori
        if colore:
            self.colore = colore
        self.et_valore.setStyleSheet(f"color: {self.colore}; font-weight: 700;")
        self._stile_cursore()


class Etichetta(QPushButton):
    """Pillola selezionabile: una emozione, un filtro, una scelta rapida."""

    def __init__(self, testo: str, colore: str, colori: dict | None = None,
                 parent=None):
        super().__init__(testo, parent)
        self.colore = colore
        # su fondo chiaro le tinte accese non si leggono: si scuriscono
        chiaro = QColor((colori or {}).get("pannello", "#1b1e27")).lightness() > 128
        self.colore_testo = scurisci(colore, 0.62) if chiaro else colore
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFlat(True)
        self.toggled.connect(lambda _: self._stile())
        self._stile()

    def _stile(self) -> None:
        if self.isChecked():
            self.setStyleSheet(
                f"QPushButton {{ background: {self.colore}; color: #0e1015; border: none;"
                f" border-radius: 15px; padding: 6px 14px; font-weight: 650; }}")
        else:
            self.setStyleSheet(
                f"QPushButton {{ background: {trasparente(self.colore, 0.10)};"
                f" color: {self.colore_testo}; border: none;"
                f" border-radius: 15px; padding: 6px 14px; }}"
                f"QPushButton:hover {{ border-color: {self.colore};"
                f" background: {trasparente(self.colore, 0.12)}; }}")


class CampoDurata(QWidget):
    """Ore e minuti affiancati: restituisce i minuti totali."""

    cambiato = Signal(int)          # minuti totali, quando li si scrive a mano

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.ore = QSpinBox(); self.ore.setRange(0, 24); self.ore.setSuffix(" h")
        self.minuti = QSpinBox(); self.minuti.setRange(0, 59)
        self.minuti.setSingleStep(5); self.minuti.setSuffix(" min")
        lay.addWidget(self.ore); lay.addWidget(self.minuti)
        self._muto = False
        for casella in (self.ore, self.minuti):
            casella.valueChanged.connect(self._avvisa)

    def _avvisa(self) -> None:
        if not self._muto:
            self.cambiato.emit(self.valore())

    def valore(self) -> int:
        return self.ore.value() * 60 + self.minuti.value()

    def imposta(self, minuti: int) -> None:
        """Scrive il valore senza far scattare `cambiato`: è l'app che parla."""
        minuti = int(minuti or 0)
        self._muto = True
        self.ore.setValue(minuti // 60)
        self.minuti.setValue(minuti % 60)
        self._muto = False


def ore_minuti(testo: str, difetto: int = 0) -> int:
    """«23:00» diventa 1380 minuti; quello che non si capisce vale il difetto."""
    try:
        o, m = testo.split(":")
        return (int(o) % 24) * 60 + int(m) % 60
    except (AttributeError, ValueError):
        return difetto


def minuti_ore(minuti: int) -> str:
    minuti = int(minuti) % 1440
    return f"{minuti // 60:02d}:{minuti % 60:02d}"


class SceltaSonno(QWidget):
    """Il quadrante del sonno: a che ora a letto, a che ora sveglio.

    Due maniglie che scorrono su un anello di ventiquattro ore, come nella
    sveglia del telefono: in mezzo le due ore scritte grandi. Trascinando la
    fascia in mezzo si sposta tutta la dormita senza cambiarne la durata.
    """

    cambiato = Signal()
    PASSO = 5                      # minuti: le maniglie scattano di cinque

    def __init__(self, colori: dict, colore: str = "", parent=None):
        super().__init__(parent)
        self.c = colori
        self.colore = colore or colori["accento"]
        self.a_letto = 23 * 60
        self.sveglia = 7 * 60
        self._presa = ""           # letto | sveglia | banda
        self._ancora = 0
        self.setMinimumSize(226, 226)
        self.setMouseTracking(True)

    # ------------------------------------------------------------ valori
    def imposta(self, a_letto, sveglia) -> None:
        self.a_letto = (ore_minuti(a_letto, 23 * 60) if isinstance(a_letto, str)
                        else int(a_letto) % 1440)
        self.sveglia = (ore_minuti(sveglia, 7 * 60) if isinstance(sveglia, str)
                        else int(sveglia) % 1440)
        self.update()

    def durata(self) -> int:
        """Quanto dura la dormita, in minuti (mezzanotte compresa)."""
        return (self.sveglia - self.a_letto) % 1440 or 1440

    def imposta_durata(self, minuti: int) -> None:
        """Cambia solo l'ora della sveglia: l'ora di andare a letto resta."""
        minuti = max(self.PASSO, min(1440, int(minuti or 0)))
        self.sveglia = (self.a_letto + minuti) % 1440
        self.update()

    def ore(self) -> tuple[str, str]:
        return minuti_ore(self.a_letto), minuti_ore(self.sveglia)

    def aggiorna_tema(self, colori: dict, colore: str = "") -> None:
        self.c = colori
        if colore:
            self.colore = colore
        self.update()

    # ------------------------------------------------------------ disegno
    def _misure(self):
        lato = min(self.width(), self.height())
        spessore = max(16.0, lato * 0.115)
        raggio = lato / 2 - spessore / 2 - 2
        centro = QPointF(self.width() / 2, self.height() / 2)
        return centro, raggio, spessore

    def _punto(self, minuti: int, raggio: float) -> QPointF:
        """Dove cade un orario sull'anello: mezzanotte in cima, poi in senso orario."""
        import math
        angolo = math.radians(minuti / 1440 * 360)
        centro, _, _ = self._misure()
        return QPointF(centro.x() + raggio * math.sin(angolo),
                       centro.y() - raggio * math.cos(angolo))

    def paintEvent(self, _):
        import math
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        centro, raggio, spessore = self._misure()
        cerchio = QRectF(centro.x() - raggio, centro.y() - raggio,
                         raggio * 2, raggio * 2)

        # l'anello spento, tutte le ventiquattro ore
        penna = QPen(QColor(self.c["tocco"]), spessore)
        penna.setCapStyle(Qt.FlatCap)
        p.setPen(penna)
        p.drawArc(cerchio, 0, 360 * 16)

        # la fascia della dormita, dalle maniglie arrotondate
        inizio = self.a_letto / 1440 * 360
        ampiezza = self.durata() / 1440 * 360
        penna = QPen(QColor(self.colore), spessore)
        penna.setCapStyle(Qt.RoundCap)
        p.setPen(penna)
        p.drawArc(cerchio, int((90 - inizio) * 16), int(-ampiezza * 16))

        # i puntini bianchi lungo la fascia: si vede dove scorre la notte
        pallino = QColor(su_tinta(self.colore))
        pallino.setAlpha(130)
        p.setPen(Qt.NoPen); p.setBrush(pallino)
        passo = 15
        for minuti in range(passo, int(self.durata()), passo):
            p.drawEllipse(self._punto((self.a_letto + minuti) % 1440, raggio),
                          spessore * 0.055, spessore * 0.055)

        # i trattini delle ore, dentro l'anello
        dentro = raggio - spessore / 2 - 6
        for quarto in range(96):
            minuti = quarto * 15
            grande = minuti % 360 == 0
            lungo = 5.0 if grande else 3.5
            angolo = math.radians(minuti / 1440 * 360)
            sx, sy = math.sin(angolo), -math.cos(angolo)
            colore = QColor(self.c["testo2"] if grande else self.c["griglia"])
            penna = QPen(colore, 1.6 if grande else 1.0)
            penna.setCapStyle(Qt.RoundCap)
            p.setPen(penna)
            p.drawLine(QPointF(centro.x() + sx * dentro, centro.y() + sy * dentro),
                       QPointF(centro.x() + sx * (dentro - lungo),
                               centro.y() + sy * (dentro - lungo)))

        # 0, 6, 12, 18: le quattro ore scritte
        f = QFont(); f.setPointSizeF(max(7.5, raggio * 0.085)); p.setFont(f)
        p.setPen(QColor(self.c["testo2"]))
        for ora in (0, 6, 12, 18):
            punto = self._punto(ora * 60, dentro - 24)
            p.drawText(QRectF(punto.x() - 14, punto.y() - 9, 28, 18),
                       Qt.AlignCenter, str(ora))

        # le due maniglie, con dentro il letto e la sveglia
        for minuti, segno in ((self.a_letto, "letto"), (self.sveglia, "sveglia")):
            punto = self._punto(minuti, raggio)
            p.setPen(Qt.NoPen); p.setBrush(QColor(self.colore))
            p.drawEllipse(punto, spessore / 2, spessore / 2)
            self._segno(p, punto, spessore * 0.30, segno)

        # in mezzo: le due ore, grandi
        self._centro(p, centro, raggio)

    def _segno(self, p: QPainter, centro: QPointF, lato: float, quale: str) -> None:
        """Il letto e la sveglia, disegnati dentro la maniglia."""
        penna = QPen(QColor(su_tinta(self.colore)), max(1.1, lato * 0.22))
        penna.setCapStyle(Qt.RoundCap); penna.setJoinStyle(Qt.RoundJoin)
        p.setPen(penna); p.setBrush(Qt.NoBrush)
        x, y = centro.x(), centro.y()
        if quale == "letto":
            p.drawLine(QPointF(x - lato, y - lato * 0.5),
                       QPointF(x - lato, y + lato * 0.7))
            cuscino = QPainterPath()
            cuscino.moveTo(x - lato, y + lato * 0.1)
            cuscino.lineTo(x - lato * 0.2, y + lato * 0.1)
            cuscino.cubicTo(x + lato * 0.9, y + lato * 0.1,
                            x + lato, y + lato * 0.7, x + lato, y + lato * 0.7)
            p.drawPath(cuscino)
            p.drawLine(QPointF(x - lato, y + lato * 0.7),
                       QPointF(x + lato, y + lato * 0.7))
        else:
            p.drawEllipse(centro, lato * 0.75, lato * 0.75)
            p.drawLine(QPointF(x, y - lato * 0.35), QPointF(x, y))
            p.drawLine(QPointF(x, y), QPointF(x + lato * 0.4, y + lato * 0.2))

    def _centro(self, p: QPainter, centro: QPointF, raggio: float) -> None:
        grande = QFont()
        grande.setPointSizeF(max(13.0, raggio * 0.24))
        grande.setWeight(QFont.DemiBold)
        p.setFont(grande)
        fm = QFontMetrics(grande)
        alto = fm.height()
        a_letto, sveglia = self.ore()
        for i, (testo, quale) in enumerate(((a_letto, "letto"), (sveglia, "sveglia"))):
            y = centro.y() - alto * 0.62 + i * alto * 1.12
            largo = fm.horizontalAdvance(testo)
            simbolo = alto * 0.30
            inizio = centro.x() - (largo + simbolo * 3.2) / 2
            self._segno(p, QPointF(inizio + simbolo, y), simbolo, quale)
            p.setPen(QColor(self.c["testo"]))
            p.setFont(grande)
            p.drawText(QRectF(inizio + simbolo * 2.6, y - alto / 2,
                              largo + 12, alto), Qt.AlignLeft | Qt.AlignVCenter,
                       testo)

    # ------------------------------------------------------------- mouse
    def _minuti(self, posizione) -> int:
        import math
        centro, _, _ = self._misure()
        gradi = math.degrees(math.atan2(posizione.x() - centro.x(),
                                        centro.y() - posizione.y())) % 360
        minuti = int(round(gradi / 360 * 1440 / self.PASSO)) * self.PASSO
        return minuti % 1440

    def mousePressEvent(self, ev):
        centro, raggio, spessore = self._misure()
        punto = ev.position()
        distanze = {}
        for quale, minuti in (("letto", self.a_letto), ("sveglia", self.sveglia)):
            maniglia = self._punto(minuti, raggio)
            distanze[quale] = ((punto.x() - maniglia.x()) ** 2
                               + (punto.y() - maniglia.y()) ** 2) ** 0.5
        vicina = min(distanze, key=distanze.get)
        dal_centro = ((punto.x() - centro.x()) ** 2
                      + (punto.y() - centro.y()) ** 2) ** 0.5
        if distanze[vicina] <= spessore:
            self._presa = vicina
        elif abs(dal_centro - raggio) <= spessore:
            self._presa = "banda"
            self._ancora = self._minuti(punto)
        else:
            self._presa = ""
        self.mouseMoveEvent(ev)

    def mouseMoveEvent(self, ev):
        if not self._presa:
            return
        minuti = self._minuti(ev.position())
        if self._presa == "letto":
            if (self.sveglia - minuti) % 1440 >= self.PASSO:
                self.a_letto = minuti
        elif self._presa == "sveglia":
            if (minuti - self.a_letto) % 1440 >= self.PASSO:
                self.sveglia = minuti
        else:                                   # tutta la fascia
            scarto = (minuti - self._ancora) % 1440
            if scarto:
                durata = self.durata()
                self.a_letto = (self.a_letto + scarto) % 1440
                self.sveglia = (self.a_letto + durata) % 1440
                self._ancora = minuti
        self.update()
        self.cambiato.emit()

    def mouseReleaseEvent(self, _ev):
        self._presa = ""


COLORE_BATTITO = "#ef5f5c"        # il cuore: lo stesso rosso dappertutto


def dati_battito(db, scelta: str) -> tuple[list, int, str]:
    """I dati del riquadro del battito: capsule, valore a riposo, nota.

    Con «oggi» o «ieri» si guardano le ore di quella giornata; con un numero
    di giorni, una capsula per giornata. Torna già pronto quello che serve a
    disegnare, così il riquadro è uguale in Salute e nel cruscotto.
    """
    from datetime import date, timedelta
    if scelta in ("oggi", "ieri"):
        giorno = (date.today() - timedelta(days=1 if scelta == "ieri" else 0)
                  ).isoformat()
        righe = db.battiti_del_giorno(giorno)
        if not righe:
            # la mattina presto il braccialetto non ha ancora misurato nulla:
            # invece di un riquadro vuoto si mostrano gli ultimi giorni
            dati, riposo, _ = dati_battito(db, "7")
            return dati, riposo, (f"{scelta} non ancora misurato · "
                                  "ultimi 7 giorni" if dati else "")
        dati = [(r["quando"][11:16], r["minimo"] or r["valore"], r["valore"],
                 r["massimo"] or r["valore"]) for r in righe]
        bassi = [r["minimo"] or r["valore"] for r in righe]
        alti = [r["massimo"] or r["valore"] for r in righe]
        nota = f"{len(righe)} ore misurate · da {min(bassi)} a {max(alti)} bpm"
        riposo = min(bassi)
    else:
        elenco = ultimi_giorni(int(scelta))
        righe = db.battiti_per_giorno(elenco[0], elenco[-1])
        dati = [(data_it(r["data"])[:5], r["minimo"], r["media"], r["massimo"])
                for r in righe]
        bassi = [r["minimo"] for r in righe]
        nota = f"{len(righe)} giornate con misure" if righe else ""
        riposo = int(round(sum(bassi) / len(bassi))) if bassi else 0
    return dati, riposo, nota


def righe_indicatori(db, colori: dict, quanti: int) -> list[tuple[str, QWidget]]:
    """Le righe di battito, variabilità, acqua e stress: (campo, riga).

    Le usano sia Salute sia il cruscotto: il campo torna indietro perché chi
    le mostra possa renderle apribili sull'andamento di quel dato.
    """
    from datetime import date

    from .punteggi import PREDEFINITI
    elenco = ultimi_giorni(quanti)
    dati = db.giorni_salute(elenco[0], elenco[-1])
    oggi = db.salute_giorno(date.today().isoformat())

    def valori(campo):
        return [float(r[campo]) for r in dati.values() if r[campo]]

    obiettivo_acqua = db.leggi_num("obiettivo_acqua", PREDEFINITI["obiettivo_acqua"])
    voci = [
        ("❤", "Battito a riposo", "battito", "bpm", COLORE_BATTITO, 0),
        ("〰", "Variabilità (HRV)", "hrv", "ms", colori["accento"], 0),
        ("💧", "Acqua", "acqua", "L", "#6c8cff", obiettivo_acqua),
        ("◐", "Stress", "stress", "", "#f0b429", 0),
    ]
    fatte = []
    for simbolo, nome, campo, unita, colore, obiettivo in voci:
        serie = valori(campo)
        if not serie and not (oggi and oggi[campo]):
            continue
        attuale = (float(oggi[campo]) if oggi and oggi[campo]
                   else (serie[-1] if serie else 0))
        decimali = 0 if campo in ("battito", "hrv", "stress") else 1
        if obiettivo:
            quota = int(min(100, attuale / obiettivo * 100))
        elif campo == "battito":
            quota = int(max(0.0, min(100.0, (85 - attuale) / 40 * 100)))
        elif campo == "hrv":
            quota = int(max(0.0, min(100.0, attuale / 80 * 100)))
        elif campo == "stress":
            # qui la barra piena vuol dire «sereno»: lo stress si rovescia
            quota = int(max(0.0, min(100.0, 100 - attuale)))
        else:
            quota = int(min(100, (attuale / max(serie) * 100) if serie else 0))
        nota = (f"obiettivo {numero(obiettivo, 1)} {unita}" if obiettivo
                else f"media {numero(media(serie), decimali)} {unita}"
                if serie else "")
        fatte.append((campo, RigaMisura(
            colori, simbolo, nome, nota, f"{numero(attuale, decimali)} {unita}",
            f"{quanti} giorni", quota, colore)))
    return fatte


def binario(voci: dict, scelto: str, al_clic,
            spiegazioni: dict | None = None) -> tuple[QWidget, dict]:
    """Un interruttore segmentato: le scelte dentro un unico fondo.

    È la forma che One UI dà alle scelte brevi — tre o quattro voci che si
    escludono — ed è quella che usa tutta l'applicazione per il tempo: giorni
    o settimane o mesi, sette o trenta giorni. Torna il binario e i pulsanti,
    perché chi lo usa possa riaccenderli quando cambia la scelta.

    Le voci possono essere simboli invece che parole: in quel caso si passa
    `spiegazioni` col nome per esteso, che finisce nel suggerimento — un
    segno senza nome è un indovinello.
    """
    contenitore = QWidget()
    contenitore.setObjectName("Segmentato")
    lay = QHBoxLayout(contenitore)
    lay.setContentsMargins(3, 3, 3, 3)
    lay.setSpacing(2)
    pulsanti: dict[str, QPushButton] = {}
    for chiave, nome in voci.items():
        b = QPushButton(nome)
        b.setObjectName("Scelta")
        b.setCheckable(True)
        b.setChecked(chiave == scelto)
        b.setCursor(Qt.PointingHandCursor)
        b.setFocusPolicy(Qt.NoFocus)
        if spiegazioni and chiave in spiegazioni:
            b.setToolTip(spiegazioni[chiave])
        b.clicked.connect(lambda _=False, k=chiave: al_clic(k))
        pulsanti[chiave] = b
        lay.addWidget(b)
    return contenitore, pulsanti


class _NomePeriodo(QLabel):
    """Il nome del periodo, fra le due frecce.

    Chiede sempre lo stesso posto — quello della frase più lunga che può
    capitare — così il gruppo non balla a ogni freccia. Ma se il riquadro è
    stretto si lascia stringere e accorcia il testo coi puntini: «30/09 – 0…»
    si legge ancora, una pastiglia tagliata a metà no.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.riserva = 100
        self.pieno = ""

    def imposta(self, testo: str) -> None:
        self.pieno = testo
        self._scrivi()

    def _scrivi(self) -> None:
        corto = self.fontMetrics().elidedText(
            self.pieno, Qt.ElideRight, max(10, self.width() - 4))
        self.setText(corto)
        self.setToolTip(self.pieno if corto != self.pieno else "")

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._scrivi()

    def sizeHint(self) -> QSize:
        chiesto = super().sizeHint()
        return QSize(max(self.riserva, chiesto.width()), chiesto.height())

    def minimumSizeHint(self) -> QSize:
        return QSize(44, super().minimumSizeHint().height())


class NavigatorePeriodo(QWidget):
    """Il comando per sfogliare i dati: una riga sola, sopra al grafico.

    A sinistra le frecce con in mezzo l'intervallo che stai guardando — in
    «Giorni» è una settimana intera, e le frecce la fanno scorrere da una
    settimana all'altra. Accanto la pastiglia del modo (giorni, settimane,
    mesi) e «Oggi», che compare solo quando ti sei allontanato dal presente.

    **Dove sta.** Non sotto il titolo, ma *sul* titolo: lo si consegna a
    `aggiungi(..., comando=nav)` e va a finire in fondo all'intestazione del
    riquadro, come le frecce dei grafici di One UI. Quei quaranta pixel di
    comando tornano al disegno, che è quello che si guarda. Se il riquadro
    diventa troppo stretto perché ci stia accanto al titolo, l'intestazione
    lo rimette sotto da sola invece di tagliarlo (vedi `Sezione`).

    Chi lo usa ascolta `cambiato` e ridisegna, leggendo `modo`, `scarto` e
    `finestre()` — che sono già gli intervalli pronti da interrogare. Con
    `scorri_con_rotella(grafico)` la rotellina del mouse sul grafico scorre
    i periodi.
    """

    cambiato = Signal()

    def __init__(self, colori: dict, modo: str = "giorni",
                 quanti: dict | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("ContenutoSezione")
        self.c = colori
        self.modo = modo
        self.scarto = 0
        self.quanti = dict(QUANTI_PREDEFINITI if quanti is None else quanti)
        # quanto posto gli hanno riservato: finché nessuno lo dice, tutto
        self._posto = 1 << 20
        # sulla riga del titolo occupa quello che gli serve e non un pixel
        # di più: a spingerlo a destra ci pensa l'intestazione
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        # ---- le frecce col nome in mezzo: un gruppo solo
        self.gruppo = QWidget()
        self.gruppo.setObjectName("NavPeriodo")
        dentro = QHBoxLayout(self.gruppo)
        dentro.setContentsMargins(2, 2, 2, 2)
        dentro.setSpacing(0)
        self.b_prima = QPushButton("‹")
        self.b_dopo = QPushButton("›")
        for freccia, passo in ((self.b_prima, 1), (self.b_dopo, -1)):
            freccia.setObjectName("NavFreccia")
            freccia.setCursor(Qt.PointingHandCursor)
            freccia.setFocusPolicy(Qt.NoFocus)
            freccia.clicked.connect(lambda _=False, p=passo: self.scorri(p))
        self.b_prima.setToolTip("Il periodo prima  (rotellina giù)")
        self.b_dopo.setToolTip("Il periodo dopo  (rotellina su)")
        self.et_quando = _NomePeriodo()
        self.et_quando.setObjectName("NavQuando")
        self.et_quando.setAlignment(Qt.AlignCenter)
        dentro.addWidget(self.b_prima)
        dentro.addWidget(self.et_quando, 1)
        dentro.addWidget(self.b_dopo)
        lay.addWidget(self.gruppo)

        # ---- il modo, nella stessa pastiglia: giorni, settimane, mesi
        self.b_modo = QPushButton("")
        self.b_modo.setObjectName("NavModo")
        self.b_modo.setCursor(Qt.PointingHandCursor)
        self.b_modo.setFocusPolicy(Qt.NoFocus)
        self.b_modo.setToolTip("Guarda per giorni, settimane o mesi")
        self.b_modo.clicked.connect(self._menu_modo)
        lay.addWidget(self.b_modo)

        self.b_oggi = QPushButton("Oggi")
        self.b_oggi.setObjectName("NavOggi")
        self.b_oggi.setCursor(Qt.PointingHandCursor)
        self.b_oggi.setFocusPolicy(Qt.NoFocus)
        self.b_oggi.setToolTip("Torna al presente")
        self.b_oggi.clicked.connect(self.torna_a_oggi)
        lay.addWidget(self.b_oggi)
        self._mostra()
        self._misura()

    # ------------------------------------------------------------- misure
    def _misura(self) -> None:
        """Tutto segue il carattere: col testo grande cresce, senza tagliarsi.

        La scritta del «quando» si tiene una larghezza minima, se no il
        gruppo ballerebbe a ogni freccia («oggi» è corto, «27/10 – 2/11» no).
        Le frecce sono quadrate sulla stessa misura, così il foglio di stile
        le arrotonda in cerchi.
        """
        for widget in (self.b_prima, self.b_dopo, self.et_quando, self.b_modo,
                       self.b_oggi):
            widget.ensurePolished()
        misura = QFontMetrics(self.et_quando.font())
        lato = max(22, misura.height() + 5)
        for freccia in (self.b_prima, self.b_dopo):
            freccia.setFixedSize(lato, lato)
        # Il raggio va dato qui, non nel foglio di stile: Qt un raggio più
        # grande di mezza altezza non lo accorcia, lo butta via, e la
        # pastiglia torna un rettangolo. L'altezza la sappiamo solo adesso,
        # che il carattere è quello vero.
        self._arrotonda(self.gruppo, lato + 4)
        self._arrotonda(self.b_prima, lato)
        self._arrotonda(self.b_dopo, lato)
        for pastiglia in (self.b_modo, self.b_oggi):
            self._arrotonda(pastiglia, pastiglia.sizeHint().height())
        # la più larga fra le frasi che possono comparire **in questo modo**:
        # così il gruppo non balla a ogni freccia, e non si porta dietro lo
        # spazio di parole che qui non compariranno mai
        frasi = (("questo mese", "mese scorso", "settembre 2026")
                 if self.modo == "mesi" else
                 ("questa settimana", "settimana scorsa", "30/09 – 06/10"))
        self.et_quando.riserva = max(misura.horizontalAdvance(t)
                                     for t in frasi) + 8
        self.et_quando.updateGeometry()

    @staticmethod
    def _arrotonda(widget, altezza: int) -> None:
        """Mezza altezza di raggio: la pastiglia tonda di One UI."""
        regola = (f"{widget.metaObject().className()}#{widget.objectName()}"
                  f" {{ border-radius: {max(2, altezza // 2)}px; }}")
        if widget.styleSheet() != regola:      # se no si ripolisce all'infinito
            widget.setStyleSheet(regola)

    def larghezza_necessaria(self) -> int:
        """Il minimo per esserci: le frecce col nome e la pastiglia del modo."""
        self._misura()
        return (self.gruppo.sizeHint().width() + self.layout().spacing()
                + self.b_modo.sizeHint().width())

    def spazio_massimo(self) -> int:
        """Quanto chiede con «Oggi» fuori, che compare quando ti allontani."""
        return (self.larghezza_necessaria() + self.layout().spacing()
                + self.b_oggi.sizeHint().width())

    def adatta_a(self, larghezza: int) -> None:
        """Dice al navigatore quanto posto gli è stato riservato.

        Serve per «Oggi»: dove c'è spazio compare appena ti allontani dal
        presente, dove non ce n'è non compare mai — e allora la riga del
        titolo non si riassetta sotto le mani a metà di una scorsa. Indietro
        ci si torna comunque con la freccia «›».
        """
        self._posto = larghezza
        self._mostra_oggi()

    def _mostra_oggi(self) -> None:
        self.b_oggi.setVisible(self.scarto > 0
                               and self._posto >= self.spazio_massimo())

    def showEvent(self, ev):
        super().showEvent(ev)
        self._misura()

    def changeEvent(self, ev):
        super().changeEvent(ev)
        if ev.type() in (QEvent.StyleChange, QEvent.FontChange,
                         QEvent.ApplicationFontChange):
            self._misura()

    # ------------------------------------------------------------- comandi
    def _menu_modo(self) -> None:
        menu = QMenu(self)
        for chiave, nome in MODI_PERIODO.items():
            azione = menu.addAction(nome)
            azione.setCheckable(True)
            azione.setChecked(chiave == self.modo)
            azione.triggered.connect(
                lambda _=False, k=chiave: self.imposta_modo(k))
        menu.exec(self.b_modo.mapToGlobal(
            QPoint(0, self.b_modo.height() + 2)))

    def imposta_modo(self, modo: str) -> None:
        if modo not in MODI_PERIODO or modo == self.modo:
            return
        self.modo, self.scarto = modo, 0      # cambiando modo si torna a oggi
        self._mostra()
        self.cambiato.emit()

    def scorri(self, passo: int) -> None:
        nuovo = max(0, self.scarto + passo)   # nel futuro non si va
        if nuovo == self.scarto:
            return
        self.scarto = nuovo
        self._mostra()
        self.cambiato.emit()

    def torna_a_oggi(self) -> None:
        if self.scarto:
            self.scarto = 0
            self._mostra()
            self.cambiato.emit()

    # --------------------------------------------------------- la rotellina
    def wheelEvent(self, ev):
        self._rotella(ev)

    def scorri_con_rotella(self, *widget) -> None:
        """La rotellina su questi widget scorre i periodi: di solito il grafico."""
        for w in widget:
            w.installEventFilter(self)

    def eventFilter(self, oggetto, evento):
        if evento.type() == QEvent.Wheel:
            self._rotella(evento)
            return True
        return super().eventFilter(oggetto, evento)

    def _rotella(self, evento) -> None:
        """Rotella giù: indietro nel tempo. Su: avanti, fino a oggi."""
        passi = evento.angleDelta().y()
        if passi:
            self.scorri(-1 if passi > 0 else 1)
            evento.accept()

    # --------------------------------------------------------------- dati
    def finestre(self) -> list[tuple[str, str, str]]:
        """Gli intervalli da disegnare: (etichetta, dal, al)."""
        return intervalli(self.modo, self.quanti.get(self.modo, 0), self.scarto)

    def scelto(self) -> tuple[str, str]:
        """L'intervallo in primo piano: l'ultimo, quello del numero grande."""
        finestre = self.finestre()
        return (finestre[-1][1], finestre[-1][2]) if finestre else ("", "")

    def esteso(self) -> tuple[str, str]:
        """Tutto quello che si vede: dal primo giorno all'ultimo."""
        finestre = self.finestre()
        return (finestre[0][1], finestre[-1][2]) if finestre else ("", "")

    def nome(self) -> str:
        # in «giorni» il nome è quello di tutta la settimana, non dell'ultimo
        dal, al = self.esteso() if self.modo == "giorni" else self.scelto()
        return nome_intervallo(self.modo, dal, al, self.scarto) if dal else ""

    def _mostra(self) -> None:
        self.et_quando.imposta(self.nome())
        self.b_modo.setText(f"{MODI_PERIODO[self.modo].lower()}  \u25be")
        self.b_dopo.setEnabled(self.scarto > 0)
        self._mostra_oggi()

    def aggiorna_tema(self, colori: dict) -> None:
        self.c = colori


class BottonePannello(QPushButton):
    """Apre e chiude la colonna delle conversazioni.

    Disegna l'icona invece di scrivere «‹» o «›»: un rettangolo con la
    colonna piena da una parte, come nelle app di chat. Si capisce al volo
    da che parte sta il pannello, e cresce col testo invece di restare un
    carattere perso in mezzo al bottone.
    """

    def __init__(self, colori: dict, aperta: bool = True, parent=None):
        super().__init__(parent)
        self.c = colori
        self.aperta = aperta
        self.setObjectName("BottonePannello")
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self._misura()

    def _misura(self) -> None:
        self.ensurePolished()
        lato = max(28, QFontMetrics(self.font()).height() + 12)
        self.setFixedSize(lato, lato)

    def imposta(self, aperta: bool) -> None:
        self.aperta = aperta
        self.setToolTip("Chiudi l'elenco delle conversazioni" if aperta
                        else "Mostra le conversazioni")
        self.update()

    def changeEvent(self, ev):
        super().changeEvent(ev)
        if ev.type() in (QEvent.StyleChange, QEvent.FontChange,
                         QEvent.ApplicationFontChange):
            self._misura()

    def aggiorna_tema(self, colori: dict) -> None:
        self.c = colori
        self.update()

    def paintEvent(self, ev):
        super().paintEvent(ev)            # lo sfondo lo mette il foglio di stile
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        lato = min(self.width(), self.height())
        riquadro = QRectF(0, 0, lato * 0.52, lato * 0.42)
        riquadro.moveCenter(QRectF(self.rect()).center())
        colore = QColor(self.c["testo2"] if not self.underMouse()
                        else self.c["accento"])
        p.setPen(QPen(colore, max(1.2, lato * 0.055)))
        p.setBrush(Qt.NoBrush)
        raggio = lato * 0.09
        p.drawRoundedRect(riquadro, raggio, raggio)
        # la colonna piena: a sinistra quando è aperta, a destra quando no
        larga = riquadro.width() * 0.34
        x = riquadro.left() if self.aperta else riquadro.right() - larga
        colonna = QRectF(x, riquadro.top(), larga, riquadro.height())
        p.setPen(Qt.NoPen)
        p.setBrush(colore)
        percorso = QPainterPath()
        percorso.addRoundedRect(riquadro, raggio, raggio)
        p.setClipPath(percorso)
        p.drawRect(colonna)


class BarraAttesa(QWidget):
    """Barra di caricamento che non sa quanto manca: un segmento che scorre.

    La stessa dell'avvio di Tess: non finge una percentuale che nessuno può
    calcolare, dice solo che qualcosa sta andando avanti.
    """

    def __init__(self, colori: dict, parent=None, altezza: int = 4):
        super().__init__(parent)
        self.c = colori
        self.setFixedHeight(altezza)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._quota = 0.0
        self._moto = QVariantAnimation(self)
        self._moto.setDuration(1100)
        self._moto.setStartValue(0.0)
        self._moto.setEndValue(1.0)
        self._moto.setLoopCount(-1)
        self._moto.setEasingCurve(QEasingCurve.InOutSine)
        self._moto.valueChanged.connect(self._passo)

    def avvia(self) -> None:
        self.show()
        if self._moto.state() != QVariantAnimation.Running:
            self._moto.start()

    def ferma(self) -> None:
        self._moto.stop()
        self.hide()

    def aggiorna_tema(self, colori: dict) -> None:
        self.c = colori
        self.update()

    def _passo(self, valore) -> None:
        self._quota = float(valore)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        raggio = self.height() / 2
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(self.c.get("bordo", "#333")))
        p.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), raggio, raggio)
        largo = max(40.0, self.width() * 0.3)
        corsa = self.width() + largo
        x = -largo + corsa * self._quota
        p.setBrush(QColor(self.c["accento"]))
        p.drawRoundedRect(QRectF(x, 0, largo, self.height()), raggio, raggio)


class Interruttore(QWidget):
    """Interruttore a scorrimento: il pallino scivola da spento ad acceso.

    Serve dove una cosa si accende o si spegne davvero — Tess, l'invio dei
    dati — e un pulsante che cambia scritta non basterebbe a dirlo.
    """

    cambiato = Signal(bool)

    def __init__(self, colori: dict, acceso: bool = False, parent=None,
                 larghezza: int = 46, altezza: int = 26):
        super().__init__(parent)
        self.c = colori
        self._acceso = acceso
        self._quota = 1.0 if acceso else 0.0
        self.setFixedSize(larghezza, altezza)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self._moto = QVariantAnimation(self)
        self._moto.setDuration(180)
        self._moto.setEasingCurve(QEasingCurve.OutCubic)
        self._moto.valueChanged.connect(self._passo)

    # ------------------------------------------------------------- stato
    def acceso(self) -> bool:
        return self._acceso

    def imposta(self, acceso: bool, avvisa: bool = False) -> None:
        if acceso == self._acceso:
            return
        self._acceso = acceso
        self._moto.stop()
        if self.isVisible():
            self._moto.setStartValue(self._quota)
            self._moto.setEndValue(1.0 if acceso else 0.0)
            self._moto.start()
        else:
            self._quota = 1.0 if acceso else 0.0
            self.update()
        if avvisa:
            self.cambiato.emit(acceso)

    def commuta(self) -> None:
        self.imposta(not self._acceso, avvisa=True)

    def aggiorna_tema(self, colori: dict) -> None:
        self.c = colori
        self.update()

    # -------------------------------------------------------- interazione
    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self.commuta()

    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
            self.commuta()
            return
        super().keyPressEvent(ev)

    def _passo(self, valore) -> None:
        self._quota = float(valore)
        self.update()

    # ------------------------------------------------------------ disegno
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        raggio = self.height() / 2
        spento = QColor(self.c.get("bordo", "#444"))
        acceso = QColor(self.c["accento"])
        fondo = QColor(
            int(spento.red() + (acceso.red() - spento.red()) * self._quota),
            int(spento.green() + (acceso.green() - spento.green()) * self._quota),
            int(spento.blue() + (acceso.blue() - spento.blue()) * self._quota))
        p.setPen(Qt.NoPen)
        p.setBrush(fondo)
        p.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), raggio, raggio)

        lato = self.height() - 6
        x = 3 + (self.width() - lato - 6) * self._quota
        p.setBrush(QColor("#ffffff" if self._quota > 0.5
                          else self.c.get("pannello", "#fff")))
        p.drawEllipse(QRectF(x, 3, lato, lato))
        if self.hasFocus():
            p.setBrush(Qt.NoBrush)
            p.setPen(QColor(self.c["accento"]))
            p.drawRoundedRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1),
                              raggio, raggio)


class CampoData(QWidget):
    """Una data che può anche non esserci.

    Senza spunta il valore è vuoto: un esame senza appello fissato, un
    progetto senza scadenza. Meglio il vuoto di una data messa lì per forza.
    """

    cambiata = Signal()

    def __init__(self, valore: str = "", vuoto: str = "non fissata", parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(9)
        self.casella = QCheckBox()
        self.casella.setToolTip("Spunta per fissare una data")
        self.data = QDateEdit()
        self.data.setCalendarPopup(True)
        self.data.setDisplayFormat("dd/MM/yyyy")
        self.et_vuoto = QLabel(vuoto)
        self.et_vuoto.setObjectName("NotaScheda")
        lay.addWidget(self.casella)
        lay.addWidget(self.data, 1)
        lay.addWidget(self.et_vuoto, 1)
        self.casella.toggled.connect(self._mostra)
        self.casella.toggled.connect(self.cambiata)
        self.data.dateChanged.connect(self.cambiata)
        self.imposta(valore)

    def _mostra(self, acceso: bool) -> None:
        self.data.setVisible(acceso)
        self.et_vuoto.setVisible(not acceso)

    def imposta(self, valore: str) -> None:
        scelta = QDate.fromString(valore or "", "yyyy-MM-dd")
        self.casella.setChecked(scelta.isValid())
        self.data.setDate(scelta if scelta.isValid() else QDate.currentDate())
        self._mostra(scelta.isValid())

    def valore(self) -> str:
        return (self.data.date().toString("yyyy-MM-dd")
                if self.casella.isChecked() else "")


# -------------------------------------------------------------------- varie
def stile_tabella(tab, altezza_riga: int = 38) -> None:
    """Aspetto comune a tutte le tabelle: niente reticolo, intestazioni sobrie."""
    tab.setShowGrid(False)
    tab.setAlternatingRowColors(False)
    tab.setWordWrap(False)
    tab.setTextElideMode(Qt.ElideRight)
    tab.verticalHeader().setVisible(False)
    tab.verticalHeader().setDefaultSectionSize(altezza_riga)
    tab.verticalHeader().setMinimumSectionSize(24)
    testata = tab.horizontalHeader()
    testata.setHighlightSections(False)
    testata.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    testata.setFixedHeight(34)
    for colonna in range(tab.columnCount()):
        voce = tab.horizontalHeaderItem(colonna)
        if voce is not None:
            voce.setText(voce.text().upper())


def riga(*widgets, spaziatura: int = 10) -> QHBoxLayout:
    lay = QHBoxLayout()
    lay.setSpacing(spaziatura)
    for w in widgets:
        if w is None:
            lay.addStretch(1)
        elif isinstance(w, QWidget):
            lay.addWidget(w)
        else:
            lay.addLayout(w)
    return lay


def separatore() -> QFrame:
    f = QFrame()
    f.setObjectName("Separatore")
    f.setFrameShape(QFrame.HLine)
    return f


def etichetta(testo: str, oggetto: str = "", colore: str = "") -> QLabel:
    e = QLabel(testo)
    if oggetto:
        e.setObjectName(oggetto)
    if colore:
        e.setStyleSheet(f"color: {colore};")
    # un'etichetta che va a capo, senza questo, in un layout si prende
    # l'altezza di una riga sola e taglia il resto
    politica = e.sizePolicy()
    politica.setHeightForWidth(True)
    e.setSizePolicy(politica)
    return e


def pillola(testo: str, colore: str, sfondo: str) -> QLabel:
    e = QLabel(testo)
    e.setAlignment(Qt.AlignCenter)
    e.setStyleSheet(f"background: {trasparente(colore, 0.16)}; color: {colore};"
                    f" border-radius: 12px; padding: 4px 11px; font-size: 11px;"
                    f" font-weight: 650;")
    return e


class ZonaRilascio(QFrame):
    """Riquadro tratteggiato: ci si trascina dentro un file o una cartella.

    Un clic apre comunque la scelta manuale: trascinare è la scorciatoia,
    non l'unico modo.
    """

    scelto = Signal(str)
    chiesto_sfoglia = Signal()

    def __init__(self, colori: dict, testo: str = "", parent=None):
        super().__init__(parent)
        self.c = colori
        self.setObjectName("ZonaRilascio")
        self.setAcceptDrops(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(104)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(4)
        self.et_simbolo = QLabel("⤓")
        self.et_simbolo.setAlignment(Qt.AlignCenter)
        self.et_titolo = QLabel(testo or "Trascina qui la cartella o lo zip")
        self.et_titolo.setAlignment(Qt.AlignCenter)
        self.et_titolo.setWordWrap(True)
        self.et_nota = QLabel("oppure fai clic per sceglierlo tu")
        self.et_nota.setAlignment(Qt.AlignCenter)
        self.et_nota.setObjectName("NotaScheda")
        for w in (self.et_simbolo, self.et_titolo, self.et_nota):
            lay.addWidget(w)
        self._dipingi(False)

    def _dipingi(self, dentro: bool) -> None:
        colore = self.c["accento"] if dentro else self.c["bordo"]
        sfondo = (trasparente(self.c["accento"], 0.10) if dentro
                  else self.c["pannello2"])
        self.setStyleSheet(
            f"#ZonaRilascio {{ background: {sfondo}; border: 2px dashed {colore};"
            f" border-radius: 20px; }}")
        self.et_simbolo.setStyleSheet(
            f"font-size: 26px; color: "
            f"{self.c['accento'] if dentro else self.c['testo2']};")
        self.et_titolo.setStyleSheet(
            f"font-size: 13px; font-weight: 600; color: {self.c['testo']};")

    # ------------------------------------------------------------ trascinamento
    @staticmethod
    def _percorsi(evento) -> list[str]:
        dati = evento.mimeData()
        if not dati.hasUrls():
            return []
        return [u.toLocalFile() for u in dati.urls() if u.isLocalFile()]

    def dragEnterEvent(self, evento):
        if self._percorsi(evento):
            evento.acceptProposedAction()
            self._dipingi(True)

    def dragLeaveEvent(self, _):
        self._dipingi(False)

    def dropEvent(self, evento):
        self._dipingi(False)
        percorsi = self._percorsi(evento)
        if percorsi:
            evento.acceptProposedAction()
            self.scelto.emit(percorsi[0])

    def mousePressEvent(self, evento):
        if evento.button() == Qt.LeftButton:
            self.chiesto_sfoglia.emit()

    def mostra_scelta(self, percorso: str, nota: str = "") -> None:
        import os
        self.et_simbolo.setText("✓")
        self.et_titolo.setText(os.path.basename(percorso.rstrip("/")) or percorso)
        self.et_nota.setText(nota or percorso)
        self._dipingi(True)

    def azzera(self) -> None:
        self.et_simbolo.setText("⤓")
        self.et_titolo.setText("Trascina qui la cartella o lo zip")
        self.et_nota.setText("oppure fai clic per sceglierlo tu")
        self._dipingi(False)

    def aggiorna_tema(self, colori: dict) -> None:
        self.c = colori
        self._dipingi(False)


class _Deselezionatore(QObject):
    """Annulla la selezione quando si clicca in un punto vuoto della tabella."""

    def eventFilter(self, oggetto, evento):
        if evento.type() == QEvent.MouseButtonPress:
            tabella = oggetto.parent()
            if tabella is not None and not tabella.indexAt(
                    evento.position().toPoint()).isValid():
                tabella.clearSelection()
                tabella.setCurrentIndex(QModelIndex())
        return False


def abilita_deselezione(*tabelle) -> None:
    for tabella in tabelle:
        filtro = _Deselezionatore(tabella)
        tabella._filtro_deselezione = filtro
        tabella.viewport().installEventFilter(filtro)
        scorciatoia = QShortcut(QKeySequence(Qt.Key_Escape), tabella)
        scorciatoia.setContext(Qt.WidgetWithChildrenShortcut)
        scorciatoia.activated.connect(tabella.clearSelection)
