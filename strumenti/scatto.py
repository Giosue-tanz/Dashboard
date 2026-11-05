#!/usr/bin/env python3
"""Una fotografia di una pagina, o di un suo riquadro.

Apre l'applicazione fuori schermo su una **copia** dell'archivio (non tocca
niente), con il tema e la dimensione del testo che hai scelto tu, e salva
l'immagine. Serve a guardare una modifica senza aprire la finestra vera.

    python3 strumenti/scatto.py salute fuori.png
    python3 strumenti/scatto.py salute fuori.png --riquadri oggi,sonno
    python3 strumenti/scatto.py salute fuori.png --largo 1366 --scala "normale"
    python3 strumenti/scatto.py salute fuori.png --tua-disposizione

Senza «--tua-disposizione» parte dalla disposizione predefinita dei riquadri:
è quella che vede chi apre l'app la prima volta.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QElapsedTimer, QLocale                      # noqa: E402
from PySide6.QtWidgets import QApplication                             # noqa: E402

import vita.tess as tess                                               # noqa: E402
# nessun motore e nessun braccialetto: si guarda e basta
tess.Motore.accendi = lambda self: (False, "scatto: motore non toccato")
tess.Motore.attiva = lambda self: False

from vita.db import DB_PATH, Database                                  # noqa: E402
from vita.finestra import VISTE, FinestraPrincipale                    # noqa: E402


def main() -> int:
    argomenti = argparse.ArgumentParser(description=__doc__)
    argomenti.add_argument("vista", help="emozioni, salute, accademica…")
    argomenti.add_argument("fuori", help="dove salvare l'immagine")
    argomenti.add_argument("--riquadri", default="",
                           help="anche i singoli riquadri, separati da virgola")
    argomenti.add_argument("--largo", type=int, default=1920)
    argomenti.add_argument("--alto", type=int, default=1030)
    argomenti.add_argument("--scala", default="", help="compatta, normale, grande…")
    argomenti.add_argument("--tema", default="")
    argomenti.add_argument("--tua-disposizione", action="store_true",
                           dest="tua", help="tieni i riquadri come li hai messi")
    opzioni = argomenti.parse_args()

    QLocale.setDefault(QLocale(QLocale.Italian, QLocale.Italy))
    app = QApplication([])
    app.setStyle("Fusion")
    banco = tempfile.mkdtemp(prefix="scatto-")
    copia = os.path.join(banco, "scatto.db")
    shutil.copy2(DB_PATH, copia)
    db = Database(copia)
    if not opzioni.tua:
        db.esegui("DELETE FROM impostazioni WHERE chiave LIKE 'layout_%'")
    if opzioni.scala:
        db.imposta("scala", opzioni.scala)

    finestra = FinestraPrincipale(db)
    finestra.resize(opzioni.largo, opzioni.alto)
    finestra.show()
    finestra.applica_tema(opzioni.tema or db.leggi("tema", "scuro"))

    nomi = [n for n, _ in VISTE]
    if opzioni.vista not in nomi:
        print(f"Vista sconosciuta: {opzioni.vista}. Ce ne sono: {', '.join(nomi)}")
        return 1
    finestra.vai(nomi.index(opzioni.vista))

    tempo = QElapsedTimer(); tempo.start()
    while tempo.elapsed() < 900:          # il tempo che i riquadri si assestino
        app.processEvents()

    finestra.grab().save(opzioni.fuori)
    print(f"scritto {opzioni.fuori}")
    vista = finestra.viste[nomi.index(opzioni.vista)]
    for chiave in filter(None, opzioni.riquadri.split(",")):
        sezione = getattr(vista, "contenitore", None)
        sezione = sezione.sezioni.get(chiave) if sezione else None
        if sezione is None:
            print(f"  riquadro assente: {chiave}")
            continue
        percorso = opzioni.fuori.replace(".png", f"-{chiave}.png")
        sezione.grab().save(percorso)
        print(f"scritto {percorso}  ({sezione.width()}×{sezione.height()})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
