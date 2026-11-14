"""La pagina di Tess: la chat con l'AI locale, a tutta finestra.

Il riquadro è lo stesso componente riutilizzabile di `vita/tess.py`: qui prende
tutta la pagina, ma può essere messo anche dentro un riquadro del cruscotto
senza cambiare una riga.
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout

from ..componenti import Interruttore
from ..tess import RiquadroTess
from . import VistaBase


class VistaTess(VistaBase):
    titolo = "Tess"
    sottotitolo = "La tua AI locale, con i dati della Dashboard in mano"
    nome_nuovo = ""
    chiave_vista = "tess"
    # la dimensione del testo della chat è cambiata: la finestra principale
    # ascolta questo segnale su ogni pagina (vedi `finestra.py`) e rifà il
    # foglio di stile — qui si passa solo quello del riquadro più su
    aspetto_cambiato = Signal()

    def costruisci(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 6, 6)
        lay.setSpacing(10)
        self.riquadro = RiquadroTess(self.db, self.c, self.fonte)
        self.riquadro.stato_cambiato.connect(self._stato)
        self.riquadro.aspetto_cambiato.connect(self.aspetto_cambiato)
        lay.addWidget(self.riquadro, 1)

        # l'interruttore in testata: lo stesso comando del cruscotto
        self.interruttore = Interruttore(self.c, area="tess")
        self.interruttore.cambiato.connect(self._commuta)
        self.azioni_intestazione = [self.interruttore]
        self._nota(False)

    # ------------------------------------------------------------- comandi
    def _commuta(self, acceso: bool) -> None:
        if acceso:
            self.riquadro.attiva()
        else:
            self.riquadro.spegni()

    def _stato(self, pronta: bool) -> None:
        self.interruttore.imposta(pronta)       # senza riemettere il segnale
        self._nota(pronta)

    def _nota(self, pronta: bool) -> None:
        self.interruttore.setToolTip(
            "Tess è in ascolto. Spegnila per liberare la memoria della scheda "
            "video." if pronta else
            "Accende la tua AI locale: finché non la accendi non parte nessun "
            "motore e non si occupa memoria.")

    # ---------------------------------------------------------------- dati
    def aggiorna(self) -> None:
        """Allinea l'interruttore a com'è davvero il motore adesso."""
        self.riquadro.sincronizza()

    def aggiorna_tema(self, colori: dict) -> None:
        self.c = colori
        self.riquadro.aggiorna_tema(colori)
        self.interruttore.aggiorna_tema(colori)
