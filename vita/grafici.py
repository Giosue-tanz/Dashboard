"""Grafici disegnati con QPainter: nessuna libreria esterna, tutto offline.

Griglia leggera, area sfumata, suggerimenti al passaggio del mouse, anello di
progresso, mappa di calore e barra delle fasi del sonno.

Quando i dati cambiano, l'anello e le barre ci arrivano con un'animazione
breve: il movimento dice che il numero si è mosso, senza far aspettare nessuno.
"""
from __future__ import annotations

import math

from PySide6.QtCore import (QEasingCurve, QPointF, QRectF, Qt, QVariantAnimation,
                            Signal)
from PySide6.QtGui import (QColor, QFont, QFontMetrics, QLinearGradient, QPainter,
                           QPainterPath, QPen)
from PySide6.QtWidgets import QSizePolicy, QToolTip, QWidget

from .tema import PALETTE_GRAFICI
from .utils import compatto, numero


def _testo_semplice(v: float) -> str:
    return compatto(v)


class BaseGrafico(QWidget):
    def __init__(self, colori: dict, parent=None):
        super().__init__(parent)
        self.c = colori
        self.setObjectName("Grafico")       # il foglio di stile lo lascia trasparente
        self.setMinimumHeight(120)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)
        self.formato = _testo_semplice
        self._zone: list[tuple[QRectF, str]] = []

    def aggiorna_tema(self, colori: dict) -> None:
        self.c = colori
        self.update()

    def _pittore(self) -> QPainter:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.TextAntialiasing, True)
        return p

    def _margine_sinistro(self, p: QPainter, valori, minimo: float = 26.0) -> float:
        fm = QFontMetrics(p.font())
        largo = max((fm.horizontalAdvance(self.formato(v)) for v in valori), default=0.0)
        return max(minimo, largo + 10.0)

    def _vuoto(self, p: QPainter, messaggio: str = "Nessun dato da mostrare") -> None:
        p.setPen(QColor(self.c["testo2"]))
        f = QFont(); f.setPointSize(10); p.setFont(f)
        p.drawText(self.rect(), Qt.AlignCenter, messaggio)

    def mouseMoveEvent(self, ev):
        for rect, testo in self._zone:
            if rect.contains(ev.position()):
                QToolTip.showText(ev.globalPosition().toPoint(), testo, self)
                return
        QToolTip.hideText()
        super().mouseMoveEvent(ev)


class GraficoLinea(BaseGrafico):
    """Andamento temporale: una o più serie con area sfumata sulla prima."""

    def __init__(self, colori: dict, parent=None):
        super().__init__(colori, parent=parent)
        self.serie: list[tuple[str, list[tuple[str, float]], str]] = []
        self.riempi = True
        self.minimo_forzato: float | None = None
        self.massimo_forzato: float | None = None

    def imposta_serie(self, serie) -> None:
        """serie = [(nome, [(etichetta, valore), ...], colore), ...]"""
        self.serie = [s for s in serie if s[1]]
        self.update()

    def imposta_dati(self, punti, colore: str | None = None, nome: str = "") -> None:
        self.imposta_serie([(nome, punti, colore or self.c["accento"])])

    def paintEvent(self, _):
        p = self._pittore()
        self._zone.clear()
        if not self.serie or max(len(s[1]) for s in self.serie) < 2:
            self._vuoto(p); return

        valori = [v for _, punti, _ in self.serie for _, v in punti]
        vmin = self.minimo_forzato if self.minimo_forzato is not None else min(valori)
        vmax = self.massimo_forzato if self.massimo_forzato is not None else max(valori)
        if vmin == vmax:
            vmin -= 1; vmax += 1
        if self.minimo_forzato is None and self.massimo_forzato is None:
            margine = (vmax - vmin) * 0.12
            vmin -= margine; vmax += margine

        ridotto = self.height() < 150
        f = QFont(); f.setPointSize(8); p.setFont(f)
        tacche = [vmax - (vmax - vmin) * i / 4 for i in range(5)]
        ml = self._margine_sinistro(p, tacche)
        mr, mt = 10, (14 if len(self.serie) < 2 or ridotto else 26)
        mb = 10 if ridotto else 28
        area = QRectF(ml, mt, max(10.0, self.width() - ml - mr),
                      max(10.0, self.height() - mt - mb))

        for i, val in enumerate(tacche):
            y = area.top() + area.height() * i / 4
            p.setPen(QPen(QColor(self.c["griglia"]), 1))
            p.drawLine(QPointF(area.left(), y), QPointF(area.right(), y))
            p.setPen(QColor(self.c["testo2"]))
            p.drawText(QRectF(0, y - 9, ml - 10, 18),
                       Qt.AlignRight | Qt.AlignVCenter, self.formato(val))

        # legenda in alto quando le serie sono più d'una
        if len(self.serie) > 1 and not ridotto:
            x = area.left()
            for nome, _, colore in self.serie:
                p.setPen(Qt.NoPen); p.setBrush(QColor(colore))
                p.drawRoundedRect(QRectF(x, 2, 9, 9), 3, 3)
                p.setPen(QColor(self.c["testo2"]))
                largo = QFontMetrics(f).horizontalAdvance(nome)
                p.drawText(QRectF(x + 13, -2, largo + 10, 16),
                           Qt.AlignLeft | Qt.AlignVCenter, nome)
                x += 13 + largo + 18

        principale = self.serie[0][1]
        for indice, (nome, punti, colore) in enumerate(self.serie):
            n = len(punti)
            if n < 2:
                continue

            def xy(i: int, v: float, n=n) -> QPointF:
                return QPointF(area.left() + area.width() * i / (n - 1),
                               area.bottom() - (v - vmin) / (vmax - vmin) * area.height())

            linea = QPainterPath(xy(0, punti[0][1]))
            for i in range(1, n):
                linea.lineTo(xy(i, punti[i][1]))

            if self.riempi and indice == 0:
                sotto = QPainterPath(linea)
                sotto.lineTo(QPointF(area.right(), area.bottom()))
                sotto.lineTo(QPointF(area.left(), area.bottom()))
                sotto.closeSubpath()
                col = QColor(colore)
                grad = QLinearGradient(0, area.top(), 0, area.bottom())
                grad.setColorAt(0, QColor(col.red(), col.green(), col.blue(), 72))
                grad.setColorAt(1, QColor(col.red(), col.green(), col.blue(), 0))
                p.setPen(Qt.NoPen); p.setBrush(grad); p.drawPath(sotto)

            p.setBrush(Qt.NoBrush)
            penna = QPen(QColor(colore), 2.4)
            penna.setCapStyle(Qt.RoundCap); penna.setJoinStyle(Qt.RoundJoin)
            p.setPen(penna)
            p.drawPath(linea)

            pallini = n <= 16
            for i, (etic, v) in enumerate(punti):
                pt = xy(i, v)
                if pallini:
                    p.setPen(Qt.NoPen); p.setBrush(QColor(colore))
                    p.drawEllipse(pt, 2.6, 2.6)
                if indice == 0:
                    self._zone.append(
                        (QRectF(pt.x() - 11, area.top(), 22, area.height()),
                         f"{etic}: " + "  ·  ".join(
                             f"{s[0] or 'valore'} {self.formato(s[1][i][1])}"
                             for s in self.serie if len(s[1]) == n)))

        if not ridotto:
            # un'etichetta ogni 70 px: con tanti punti si diradano da sole
            passo = max(1, math.ceil(len(principale) / max(1.0, area.width() / 70)))
            p.setPen(QColor(self.c["testo2"]))
            ultimo = len(principale) - 1
            for i, (etic, _) in enumerate(principale):
                if i % passo and not (i == ultimo and ultimo % passo > passo / 2):
                    continue
                x = area.left() + area.width() * i / max(1, len(principale) - 1)
                p.drawText(QRectF(x - 36, area.bottom() + 5, 72, 16),
                           Qt.AlignCenter, etic)


class GraficoBarre(BaseGrafico):
    """Barre verticali, singole o raggruppate; opzionalmente orizzontali.

    Un valore `None` non è uno zero: è un giorno di cui non si sa niente.
    Al suo posto resta un trattino sulla linea di base.
    """

    SOTTO = 26              # spazio sotto le barre per le etichette dell'asse
    TRACCIA_MINIMA = 36     # sotto a tanto le barre non direbbero più niente

    def __init__(self, colori: dict, parent=None):
        super().__init__(colori, parent=parent)
        self.dati: list[tuple[str, list[float]]] = []
        self.serie: list[tuple[str, str]] = []
        self.orizzontale = False
        self.evidenzia_ultima = False
        self.crescita = 1.0        # 0..1 mentre le barre salgono
        self.riferimento: float | None = None      # linea dell'obiettivo

    def imposta_dati(self, dati, serie) -> None:
        self.dati, self.serie = dati, serie
        self._cresci()
        self.update()

    def _cresci(self) -> None:
        """Le barre salgono dal basso quando arrivano dati nuovi."""
        if not hasattr(self, "_moto"):
            self._moto = QVariantAnimation(self)
            self._moto.setDuration(520)
            self._moto.setEasingCurve(QEasingCurve.OutCubic)
            self._moto.valueChanged.connect(self._passo)
        self._moto.stop()
        if not self.isVisible():
            self.crescita = 1.0
            return
        self._moto.setStartValue(0.0)
        self._moto.setEndValue(1.0)
        self._moto.start()

    def _passo(self, valore) -> None:
        self.crescita = float(valore)
        self.update()

    def paintEvent(self, _):
        p = self._pittore()
        self._zone.clear()
        if not self.dati:
            self._vuoto(p); return
        if self.orizzontale:
            self._orizzontale(p); return

        # in poco spazio sparisce prima la legenda, poi le date, infine si
        # diradano le tacche: le date se ne vanno solo quando non starebbero
        compatta = self.height() < 150
        mt = 12 if (compatta or len(self.serie) < 2) else 30
        etichette = self.height() - mt - self.SOTTO >= self.TRACCIA_MINIMA
        mb = self.SOTTO if etichette else 10
        utile = max(10.0, self.height() - mt - mb)

        presenti = [x for _, v in self.dati for x in v if x is not None]
        massimo = max(presenti) if presenti else 0
        if self.riferimento:
            massimo = max(massimo, self.riferimento)
        massimo = (massimo or 1) * 1.15
        f = QFont(); f.setPointSize(8); p.setFont(f)

        passi = 4 if utile >= 92 else 2
        tacche = [massimo - massimo * i / passi for i in range(passi + 1)]
        ml = self._margine_sinistro(p, tacche)
        mr = 10
        area = QRectF(ml, mt, max(10.0, self.width() - ml - mr), utile)

        for i, val in enumerate(tacche):
            y = area.top() + area.height() * i / passi
            p.setPen(QPen(QColor(self.c["griglia"]), 1))
            p.drawLine(QPointF(area.left(), y), QPointF(area.right(), y))
            p.setPen(QColor(self.c["testo2"]))
            p.drawText(QRectF(0, y - 9, ml - 10, 18),
                       Qt.AlignRight | Qt.AlignVCenter, self.formato(val))

        if len(self.serie) > 1 and not compatta:
            x = area.left()
            for nome, colore in self.serie:
                p.setPen(Qt.NoPen); p.setBrush(QColor(colore))
                p.drawRoundedRect(QRectF(x, 8, 9, 9), 3, 3)
                p.setPen(QColor(self.c["testo2"]))
                largo = QFontMetrics(f).horizontalAdvance(nome)
                p.drawText(QRectF(x + 13, 4, largo + 10, 16),
                           Qt.AlignLeft | Qt.AlignVCenter, nome)
                x += 13 + largo + 18

        if self.riferimento:
            y = area.bottom() - (self.riferimento / massimo) * area.height()
            penna = QPen(QColor(self.c["testo2"]), 1, Qt.DashLine)
            p.setPen(penna)
            p.drawLine(QPointF(area.left(), y), QPointF(area.right(), y))

        n_gruppi = len(self.dati)
        n_serie = max(1, len(self.serie))
        largo_gruppo = area.width() / n_gruppi
        largo_barra = max(2.0, min(30.0, (largo_gruppo * 0.72) / n_serie))

        for g, (etic, valori) in enumerate(self.dati):
            centro = area.left() + largo_gruppo * (g + 0.5)
            inizio = centro - (largo_barra * n_serie) / 2
            for s, v in enumerate(valori):
                x = inizio + s * largo_barra + 1.2
                largo = max(1.0, largo_barra - 2.4)
                nome_s = self.serie[s][0] if s < len(self.serie) else ""
                if v is None:
                    # niente dato: un trattino spento, non una barra a zero
                    rect = QRectF(x, area.bottom() - 2.4, largo, 2.4)
                    p.setPen(Qt.NoPen); p.setBrush(QColor(self.c["griglia"]))
                    p.drawRoundedRect(rect, 1.2, 1.2)
                    self._zone.append((rect.adjusted(-2, -12, 2, 10),
                                       f"{etic}" + (f" · {nome_s}" if nome_s else "")
                                       + ": nessun dato"))
                    continue
                altezza = max(1.0, (v / massimo) * area.height()) if v else 1.0
                altezza *= self.crescita
                rect = QRectF(x, area.bottom() - altezza, largo, max(1.0, altezza))
                colore = QColor(self.serie[s][1] if s < len(self.serie)
                                else PALETTE_GRAFICI[s % 12])
                if self.evidenzia_ultima and g != n_gruppi - 1:
                    colore.setAlpha(110)
                p.setPen(Qt.NoPen); p.setBrush(colore)
                # candele a pastiglia, come One UI: raggio pieno, mai spigoli
                raggio = largo / 2
                p.drawRoundedRect(rect, raggio, min(raggio, rect.height() / 2))
                self._zone.append((rect.adjusted(-2, -8, 2, 8),
                                   f"{etic}" + (f" · {nome_s}" if nome_s else "") +
                                   f": {self.formato(v)}"))
            if etichette:
                p.setPen(QColor(self.c["testo2"]))
                p.drawText(QRectF(centro - largo_gruppo / 2, area.bottom() + 4,
                                  largo_gruppo, 16), Qt.AlignCenter, etic)

    def _orizzontale(self, p: QPainter) -> None:
        f = QFont(); f.setPointSize(9); p.setFont(f)
        fm = QFontMetrics(f)
        ml = min(170.0, max(70.0, max(
            (fm.horizontalAdvance(e[:26]) for e, _ in self.dati), default=70) + 12))
        mr = 64
        area = QRectF(ml, 6, max(10.0, self.width() - ml - mr),
                      max(10.0, self.height() - 12))
        presenti = [x for _, v in self.dati for x in v if x is not None]
        massimo = (max(presenti) if presenti else 0) or 1
        n = len(self.dati)
        passo = min(34.0, area.height() / max(1, n))
        for i, (etic, valori) in enumerate(self.dati):
            v = (valori[0] if valori else 0) or 0
            y = area.top() + i * passo + passo * 0.2
            h = passo * 0.6
            colore = self.serie[i][1] if i < len(self.serie) else PALETTE_GRAFICI[i % 12]
            p.setPen(QColor(self.c["testo"]))
            p.drawText(QRectF(2, y - 3, ml - 12, h + 6),
                       Qt.AlignRight | Qt.AlignVCenter, etic[:26])
            largo = max(2.0, (v / massimo) * area.width() * self.crescita)
            rect = QRectF(area.left(), y, largo, h)
            p.setPen(Qt.NoPen); p.setBrush(QColor(colore))
            p.drawRoundedRect(rect, min(h / 2, 9), h / 2)
            p.setPen(QColor(self.c["testo2"]))
            p.drawText(QRectF(area.left() + largo + 8, y - 3, mr - 10, h + 6),
                       Qt.AlignLeft | Qt.AlignVCenter, self.formato(v))
            self._zone.append((rect, f"{etic}: {self.formato(v)}"))


class GraficoCiambella(BaseGrafico):
    """Ripartizione percentuale con legenda laterale."""

    def __init__(self, colori: dict, parent=None):
        super().__init__(colori, parent=parent)
        self.dati: list[tuple[str, float, str]] = []
        self.centro_testo = ""
        self.centro_nota = ""

    def imposta_dati(self, dati, centro_testo="", centro_nota="") -> None:
        self.dati = dati
        self.centro_testo = centro_testo
        self.centro_nota = centro_nota
        self.update()

    def paintEvent(self, _):
        p = self._pittore()
        self._zone.clear()
        totale = sum(v for _, v, _ in self.dati)
        if totale <= 0:
            self._vuoto(p); return

        lato = max(80.0, min(self.width() * 0.52, self.height()) - 14)
        rect = QRectF(12, (self.height() - lato) / 2, lato, lato)
        spessore = lato * 0.2
        interno = rect.adjusted(spessore, spessore, -spessore, -spessore)

        angolo = 90 * 16
        for i, (nome, valore, colore) in enumerate(self.dati):
            esteso = int(-360 * 16 * (valore / totale))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(colore or PALETTE_GRAFICI[i % 12]))
            p.drawPie(rect, angolo, esteso)
            angolo += esteso
        p.setBrush(QColor(self.c["pannello"]))
        p.drawEllipse(interno)

        f = QFont(); f.setBold(True)
        dim = max(7, min(15, int(interno.width() / 6.5)))
        f.setPointSize(dim)
        while dim > 6 and QFontMetrics(f).horizontalAdvance(
                self.centro_testo) > interno.width() - 10:
            dim -= 1; f.setPointSize(dim)
        p.setFont(f); p.setPen(QColor(self.c["testo"]))
        con_nota = interno.height() > 52 and self.centro_nota
        p.drawText(interno.adjusted(0, -8 if con_nota else 0, 0, -8 if con_nota else 0),
                   Qt.AlignCenter, self.centro_testo)
        if con_nota:
            f.setPointSize(max(6, dim - 5)); f.setBold(False); p.setFont(f)
            p.setPen(QColor(self.c["testo2"]))
            p.drawText(interno.adjusted(0, 15, 0, 15), Qt.AlignCenter, self.centro_nota)

        x = rect.right() + 20
        f.setPointSize(9); f.setBold(False); p.setFont(f)
        righe = max(1, int((self.height() - 8) // 21))
        for i, (nome, valore, colore) in enumerate(self.dati[:righe]):
            y = 6 + i * 21
            p.setPen(Qt.NoPen); p.setBrush(QColor(colore or PALETTE_GRAFICI[i % 12]))
            p.drawRoundedRect(QRectF(x, y + 4, 10, 10), 3, 3)
            p.setPen(QColor(self.c["testo"]))
            quota = valore / totale * 100
            p.drawText(QRectF(x + 16, y, max(40.0, self.width() - x - 20), 18),
                       Qt.AlignLeft | Qt.AlignVCenter,
                       f"{nome[:22]}  ·  {quota:.0f}%")
            self._zone.append((QRectF(x, y, self.width() - x, 20),
                               f"{nome}: {self.formato(valore)} ({quota:.1f}%)"))


class Anello(QWidget):
    """Anello di progresso con valore al centro: l'obiettivo del giorno."""

    def __init__(self, colori: dict, colore: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("Grafico")
        self.c = colori
        self.colore = colore or colori["accento"]
        self.quota = 0.0          # 0..1 (oltre 1 disegna il secondo giro)
        self._disegnata = 0.0     # quella che si vede: insegue `quota`
        self.testo = "—"
        self.nota = ""
        self.setMinimumSize(92, 92)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._moto = QVariantAnimation(self)
        self._moto.setDuration(640)
        self._moto.setEasingCurve(QEasingCurve.OutCubic)
        self._moto.valueChanged.connect(self._passo)

    def _passo(self, valore) -> None:
        self._disegnata = float(valore)
        self.update()

    def imposta(self, quota: float, testo: str, nota: str = "",
                colore: str = "") -> None:
        self.quota = max(0.0, quota)
        self.testo, self.nota = testo, nota
        if colore:
            self.colore = colore
        self._moto.stop()
        if not self.isVisible() or abs(self.quota - self._disegnata) < 0.004:
            self._disegnata = self.quota
            self.update()
            return
        self._moto.setStartValue(self._disegnata)
        self._moto.setEndValue(self.quota)
        self._moto.start()

    def aggiorna_tema(self, colori: dict) -> None:
        self.c = colori
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        lato = min(self.width(), self.height()) - 6
        if lato < 24:
            return
        spessore = max(7.0, lato * 0.12)
        rect = QRectF((self.width() - lato) / 2 + spessore / 2,
                      (self.height() - lato) / 2 + spessore / 2,
                      lato - spessore, lato - spessore)
        penna = QPen(QColor(self.c["griglia"]), spessore)
        penna.setCapStyle(Qt.RoundCap)
        p.setPen(penna); p.setBrush(Qt.NoBrush)
        p.drawArc(rect, 0, 360 * 16)

        quota = self._disegnata
        if quota > 0:
            penna.setColor(QColor(self.colore))
            p.setPen(penna)
            p.drawArc(rect, 90 * 16, -int(360 * 16 * min(1.0, quota)))
            if quota > 1:              # secondo giro appena accennato
                col = QColor(self.colore); col.setAlpha(120)
                penna.setColor(col); penna.setWidthF(spessore * 0.45)
                p.setPen(penna)
                p.drawArc(rect.adjusted(spessore * 0.4, spessore * 0.4,
                                        -spessore * 0.4, -spessore * 0.4),
                          90 * 16, -int(360 * 16 * min(1.0, quota - 1)))

        f = QFont(); f.setBold(True)
        dim = max(9, int(lato * 0.2))
        f.setPixelSize(dim); p.setFont(f)
        while dim > 8 and QFontMetrics(f).horizontalAdvance(self.testo) > rect.width() - 12:
            dim -= 1; f.setPixelSize(dim); p.setFont(f)
        p.setPen(QColor(self.c["testo"]))
        con_nota = bool(self.nota) and lato > 70
        p.drawText(rect.adjusted(0, -dim * 0.35 if con_nota else 0, 0,
                                 -dim * 0.35 if con_nota else 0),
                   Qt.AlignCenter, self.testo)
        if con_nota:
            f.setBold(False); f.setPixelSize(max(9, int(dim * 0.46))); p.setFont(f)
            p.setPen(QColor(self.c["testo2"]))
            p.drawText(rect.adjusted(0, dim * 0.85, 0, dim * 0.85),
                       Qt.AlignCenter, self.nota)


class BarraFasi(QWidget):
    """Barra a segmenti: le fasi del sonno, o qualunque ripartizione in fila."""

    def __init__(self, colori: dict, parent=None):
        super().__init__(parent)
        self.setObjectName("Grafico")
        self.c = colori
        self.fasi: list[tuple[str, float, str]] = []
        self.setFixedHeight(13)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMouseTracking(True)

    def imposta_dati(self, fasi) -> None:
        self.fasi = [f for f in fasi if f[1] > 0]
        self.setToolTip("   ·   ".join(f"{n}: {v:.0f} min" for n, v, _ in self.fasi))
        self.update()

    def aggiorna_tema(self, colori: dict) -> None:
        self.c = colori
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        totale = sum(v for _, v, _ in self.fasi)
        raggio = self.height() / 2
        if totale <= 0:
            p.setPen(Qt.NoPen); p.setBrush(QColor(self.c["griglia"]))
            p.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), raggio, raggio)
            return
        percorso = QPainterPath()
        percorso.addRoundedRect(QRectF(0, 0, self.width(), self.height()), raggio, raggio)
        p.setClipPath(percorso)
        x = 0.0
        p.setPen(Qt.NoPen)
        for nome, valore, colore in self.fasi:
            largo = self.width() * valore / totale
            p.setBrush(QColor(colore))
            p.drawRect(QRectF(x, 0, largo + 0.6, self.height()))
            x += largo


class MappaCalore(QWidget):
    """Calendario a quadretti: un colore per giorno (umore, abitudini, ore)."""

    giorno_scelto = Signal(str)
    LATO_MASSIMO = 46.0        # oltre, i quadretti diventano mattoni

    def __init__(self, colori: dict, parent=None):
        super().__init__(parent)
        self.setObjectName("Grafico")
        self.c = colori
        self.dati: dict[str, tuple[float, str]] = {}   # data -> (quota 0..1, colore)
        self.giorni: list[str] = []
        self.etichette = True
        self.setMinimumHeight(90)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)
        self._celle: list[tuple[QRectF, str]] = []
        self._suggerimenti: dict[str, str] = {}

    def imposta_dati(self, giorni: list[str], dati: dict, suggerimenti: dict | None = None):
        self.giorni, self.dati = giorni, dati
        self._suggerimenti = suggerimenti or {}
        self.update()

    def aggiorna_tema(self, colori: dict) -> None:
        self.c = colori
        self.update()

    def paintEvent(self, _):
        from datetime import date as _date
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        self._celle.clear()
        if not self.giorni:
            p.setPen(QColor(self.c["testo2"]))
            p.drawText(self.rect(), Qt.AlignCenter, "Nessun dato da mostrare")
            return

        salto = _date.fromisoformat(self.giorni[0]).weekday()
        settimane = math.ceil((len(self.giorni) + salto) / 7)
        intestazione = 16 if self.etichette else 0

        # Due modi di posare lo stesso calendario: i giorni in colonna (sette
        # colonne, una riga per settimana) o le settimane in colonna (sette
        # righe). Vince quello che fa i quadretti più grandi.
        verticale = min(self.width() / 7,
                        max(12.0, self.height() - intestazione) / max(1, settimane))
        orizzontale = min(self.width() / max(1, settimane), self.height() / 7)
        disteso = orizzontale > verticale * 1.05
        if disteso:
            colonne, righe, intestazione = settimane, 7, 0
        else:
            colonne, righe = 7, settimane

        utile = max(12.0, self.height() - intestazione)
        naturale = min(self.width() / colonne, utile / max(1, righe))
        lato = max(6.0, min(naturale * 0.86, self.LATO_MASSIMO))
        # con quadretti grandi le colonne si allargano a riempire il riquadro;
        # con quadretti piccoli restano strette e il blocco si centra
        passo_x = min(self.width() / colonne, lato * 1.45)
        passo_y = min(utile / max(1, righe), lato * 1.45)
        sinistra = (self.width() - passo_x * colonne) / 2
        alto = intestazione + max(0.0, (utile - passo_y * righe) / 2)

        if self.etichette and not disteso:
            f = QFont(); f.setPointSize(8); f.setBold(True); p.setFont(f)
            p.setPen(QColor(self.c["testo2"]))
            for i, nome in enumerate("LMMGVSD"):
                p.drawText(QRectF(sinistra + i * passo_x, 0, passo_x, intestazione),
                           Qt.AlignCenter, nome)

        for indice, giorno in enumerate(self.giorni):
            posizione = indice + salto
            if disteso:
                colonna, riga = divmod(posizione, 7)
            else:
                riga, colonna = divmod(posizione, 7)
            x = sinistra + colonna * passo_x + (passo_x - lato) / 2
            y = alto + riga * passo_y + (passo_y - lato) / 2
            rect = QRectF(x, y, lato, lato)
            quota, colore = self.dati.get(giorno, (0.0, ""))
            p.setPen(Qt.NoPen)
            if not colore:
                p.setBrush(QColor(self.c["griglia"]))
            else:
                col = QColor(colore)
                col.setAlpha(int(70 + 185 * max(0.0, min(1.0, quota))))
                p.setBrush(col)
            p.drawRoundedRect(rect, lato * 0.34, lato * 0.34)
            if giorno == _date.today().isoformat():
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(QColor(self.c["testo"]), max(1.2, lato * 0.07)))
                p.drawRoundedRect(rect.adjusted(-2, -2, 2, 2),
                                  lato * 0.32, lato * 0.32)
            self._celle.append((rect, giorno))

    def mouseMoveEvent(self, ev):
        for rect, giorno in self._celle:
            if rect.contains(ev.position()):
                from .utils import data_it
                QToolTip.showText(ev.globalPosition().toPoint(),
                                  self._suggerimenti.get(giorno, data_it(giorno)), self)
                return
        QToolTip.hideText()

    def mousePressEvent(self, ev):
        for rect, giorno in self._celle:
            if rect.contains(ev.position()):
                self.giorno_scelto.emit(giorno)
                return


class Sparkline(QWidget):
    """Micro-grafico per le schede riepilogative."""

    def __init__(self, colori: dict, parent=None):
        super().__init__(parent)
        self.setObjectName("Grafico")
        self.c = colori
        self.valori: list[float] = []
        self.colore = colori["accento"]
        self.setFixedHeight(32)

    def imposta_dati(self, valori: list[float], colore: str | None = None) -> None:
        self.valori = [v for v in valori if v is not None]
        if colore:
            self.colore = colore
        self.update()

    def aggiorna_tema(self, colori: dict) -> None:
        self.c = colori
        self.update()

    def paintEvent(self, _):
        if len(self.valori) < 2:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        vmin, vmax = min(self.valori), max(self.valori)
        if vmin == vmax:
            vmin -= 1; vmax += 1
        w, h = self.width(), self.height() - 6
        percorso = QPainterPath()
        for i, v in enumerate(self.valori):
            x = w * i / (len(self.valori) - 1)
            y = 3 + h - (v - vmin) / (vmax - vmin) * h
            percorso.moveTo(x, y) if i == 0 else percorso.lineTo(x, y)
        penna = QPen(QColor(self.colore), 1.8)
        penna.setCapStyle(Qt.RoundCap); penna.setJoinStyle(Qt.RoundJoin)
        p.setPen(penna)
        p.drawPath(percorso)
