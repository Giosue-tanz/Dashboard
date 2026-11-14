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
from .utils import compatto, durata, minuti_notturni, minuti_ore, numero, ore_minuti


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
        # cosa scrivere quando non c'è niente da disegnare. Chi lo sa può
        # cambiarlo e dire **perché** è vuoto: «una voce sola, oggi» spiega,
        # «nessun dato» lascia lì a chiedersi se si è rotto qualcosa
        self.vuoto = "Nessun dato da mostrare"
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

    def _vuoto(self, p: QPainter, messaggio: str = "") -> None:
        p.setPen(QColor(self.c["testo2"]))
        f = QFont(); f.setPointSize(10); p.setFont(f)
        p.drawText(self.rect().adjusted(12, 0, -12, 0),
                   Qt.AlignCenter | Qt.TextWordWrap, messaggio or self.vuoto)

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
        # a chi tiene già una sua legenda che si tocca — una riga di
        # pastiglie accendibili, sotto il grafico — quella disegnata qui
        # sopra sarebbe la stessa cosa detta due volte, una muta e una viva
        self.mostra_legenda = True
        # i pallini su ogni punto: utili con pochi dati (si contano i giorni
        # scritti), ma su una linea morbida con tanti punti sono solo
        # puntini che si accavallano — qui si può spegnerli per un disegno
        # più pulito, da linea sola, senza perdere il suggerimento al passaggio
        self.mostra_punti = True

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
        con_legenda = len(self.serie) > 1 and not ridotto and self.mostra_legenda
        mr, mt = 10, (26 if con_legenda else 14)
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

        # legenda in alto quando le serie sono più d'una — a meno che non
        # ce ne sia già una viva sotto il grafico (`mostra_legenda = False`)
        if con_legenda:
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

            pallini = self.mostra_punti and n <= 16
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
        # quale barra è «quella di adesso»: -1 vuol dire nessuna. Con le
        # settimane del calendario l'ultima barra è la domenica, che di
        # mercoledì deve ancora arrivare: accendere quella era una bugia
        self.evidenziata = -1
        self.crescita = 1.0        # 0..1 mentre le barre salgono
        self.riferimento: float | None = None      # linea dell'obiettivo
        self.pallino_media = False                 # pallino per la media giornaliera

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
        # L'obiettivo alza la scala solo se è a portata. Con 10.000 passi di
        # obiettivo e giornate da tremila, tenerlo in cima schiacciava tutte
        # le candele nel quinto basso: in quel caso comanda il dato, e
        # l'obiettivo resta una riga tratteggiata appena sopra.
        self._fuori_scala = bool(self.riferimento and massimo
                                 and self.riferimento > massimo * 2)
        if self.riferimento and not self._fuori_scala:
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
            fuori = getattr(self, "_fuori_scala", False)
            y = (area.top() + 1 if fuori else
                 area.bottom() - (self.riferimento / massimo) * area.height())
            penna = QPen(QColor(self.c["testo2"]), 1, Qt.DashLine)
            p.setPen(penna)
            p.drawLine(QPointF(area.left(), y), QPointF(area.right(), y))
            if fuori:
                # l'obiettivo è lontano: lo si dice, invece di fingere la scala
                p.setPen(QColor(self.c["testo2"]))
                p.drawText(QRectF(area.right() - 150, y + 2, 150, 14),
                           Qt.AlignRight | Qt.AlignVCenter,
                           f"obiettivo {self.formato(self.riferimento)} ↑")

        n_gruppi = len(self.dati)
        n_serie = max(1, len(self.serie))
        largo_gruppo = area.width() / n_gruppi
        largo_barra = max(2.0, min(30.0, (largo_gruppo * 0.72) / n_serie))

        # con tanti giorni le date si sovrappongono: se ne scrive una ogni
        # tanto, quante ne stanno nello spazio che c'è
        serve = max((QFontMetrics(f).horizontalAdvance(e) for e, _ in self.dati),
                    default=20) + 10
        ogni = max(1, int(serve / max(1.0, largo_gruppo) + 0.999))
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
                if self.evidenzia_ultima:
                    quale = (self.evidenziata if self.evidenziata >= 0
                             else n_gruppi - 1)
                    if g != quale:
                        colore.setAlpha(110)
                p.setPen(Qt.NoPen); p.setBrush(colore)
                # candele a pastiglia, come One UI: raggio pieno, mai spigoli
                raggio = largo / 2
                p.drawRoundedRect(rect, raggio, min(raggio, rect.height() / 2))
                if self.pallino_media and rect.height() >= 8:
                    cy = rect.top() + min(raggio, rect.height() / 2)
                    cx = rect.center().x()
                    r_dot = max(2.0, min(largo * 0.22, rect.height() * 0.35))
                    p.setPen(Qt.NoPen)
                    p.setBrush(QColor(self.c["pannello"]))
                    p.drawEllipse(QPointF(cx, cy), r_dot, r_dot)
                testo_val = f"media {self.formato(v)}" if self.pallino_media else self.formato(v)
                self._zone.append((rect.adjusted(-2, -8, 2, 8),
                                   f"{etic}" + (f" · {nome_s}" if nome_s else "") +
                                   f": {testo_val}"))
            if etichette and g % ogni == 0:
                p.setPen(QColor(self.c["testo2"]))
                p.drawText(QRectF(centro - largo_gruppo, area.bottom() + 4,
                                  largo_gruppo * 2, 16), Qt.AlignCenter, etic)

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


class GraficoIntervalli(BaseGrafico):
    """Capsule da un minimo a un massimo, col valore medio segnato sopra.

    È il disegno giusto per il battito: in un'ora (o in un giorno) il cuore
    non fa un numero solo, fa un intervallo. Una barra che parte da zero
    direbbe una bugia; una capsula che va da 57 a 106 racconta la verità, e
    il puntino dice dove sta la media.
    """

    def __init__(self, colori: dict, colore: str = "", parent=None):
        super().__init__(colori, parent)
        self.dati: list[tuple[str, float, float, float]] = []   # etichetta, min, media, max
        self.colore = colore or colori["accento"]
        self.unita = "bpm"
        self.setMinimumHeight(120)

    def imposta_dati(self, dati, colore: str = "") -> None:
        self.dati = [d for d in dati]
        if colore:
            self.colore = colore
        self.update()

    def paintEvent(self, _):
        p = self._pittore()
        self._zone = []
        presenti = [v for _, basso, _, alto in self.dati
                    for v in (basso, alto) if v]
        if not presenti:
            self._vuoto(p, "Nessuna misura")
            return
        f = QFont(); f.setPointSize(9); p.setFont(f)
        fm = QFontMetrics(f)

        minimo = max(0.0, min(presenti) - 6)
        massimo = max(presenti) + 6
        campo = max(1.0, massimo - minimo)
        sinistra = self._margine_sinistro(p, (minimo, massimo))
        area = QRectF(sinistra, 8.0, max(10.0, self.width() - sinistra - 6),
                      max(10.0, self.height() - 8 - 22))

        # le righe di riferimento, con il valore a sinistra
        p.setPen(QColor(self.c["testo2"]))
        for quota in (0.0, 0.5, 1.0):
            y = area.bottom() - quota * area.height()
            p.setPen(QPen(QColor(self.c["griglia"]), 1))
            p.drawLine(QPointF(area.left(), y), QPointF(area.right(), y))
            p.setPen(QColor(self.c["testo2"]))
            p.drawText(QRectF(2, y - 8, sinistra - 8, 16),
                       Qt.AlignRight | Qt.AlignVCenter,
                       self.formato(minimo + quota * campo))

        passo = area.width() / max(1, len(self.dati))
        largo = max(5.0, min(26.0, passo * 0.55))
        for i, (etichetta, basso, media_, alto) in enumerate(self.dati):
            centro = area.left() + passo * (i + 0.5)
            if not alto:
                continue
            basso = basso or alto
            cima = area.bottom() - (alto - minimo) / campo * area.height()
            fondo = area.bottom() - (basso - minimo) / campo * area.height()
            rect = QRectF(centro - largo / 2, cima, largo,
                          max(largo, fondo - cima))
            colore = QColor(self.colore)
            colore.setAlpha(190)
            p.setPen(Qt.NoPen); p.setBrush(colore)
            p.drawRoundedRect(rect, largo / 2, largo / 2)
            if media_:
                y = area.bottom() - (media_ - minimo) / campo * area.height()
                p.setBrush(QColor(self.c["pannello"]))
                p.drawEllipse(QPointF(centro, y), largo * 0.22, largo * 0.22)
            self._zone.append((rect.adjusted(-4, -6, 4, 6),
                               f"{etichetta}: {self.formato(basso)}–"
                               f"{self.formato(alto)} {self.unita}"
                               + (f" · media {self.formato(media_)}" if media_ else "")))

        # le etichette in fondo: si scrivono solo quelle che ci stanno
        p.setPen(QColor(self.c["testo2"]))
        larghezza_minima = max(
            (fm.horizontalAdvance(e) for e, *_ in self.dati), default=20) + 8
        ogni = max(1, int(larghezza_minima / max(1.0, passo) + 0.5))
        for i, (etichetta, *_) in enumerate(self.dati):
            if i % ogni:
                continue
            centro = area.left() + passo * (i + 0.5)
            p.drawText(QRectF(centro - passo, area.bottom() + 4, passo * 2, 16),
                       Qt.AlignCenter, etichetta)


class GraficoSonno(BaseGrafico):
    """Non le ore di sonno: l'orario. Una barra sospesa da quando sei andato
    a letto a quando ti sei svegliato.

    Due notti da otto ore si somigliano pochissimo se una va dalle 23 alle 7
    e l'altra dall'1 di notte alle 9 del mattino: una barra che parte da
    zero le farebbe sembrare identiche. Qui si vede a che ora, non solo per
    quanto.

    Una notte senza orario registrato (il sonno c'è, ma viene da un'importazione
    che non porta l'ora di inizio e fine) resta un trattino sulla linea di
    base, come i giorni senza dato nelle barre: non si inventa un orario.
    """

    SOTTO = 26

    def __init__(self, colori: dict, colore: str = "", parent=None):
        super().__init__(colori, parent=parent)
        # etichetta, orario a letto ("23:40" o ""), orario sveglia, durata in minuti
        self.dati: list[tuple[str, str, str, float]] = []
        self.colore = colore or colori["accento"]
        self.evidenzia_ultima = False
        self.evidenziata = -1
        self.formato = minuti_ore

    def imposta_dati(self, dati, colore: str = "") -> None:
        self.dati = list(dati)
        if colore:
            self.colore = colore
        self.update()

    @staticmethod
    def _intervallo(a_letto: str, sveglia: str) -> tuple[int, int] | None:
        """(minuti a letto, minuti sveglia) su un asse che comincia la sera
        (vedi `minuti_notturni`): così 23:40 e 01:07 stanno nell'ordine
        giusto — la seconda dopo la prima — qualunque sia l'ordine in cui
        arrivano i dati. `None` se manca l'uno o l'altro orario.
        """
        if not a_letto or not sveglia:
            return None
        inizio = minuti_notturni(ore_minuti(a_letto))
        fine = minuti_notturni(ore_minuti(sveglia))
        if fine <= inizio:
            fine += 1440
        return inizio, fine

    def paintEvent(self, _):
        p = self._pittore()
        self._zone = []
        if not self.dati:
            self._vuoto(p); return

        intervalli = [self._intervallo(a, s) for _, a, s, _ in self.dati]
        if not any(intervalli):
            self._vuoto(p, "Nessun orario registrato per questo periodo"); return

        presenti = [x for iv in intervalli if iv for x in iv]
        minimo = (min(presenti) // 60) * 60
        massimo = -(-max(presenti) // 60) * 60      # arrotondato all'ora, per eccesso
        if massimo == minimo:
            massimo += 60

        f = QFont(); f.setPointSize(9); p.setFont(f)
        fm = QFontMetrics(f)
        # tacche su ore tonde: non una griglia arbitraria come per un numero
        # qualunque, un orologio si legge solo se segna ore intere
        ore_totali = (massimo - minimo) / 60
        passo_ore = next((p_ for p_ in (1, 2, 3, 4, 6, 8, 12)
                          if ore_totali / p_ <= 6), 12)
        tacche = []
        t = minimo
        while t <= massimo + 1:
            tacche.append(t)
            t += passo_ore * 60
        campo = max(60.0, massimo - minimo)

        etichette = self.height() - 12 - self.SOTTO >= 36
        mb = self.SOTTO if etichette else 10
        mt = 12
        sinistra = self._margine_sinistro(p, tacche)
        area = QRectF(sinistra, mt, max(10.0, self.width() - sinistra - 10),
                      max(10.0, self.height() - mt - mb))

        def y(valore: float) -> float:
            # capovolto: l'ora più presto (quando vai a letto) sta in
            # fondo, quella più tarda (la sveglia) sta in cima — dormire
            # si legge come salire, non come scendere.
            return area.bottom() - (valore - minimo) / campo * area.height()

        for t in tacche:
            yt = y(t)
            p.setPen(QPen(QColor(self.c["griglia"]), 1))
            p.drawLine(QPointF(area.left(), yt), QPointF(area.right(), yt))
            p.setPen(QColor(self.c["testo2"]))
            p.drawText(QRectF(0, yt - 9, sinistra - 10, 18),
                       Qt.AlignRight | Qt.AlignVCenter, self.formato(t))

        n = len(self.dati)
        passo = area.width() / n
        largo = max(5.0, min(26.0, passo * 0.55))
        serve = max((fm.horizontalAdvance(e) for e, *_ in self.dati), default=20) + 8
        ogni = max(1, int(serve / max(1.0, passo) + 0.5))

        for i, (etic, a_letto, sveglia, tot) in enumerate(self.dati):
            centro = area.left() + passo * (i + 0.5)
            iv = intervalli[i]
            if iv is None:
                rect = QRectF(centro - largo / 2, area.bottom() - 2.4, largo, 2.4)
                p.setPen(Qt.NoPen); p.setBrush(QColor(self.c["griglia"]))
                p.drawRoundedRect(rect, 1.2, 1.2)
                self._zone.append((rect.adjusted(-4, -10, 4, 10),
                                   f"{etic}: nessun orario registrato"))
            else:
                inizio, fine = iv
                # l'asse è capovolto: l'ora più tarda (fine, la sveglia) sta
                # più in alto sullo schermo — y più piccola — e l'ora più
                # presto (inizio, quando vai a letto) sta più in basso.
                cima = y(fine)
                fondo = y(inizio)
                rect = QRectF(centro - largo / 2, cima, largo,
                              max(largo, fondo - cima))
                colore = QColor(self.colore)
                if self.evidenzia_ultima:
                    quale = self.evidenziata if self.evidenziata >= 0 else n - 1
                    if i != quale:
                        colore.setAlpha(140)
                p.setPen(Qt.NoPen); p.setBrush(colore)
                p.drawRoundedRect(rect, largo / 2, largo / 2)
                suggerimento = f"{etic}: {a_letto} → {sveglia}"
                if tot:
                    suggerimento += f" · {durata(tot)}"
                self._zone.append((rect.adjusted(-4, -6, 4, 6), suggerimento))

            if etichette and i % ogni == 0:
                p.setPen(QColor(self.c["testo2"]))
                p.drawText(QRectF(centro - passo, area.bottom() + 4, passo * 2, 16),
                           Qt.AlignCenter, etic)


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

        lato = max(90.0, min(self.width() * 0.46, self.height() - 20.0))
        rect = QRectF(16, (self.height() - lato) / 2, lato, lato)
        spessore = lato * 0.17
        interno = rect.adjusted(spessore, spessore, -spessore, -spessore)
        centro_d = rect.center()
        r_out = lato / 2
        r_in = r_out - spessore

        # Fette della ciambella
        angolo = 90.0 * 16
        for nome, valore, colore in self.dati:
            if valore <= 0:
                continue
            esteso = -360.0 * 16 * (valore / totale)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(colore or PALETTE_GRAFICI[0]))
            p.drawPie(rect, int(round(angolo)), int(round(esteso)))
            angolo += esteso

        # Foro centrale: sfondo della scheda
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(self.c["pannello"]))
        p.drawEllipse(interno)

        # Spacchi radiali puliti fra le fette (stile segmenti moderni)
        if len(self.dati) > 1:
            pen_gap = QPen(QColor(self.c["pannello"]), 2.6)
            pen_gap.setCapStyle(Qt.FlatCap)
            p.setPen(pen_gap)
            cur_ang = 90.0
            r_mid = (r_in + r_out) / 2
            for nome, valore, _ in self.dati:
                if valore <= 0:
                    continue
                # Linea di stacco al confine della fetta
                ang_rad = math.radians(cur_ang)
                cos_a, sin_a = math.cos(ang_rad), -math.sin(ang_rad)
                p.drawLine(
                    QPointF(centro_d.x() + (r_in - 1) * cos_a, centro_d.y() + (r_in - 1) * sin_a),
                    QPointF(centro_d.x() + (r_out + 1) * cos_a, centro_d.y() + (r_out + 1) * sin_a)
                )
                # Zona interattiva sul corpo della fetta per il tooltip
                quota = valore / totale * 100
                mid_ang = cur_ang - 180.0 * (valore / totale)
                m_rad = math.radians(mid_ang)
                pt_x = centro_d.x() + r_mid * math.cos(m_rad)
                pt_y = centro_d.y() - r_mid * math.sin(m_rad)
                self._zone.append((
                    QRectF(pt_x - spessore, pt_y - spessore, spessore * 2, spessore * 2),
                    f"{nome}: {self.formato(valore)} ({quota:.1f}%)"))
                cur_ang -= 360.0 * (valore / totale)

        # Scritta al centro: numero in grande e nota sotto, ben proporzionati
        con_nota = bool(interno.height() > 46 and self.centro_nota)
        dim_num = max(11, min(24, int(interno.width() / (4.5 if con_nota else 3.6))))
        f_num = QFont()
        f_num.setPointSize(dim_num)
        f_num.setBold(True)
        while dim_num > 8 and QFontMetrics(f_num).horizontalAdvance(self.centro_testo) > interno.width() - 8:
            dim_num -= 1
            f_num.setPointSize(dim_num)
        fm_num = QFontMetrics(f_num)

        if con_nota:
            dim_sub = max(7, min(10, int(interno.width() / 9.5)))
            f_sub = QFont()
            f_sub.setPointSize(dim_sub)
            f_sub.setBold(False)
            fm_sub = QFontMetrics(f_sub)
            tot_h = fm_num.ascent() + 3 + fm_sub.height()
            y_base = centro_d.y() - tot_h / 2
            p.setFont(f_num)
            p.setPen(QColor(self.c["testo"]))
            p.drawText(QRectF(interno.left(), y_base, interno.width(), fm_num.height()),
                       Qt.AlignCenter, self.centro_testo)
            p.setFont(f_sub)
            p.setPen(QColor(self.c["testo2"]))
            p.drawText(QRectF(interno.left(), y_base + fm_num.ascent() + 3, interno.width(), fm_sub.height()),
                       Qt.AlignCenter, self.centro_nota)
        else:
            p.setFont(f_num)
            p.setPen(QColor(self.c["testo"]))
            p.drawText(interno, Qt.AlignCenter, self.centro_testo)

        # Legenda allineata a destra: pallini tondi, nomi a sinistra, percentuali a destra in colonna
        x_leg = rect.right() + 22
        w_leg = max(90.0, self.width() - x_leg - 14)
        n_righe = min(len(self.dati), max(1, int((self.height() - 14) // 20)))
        passo = min(25.0, (self.height() - 16.0) / max(1, n_righe))
        y_start = (self.height() - (n_righe * passo)) / 2

        f_nome = QFont(); f_nome.setPointSize(9); f_nome.setBold(False)
        fm_nome = QFontMetrics(f_nome)
        f_pct = QFont(); f_pct.setPointSize(9); f_pct.setBold(True)

        for i, (nome, valore, colore) in enumerate(self.dati[:n_righe]):
            y = y_start + i * passo
            col = QColor(colore or PALETTE_GRAFICI[i % 12])
            # Pastiglietta / pallino tondo della tinta
            p.setPen(Qt.NoPen)
            p.setBrush(col)
            p.drawRoundedRect(QRectF(x_leg, y + (passo - 7) / 2, 7, 7), 3.5, 3.5)

            # Nome emozione a sinistra
            quota = valore / totale * 100
            largo_n = max(30.0, w_leg - 48.0)
            nome_elided = fm_nome.elidedText(nome, Qt.ElideRight, int(largo_n))
            p.setFont(f_nome)
            p.setPen(QColor(self.c["testo"]))
            p.drawText(QRectF(x_leg + 14, y, largo_n, passo),
                       Qt.AlignLeft | Qt.AlignVCenter, nome_elided)

            # Percentuale allineata a destra, in colonna pulita
            p.setFont(f_pct)
            p.setPen(QColor(self.c["testo2"]))
            p.drawText(QRectF(x_leg + w_leg - 34, y, 34, passo),
                       Qt.AlignRight | Qt.AlignVCenter, f"{quota:.0f}%")

            self._zone.append((QRectF(x_leg, y, w_leg, passo),
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
        # un anello senza nota sotto (vedi `con_nota`) ha solo il numero a
        # dire qualcosa: qui si può chiedere un carattere più grande di
        # quello che verrebbe da solo, senza toccare tutti gli altri
        # anelli dell'app — il ciclo qui sotto, che restringe finché il
        # testo non ci sta, resta comunque l'ultima parola: non taglia mai
        self.scala_testo = 1.0
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
        dim = max(9, int(lato * 0.2 * self.scala_testo))
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
    """Calendario a quadretti: un colore per giorno (umore, abitudini, ore).

    **Sette colonne, sempre, e riempiono la larghezza.** Il lato del
    quadretto è quello che serve perché i sette giorni occupino tutta la
    riga: prima il lato aveva un massimo di 44 pixel e il calendario si
    metteva in mezzo, lasciando due bande vuote ai lati di un riquadro
    largo. Se tanti quadretti così alti non ci stanno in altezza, il lato
    si accorcia quel tanto che basta — ma le colonne restano distese da un
    bordo all'altro, che è la cosa che si vedeva.

    Lo spazio fra l'uno e l'altro, gli angoli e le lettere dei giorni
    seguono la stessa proporzione del lato, così il calendario ha la stessa
    faccia in un riquadro piccolo e in uno grande, col testo normale e col
    testo molto grande.

    Il riempimento va **a gradini**, non a sfumatura continua: fra il 40% e
    il 45% dell'obiettivo, in un quadretto di dieci pixel, non vedrebbe la
    differenza nessuno; fra un gradino e l'altro sì.
    """

    giorno_scelto = Signal(str)
    COLONNE = 7                # i giorni della settimana, da lunedì
    SOGLIE = (0.08, 0.3, 0.55, 0.8)                 # i gradini
    OPACITA = (0.20, 0.40, 0.62, 0.82, 1.0)         # quanto tinge ognuno

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
        # le lettere dei giorni seguono il carattere dell'applicazione: col
        # testo grande crescono anche loro, invece di restare otto punti
        carattere = QFont(self.font())
        carattere.setBold(True)
        misura = QFontMetrics(carattere)
        intestazione = (misura.height() + 3) if self.etichette else 0

        colonne, righe = self.COLONNE, settimane
        utile = max(12.0, self.height() - intestazione)
        # il passo orizzontale è tutta la larghezza divisa sette: è così che
        # le colonne arrivano ai due bordi invece di stare in mezzo
        passo_x = self.width() / colonne
        passo_y = utile / max(1, righe)
        # lo spazio fra un quadretto e l'altro è un quinto del quadretto, mai
        # meno di tre pixel: a quadretti grandi non diventa un corridoio, a
        # quadretti piccoli non spariscono i confini
        stacco = max(3.0, min(passo_x, passo_y) * 0.18)
        # **La larghezza si riempie sempre**: il quadretto è largo quanto la
        # sua colonna. L'altezza la prende uguale finché ce n'è; quando le
        # settimane sono tante e il riquadro è basso si schiaccia, e invece
        # di quadretti piccoli in mezzo a due bande vuote restano pastiglie
        # distese da un bordo all'altro.
        largo = max(6.0, passo_x - stacco)
        alto_cella = max(5.0, min(largo, passo_y - stacco))
        # ma un quadretto deve restare riconoscibile: oltre una volta e mezza
        # più largo che alto smette di essere un quadretto e diventa una
        # striscia, e allora si stringe un po' lasciandosi aria intorno —
        # la griglia continua a toccare i due bordi, che è quello che conta
        largo = min(largo, alto_cella * 1.5)
        lato = min(largo, alto_cella)          # per raggi e spessori
        sinistra = 0.0
        alto = intestazione + max(0.0, (utile - passo_y * righe) / 2)
        raggio = min(lato * 0.3, alto_cella / 2)

        # con le colonne strette la lettera non ci sta: meglio nessuna lettera
        # che sette lettere appiccicate
        if (self.etichette
                and misura.horizontalAdvance("M") <= passo_x - 2):
            p.setFont(carattere)
            p.setPen(QColor(self.c["testo2"]))
            for i, nome in enumerate("LMMGVSD"):
                p.drawText(QRectF(sinistra + i * passo_x, 0, passo_x, intestazione),
                           Qt.AlignCenter, nome)

        for indice, giorno in enumerate(self.giorni):
            posizione = indice + salto
            riga, colonna = divmod(posizione, self.COLONNE)
            x = sinistra + colonna * passo_x + (passo_x - largo) / 2
            y = alto + riga * passo_y + (passo_y - alto_cella) / 2
            rect = QRectF(x, y, largo, alto_cella)
            quota, colore = self.dati.get(giorno, (0.0, ""))
            p.setPen(Qt.NoPen)
            if not colore:
                p.setBrush(QColor(self.c["griglia"]))
            else:
                col = QColor(colore)
                gradino = sum(1 for s in self.SOGLIE if quota > s)
                col.setAlphaF(self.OPACITA[gradino])
                p.setBrush(col)
            p.drawRoundedRect(rect, raggio, raggio)
            if giorno == _date.today().isoformat():
                # il contorno di oggi sta **dentro** il quadretto: fuori,
                # sul bordo del riquadro, veniva tagliato
                p.setBrush(Qt.NoBrush)
                spessore = max(1.4, lato * 0.1)
                p.setPen(QPen(QColor(self.c["testo"]), spessore))
                p.drawRoundedRect(
                    rect.adjusted(spessore / 2, spessore / 2,
                                  -spessore / 2, -spessore / 2),
                    raggio, raggio)
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
        # un pallino sull'ultimo punto: dice dove sei arrivato quando la
        # linea è il grafico principale di un riquadro, non una miniatura
        self.punto_finale = False
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
        # col pallino in fondo la linea si tira indietro di un filo da tutti
        # e due i lati: se no il cerchio dell'ultimo punto nasce a cavallo
        # del bordo e si vede mezzo
        lato = 4.0 if self.punto_finale else 0.0
        w, h = self.width() - lato * 2, self.height() - 6
        percorso = QPainterPath()
        for i, v in enumerate(self.valori):
            x = lato + w * i / (len(self.valori) - 1)
            y = 3 + h - (v - vmin) / (vmax - vmin) * h
            percorso.moveTo(x, y) if i == 0 else percorso.lineTo(x, y)
        penna = QPen(QColor(self.colore), 1.8)
        penna.setCapStyle(Qt.RoundCap); penna.setJoinStyle(Qt.RoundJoin)
        p.setPen(penna)
        p.drawPath(percorso)
        if self.punto_finale:
            p.setPen(Qt.NoPen); p.setBrush(QColor(self.colore))
            p.drawEllipse(percorso.currentPosition(), 3.2, 3.2)
