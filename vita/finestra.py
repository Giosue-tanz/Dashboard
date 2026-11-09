"""Finestra principale: barra laterale con i punteggi, viste impilate."""
from __future__ import annotations

import os

from PySide6.QtCore import (QEasingCurve, QEvent, QPropertyAnimation, QSize, Qt,
                            QVariantAnimation)
from PySide6.QtGui import QColor, QIcon, QKeySequence, QPalette, QShortcut
from PySide6.QtWidgets import (QApplication, QButtonGroup, QGraphicsOpacityEffect,
                               QGridLayout, QHBoxLayout, QLabel, QMainWindow,
                               QPushButton, QSizePolicy, QSpacerItem, QStackedWidget,
                               QStatusBar, QVBoxLayout, QWidget)

from . import punteggi as calcolo
from .componenti import separatore
from .db import DATA_DIR, Database
from .fonti import fonte_finanza
from .grafici import Anello
from .icone_nav import (RISORSE, icona, icona_menu, logo_app,
                        percorso_logo)
from .tema import (AREE, SCALE, colore_area, colori,
                   foglio_stile, frecce_spin, luminosita, su_colore)
from .utils import durata, euro, numero
from .views.abitudini import VistaAbitudini
from .views.accademica import VistaAccademica
from .views.carriera import VistaCarriera
from .views.cruscotto import VistaCruscotto
from .views.emozioni import VistaEmozioni
from .views.finanza import VistaFinanza
from .views.impostazioni import VistaImpostazioni
from .views.salute import VistaSalute
from .views.tess import VistaTess

LARGHEZZA_APERTA = 222
LARGHEZZA_CHIUSA = 62

VISTE = [
    ("cruscotto", VistaCruscotto),
    ("emozioni", VistaEmozioni),
    ("carriera", VistaCarriera),
    ("accademica", VistaAccademica),
    ("salute", VistaSalute),
    ("finanza", VistaFinanza),
    ("abitudini", VistaAbitudini),
    ("impostazioni", VistaImpostazioni),
    ("tess", VistaTess),
]
# Il cruscotto non ha una voce propria: ci si arriva dal marchio TANZ.
# Sopra la riga le cinque aree — finanza compresa — sotto gli strumenti.
NAVIGAZIONE = [1, 2, 3, 4, 5, None, 6, 8, 7]
CRUSCOTTO = 0


class Punteggio(QWidget):
    """Un indicatore in fondo alla barra: anello, nome e valore.

    Con `formato="euro"` il numero grande è il patrimonio invece del punteggio
    da 1 a 100: l'anello continua a mostrare lo stato dei conti.
    Da barra chiusa resta il solo anello: il valore si legge nel suggerimento.
    """

    def __init__(self, nome: str, colore: str, colori_tema: dict,
                 formato: str = "punteggio", parent=None):
        super().__init__(parent)
        self.formato = formato
        self.setObjectName("Punteggio")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.nome = nome
        self.colore = colore
        self.c = colori_tema
        self.valore = 0
        self.testo_valore = ""
        self.setCursor(Qt.PointingHandCursor)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 7, 10, 7)
        lay.setSpacing(11)

        self.anello = Anello(colori_tema, colore)
        self.anello.setFixedSize(36, 36)
        lay.addWidget(self.anello)

        self.testi = QWidget()
        self.testi.setObjectName("ContenutoSezione")
        colonna = QVBoxLayout(self.testi)
        colonna.setContentsMargins(0, 0, 0, 0)
        colonna.setSpacing(1)
        self.et_nome = QLabel(nome.upper())
        self.et_nome.setObjectName("NomePunteggio")
        self.et_valore = QLabel("—")
        self.et_valore.setObjectName("ValorePunteggio")
        colonna.addWidget(self.et_nome)
        colonna.addWidget(self.et_valore)
        lay.addWidget(self.testi, 1)

    def imposta(self, dati: dict) -> None:
        self.valore = dati["valore"]
        # l'anello resta il punteggio anche quando il numero sono i soldi
        self.anello.imposta(self.valore / 100, "", "")
        if self.formato == "euro":
            self.testo_valore = euro(dati.get("saldo", 0.0)).replace(",00", "")
            suggerimento = calcolo.dettaglio_finanza(dati)
        else:
            self.testo_valore = str(self.valore)
            suggerimento = calcolo.dettaglio_testo(self.nome, dati)
        self.et_valore.setText(self.testo_valore)
        self.setToolTip(suggerimento)

    def mostra_testi(self, visibili: bool) -> None:
        self.testi.setVisible(visibili)
        self.layout().setContentsMargins(*((0, 5, 0, 5) if not visibili
                                           else (8, 7, 10, 7)))
        self.layout().setAlignment(Qt.AlignCenter if not visibili
                                   else Qt.AlignLeft | Qt.AlignVCenter)

    def aggiorna_tema(self, colori_tema: dict) -> None:
        self.c = colori_tema
        self.anello.aggiorna_tema(colori_tema)
        if getattr(self, "testo_valore", ""):
            self.et_valore.setText(self.testo_valore)


class FinestraPrincipale(QMainWindow):
    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.fonte = fonte_finanza(db)
        self.tema = db.leggi("tema", "scuro")
        self.c = colori(db.leggi("tema", "scuro"))
        # stato delle icone animate della barra, una voce per pulsante:
        # «fase» è il fotogramma del disegno (1 = icona ferma)
        self._fase_icona: dict[int, float] = {}
        self._animazioni_icona: dict[int, QVariantAnimation] = {}
        self.setWindowTitle("Dashboard")
        self.resize(1360, 880)
        self.setMinimumSize(1060, 700)
        self.setWindowIcon(logo_app(db.leggi("tema", "scuro")))

        centrale = QWidget()
        self.setCentralWidget(centrale)
        lay = QHBoxLayout(centrale)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self._barra())
        lay.addWidget(self._contenuto(), 1)

        self.setStatusBar(QStatusBar())
        self.statusBar().setSizeGripEnabled(False)
        self._scorciatoie()
        self.applica_tema(db.leggi("tema", "scuro"))
        self.vai(0)

    # ------------------------------------------------------------- barra
    def _barra(self) -> QWidget:
        self.barra = QWidget()
        self.barra.setObjectName("Barra")
        self.barra.setFixedWidth(LARGHEZZA_APERTA)
        lay = QVBoxLayout(self.barra)
        lay.setContentsMargins(12, 14, 12, 14)
        lay.setSpacing(5)
        self.lay_barra = lay

        self.testata = QWidget()
        self.testata.setObjectName("TestataBarra")
        self.testata.setFixedHeight(44)
        testa = QHBoxLayout(self.testata)
        testa.setContentsMargins(6, 0, 0, 0)
        testa.setSpacing(8)
        self.b_logo = QPushButton()
        self.b_logo.setObjectName("LogoApp")
        self.b_logo.setCursor(Qt.PointingHandCursor)
        self.b_logo.setCheckable(True)
        self.b_logo.clicked.connect(self._marchio_premuto)
        self._aggiorna_logo(self.db.leggi("tema", "scuro"))

        self.b_menu = QPushButton()
        self.b_menu.setObjectName("BottoneMenu")
        self.b_menu.setFixedSize(32, 32)
        self.b_menu.setIconSize(QSize(18, 18))
        self.b_menu.setToolTip("Apri o chiudi il menu  (Ctrl+B)")
        self.b_menu.clicked.connect(self.commuta_barra)

        self.spazio_testa = QSpacerItem(0, 0, QSizePolicy.Fixed, QSizePolicy.Minimum)
        testa.addItem(self.spazio_testa)
        testa.addWidget(self.b_logo)
        testa.addStretch(1)
        testa.addWidget(self.b_menu)
        self.lay_testa = testa
        lay.addWidget(self.testata)
        lay.addSpacing(14)

        self.gruppo = QButtonGroup(self)
        self.gruppo.setExclusive(True)
        self.pulsanti: dict[int, QPushButton] = {}
        for voce in NAVIGAZIONE:
            if voce is None:
                self.separatore_aree = separatore()
                self.separatore_aree.setContentsMargins(6, 8, 6, 8)
                lay.addWidget(self.separatore_aree)
                continue
            b = QPushButton()
            b.setObjectName("Navigazione")
            b.setIconSize(QSize(19, 19))
            b.setCheckable(True)
            # la tinta della sezione: il foglio di stile ha una regola per voce
            b.setProperty("area", VISTE[voce][0])
            b.installEventFilter(self)       # per animare l'icona al passaggio
            b.clicked.connect(lambda _=False, idx=voce: self.vai(idx))
            self.gruppo.addButton(b, voce)
            self.pulsanti[voce] = b
            lay.addWidget(b)

        lay.addStretch(1)

        # in fondo: come stai andando, sempre sott'occhio, in un riquadro loro
        self.piede = QWidget()
        self.piede.setObjectName("PiedeBarra")
        self.lay_piede = QVBoxLayout(self.piede)
        self.lay_piede.setContentsMargins(6, 6, 6, 6)
        self.lay_piede.setSpacing(2)
        self.punteggi = {
            "emotivita": Punteggio("Emotività", AREE["emozioni"], self.c),
            "salute": Punteggio("Salute", AREE["salute"], self.c),
            # la finanza mostra il patrimonio, non un voto da 1 a 100
            "finanza": Punteggio("Finanza", AREE["finanza"], self.c,
                                 formato="euro"),
        }
        for chiave, widget in self.punteggi.items():
            indice = {"emotivita": 1, "finanza": 5, "salute": 4}[chiave]
            widget.mousePressEvent = lambda _ev, i=indice: self.vai(i)
            self.lay_piede.addWidget(widget)
        lay.addWidget(self.piede)

        self.barra_chiusa = self.db.leggi("barra_chiusa", "0") == "1"
        self._disegna_barra()
        return self.barra

    def _disegna_barra(self, applica_larghezza: bool = True) -> None:
        chiusa = self.barra_chiusa
        if applica_larghezza:
            self.barra.setFixedWidth(LARGHEZZA_CHIUSA if chiusa else LARGHEZZA_APERTA)
        self.b_menu.setVisible(not chiusa)
        self.testata.setFixedHeight(44)
        self.piede.setObjectName("" if chiusa else "PiedeBarra")
        self.piede.style().unpolish(self.piede); self.piede.style().polish(self.piede)
        self.lay_piede.setContentsMargins(*((0, 4, 0, 4) if chiusa else (6, 6, 6, 6)))
        for widget in self.punteggi.values():
            widget.mostra_testi(not chiusa)
        self._aggiorna_logo(self.tema)
        self.b_logo.setToolTip("Apri il menu  (Ctrl+B)" if chiusa
                               else "Cruscotto  (Ctrl+1)")
        self.lay_testa.setContentsMargins(*((0, 0, 0, 0) if chiusa else (6, 0, 0, 0)))
        self.spazio_testa.changeSize(
            0, 0, QSizePolicy.Expanding if chiusa else QSizePolicy.Fixed,
            QSizePolicy.Minimum)
        self.lay_testa.invalidate()
        self.lay_barra.setContentsMargins(*((8, 14, 8, 16) if chiusa else (12, 14, 12, 14)))
        for indice, b in self.pulsanti.items():
            if chiusa:
                b.setFixedSize(46, 44)
            else:
                b.setMinimumSize(0, 0)
                b.setMaximumSize(16777215, 16777215)
            classe = VISTE[indice][1]
            b.setText("" if chiusa else f"   {classe.titolo}")
            # la riga di spiegazione è sparita dalla pagina: vive nel suggerimento
            b.setToolTip(f"{classe.titolo} — {classe.sottotitolo}" if chiusa
                         else classe.sottotitolo)
            b.setProperty("compatta", "si" if chiusa else "no")
            b.style().unpolish(b); b.style().polish(b)

    def commuta_barra(self) -> None:
        self.barra_chiusa = not self.barra_chiusa
        self.db.imposta("barra_chiusa", "1" if self.barra_chiusa else "0")
        destinazione = LARGHEZZA_CHIUSA if self.barra_chiusa else LARGHEZZA_APERTA
        self._disegna_barra(applica_larghezza=False)
        self.animazione = QPropertyAnimation(self.barra, b"minimumWidth", self)
        self.animazione.setDuration(170)
        self.animazione.setStartValue(self.barra.width())
        self.animazione.setEndValue(destinazione)
        self.animazione.setEasingCurve(QEasingCurve.InOutCubic)
        self.animazione.valueChanged.connect(
            lambda valore: self.barra.setFixedWidth(int(valore)))
        self.animazione.start()

    # ---------------------------------------------------------- contenuto
    def _contenuto(self) -> QWidget:
        contenitore = QWidget()
        lay = QVBoxLayout(contenitore)
        lay.setContentsMargins(26, 18, 26, 18)
        lay.setSpacing(16)

        testa = QHBoxLayout()
        testa.setContentsMargins(0, 0, 0, 0)
        testa.setSpacing(12)

        self.et_titolo = QLabel("")
        self.et_titolo.setObjectName("Titolo")
        testa.addWidget(self.et_titolo, 0, Qt.AlignVCenter)
        testa.addStretch(1)

        self.azioni_vista = QHBoxLayout()
        self.azioni_vista.setSpacing(8)
        testa.addLayout(self.azioni_vista)
        # i pulsanti delle viste che non sono in primo piano aspettano qui:
        # senza un genitore diventerebbero finestrelle per conto loro appena
        # qualcuno li rende visibili (per esempio al cambio di tema)
        self.deposito_azioni = QWidget(contenitore)
        self.deposito_azioni.hide()
        self.b_nuovo = QPushButton("")
        self.b_nuovo.setObjectName("Primario")
        self.b_nuovo.setMinimumHeight(34)
        self.b_nuovo.clicked.connect(self.nuovo)
        testa.addWidget(self.b_nuovo, 0, Qt.AlignVCenter)
        lay.addLayout(testa)

        self.pila = QStackedWidget()
        self.viste = []
        for _, classe in VISTE:
            vista = classe(self.db, self.c, self.fonte)
            vista.area_richiesta.connect(self.vai_ad_area)
            vista.dati_cambiati.connect(self.ricarica)
            if hasattr(vista, "tema_cambiato"):
                vista.tema_cambiato.connect(self.applica_tema)
            if hasattr(vista, "aspetto_cambiato"):
                vista.aspetto_cambiato.connect(
                    lambda: self.applica_tema(self.db.leggi("tema", "scuro")))
            if hasattr(vista, "fonte_cambiata"):
                vista.fonte_cambiata.connect(self.cambia_fonte)
            # i pulsanti della testata nascono senza genitore: si parcheggiano
            # subito nel deposito, se no la prima volta che qualcuno li rende
            # visibili (cambio di tema, ricarica) spuntano come finestrelle
            for pulsante in getattr(vista, "azioni_intestazione", []):
                pulsante.setParent(self.deposito_azioni)
                pulsante.hide()
            self.viste.append(vista)
            self.pila.addWidget(vista)
        lay.addWidget(self.pila, 1)
        self._ripulisci_impostazioni()
        return contenitore

    def _scorciatoie(self) -> None:
        QShortcut(QKeySequence("Ctrl+N"), self, self.nuovo)
        QShortcut(QKeySequence("Ctrl+R"), self, self.ricarica)
        QShortcut(QKeySequence("Ctrl+T"), self, self.commuta_tema)
        QShortcut(QKeySequence("Ctrl+B"), self, self.commuta_barra)
        QShortcut(QKeySequence("Ctrl+Q"), self, self.close)
        for i in range(len(VISTE)):
            QShortcut(QKeySequence(f"Ctrl+{i + 1}"), self, lambda idx=i: self.vai(idx))

    def _ripulisci_impostazioni(self) -> None:
        """Le disposizioni di versioni passate, e i periodi di riquadri che non
        esistono più, resterebbero nell'archivio per sempre: qui se ne vanno.

        Lo sanno le viste stesse quali impostazioni usano, così la pulizia non
        va aggiornata a mano ogni volta che cambia un riquadro.
        """
        usate: dict = {}
        for vista in self.viste:
            if hasattr(vista, "impostazioni_usate"):
                usate.update(vista.impostazioni_usate())
        self.db.impostazioni_tolte = self.db.ripulisci_impostazioni(usate)

    # -------------------------------------------------------------- azioni
    def vai(self, indice: int) -> None:
        self.pila.setCurrentIndex(indice)
        pulsante = self.pulsanti.get(indice)
        if pulsante is not None:
            pulsante.setChecked(True)
            self.anima_icona(indice)
        else:                      # cruscotto: nessuna voce, si accende il marchio
            # in un gruppo esclusivo Qt rifiuta di spegnere l'ultimo acceso:
            # si allenta il vincolo per il tempo di spegnerli tutti
            self.gruppo.setExclusive(False)
            for b in self.pulsanti.values():
                b.setChecked(False)
            self.gruppo.setExclusive(True)
        self.b_logo.setChecked(indice == CRUSCOTTO)
        vista = self.viste[indice]
        self._comandi_vista(vista)
        self.et_titolo.setText(vista.titolo)
        self.b_nuovo.setText(vista.nome_nuovo)
        self.b_nuovo.setVisible(bool(vista.nome_nuovo))
        self._stile_nuovo(vista)
        vista.aggiorna()
        self._aggiorna_stato()
        self._dissolvi(vista)

    def _dissolvi(self, vista) -> None:
        """Un velo che se ne va in due decimi: il cambio pagina si vede."""
        if not self.isVisible():
            return
        effetto = QGraphicsOpacityEffect(vista)
        vista.setGraphicsEffect(effetto)
        self.dissolvenza = QPropertyAnimation(effetto, b"opacity", self)
        self.dissolvenza.setDuration(180)
        self.dissolvenza.setStartValue(0.25)
        self.dissolvenza.setEndValue(1.0)
        self.dissolvenza.setEasingCurve(QEasingCurve.OutCubic)
        # l'effetto si toglie a fine corsa: pesa, e serve solo per l'entrata
        self.dissolvenza.finished.connect(lambda: vista.setGraphicsEffect(None))
        self.dissolvenza.start()

    def _stile_nuovo(self, vista) -> None:
        """Il pulsante è verde solo se l'azione si può davvero fare."""
        risalto = bool(getattr(vista, "nuovo_in_risalto", True))
        self.b_nuovo.setObjectName("Primario" if risalto else "AzioneTestata")
        self.b_nuovo.setToolTip(getattr(vista, "nota_nuovo", ""))
        self.b_nuovo.style().unpolish(self.b_nuovo)
        self.b_nuovo.style().polish(self.b_nuovo)

    def _comandi_vista(self, vista) -> None:
        while self.azioni_vista.count():
            elemento = self.azioni_vista.takeAt(0)
            widget = elemento.widget()
            if widget is not None:
                widget.setParent(self.deposito_azioni)
                widget.hide()
        for widget in getattr(vista, "azioni_intestazione", []):
            # i pulsanti prendono lo stile della testata (una vista può chiedere
            # il risalto); gli altri comandi tengono il nome che si sono dati
            if isinstance(widget, QPushButton):
                widget.setObjectName("Primario" if widget.property("risalto")
                                     else "AzioneTestata")
            widget.setMinimumHeight(34)
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            self.azioni_vista.addWidget(widget)
            widget.show()

    def vai_ad_area(self, nome: str) -> None:
        """Una vista chiede di passare a un'altra pagina (per nome)."""
        for indice, (chiave, _) in enumerate(VISTE):
            if chiave == nome:
                self.vai(indice)
                return

    def nuovo(self) -> None:
        self.viste[self.pila.currentIndex()].nuovo()

    def ricarica(self) -> None:
        self.viste[self.pila.currentIndex()].aggiorna()
        self._aggiorna_stato()

    def cambia_fonte(self) -> None:
        vecchia = self.fonte
        self.fonte = fonte_finanza(self.db)
        if hasattr(vecchia, "chiudi"):
            vecchia.chiudi()
        for vista in self.viste:
            vista.fonte = self.fonte
        self._stile_nuovo(self.viste[self.pila.currentIndex()])
        self.ricarica()

    def commuta_tema(self) -> None:
        nuovo = "chiaro" if self.db.leggi("tema", "scuro") == "scuro" else "scuro"
        self.db.imposta("tema", nuovo)
        self.applica_tema(nuovo)

    # --------------------------------------------------------------- stato
    def _aggiorna_stato(self) -> None:
        dati = calcolo.tutti(self.db, self.fonte)
        for chiave, widget in self.punteggi.items():
            widget.imposta(dati[chiave])

        from .utils import settimana_corrente
        dal, al = settimana_corrente()
        studio = self.db.minuti_studio(dal, al)
        lavoro = self.db.minuti_lavoro(dal, al)
        self.statusBar().showMessage(
            f"questa settimana: {durata(studio)} di studio · {durata(lavoro)} di lavoro"
            f"   ·   finanza da {self.fonte.nome}"
            f"   ·   archivio locale: {self.db.percorso}"
            "   ·   nessuna connessione di rete")

    @staticmethod
    def _palette(c: dict) -> QPalette:
        p = QPalette()
        p.setColor(QPalette.Window, QColor(c["fondo"]))
        p.setColor(QPalette.WindowText, QColor(c["testo"]))
        p.setColor(QPalette.Base, QColor(c["pannello"]))
        p.setColor(QPalette.AlternateBase, QColor(c["pannello2"]))
        p.setColor(QPalette.Text, QColor(c["testo"]))
        p.setColor(QPalette.PlaceholderText, QColor(c["testo2"]))
        p.setColor(QPalette.Button, QColor(c["pannello2"]))
        p.setColor(QPalette.ButtonText, QColor(c["testo"]))
        p.setColor(QPalette.ToolTipBase, QColor(c["pannello2"]))
        p.setColor(QPalette.ToolTipText, QColor(c["testo"]))
        p.setColor(QPalette.Highlight, QColor(c["accento"]))
        p.setColor(QPalette.HighlightedText, QColor("#ffffff"))
        p.setColor(QPalette.Link, QColor(c["accento"]))
        return p

    def _marchio_premuto(self) -> None:
        """Da barra aperta porta al cruscotto; da chiusa riapre la barra."""
        if self.barra_chiusa:
            self.commuta_barra()
            self.b_logo.setChecked(self.pila.currentIndex() == CRUSCOTTO)
        else:
            self.vai(CRUSCOTTO)

    def _aggiorna_logo(self, tema: str) -> None:
        """Il marchio segue il tema: chiaro su scuro, scuro su chiaro.

        È sempre la sola scritta, su fondo trasparente — anche a barra chiusa,
        dove prima stava il quadrato dell'icona: quella piastrella ha il suo
        nero cotto dentro e sul pannello si vedeva come un francobollo
        attaccato sopra. Il quadrato resta dov'è giusto che sia: l'icona
        dell'applicazione nella barra del sistema.
        """
        chiusa = getattr(self, "barra_chiusa", False)
        percorso = os.path.join(
            RISORSE, "marchio-chiaro.png" if tema == "scuro"
            else "marchio-scuro.png")
        if chiusa:
            self.b_logo.setIconSize(QSize(42, 11))
            self.b_logo.setFixedSize(46, 42)
        else:
            self.b_logo.setIconSize(QSize(78, 20))
            self.b_logo.setFixedSize(86, 30)
        if percorso and os.path.exists(percorso):
            self.b_logo.setIcon(QIcon(percorso))
        self.setWindowIcon(logo_app(tema))

    def _aggiorna_icone(self) -> None:
        self.b_menu.setIcon(icona_menu(self.c["testo2"]))
        for indice in self.pulsanti:
            self._icona_voce(indice)

    def _icona_voce(self, indice: int, fase: float | None = None) -> None:
        """Rifà l'icona di una voce: sempre nella tinta della sua sezione, in
        negativo quando la pastiglia è piena.

        `fase` è il fotogramma del disegno (1 = icona ferma); se non la si
        passa vale quella a cui è arrivata l'animazione in corso.
        """
        b = self.pulsanti.get(indice)
        if b is None:
            return
        if fase is None:
            fase = self._fase_icona.get(indice, 1.0)
        else:
            self._fase_icona[indice] = fase
        chiave = VISTE[indice][0]
        tinta = colore_area(chiave, luminosita(self.c["fondo"]) > 0.5)
        b.setIcon(icona(chiave, tinta, su_colore(tinta), tinta, fase))

    # ------------------------------------------------------ icone animate
    def eventFilter(self, oggetto, evento):
        """Il mouse che entra su una voce le fa fare il suo gesto."""
        if evento.type() == QEvent.Enter:
            for indice, b in getattr(self, "pulsanti", {}).items():
                if b is oggetto:
                    self.anima_icona(indice)
                    break
        return super().eventFilter(oggetto, evento)

    def _anima(self, deposito: dict, indice: int, da: float, a: float,
               durata: int, passo) -> None:
        """Una sola animazione per voce e per genere, riusata ogni volta: la
        nuova corsa sostituisce quella in atto invece di accavallarsi."""
        anim = deposito.get(indice)
        if anim is None:
            anim = QVariantAnimation(self)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            anim.valueChanged.connect(lambda v, i=indice: passo(i, float(v)))
            anim.finished.connect(
                lambda i=indice, an=anim: passo(i, float(an.endValue())))
            deposito[indice] = anim
        anim.stop()
        anim.setDuration(durata)
        anim.setStartValue(da)
        anim.setEndValue(a)
        anim.start()

    def anima_icona(self, indice: int) -> None:
        """Mezzo secondo di vita: il cuore batte, la spunta si scrive."""
        if not self.isVisible() or indice not in self.pulsanti:
            return
        vecchia = self._animazioni_icona.get(indice)
        if vecchia is not None and vecchia.state() == QVariantAnimation.Running:
            return                      # già in corso: non si accavalla
        self._anima(self._animazioni_icona, indice, 0.0, 1.0, 620,
                    self._icona_voce)

    def applica_tema(self, nome: str) -> None:
        self.tema = nome
        self.c = colori(nome)
        scala = SCALE.get(self.db.leggi("scala", "normale"), 1.0)
        app = QApplication.instance()
        if app is not None:
            app.setPalette(self._palette(self.c))
        extra = f"""
        QWidget#Punteggio {{ background: transparent; border-radius: 10px; }}
        QWidget#Punteggio:hover {{ background: {self.c['pannello2']}; }}
        QFrame#Cartellino {{ border-radius: 10px; }}
        """
        self.setStyleSheet(foglio_stile(self.c, scala, frecce_spin(
            os.path.join(DATA_DIR, "cache"), self.c["testo2"])) + extra)
        if hasattr(self, "pulsanti"):
            self._aggiorna_icone()
        if hasattr(self, "b_logo"):
            self._aggiorna_logo(nome)
        for widget in self.punteggi.values():
            widget.aggiorna_tema(self.c)
        for vista in self.viste:
            vista.aggiorna_tema(self.c)
        self._aggiorna_stato()

    def closeEvent(self, ev) -> None:
        for vista in self.viste:
            riquadro = getattr(vista, "riquadro", None)
            if hasattr(riquadro, "chiudi"):
                riquadro.chiudi()
        if hasattr(self.fonte, "chiudi"):
            self.fonte.chiudi()
        self.db.chiudi()
        super().closeEvent(ev)
