#!/usr/bin/env python3
"""Come sta il braccialetto adesso: batteria, ora, e se ha dati da dare.

Non scrive niente né sul braccialetto né nell'archivio: guarda e basta.

    python3 strumenti/stato_banda.py
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QCoreApplication, QTimer                    # noqa: E402

from vita.banda import Braccialetto, cerca_braccialetto                # noqa: E402


def main() -> int:
    trovato = cerca_braccialetto()
    if not trovato:
        print("Nessun braccialetto accoppiato con questo PC.")
        return 1
    print(f"Braccialetto: {trovato[1]}  ({trovato[0]})")
    app = QCoreApplication([])
    banda = Braccialetto()
    visto = {"batteria": False, "ora": False}

    def riga(testo: str) -> None:
        print(f"  {testo}", flush=True)

    banda.stato.connect(lambda _c, frase: riga(frase))
    banda.batteria.connect(
        lambda livello, carica: (visto.__setitem__("batteria", True),
                                 riga(f"batteria {livello}%"
                                      + (" (in carica)" if carica else ""))))
    banda.orologio.connect(
        lambda quando: (visto.__setitem__("ora", True),
                        riga(f"segna {quando} — qui sono le "
                             f"{time.strftime('%d/%m %H:%M')}")))
    banda.battito.connect(lambda v: riga(f"battito {v} bpm"))
    banda.sincronia.connect(
        lambda lotti, esito: riga(f"dati da prendere: {lotti} lotti · {esito}"))

    banda.accendi()
    QTimer.singleShot(9000, lambda: banda.sincronizza(0))
    QTimer.singleShot(18000, lambda: (banda.spegni(), app.quit()))
    app.exec()
    if visto["batteria"]:
        print("Il braccialetto risponde: niente da ripristinare, "
              "le sue impostazioni e i suoi dati sono al loro posto.")
    else:
        print("Non ha risposto: controlla che sia sveglio e al polso.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
