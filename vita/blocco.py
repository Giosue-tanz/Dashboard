"""La password della Dashboard.

**Una porta, non una cassaforte.** La password impedisce di aprire l'app —
non cifra l'archivio: `~/.local/share/Vita/vita.db` resta un file SQLite che
chiunque abbia accesso al computer può aprire con altri programmi. Serve
contro l'occhiata di chi ti passa accanto, non contro chi ti ruba il portatile.
Per quello servirebbe cifrare il disco (LUKS), che è il mestiere del sistema.

La password non viene salvata: si salva solo la sua impronta, calcolata con
PBKDF2-SHA256 e 240.000 giri, insieme a un pizzico di sale diverso per ognuno.
Chi legge l'archivio trova quella, e da quella non si torna indietro.

Se la dimentichi, si toglie da terminale:

    sqlite3 ~/.local/share/Vita/vita.db \\
        "DELETE FROM impostazioni WHERE chiave LIKE 'blocco_%';"
"""
from __future__ import annotations

import hashlib
import os

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QVBoxLayout, QWidget)

from .icone_nav import percorso_logo

GIRI = 240_000
ATTESE = {3: 2, 5: 5, 7: 15, 10: 60}     # tentativi sbagliati → secondi di stop


def _impronta(password: str, sale: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), sale,
                               GIRI).hex()


def attivo(db) -> bool:
    """C'è una password da chiedere all'avvio?"""
    return bool(db.leggi("blocco_impronta", ""))


def imposta(db, password: str) -> None:
    """Mette (o toglie, con la stringa vuota) la password."""
    if not password:
        for chiave in ("blocco_impronta", "blocco_sale"):
            db.esegui("DELETE FROM impostazioni WHERE chiave=?", (chiave,))
        return
    sale = os.urandom(16)
    db.imposta("blocco_sale", sale.hex())
    db.imposta("blocco_impronta", _impronta(password, sale))


def verifica(db, password: str) -> bool:
    impronta = db.leggi("blocco_impronta", "")
    sale = db.leggi("blocco_sale", "")
    if not impronta or not sale:
        return True
    # confronto a tempo costante: non si fa indovinare lettera per lettera
    import hmac
    return hmac.compare_digest(_impronta(password, bytes.fromhex(sale)), impronta)


class DialogoBlocco(QDialog):
    """La schermata che chiede la password prima di aprire la Dashboard."""

    def __init__(self, db, colori: dict, tema: str = "scuro", parent=None):
        super().__init__(parent)
        self.db = db
        self.c = colori
        self.sbagliati = 0
        self.setWindowTitle("Dashboard")
        self.setModal(True)
        self.setFixedWidth(380)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 26, 28, 22)
        lay.setSpacing(14)

        marchio = QLabel()
        marchio.setAlignment(Qt.AlignCenter)
        percorso = percorso_logo(tema, 128)
        if percorso:
            marchio.setPixmap(QPixmap(percorso).scaled(
                54, 54, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        lay.addWidget(marchio)

        titolo = QLabel("Dashboard")
        titolo.setObjectName("ValoreScheda")
        titolo.setAlignment(Qt.AlignCenter)
        lay.addWidget(titolo)

        self.nota = QLabel("Scrivi la password per entrare.")
        self.nota.setObjectName("NotaScheda")
        self.nota.setAlignment(Qt.AlignCenter)
        self.nota.setWordWrap(True)
        lay.addWidget(self.nota)

        self.campo = QLineEdit()
        self.campo.setObjectName("CampoTess")
        self.campo.setEchoMode(QLineEdit.Password)
        self.campo.setMinimumHeight(42)
        self.campo.setAlignment(Qt.AlignCenter)
        self.campo.returnPressed.connect(self._prova)
        lay.addWidget(self.campo)

        self.b_entra = QPushButton("Entra")
        self.b_entra.setObjectName("Primario")
        self.b_entra.setMinimumHeight(42)
        self.b_entra.clicked.connect(self._prova)
        b_esci = QPushButton("Esci")
        b_esci.setMinimumHeight(42)
        b_esci.clicked.connect(self.reject)
        fila = QHBoxLayout()
        fila.setSpacing(10)
        fila.addWidget(b_esci)
        fila.addWidget(self.b_entra, 1)
        lay.addLayout(fila)

    def _prova(self) -> None:
        if verifica(self.db, self.campo.text()):
            self.accept()
            return
        self.sbagliati += 1
        self.campo.clear()
        attesa = ATTESE.get(self.sbagliati, 0)
        if attesa:
            # dopo qualche errore si aspetta: a tentare a caso non si arriva
            self.campo.setEnabled(False)
            self.b_entra.setEnabled(False)
            self.nota.setText(f"Non è quella. Riprova fra {attesa} secondi.")
            QTimer.singleShot(attesa * 1000, self._riapri)
        else:
            self.nota.setText("Non è quella. Riprova.")

    def _riapri(self) -> None:
        self.campo.setEnabled(True)
        self.b_entra.setEnabled(True)
        self.campo.setFocus()
        self.nota.setText("Scrivi la password per entrare.")


def chiedi(db, colori: dict, tema: str = "scuro") -> bool:
    """Chiede la password se serve. Torna False se si deve chiudere l'app."""
    if not attivo(db):
        return True
    dialogo = DialogoBlocco(db, colori, tema)
    return dialogo.exec() == QDialog.Accepted
