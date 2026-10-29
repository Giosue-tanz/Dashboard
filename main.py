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

from vita.db import Database
from vita.finestra import FinestraPrincipale
from vita.icone_nav import logo_app


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
    app.setWindowIcon(logo_app(db.leggi("tema", "scuro")))
    finestra = FinestraPrincipale(db)
    finestra.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
