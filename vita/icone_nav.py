"""Icone della barra di navigazione, disegnate con QPainter.

I simboli tipografici hanno metriche diverse fra loro e risultano disallineati
dentro i pulsanti: qui ogni icona nasce dentro un riquadro quadrato, così
restano centrate sia a barra aperta sia a barra chiusa.
"""
from __future__ import annotations

import math
import os

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import (QColor, QGuiApplication, QIcon, QPainter, QPainterPath,
                           QPen, QPixmap)

LATO = 20
SPESSORE = 1.7
CENTRO = QPointF(10.0, 10.0)


# ------------------------------------------------------- aiuti d'animazione
# Ogni disegno riceve una «fase» da 0 a 1: 1 è l'icona ferma, i valori in
# mezzo sono i fotogrammi di quando la voce viene scelta o sfiorata.
def _onda(fase: float, giri: float = 2.0) -> float:
    """Un'oscillazione che si smorza: forte all'inizio, spenta alla fine."""
    if fase >= 1.0:
        return 0.0
    return math.sin(math.pi * giri * fase) * (1.0 - fase)

def _battito(fase: float) -> float:
    """Come l'onda, ma sempre positiva: cresce e torna, due volte."""
    if fase >= 1.0:
        return 0.0
    return abs(math.sin(math.pi * 2 * fase)) * (1.0 - fase)

def _scala(p: QPainter, fattore: float, centro: QPointF = CENTRO) -> None:
    p.translate(centro)
    p.scale(fattore, fattore)
    p.translate(-centro)

def _ruota(p: QPainter, gradi: float, centro: QPointF = CENTRO) -> None:
    p.translate(centro)
    p.rotate(gradi)
    p.translate(-centro)

def _parziale(percorso: QPainterPath, quota: float) -> QPainterPath:
    """La prima parte di un tracciato: l'icona si disegna da sé."""
    if quota >= 1.0:
        return percorso
    quota = max(0.0, quota)
    parti = QPainterPath()
    parti.moveTo(percorso.pointAtPercent(0.0))
    passi = 40
    for i in range(1, passi + 1):
        parti.lineTo(percorso.pointAtPercent(quota * i / passi))
    return parti

def _corsa(fase: float, inizio: float = 0.0, durata: float = 0.75) -> float:
    """Quanto è avanzato un tratto che si scrive, da 0 a 1."""
    if fase >= 1.0:
        return 1.0
    return min(1.0, max(0.0, (fase - inizio) / durata))


def _fattore_schermo() -> float:
    app = QGuiApplication.instance()
    if app is None:
        return 1.0
    schermo = app.primaryScreen()
    return float(schermo.devicePixelRatio()) if schermo else 1.0


def _pittore(pixmap: QPixmap, colore: str, scala: float) -> QPainter:
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.scale(scala, scala)
    penna = QPen(QColor(colore))
    penna.setWidthF(SPESSORE)
    penna.setCapStyle(Qt.RoundCap)
    penna.setJoinStyle(Qt.RoundJoin)
    p.setPen(penna)
    p.setBrush(Qt.NoBrush)
    return p


# --------------------------------------------------------------- i disegni
# Ognuno disegna dentro un quadrato di 20×20 e riceve la fase: a 1 l'icona è
# ferma, sotto è un fotogramma dell'animazione.
def _cruscotto(p: QPainter, fase: float = 1.0) -> None:
    """I quattro riquadri si accendono uno dopo l'altro."""
    for i, (x, y) in enumerate(((2.5, 2.5), (11.5, 2.5), (2.5, 11.5), (11.5, 11.5))):
        q = _corsa(fase, i * 0.11, 0.42)
        p.save()
        _scala(p, 0.55 + 0.45 * q + 0.12 * _battito(min(1.0, fase + i * 0.0)),
               QPointF(x + 3, y + 3))
        p.drawRoundedRect(QRectF(x, y, 6, 6), 1.6, 1.6)
        p.restore()


def _emozioni(p: QPainter, fase: float = 1.0) -> None:
    """Il cuore batte: due pulsazioni che si smorzano."""
    p.save()
    _scala(p, 1.0 + 0.22 * _battito(fase))
    percorso = QPainterPath()
    percorso.moveTo(10, 17.2)
    percorso.cubicTo(3.2, 12.4, 2.2, 9.6, 3.4, 6.6)
    percorso.cubicTo(4.6, 3.8, 8.4, 3.4, 10, 6.4)
    percorso.cubicTo(11.6, 3.4, 15.4, 3.8, 16.6, 6.6)
    percorso.cubicTo(17.8, 9.6, 16.8, 12.4, 10, 17.2)
    p.drawPath(percorso)
    p.restore()


def _carriera(p: QPainter, fase: float = 1.0) -> None:
    """La ventiquattrore: il manico si solleva e si riposa."""
    p.drawRoundedRect(QRectF(2.4, 6.2, 15.2, 11), 2, 2)
    p.drawLine(QPointF(2.4, 10.6), QPointF(17.6, 10.6))
    p.save()
    p.translate(0.0, -1.5 * _battito(fase))
    manico = QPainterPath()
    manico.moveTo(7.2, 6.2)
    manico.lineTo(7.2, 4.2)
    manico.lineTo(12.8, 4.2)
    manico.lineTo(12.8, 6.2)
    p.drawPath(manico)
    p.restore()


def _accademica(p: QPainter, fase: float = 1.0) -> None:
    """Il tocco di laurea si inclina, come se lo lanciassi."""
    p.save()
    _ruota(p, 13.0 * _onda(fase), QPointF(10.0, 7.4))
    cappello = QPainterPath()
    cappello.moveTo(10, 3.4)
    cappello.lineTo(18.2, 7.4)
    cappello.lineTo(10, 11.4)
    cappello.lineTo(1.8, 7.4)
    cappello.closeSubpath()
    p.drawPath(cappello)
    p.restore()
    falde = QPainterPath()
    falde.moveTo(5.2, 9.2)
    falde.lineTo(5.2, 13.4)
    falde.cubicTo(5.2, 15.6, 14.8, 15.6, 14.8, 13.4)
    falde.lineTo(14.8, 9.2)
    p.drawPath(falde)


def _salute(p: QPainter, fase: float = 1.0) -> None:
    """Il battito si scrive da sinistra a destra, come sul monitor."""
    percorso = QPainterPath()
    percorso.moveTo(2, 10)
    percorso.lineTo(5.6, 10)
    percorso.lineTo(7.8, 4.2)
    percorso.lineTo(12.2, 15.8)
    percorso.lineTo(14.4, 10)
    percorso.lineTo(18, 10)
    p.drawPath(_parziale(percorso, _corsa(fase, 0.0, 0.8)))


def _finanza(p: QPainter, fase: float = 1.0) -> None:
    """La linea sale tracciandosi, e la punta fa un saltello."""
    percorso = QPainterPath()
    percorso.moveTo(2.2, 14.6)
    percorso.lineTo(7.6, 9.2)
    percorso.lineTo(11.2, 12.8)
    percorso.lineTo(17.6, 5.6)
    p.drawPath(_parziale(percorso, _corsa(fase, 0.0, 0.72)))
    if _corsa(fase, 0.0, 0.72) > 0.85:
        p.save()
        p.translate(0.0, -1.6 * _battito(fase))
        freccia = QPainterPath()
        freccia.moveTo(13.2, 5.6)
        freccia.lineTo(17.8, 5.6)
        freccia.lineTo(17.8, 10)
        p.drawPath(freccia)
        p.restore()


def _abitudini(p: QPainter, fase: float = 1.0) -> None:
    """La spunta si disegna dentro il foglio."""
    p.drawRoundedRect(QRectF(2.6, 3.6, 14.8, 13.4), 2.4, 2.4)
    p.drawLine(QPointF(2.6, 7.6), QPointF(17.4, 7.6))
    segno = QPainterPath()
    segno.moveTo(6.6, 12.2)
    segno.lineTo(9, 14.4)
    segno.lineTo(13.6, 10)
    p.drawPath(_parziale(segno, _corsa(fase, 0.12, 0.5)))


def _impostazioni(p: QPainter, fase: float = 1.0) -> None:
    """I tre cursori scorrono sulle loro guide e tornano al posto."""
    for x in (4.6, 10, 15.4):
        p.drawLine(QPointF(x, 2.8), QPointF(x, 17.2))
    scorsa = 2.6 * _onda(fase, 1.0)
    for verso, (x, y) in zip((1, -1, 1), ((4.6, 12.6), (10, 6.6), (15.4, 10.4))):
        p.drawEllipse(QPointF(x, y + verso * scorsa), 2.0, 2.0)


def _tess(p: QPainter, fase: float = 1.0) -> None:
    """Una nuvoletta con la scintilla: la scintilla gira e si accende."""
    nuvola = QPainterPath()
    nuvola.moveTo(5.0, 15.2)
    nuvola.lineTo(5.0, 17.6)
    nuvola.lineTo(8.4, 15.2)
    p.drawPath(nuvola)
    p.drawRoundedRect(QRectF(2.4, 3.4, 15.2, 11.8), 3.4, 3.4)
    p.save()
    perno = QPointF(10.0, 9.3)
    _ruota(p, 180.0 * _corsa(fase, 0.0, 0.8), perno)
    _scala(p, 1.0 + 0.3 * _battito(fase), perno)
    scintilla = QPainterPath()
    scintilla.moveTo(10.0, 6.2)
    scintilla.lineTo(11.1, 8.6)
    scintilla.lineTo(13.5, 9.3)
    scintilla.lineTo(11.1, 10.0)
    scintilla.lineTo(10.0, 12.4)
    scintilla.lineTo(8.9, 10.0)
    scintilla.lineTo(6.5, 9.3)
    scintilla.lineTo(8.9, 8.6)
    scintilla.closeSubpath()
    p.drawPath(scintilla)
    p.restore()


def _matita(p: QPainter, fase: float = 1.0) -> None:
    corpo = QPainterPath()
    corpo.moveTo(5.1, 14.9)                      # punta
    corpo.lineTo(6.0, 11.0)
    corpo.lineTo(12.0, 5.0)
    corpo.lineTo(15.0, 8.0)
    corpo.lineTo(9.0, 14.0)
    corpo.closeSubpath()
    p.drawPath(corpo)
    p.drawLine(QPointF(6.0, 11.0), QPointF(9.0, 14.0))


def _punti(p: QPainter, fase: float = 1.0) -> None:
    p.setBrush(p.pen().color())
    for x in (5.2, 10.0, 14.8):
        p.drawEllipse(QPointF(x, 10.0), 1.25, 1.25)
    p.setBrush(Qt.NoBrush)


def _menu(p: QPainter, fase: float = 1.0) -> None:
    for y in (5.6, 10, 14.4):
        p.drawLine(QPointF(3.4, y), QPointF(16.6, y))


DISEGNI = {
    "cruscotto": _cruscotto, "emozioni": _emozioni, "carriera": _carriera,
    "accademica": _accademica, "salute": _salute, "finanza": _finanza,
    "abitudini": _abitudini, "impostazioni": _impostazioni, "tess": _tess,
    "menu": _menu,
    "matita": _matita, "punti": _punti,
}


def _pixmap(nome: str, colore: str, fase: float = 1.0) -> QPixmap:
    densita = _fattore_schermo()
    pixmap = QPixmap(int(LATO * densita), int(LATO * densita))
    pixmap.setDevicePixelRatio(densita)
    pixmap.fill(Qt.transparent)
    p = _pittore(pixmap, colore, densita)
    DISEGNI.get(nome, _cruscotto)(p, fase)
    p.end()
    return pixmap


def icona(nome: str, colore: str, colore_attivo: str = "",
          colore_passaggio: str = "", fase: float = 1.0) -> QIcon:
    """Icona con tre stati: ferma, sfiorata e scelta.

    `colore` è quello a riposo, `colore_passaggio` quello del mouse sopra (la
    tinta della sezione), `colore_attivo` quello sulla pastiglia piena.
    """
    ic = QIcon()
    ic.addPixmap(_pixmap(nome, colore, fase), QIcon.Normal, QIcon.Off)
    attivo = _pixmap(nome, colore_attivo or colore, fase)
    sfiorata = _pixmap(nome, colore_passaggio or colore_attivo or colore, fase)
    ic.addPixmap(attivo, QIcon.Normal, QIcon.On)
    ic.addPixmap(sfiorata, QIcon.Active, QIcon.Off)
    ic.addPixmap(attivo, QIcon.Active, QIcon.On)
    ic.addPixmap(attivo, QIcon.Selected, QIcon.On)
    return ic


def icona_menu(colore: str) -> QIcon:
    return QIcon(_pixmap("menu", colore))


RISORSE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "risorse")


def percorso_logo(tema: str = "scuro", lato: int = 0) -> str:
    """Il logo TANZ nella versione adatta al tema: bianco su nero o nero su bianco.

    Per la pagina: `b_logo` nella barra laterale e il marchio nello schermo
    di blocco stanno su uno sfondo che l'app sceglie, e lì il contrasto col
    tema conta. Per l'icona della FINESTRA (barra del titolo, barra delle
    applicazioni) usa invece `logo_app`, che non segue questo parametro: è
    il sistema a disegnarla sopra uno sfondo che l'app non controlla.
    """
    base = "icona" if tema == "scuro" else "icona-chiara"
    candidati = [f"{base}-{lato}.png"] if lato else []
    candidati += [f"{base}.png", "icona.png"]
    for nome in candidati:
        percorso = os.path.join(RISORSE, nome)
        if os.path.exists(percorso):
            return percorso
    return ""


def logo_app() -> QIcon:
    """Icona della finestra/applicazione: **sempre la piastrella nera**,
    scuro o chiaro che sia il tema dell'app o il desktop.

    La disegna il sistema sopra uno sfondo che l'app non sceglie — barra del
    titolo, barra delle applicazioni. Scegliendola per tema o per schema del
    desktop, un caso restava sempre scoperto (app scura su desktop chiaro, o
    viceversa): la piastrella chiara ci finiva su un fondo scuro, e i suoi
    angoli arrotondati — trasparenti — mostravano lo sfondo dietro come
    quattro spigoli slegati. Una piastrella sola, sempre leggibile, chiude
    il problema invece di inseguire ogni combinazione.
    """
    icona_app = QIcon()
    for lato in (16, 24, 32, 48, 64, 128, 256, 512):
        percorso = os.path.join(RISORSE, f"icona-{lato}.png")
        if os.path.exists(percorso):
            icona_app.addFile(percorso, QSize(lato, lato))
    if icona_app.isNull():
        percorso = percorso_logo("scuro")
        if percorso:
            icona_app.addFile(percorso)
    return icona_app
