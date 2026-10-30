"""Il riquadro del braccialetto dentro Salute.

Si comporta come Tess: finché non accendi l'interruttore non si collega
niente. Il braccialetto parla con un solo compagno alla volta, quindi
collegarlo al PC vuol dire togliere per un attimo il telefono di mezzo — ed è
giusto che a deciderlo sia tu, non l'app all'avvio.

Quello che mostra: la batteria, l'ora che segna il braccialetto e il **battito
in diretta** mentre lo stai misurando (si apre «Frequenza cardiaca» al polso).
Il battito più basso di una sessione si può salvare come battito a riposo del
giorno, che è poi il numero che conta.
"""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QHBoxLayout, QPushButton, QSizePolicy,
                               QVBoxLayout, QWidget)

from .banda import DISPONIBILE, Braccialetto, cerca_braccialetto
from .componenti import (DisposizioneFluida, EtichettaAlta,
                         Interruttore, etichetta)
from .grafici import Sparkline


class RiquadroBraccialetto(QWidget):
    """Batteria, ora e battito in diretta del braccialetto."""

    dati_cambiati = Signal()

    def __init__(self, db, colori: dict, parent=None):
        super().__init__(parent)
        self.db = db
        self.c = colori
        self.banda = Braccialetto(self)
        self.battiti: list[int] = []
        self.setObjectName("ContenutoSezione")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        # ------------------------------------------------------- la testa
        testa = QHBoxLayout()
        testa.setSpacing(8)
        trovato = cerca_braccialetto()
        self.et_nome = etichetta(trovato[1] if trovato else "Nessun braccialetto",
                                 "TitoloRiga")
        self.interruttore = Interruttore(colori)
        self.interruttore.setToolTip(
            "Collega il braccialetto a questo PC.\\nMentre è collegato qui, il "
            "telefono potrebbe non vederlo: spegnilo quando hai finito.")
        self.interruttore.cambiato.connect(self._commuta)
        testa.addWidget(self.et_nome)
        testa.addStretch(1)
        testa.addWidget(self.interruttore)
        lay.addLayout(testa)

        # ------------------------------------------------- il battito grande
        self.et_battito = EtichettaAlta("—")
        self.et_battito.setObjectName("ValoreScheda")
        self.et_battito.setAlignment(Qt.AlignCenter)
        self.et_battito.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lay.addWidget(self.et_battito)
        self.linea = Sparkline(colori)
        self.linea.setFixedHeight(28)
        self.linea.hide()            # compare al primo battito che arriva
        lay.addWidget(self.linea)

        self.et_stato = etichetta("", "NotaScheda")
        self.et_stato.setWordWrap(True)
        self.et_stato.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.et_stato)

        # --------------------------------------------------- numeri e comandi
        self.et_numeri = etichetta("", "NotaScheda")
        self.et_numeri.setWordWrap(True)
        lay.addStretch(1)
        lay.addWidget(self.et_numeri)

        fila = DisposizioneFluida(spaziatura=8)
        self.b_salva = QPushButton("Salva battito")
        self.b_salva.setObjectName("Segmento")
        self.b_salva.setMinimumHeight(34)
        self.b_salva.setEnabled(False)
        self.b_salva.clicked.connect(self._salva_battito)
        self.b_salva.setToolTip("Scrive il battito più basso di questa sessione "
                                "come battito a riposo di oggi.")
        self.b_sincronizza = QPushButton("Cerca dati")
        self.b_sincronizza.setObjectName("Segmento")
        self.b_sincronizza.setMinimumHeight(34)
        self.b_sincronizza.setEnabled(False)
        self.b_sincronizza.setToolTip(
            "Chiede al braccialetto quello che ha in pancia. Di solito non ha "
            "niente: il telefono lo svuota a ogni sincronizzazione.")
        self.b_sincronizza.clicked.connect(lambda: self.banda.sincronizza(0))
        fila.addWidget(self.b_salva)
        fila.addWidget(self.b_sincronizza)
        lay.addLayout(fila)

        for segnale, gestore in (("stato", self._stato), ("battito", self._battito),
                                 ("batteria", self._batteria),
                                 ("orologio", self._orologio),
                                 ("sincronia", self._sincronia)):
            getattr(self.banda, segnale).connect(gestore)

        if not DISPONIBILE:
            self.interruttore.setEnabled(False)
            self.et_stato.setText("Su questo computer non c'è il Bluetooth di "
                                  "sistema.")
        elif not trovato:
            self.interruttore.setEnabled(False)
            self.et_stato.setText(
                "Accoppia il braccialetto dalle impostazioni Bluetooth del "
                "sistema: poi comparirà qui.")
        else:
            self.et_stato.setText("Spento. Accendi l'interruttore per collegarlo.")
        self._numeri()

    # ------------------------------------------------------------- comandi
    def _commuta(self, acceso: bool) -> None:
        if acceso:
            if not self.banda.accendi():
                self.interruttore.imposta(False)
        else:
            self.banda.spegni()
            self.et_battito.setText("—")
            self.b_sincronizza.setEnabled(False)

    def _stato(self, codice: str, frase: str) -> None:
        self.et_stato.setText(frase)
        self.b_sincronizza.setEnabled(codice == "pronta")
        if codice in ("assente", "sconosciuto", "spento"):
            self.interruttore.imposta(False)

    def _battito(self, valore: int) -> None:
        self.battiti.append(valore)
        self.et_battito.setText(str(valore))
        self.linea.show()
        self.linea.imposta_dati(self.battiti[-60:], self.c["uscita"])
        self.b_salva.setEnabled(True)
        minimo = min(self.battiti)
        medio = sum(self.battiti) / len(self.battiti)
        self.et_stato.setText(
            f"{len(self.battiti)} misure · minimo {minimo} · medio {medio:.0f} bpm")

    def _batteria(self, livello: int, carica: int) -> None:
        self.db.imposta("banda_batteria", str(livello))
        self.db.imposta("banda_carica", str(carica))
        self._numeri()

    def _orologio(self, quando: str) -> None:
        self.db.imposta("banda_orologio", quando)
        self._numeri()

    def _sincronia(self, lotti: int, esito: str) -> None:
        self.et_stato.setText(
            f"{lotti} lotti di dati" if lotti else f"Niente da prendere: {esito}")

    def _numeri(self) -> None:
        pezzi = []
        livello = self.db.leggi("banda_batteria", "")
        if livello:
            in_carica = self.db.leggi("banda_carica", "0") != "0"
            pezzi.append(f"batteria {livello}%" + (" in carica" if in_carica else ""))
        orologio = self.db.leggi("banda_orologio", "")
        if orologio:
            pezzi.append(f"segna {orologio}")
        self.et_numeri.setText("  ·  ".join(pezzi) or
                               "apri «Frequenza cardiaca» sul braccialetto per "
                               "vedere il battito arrivare qui")

    def _salva_battito(self) -> None:
        """Il più basso della sessione: è quello che somiglia al riposo."""
        if not self.battiti:
            return
        oggi = date.today().isoformat()
        riga = self.db.salute_giorno(oggi)
        valori = dict(riga) if riga else {}
        valori.update({"data": oggi, "battito": min(self.battiti), "note": ""})
        self.db.salva_salute(valori)
        self.et_stato.setText(f"Salvato: {min(self.battiti)} bpm come battito a "
                              "riposo di oggi.")
        self.dati_cambiati.emit()

    # -------------------------------------------------------------- tema
    def aggiorna_tema(self, colori: dict) -> None:
        self.c = colori
        self.interruttore.aggiorna_tema(colori)
        self.linea.aggiorna_tema(colori)

    def aggiorna(self) -> None:
        self._numeri()

    def chiudi(self) -> None:
        """Lascia libero il braccialetto quando l'app si chiude."""
        self.banda.spegni()
