#!/usr/bin/env python3
"""Dashboard — diario, salute, carriera, studio e finanza. Tutto in locale.

Avvio:  python3 main.py
"""
from __future__ import annotations

import os
import sys

# Nessuna connessione di rete: l'app lavora solo su file locali.
os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.*=false")

from PySide6.QtCore import QLocale, Qt
from PySide6.QtWidgets import QApplication

from vita import blocco
from vita.db import Database
from vita.finestra import FinestraPrincipale
from vita.icone_nav import logo_app
from vita.tema import SCALE, colori, foglio_stile


def main() -> int:
    QApplication.setAttribute(Qt.AA_DontUseNativeMenuBar, False)
    QLocale.setDefault(QLocale(QLocale.Italian, QLocale.Italy))
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("Dashboard")
    # niente setApplicationDisplayName: Qt lo accoderebbe a ogni titolo
    # («Andamento — Dashboard»), e la barra del titolo diventa un elenco
    app.setDesktopFileName("dashboard")

    db = Database()
    tema = db.leggi("tema", "scuro")
    app.setWindowIcon(logo_app(tema))

    # se c'è una password, si entra solo da lì: la finestra non nasce nemmeno
    if blocco.attivo(db):
        c = colori(tema)
        app.setStyleSheet(foglio_stile(
            c, SCALE.get(db.leggi("scala", "normale"), 1.0)))
        if not blocco.chiedi(db, c, tema):
            return 0

    finestra = FinestraPrincipale(db)
    finestra.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
