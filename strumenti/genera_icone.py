#!/usr/bin/env python3
"""Genera le icone dell'app dal logo TANZ, in versione scura e chiara.

    python3 strumenti/genera_icone.py                 # fedele all'originale
    python3 strumenti/genera_icone.py --occupazione 0.74   # scritta più grande
    python3 strumenti/genera_icone.py --provino          # solo il confronto

Sorgenti in `risorse/sorgente/`, risultato in `risorse/`:
`icona*.png` (scritta bianca su nero) e `icona-chiara*.png` (nera su bianco).
"""
from __future__ import annotations

import argparse
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import (QColor, QFont, QImage, QPainter, QPainterPath,
                           QPixmap)
from PySide6.QtWidgets import QApplication

RADICE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SORGENTI = {
    "scuro": os.path.join(RADICE, "risorse", "sorgente", "logo-tanz-scuro.png"),
    "chiaro": os.path.join(RADICE, "risorse", "sorgente", "logo-tanz-chiaro.png"),
}
MISURE = (16, 24, 32, 48, 64, 128, 256, 512)


def ritaglio(immagine: QImage) -> tuple[QRect, QColor]:
    """Riquadro che contiene la scritta e colore del fondo."""
    fondo = QColor(immagine.pixelColor(2, 2))
    larghezza, altezza = immagine.width(), immagine.height()
    sinistra, destra, alto, basso = larghezza, -1, altezza, -1
    for y in range(altezza):
        for x in range(larghezza):
            colore = immagine.pixelColor(x, y)
            scarto = (abs(colore.red() - fondo.red())
                      + abs(colore.green() - fondo.green())
                      + abs(colore.blue() - fondo.blue()))
            if scarto > 90:
                sinistra = min(sinistra, x); destra = max(destra, x)
                alto = min(alto, y); basso = max(basso, y)
    if destra < 0:
        return QRect(0, 0, larghezza, altezza), fondo
    return QRect(sinistra, alto, destra - sinistra + 1, basso - alto + 1), fondo


def icona(sorgente: QImage, riquadro: QRect, fondo: QColor, lato: int,
          occupazione: float, raggio: float = 0.22) -> QImage:
    """Icona quadrata con gli angoli arrotondati.

    La scritta occupa la quota indicata della larghezza; fuori dal riquadro
    arrotondato resta trasparente, così l'icona si appoggia a qualsiasi sfondo.
    """
    risultato = QImage(lato, lato, QImage.Format_ARGB32)
    risultato.fill(Qt.transparent)
    marchio = sorgente.copy(riquadro)
    larghezza = max(1, int(round(lato * occupazione)))
    altezza = max(1, int(round(larghezza * riquadro.height() / riquadro.width())))
    marchio = marchio.scaled(larghezza, altezza, Qt.IgnoreAspectRatio,
                             Qt.SmoothTransformation)
    p = QPainter(risultato)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.SmoothPixmapTransform, True)
    angolo = lato * max(0.0, min(0.5, raggio))
    contorno = QPainterPath()
    contorno.addRoundedRect(QRectF(0, 0, lato, lato), angolo, angolo)
    p.fillPath(contorno, fondo)
    p.setClipPath(contorno)
    p.drawImage((lato - larghezza) // 2, (lato - altezza) // 2, marchio)
    p.end()
    return risultato


def marchio(sorgente: QImage, riquadro: QRect, fondo: QColor,
            altezza: int, colore: QColor) -> QImage:
    """Solo la scritta, su fondo trasparente: per la barra laterale.

    La trasparenza nasce dalla luminosità: i pixel del fondo spariscono, quelli
    della scritta restano pieni, e i bordi sfumati restano sfumati.
    """
    ritagliata = sorgente.copy(riquadro).convertToFormat(QImage.Format_ARGB32)
    chiaro_su_scuro = fondo.lightness() < 128
    for y in range(ritagliata.height()):
        for x in range(ritagliata.width()):
            luce = QColor(ritagliata.pixelColor(x, y)).lightness()
            alfa = luce if chiaro_su_scuro else 255 - luce
            ritagliata.setPixelColor(x, y, QColor(colore.red(), colore.green(),
                                                  colore.blue(), alfa))
    larghezza = max(1, int(round(altezza * riquadro.width() / riquadro.height())))
    return ritagliata.scaled(larghezza, altezza, Qt.IgnoreAspectRatio,
                             Qt.SmoothTransformation)


def provino(percorso: str, dati: dict, quote: list[float]) -> None:
    """Foglio di confronto: le due versioni alle misure che contano."""
    misure = (128, 64, 48, 32, 24, 16)
    larghezza, altezza_riga = 660, 152
    foglio = QPixmap(larghezza * 2, (altezza_riga * len(quote) * 2 + 120) * 2)
    foglio.fill(QColor("#13151c"))
    p = QPainter(foglio)
    p.setRenderHint(QPainter.SmoothPixmapTransform, True)
    p.scale(2, 2)
    f = QFont("Noto Sans"); f.setPixelSize(20); f.setBold(True)
    p.setFont(f); p.setPen(QColor("#e7e9ee"))
    p.drawText(QRectF(34, 26, 600, 30), Qt.AlignLeft, "Logo TANZ come icona")
    f.setPixelSize(13); f.setBold(False); p.setFont(f); p.setPen(QColor("#9aa1b1"))
    p.drawText(QRectF(34, 54, 600, 22), Qt.AlignLeft,
               "128 · 64 · 48 · 32 · 24 · 16 px")
    y = 92
    for quota in quote:
        for tema in ("scuro", "chiaro"):
            sorgente, riquadro, fondo = dati[tema]
            f.setPixelSize(13); f.setBold(True); p.setFont(f)
            p.setPen(QColor("#e7e9ee"))
            p.drawText(QRectF(34, y + 54, 170, 20), Qt.AlignLeft,
                       f"{int(quota * 100)}%  ·  {tema}")
            x = 210
            for lato in misure:
                immagine = icona(sorgente, riquadro, fondo, lato * 2, quota)
                p.drawPixmap(QRectF(x, y + 70 - lato / 2, lato, lato),
                             QPixmap.fromImage(immagine),
                             QRectF(0, 0, lato * 2, lato * 2))
                x += lato + 22
            y += altezza_riga
        p.setPen(QColor("#2c313f"))
        p.drawLine(34, y + 6, larghezza - 34, y + 6)
        y += 18
    p.end()
    foglio.save(percorso)


def main() -> int:
    argomenti = argparse.ArgumentParser(description=__doc__)
    argomenti.add_argument("--occupazione", type=float, default=0.0,
                           help="quota di larghezza occupata dalla scritta "
                                "(0 = come nell'originale)")
    argomenti.add_argument("--raggio", type=float, default=0.22,
                           help="quanto sono arrotondati gli angoli (0 = quadrato)")
    argomenti.add_argument("--provino", default="",
                           help="scrive solo un foglio di confronto nel percorso dato")
    opzioni = argomenti.parse_args()

    app = QApplication([])
    dati = {}
    for tema, percorso in SORGENTI.items():
        if not os.path.exists(percorso):
            print(f"Manca il file sorgente: {percorso}")
            return 1
        sorgente = QImage(percorso)
        riquadro, fondo = ritaglio(sorgente)
        dati[tema] = (sorgente, riquadro, fondo)

    naturale = dati["scuro"][1].width() / dati["scuro"][0].width()
    quota = opzioni.occupazione or naturale

    if opzioni.provino:
        provino(opzioni.provino, dati, [naturale, 0.74, 0.86])
        print(f"provino in {opzioni.provino} "
              f"(originale {naturale:.0%}, poi 74% e 86%)")
        return 0

    risorse = os.path.join(RADICE, "risorse")
    for tema, prefisso in (("scuro", "icona"), ("chiaro", "icona-chiara")):
        sorgente, riquadro, fondo = dati[tema]
        for lato in MISURE:
            icona(sorgente, riquadro, fondo, lato, quota, opzioni.raggio).save(
                os.path.join(risorse, f"{prefisso}-{lato}.png"))
        icona(sorgente, riquadro, fondo, 256, quota, opzioni.raggio).save(
            os.path.join(risorse, f"{prefisso}.png"))

    # la sola scritta, trasparente, per l'intestazione della barra laterale
    sorgente, riquadro, fondo = dati["scuro"]
    for nome, colore in (("marchio-chiaro", QColor("#ffffff")),
                         ("marchio-scuro", QColor("#0f1115"))):
        marchio(sorgente, riquadro, fondo, 96, colore).save(
            os.path.join(risorse, f"{nome}.png"))
    print(f"icone rigenerate in {risorse} · scritta al {quota:.0%} della larghezza "
          f"· angoli al {opzioni.raggio:.0%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
