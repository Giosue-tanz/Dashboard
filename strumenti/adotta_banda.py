#!/usr/bin/env python3
"""L'adozione del braccialetto: questo computer al posto del telefono.

Due modi, e il primo non tocca niente:

    python3 strumenti/adotta_banda.py              chiede e basta
    python3 strumenti/adotta_banda.py --adotta     scrive, e cambia il compagno

Senza `--adotta` manda solo le due domande del servizio 1 («chi sei», «come
stai»): se il braccialetto risponde, vuol dire che parla la lingua
dell'adozione e che il resto ha senso provarlo.

Con `--adotta` manda anche i due passi che **scrivono** (ora, fuso, lingua e
l'accordo): da lì in poi il compagno del braccialetto è questo PC. Prima di
usarlo, leggi quello che dice il README sul reset.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QCoreApplication, QTimer                    # noqa: E402

from vita.banda import Braccialetto, cerca_braccialetto                # noqa: E402


def main() -> int:
    argomenti = argparse.ArgumentParser(description=__doc__)
    argomenti.add_argument("--adotta", action="store_true",
                           help="manda anche i passi che scrivono")
    argomenti.add_argument("--secondi", type=int, default=45)
    opzioni = argomenti.parse_args()

    trovato = cerca_braccialetto()
    if not trovato:
        print("Nessun braccialetto accoppiato con questo PC.")
        return 1
    print(f"Braccialetto: {trovato[1]}  ({trovato[0]})")
    print("Scrivo sul braccialetto: SÌ" if opzioni.adotta
          else "Solo domande: non scrivo niente")

    app = QCoreApplication([])
    banda = Braccialetto()
    risposte = {"viste": 0}

    def riga(testo: str) -> None:
        print(f"  [{time.strftime('%H:%M:%S')}] {testo}", flush=True)

    banda.stato.connect(lambda _c, frase: riga(frase))
    banda.firmware.connect(lambda v: riga(f"FIRMWARE: {v}"))
    banda.batteria.connect(lambda l, _c: riga(f"batteria {l}%"))
    banda.sincronia.connect(lambda n, e: riga(f"salute: {n} lotti · {e}"))

    def adozione(nota: str) -> None:
        risposte["viste"] += 1
        riga(f"adozione · {nota}")
    banda.adozione.connect(adozione)

    banda.accendi()
    if opzioni.adotta:
        QTimer.singleShot(11000, lambda: banda.adotta(conferma=True))
        QTimer.singleShot(24000, lambda: banda.sincronizza(0))
    else:
        QTimer.singleShot(11000, banda.presentati)
        QTimer.singleShot(20000, lambda: banda.sincronizza(0))
    QTimer.singleShot(opzioni.secondi * 1000, lambda: (banda.spegni(), app.quit()))
    app.exec()
    print("Il braccialetto ha risposto ai passi dell'adozione."
          if risposte["viste"] > 1 else
          "Nessuna risposta dal servizio dell'adozione.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
