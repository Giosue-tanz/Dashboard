"""Palette e foglio di stile Qt: tema chiaro, tema scuro, e basta.

Stesso linguaggio visivo dell'app Finance: stessi fondi, stessi bordi, stesse
misure. Qui si aggiungono solo le tinte delle cinque aree.

Il colore principale **non si sceglie**. C'era una fila di campioni nelle
impostazioni, e serviva solo a rompere l'accordo con le tinte delle aree —
che sono fisse per un motivo: il rosso è Emozioni, il blu è Carriera, il
turchese è Salute. Il verde di casa è l'unico accento, e tutto il resto è
costruito per andarci d'accordo.
"""
from __future__ import annotations

SCURO = {
    "fondo": "#0a0a0c",
    "pannello": "#17181d",
    "pannello2": "#1f2027",
    "tocco": "#272930",          # fondo al passaggio del mouse
    "bordo": "#272930",
    "testo": "#f3f4f7",
    "testo2": "#9aa0ac",
    "accento": "#16c47f",
    "entrata": "#16c47f",
    "uscita": "#ff5a5a",
    "attenzione": "#f0b429",
    "griglia": "#272930",
}

CHIARO = {
    "fondo": "#f1f2f6",
    "pannello": "#ffffff",
    "pannello2": "#f4f5f9",
    "tocco": "#e9ebf2",
    "bordo": "#e6e8ef",
    "testo": "#15171c",
    "testo2": "#6b7280",
    "accento": "#0f9d63",
    "entrata": "#0f9d63",
    "uscita": "#d9453f",
    "attenzione": "#b07d08",
    "griglia": "#e6e8ef",
}

# Tinta fissa di ogni sezione: non dipende dall'accento scelto. Come in One
# UI ogni voce ha il suo colore invece di un unico accento che tinge tutto,
# così la barra si legge a colpo d'occhio anche senza leggere le scritte.
AREE = {
    "emozioni":     "#ff4d6d",   # rosso: il cuore
    "carriera":     "#3d7bfd",   # blu: il lavoro
    "accademica":   "#8b5cf6",   # viola: lo studio
    "salute":       "#19c2e0",   # turchese: il corpo
    "finanza":      "#22c55e",   # verde: i soldi
    "abitudini":    "#ffa62b",   # ambra: i giorni di fila
    # rosso chiaro: l'AI. Stessa famiglia di «emozioni» (349°) ma nove
    # punti di luce piu' su, cosi' si distinguono nella barra; e sul tema
    # scuro il testo che ci va sopra passa da 2,6:1 a 7,7:1.
    "tess":         "#ff7b8c",
    "impostazioni": "#94a3b8",   # ardesia: gli attrezzi
    "cruscotto":    "#16c47f",   # il verde di casa
}


def colore_area(chiave: str, chiaro: bool = False) -> str:
    """La tinta di una sezione, scurita quel tanto che serve sul tema chiaro."""
    base = AREE.get(chiave, AREE["cruscotto"])
    return scurisci(base, 0.86) if chiaro else base


def su_colore(colore: str) -> str:
    """Il colore del testo che ci va sopra: bianco, o scuro se la tinta è chiara."""
    return "#0a1014" if luminosita(colore) > 0.58 else "#ffffff"


def colori(tema: str = "scuro") -> dict:
    """Palette completa del tema richiesto."""
    base = dict(SCURO if tema == "scuro" else CHIARO)
    # su una tinta chiara il bianco non si legge: il testo diventa scuro
    base["su_accento"] = "#0a1a12" if luminosita(base["accento"]) > 0.58 else "#ffffff"
    return base


def luminosita(colore: str) -> float:
    """Quanto è chiara una tinta, da 0 (nero) a 1 (bianco)."""
    colore = colore.lstrip("#")
    r, v, b = (int(colore[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * v + 0.0722 * b


PALETTE_GRAFICI = [
    "#3d7bfd", "#16c47f", "#ff9f45", "#a46bff", "#2bc4e0",
    "#ff5a5a", "#f0b429", "#ff8fc7", "#7c8cff", "#34d4a8",
    "#b388eb", "#9aa0ac",
]


SCALE = {"compatta": 0.9, "normale": 1.0, "grande": 1.15, "molto grande": 1.3}


def frecce_spin(cartella: str, colore: str) -> tuple[str, str]:
    """Crea (una volta sola) le due freccine usate da spinbox e tendine.

    Qt non disegna frecce affidabili quando i pulsanti sono ridefiniti dal
    foglio di stile: qui vengono generate come immagini e richiamate con url().
    """
    import os

    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QColor, QPainter, QPainterPath, QPixmap

    os.makedirs(cartella, exist_ok=True)
    chiave = colore.lstrip("#")
    percorsi = (os.path.join(cartella, f"su-{chiave}.png"),
                os.path.join(cartella, f"giu-{chiave}.png"))
    if all(os.path.exists(p) for p in percorsi):
        return percorsi

    for percorso, verso in zip(percorsi, (-1, 1)):
        pixmap = QPixmap(11, 7)
        pixmap.fill(Qt.transparent)
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.Antialiasing, True)
        path = QPainterPath()
        if verso < 0:
            path.moveTo(QPointF(1.0, 5.4)); path.lineTo(QPointF(5.5, 1.3))
            path.lineTo(QPointF(10.0, 5.4))
        else:
            path.moveTo(QPointF(1.0, 1.6)); path.lineTo(QPointF(5.5, 5.7))
            path.lineTo(QPointF(10.0, 1.6))
        path.closeSubpath()
        p.fillPath(path, QColor(colore))
        p.end()
        pixmap.save(percorso)
    return percorsi


def scurisci(colore: str, fattore: float = 0.7) -> str:
    """Versione più scura di una tinta: serve ai testi colorati su fondo chiaro."""
    colore = colore.lstrip("#")
    r, v, b = (int(int(colore[i:i + 2], 16) * fattore) for i in (0, 2, 4))
    return f"#{r:02x}{v:02x}{b:02x}"


def trasparente(colore: str, opacita: float) -> str:
    """Converte #rrggbb in rgba(): in Qt l'esadecimale a 8 cifre è #AARRGGBB,
    quindi scriverlo a mano porta a colori sbagliati."""
    colore = colore.lstrip("#")
    r, v, b = (int(colore[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r}, {v}, {b}, {opacita:.2f})"


def foglio_stile(c: dict, scala: float = 1.0,
                 frecce: tuple[str, str] | None = None) -> str:
    """Foglio di stile dell'applicazione: angoli larghi, niente bordi duri.

    Stessa idea di One UI: le superfici si distinguono per tinta, non per
    cornice; i pulsanti sono pastiglie; i numeri contano più delle linee.
    """

    def p(px: float) -> str:
        """Dimensione in pixel adattata alla scala del testo."""
        return f"{px * scala:.1f}px"

    def q(px: float) -> str:
        """Come `p`, ma intera: raggi e spessori Qt li vuole senza virgola."""
        return f"{round(px * scala)}px"

    chiaro = luminosita(c["fondo"]) > 0.5
    # una regola per ogni voce della barra: il suo colore al passaggio del
    # mouse, la pastiglia piena del suo colore quando la pagina è aperta
    voci_colorate = "".join(f"""
    QPushButton#Navigazione[area="{chiave}"]:hover {{
        background: {trasparente(colore_area(chiave, chiaro), 0.16)};
        color: {colore_area(chiave, chiaro)};
    }}
    QPushButton#Navigazione[area="{chiave}"]:checked,
    QPushButton#Navigazione[area="{chiave}"]:checked:hover {{
        background: {colore_area(chiave, chiaro)};
        color: {su_colore(colore_area(chiave, chiaro))};
    }}""" for chiave in AREE)
    selezione = trasparente(c["accento"], 0.30)
    velo = trasparente("#ffffff", 0.22)
    # Tess ha il suo colore, come ogni area: il rosa. Il filo dei suoi
    # messaggi ce l'ha sempre avuto — il bottone che manda, la conversazione
    # aperta e la bolla di quello che scrivi tu invece erano verdi come il
    # resto dell'app, e nella stessa pagina si vedevano due accenti diversi.
    # Adesso la chat è tutta del colore di Tess.
    rosa = colore_area("tess", chiaro)
    su_rosa = su_colore(rosa)
    tocco = c.get("tocco", c["pannello2"])
    su_accento = c.get("su_accento", "#ffffff")
    # in chiaro le schede bianche hanno bisogno di un filo di contorno,
    # in scuro basta la differenza di tinta
    bordo_scheda = f"1px solid {c['bordo']}" if chiaro else "1px solid transparent"
    su, giu = frecce if frecce else ("", "")
    frecce_qss = f"""
    QSpinBox::up-arrow, QDoubleSpinBox::up-arrow, QDateEdit::up-arrow {{
        image: url({su}); width: 11px; height: 7px;
    }}
    QSpinBox::down-arrow, QDoubleSpinBox::down-arrow, QDateEdit::down-arrow,
    QComboBox::down-arrow {{ image: url({giu}); width: 11px; height: 7px; }}
    """ if frecce else ""

    return f"""
    * {{
        font-family: "Inter", "SamsungOne", "Noto Sans", "Segoe UI",
                     "Noto Sans CJK SC", "Source Han Sans SC", sans-serif;
        font-size: {p(13)};
    }}
    QWidget {{ color: {c['testo']}; }}
    QMainWindow, QDialog {{ background: {c['fondo']}; }}
    QLabel, QCheckBox, QRadioButton {{ background: transparent; }}

    /* ------------------------------------------------------- barra laterale */
    #Barra {{ background: {c['pannello']}; border: none; }}
    #Titolo {{ font-size: {p(25)}; font-weight: 750; color: {c['testo']}; }}
    #Sottotitolo {{ color: {c['testo2']}; font-size: {p(12)}; }}
    #Logo {{ font-size: {p(19)}; font-weight: 800; color: {c['accento']}; }}

    QPushButton#Navigazione {{
        background: transparent; border: none; border-radius: 17px;
        padding: 11px 14px; text-align: left; color: {c['testo2']};
        font-size: {p(13.5)};
    }}
    QPushButton#Navigazione:hover {{ background: {tocco}; color: {c['testo']}; }}
    QPushButton#Navigazione[compatta="si"] {{
        text-align: center; padding: 0; font-size: {p(20)}; border-radius: 16px;
    }}
    QPushButton#Navigazione[compatta="si"]:hover {{ background: {tocco}; }}
    QPushButton#Navigazione:checked {{
        background: {c['accento']}; color: {su_accento}; font-weight: 650;
    }}
    {voci_colorate}
    QPushButton#BottoneMenu {{
        background: transparent; border: none; border-radius: 16px;
        color: {c['testo2']}; font-size: {p(15)};
    }}
    QPushButton#BottoneMenu:hover {{ background: {tocco}; color: {c['testo']}; }}

    /* ------------------------------------------------------------- schede */
    QFrame#Scheda {{
        background: {c['pannello']}; border: {bordo_scheda}; border-radius: 22px;
    }}
    QWidget#Grafico, QWidget#ContenutoSezione, QScrollArea#ContenutoSezione,
    QScrollArea#ContenutoSezione > QWidget {{ background: transparent; }}
    QFrame#Separatore {{ background: {c['bordo']}; max-height: 1px; border: none; }}

    QLabel#EtichettaScheda {{ color: {c['testo2']}; font-size: {p(10.5)};
                              font-weight: 700; letter-spacing: 1px; }}
    QLabel#ValoreScheda {{ font-size: {p(26)}; font-weight: 780; }}
    QLabel#NotaScheda {{ color: {c['testo2']}; font-size: {p(11.5)}; }}
    /* i numeri della giornata nel riquadro «Oggi»: il colore glielo dà chi
       li scrive, la misura la dà qui, così cresce col resto del testo */
    QLabel#NumeroOggi {{ font-size: {p(18)}; font-weight: 750; }}
    QLabel#TitoloRiga {{ font-size: {p(13)}; font-weight: 650; }}
    QLabel#ValoreRiga {{ font-size: {p(14)}; font-weight: 780; }}
    QLabel#Sezione {{ font-size: {p(15)}; font-weight: 700; padding: 2px 0; }}

    /* ---------------------------------------------------------- pastiglie */
    QPushButton {{
        background: {c['pannello2']}; color: {c['testo']}; border: none;
        border-radius: 17px; padding: 9px 18px; font-size: {p(13)};
    }}
    QPushButton:hover {{ background: {tocco}; }}
    QPushButton:pressed {{ background: {c['bordo']}; }}
    QPushButton:disabled {{ color: {c['testo2']}; background: {c['pannello2']}; }}
    /* un campo spento si vede che è spento: scritta smorta, fondo piatto */
    QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled,
    QDoubleSpinBox:disabled, QDateEdit:disabled, QTimeEdit:disabled,
    QPlainTextEdit:disabled, QTextEdit:disabled {{
        color: {trasparente(c['testo2'], 0.55)};
        background: {trasparente(c['pannello2'], 0.45)};
    }}
    QLabel:disabled, QCheckBox:disabled {{ color: {trasparente(c['testo2'], 0.55)}; }}
    QPushButton#Primario {{
        background: {c['accento']}; color: {su_accento}; border: none;
        font-weight: 700; border-radius: 17px; padding: 9px 20px;
    }}
    QPushButton#Primario:hover {{ background: {c['accento']}; border: 1px solid {velo}; }}
    QPushButton#Primario:pressed {{ background: {scurisci(c['accento'], 0.88)}; }}
    QPushButton#Pericolo {{ background: {c['uscita']}; color: #ffffff; border: none; }}

    /* ------------------------------------------------------------- campi */
    QLineEdit, QComboBox, QDateEdit, QTimeEdit, QDoubleSpinBox, QSpinBox,
    QTextEdit, QPlainTextEdit {{
        background: {c['pannello2']}; border: 1px solid transparent;
        border-radius: 14px; padding: 9px 12px;
        selection-background-color: {c['accento']}; selection-color: {su_accento};
    }}
    QLineEdit:hover, QComboBox:hover, QDateEdit:hover, QTimeEdit:hover,
    QDoubleSpinBox:hover, QSpinBox:hover {{ background: {tocco}; }}
    QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QTimeEdit:focus,
    QDoubleSpinBox:focus, QSpinBox:focus, QTextEdit:focus,
    QPlainTextEdit:focus {{ border: 1px solid {c['accento']}; background: {c['pannello2']}; }}
    QComboBox::drop-down {{ border: none; width: 24px; }}
    QSpinBox::up-button, QDoubleSpinBox::up-button,
    QSpinBox::down-button, QDoubleSpinBox::down-button {{
        background: transparent; border: none; width: 18px;
        subcontrol-origin: border;
    }}
    QSpinBox::up-button, QDoubleSpinBox::up-button {{ subcontrol-position: top right; }}
    QSpinBox::down-button, QDoubleSpinBox::down-button {{ subcontrol-position: bottom right; }}
    QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
    QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
        background: {c['bordo']}; border-radius: 7px;
    }}
    QDateEdit::drop-down, QTimeEdit::drop-down {{ border: none; width: 24px; }}
    QComboBox QAbstractItemView {{
        background: {c['pannello']}; border: 1px solid {c['bordo']}; border-radius: 14px;
        padding: 6px; selection-background-color: {c['accento']};
        selection-color: {su_accento}; outline: none;
    }}

    /* ------------------------------------------------------------ tabelle */
    QTableWidget, QTableView {{
        background: {c['pannello2']}; border: none; border-radius: 18px;
        gridline-color: transparent; outline: none;
        selection-background-color: {selezione}; selection-color: {c['testo']};
    }}
    QTableWidget::item, QTableView::item {{
        padding: 7px 9px; border: none; border-bottom: 1px solid {c['griglia']};
    }}
    QTableWidget::item:selected, QTableView::item:selected {{
        background: {selezione}; color: {c['testo']};
    }}
    QHeaderView {{ background: transparent; border: none; }}
    QHeaderView::section {{
        background: transparent; color: {c['testo2']}; border: none;
        padding: 9px 9px; font-weight: 700; font-size: {p(10.5)};
        letter-spacing: 0.6px;
    }}
    QHeaderView::section:hover {{ color: {c['testo']}; }}
    QHeaderView::up-arrow, QHeaderView::down-arrow {{ width: 9px; height: 9px; }}
    QTableCornerButton::section {{ background: transparent; border: none; }}

    QProgressBar {{
        background: {c['pannello2']}; border: none; border-radius: 6px;
        height: 12px; text-align: center; color: transparent;
    }}
    QProgressBar::chunk {{ background: {c['accento']}; border-radius: 6px; }}

    /* --------------------------------------------------------- punteggi */
    QLabel#NomePunteggio {{
        color: {c['testo2']}; font-size: {p(10)}; font-weight: 750;
        letter-spacing: 1.1px;
    }}
    QLabel#ValorePunteggio {{ font-size: {p(19)}; font-weight: 780; }}
    QWidget#Punteggio {{ background: transparent; border-radius: 16px; }}
    QWidget#Punteggio:hover {{ background: {tocco}; }}
    QWidget#PiedeBarra {{ background: {c['pannello2']}; border-radius: 20px; }}
    QLabel#SaldoBarra {{ font-size: {p(20)}; font-weight: 750; }}

    /* --------------------------------------------------- azioni in testata */
    QPushButton#AzioneTestata {{
        background: {c['pannello']}; border: {bordo_scheda}; border-radius: 17px;
        padding: 9px 18px; color: {c['testo2']}; font-size: {p(12.5)};
    }}
    QPushButton#AzioneTestata:hover {{ background: {tocco}; color: {c['testo']}; }}
    QPushButton#AzioneTestata:pressed {{ background: {c['bordo']}; }}
    /* comando della testata senza cornice: solo la scritta e l'interruttore */
    QWidget#ComandoTestata {{ background: transparent; border: none; }}
    QWidget#ComandoTestata QLabel {{ color: {c['testo2']}; font-size: {p(13)};
                                     font-weight: 600; }}

    QPushButton#AzioneTestata::menu-indicator {{
        subcontrol-origin: padding; subcontrol-position: center right;
        right: 9px; width: 10px;
    }}

    /* ------------------------------------------------- moduli d'inserimento */
    QFrame#SchedaModulo {{
        background: {c['pannello']}; border: {bordo_scheda}; border-radius: 20px;
    }}
    QFrame#SchedaModulo QLabel {{ background: transparent; }}
    /* dentro i moduli i campi sono pastiglie piene, e quello su cui stai
       scrivendo si cinge di un anello spesso: è il modo di One UI */
    QFrame#SchedaModulo QLineEdit, QFrame#SchedaModulo QSpinBox,
    QFrame#SchedaModulo QDoubleSpinBox, QFrame#SchedaModulo QComboBox,
    QFrame#SchedaModulo QDateEdit, QFrame#SchedaModulo QTimeEdit {{
        border-radius: 16px; padding: 10px 14px; background: {c['pannello2']};
    }}
    QFrame#SchedaModulo QLineEdit:focus, QFrame#SchedaModulo QSpinBox:focus,
    QFrame#SchedaModulo QDoubleSpinBox:focus, QFrame#SchedaModulo QComboBox:focus,
    QFrame#SchedaModulo QDateEdit:focus, QFrame#SchedaModulo QTimeEdit:focus {{
        border: 2px solid {c['accento']}; padding: 9px 13px;
    }}
    /* dentro i moduli niente frecce da spinbox: si scrive il numero (rotella
       e tasti su/giù continuano a funzionare) */
    QFrame#SchedaModulo QSpinBox::up-button,
    QFrame#SchedaModulo QSpinBox::down-button,
    QFrame#SchedaModulo QDoubleSpinBox::up-button,
    QFrame#SchedaModulo QDoubleSpinBox::down-button {{
        width: 0; height: 0; border: none; background: transparent;
    }}
    QFrame#SchedaModulo QSpinBox::up-arrow,
    QFrame#SchedaModulo QSpinBox::down-arrow,
    QFrame#SchedaModulo QDoubleSpinBox::up-arrow,
    QFrame#SchedaModulo QDoubleSpinBox::down-arrow {{
        image: none; width: 0; height: 0;
    }}
    /* la pastiglia dei comandi in fondo alle finestre d'inserimento:
       pulsanti piatti dentro un'unica pastiglia, divisi da un filo */
    QWidget#PiedePillola {{
        background: {c['pannello']}; border: {bordo_scheda}; border-radius: 24px;
    }}
    QWidget#PiedePillola QPushButton {{
        background: transparent; border: none; border-radius: 20px;
        padding: 11px 26px; color: {c['testo2']}; font-size: {p(13.5)};
        font-weight: 600;
    }}
    QWidget#PiedePillola QPushButton:hover {{ background: {tocco}; color: {c['testo']}; }}
    QWidget#PiedePillola QPushButton#ComandoForte {{
        color: {c['accento']}; font-weight: 750;
    }}
    QWidget#PiedePillola QPushButton#ComandoForte:hover {{
        background: {trasparente(c['accento'], 0.14)}; color: {c['accento']};
    }}
    QFrame#FiloPiede {{ background: {c['bordo']}; border: none; max-width: 1px; }}

    /* la data in cima a «Inserimento dati»: una pastiglia, come il «Today» */
    QDateEdit#ChipData {{
        background: {c['pannello2']}; border: none; border-radius: 19px;
        padding: 8px 16px; font-size: {p(14)}; font-weight: 650;
        color: {c['testo']};
    }}
    QDateEdit#ChipData::drop-down {{ width: 0; border: none; }}
    QDateEdit#ChipData::down-arrow {{ image: none; width: 0; height: 0; }}
    QLabel#NotaSonno {{ font-size: {p(13)}; font-weight: 650; }}

    QPushButton#FrecciaGiorno {{
        background: {c['pannello2']}; border: none; border-radius: 17px;
        padding: 0; font-size: {p(15)}; color: {c['testo2']};
    }}
    QPushButton#FrecciaGiorno:hover {{ background: {tocco}; color: {c['testo']}; }}

    /* la chat di Tess */
    QLabel#BollaTu {{
        background: {trasparente(rosa, 0.16 if not chiaro else 0.13)};
        color: {c['testo']};
        border-radius: 15px; padding: 9px 14px; font-size: {p(13)};
    }}
    QLabel#BollaTess {{
        background: {c['pannello2']}; color: {c['testo']};
        border-radius: 17px; padding: 10px 14px; font-size: {p(13)};
    }}
    QListWidget#ElencoChat {{
        background: transparent; border: none; outline: none;
    }}
    /* le voci sono widget nostri: qui resta solo il fondo che le accoglie */
    QListWidget#ElencoChat::item {{
        background: transparent; border-radius: 14px; margin-bottom: 4px;
        color: {c['testo2']};
    }}
    QListWidget#ElencoChat::item:selected {{ background: transparent; }}
    /* i titoletti «OGGI», «IERI»…: non si cliccano, si leggono */
    QListWidget#ElencoChat::item:disabled {{
        color: {c['testo2']}; font-size: {p(10.5)}; font-weight: 700;
        padding: 10px 10px 2px 10px; background: transparent;
    }}
    QWidget#VoceChat {{ background: {c['pannello2']}; border-radius: 14px; }}
    QWidget#VoceChat:hover {{ background: {tocco}; }}
    QWidget#VoceChat[aperta="si"] {{
        background: {trasparente(rosa, 0.18)};
    }}
    QWidget#VoceChat[aperta="si"] QLabel#NomeChat {{
        color: {c['testo']}; font-weight: 650;
    }}
    QLabel#NomeChat {{ color: {c['testo2']}; font-size: {p(12.5)}; }}
    QWidget#VoceChat:hover QLabel#NomeChat {{ color: {c['testo']}; }}
    QLabel#QuandoChat {{ color: {c['testo2']}; font-size: {p(10.5)}; }}
    QPushButton#MenuChat {{
        background: transparent; border: none; border-radius: {q(11)};
        padding: 0; color: {c['testo2']}; font-size: {p(14)}; font-weight: 700;
    }}
    QPushButton#MenuChat:hover {{
        background: {trasparente(rosa, 0.18)}; color: {rosa};
    }}
    /* la casella che compare quando rinomini una conversazione */
    QLineEdit#RinominaChat {{
        background: {c['pannello']}; border: 1px solid {rosa};
        border-radius: 10px; padding: 2px 8px; color: {c['testo']};
        font-size: {p(12.5)}; selection-background-color: {rosa};
        selection-color: {su_rosa};
    }}
    /* il bottone che apre e chiude la colonna: l'icona la disegna lui */
    QPushButton#BottonePannello {{
        background: transparent; border: none; border-radius: {q(10)};
    }}
    QPushButton#BottonePannello:hover {{
        background: {trasparente(rosa, 0.14)};
    }}
    QLabel#TitoloChat {{ font-size: {p(13.5)}; font-weight: 650; }}

    /* ---------------------------------------------------- i messaggi */
    /* Tess senza bolla: il tondo col suo nome e il testo largo quanto la
       pagina. Quello che scrivi tu in una bolla a destra. */
    QLabel#SegnoTess {{
        background: {c['accento']}; color: {su_accento};
        font-size: {p(12)}; font-weight: 750;
    }}
    /* il filo verticale al posto della bolla: dice chi parla senza colorare */
    QFrame#FiloTess {{
        background: {colore_area('tess', chiaro)}; border: none;
        border-radius: 1px; max-width: 2px; min-width: 2px;
    }}
    QLabel#NomeTess {{
        color: {c['testo2']}; font-size: {p(11)}; font-weight: 700;
    }}
    QLabel#TestoTess {{
        background: transparent; color: {c['testo']}; font-size: {p(13)};
        padding: 1px 0 2px 0;
    }}
    QPushButton#AzioneMessaggio {{
        background: transparent; border: none; border-radius: {q(9)};
        padding: 1px 8px; color: {c['testo2']}; font-size: {p(10.5)};
    }}
    QPushButton#AzioneMessaggio:hover {{
        background: {tocco}; color: {c['testo']};
    }}
    /* i bottoncini con l'icona disegnata: modifica, copia, elimina */
    QPushButton#BottoneIcona {{ background: transparent; border: none; }}
    QPushButton#BottoneIcona:hover {{
        background: {trasparente(c['accento'], 0.16)};
    }}
    QPushButton#BottoneIcona:pressed {{
        background: {trasparente(c['accento'], 0.28)};
    }}
    /* la casella che prende il posto del messaggio quando lo correggi */
    QPlainTextEdit#ModificaMessaggio {{
        background: {c['pannello2']}; border: 1px solid {c['accento']};
        border-radius: 14px; padding: 8px 12px; font-size: {p(13)};
        color: {c['testo']}; selection-background-color: {c['accento']};
        selection-color: {su_accento};
    }}

    /* ------------------------------------------- la scheda della chat */
    /* stesso linguaggio dei riquadri delle altre pagine: fondo pannello,
       un bordo da 1px, angoli da 18 */
    QFrame#SchedaChat {{
        background: {c['pannello']}; border: 1px solid {c['bordo']};
        border-radius: 18px;
    }}
    QWidget#TestataChat {{ background: transparent; border: none; }}
    QWidget#PastigliaModello {{
        background: {c['pannello2']}; border: 1px solid {c['bordo']};
        border-radius: {q(13)};
    }}
    QLabel#NomeModello {{ color: {c['testo2']}; font-size: {p(11)}; }}
    /* quale livello sta rispondendo: il nome e la freccina li disegna lui */
    QPushButton#BottoneTendina {{
        background: transparent; border: none; border-radius: {q(10)};
        padding: 0; font-size: {p(11)}; font-weight: 650;
    }}
    QPushButton#BottoneTendina:hover {{ background: {trasparente(rosa, 0.18)}; }}
    /* La tendina dei livelli: una scheda che scende sotto il bottone.
       Il fondo è `pannello2` e non `pannello`: la testata della chat è già
       pannello, e una scheda dello stesso colore sopra un'altra non si
       stacca — con l'ombra sotto, così, sembra appoggiata. */
    QFrame#TendinaModelli {{
        background: {c['pannello2']}; border: 1px solid {c['bordo']};
        border-radius: {q(16)};
    }}
    QWidget#RigaModello {{
        background: transparent; border: 1px solid transparent;
        border-radius: {q(12)};
    }}
    QWidget#RigaModello:hover {{ background: {trasparente(rosa, 0.12)}; }}
    /* quello acceso si riconosce da tre cose insieme — fondo, bordo e nome
       rosa — perché col testo grande il solo fondo si legge male */
    QWidget#RigaModello[acceso="si"] {{
        background: {trasparente(rosa, 0.20)};
        border: 1px solid {trasparente(rosa, 0.45)};
    }}
    QLabel#NomeLivello {{ font-size: {p(12.5)}; font-weight: 700; color: {c['testo']}; }}
    QWidget#RigaModello[acceso="si"] QLabel#NomeLivello {{ color: {rosa}; }}
    QLabel#SpiegaLivello {{ font-size: {p(10.5)}; color: {c['testo2']}; }}
    QLabel#SegnoLivello {{ font-size: {p(12)}; font-weight: 700; color: {rosa};
                           min-width: {q(16)}; }}
    /* il pannello delle conversazioni, a destra: un riquadro suo, come i
       pannelli laterali di NotebookLM. La conversazione invece non sta in
       nessuna scatola: è testo sulla pagina. */
    QWidget#PannelloChat {{
        background: {c['pannello']}; border: 1px solid {c['bordo']};
        border-radius: 16px;
    }}

    /* la barra in fondo: una pastiglia sola che tiene tutto */
    QWidget#BarraTess {{
        background: {c['pannello2']}; border: 1px solid {c['bordo']};
        border-radius: {q(16)};
    }}
    QWidget#BarraTess:focus-within {{ border-color: {c['accento']}; }}
    QLineEdit#CampoTess {{
        background: transparent; border: none; padding: 4px 10px;
        font-size: {p(13)};
    }}
    QPushButton#InviaTondo {{
        background: {rosa}; border: none; color: {su_rosa};
        font-size: {p(15)}; font-weight: 700; padding: 0;
    }}
    QPushButton#InviaTondo:hover {{ background: {scurisci(rosa, 0.88)}; }}
    QPushButton#InviaTondo:disabled {{
        background: {c['bordo']}; color: {c['testo2']};
    }}

    QPlainTextEdit#CampoDiario {{
        background: {c['pannello2']}; border: 1px solid transparent;
        border-radius: 16px; padding: 12px 14px; font-size: {p(13)};
        line-height: 150%;
    }}
    QPlainTextEdit#CampoDiario:focus {{ border: 1px solid {c['accento']}; }}

    /* ------------------------------------------------ intestazioni di sezione */
    /* la nota grigia accanto al titolo: racconta, non comanda */
    QLabel#Periodo {{
        color: {c['testo2']}; font-size: {p(11.5)};
        padding: 2px 0; background: transparent;
    }}
    /* il periodo invece è un comando: pastiglia con la punta in giù */
    QPushButton#Periodo {{
        background: {c['pannello2']}; border: none; border-radius: 12px;
        padding: 4px 11px; color: {c['testo2']}; font-size: {p(11.5)};
        font-weight: 600; text-align: center;
    }}
    QPushButton#Periodo:hover {{
        background: {trasparente(c['accento'], 0.16)}; color: {c['accento']};
    }}
    QPushButton#Periodo:pressed {{ background: {c['bordo']}; }}
    /* la stessa pastiglia, ma stretta: sta sulla riga del titolo accanto
       agli altri comandi invece di scacciarli */
    QPushButton#PeriodoCorto {{
        background: {c['pannello2']}; border: none;
        padding: 4px 9px; color: {c['testo2']}; font-size: {p(11)};
        font-weight: 650; text-align: center;
    }}
    QPushButton#PeriodoCorto:hover {{
        background: {trasparente(c['accento'], 0.16)}; color: {c['accento']};
    }}
    QPushButton#PeriodoCorto:pressed {{ background: {c['bordo']}; }}
    QFrame#IndicatoreRilascio {{
        background: {c['accento']}; border: none; border-radius: 3px;
    }}

    QSplitter::handle {{ background: transparent; }}
    QSplitter::handle:hover {{ background: {selezione}; border-radius: 4px; }}
    QSplitter::handle:pressed {{ background: {c['accento']}; }}

    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px 2px; }}
    QScrollBar::handle:vertical {{ background: {c['bordo']}; border-radius: 5px;
                                   min-height: 34px; }}
    QScrollBar::handle:vertical:hover {{ background: {c['testo2']}; }}
    QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px 4px; }}
    QScrollBar::handle:horizontal {{ background: {c['bordo']}; border-radius: 5px;
                                     min-width: 34px; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}

    QTabWidget::pane {{ border: none; background: {c['pannello']};
                        border-radius: 20px; top: -1px; }}
    QTabBar::tab {{
        background: transparent; color: {c['testo2']}; padding: 10px 18px;
        border-radius: 15px; margin-right: 4px;
    }}
    QTabBar::tab:selected {{ background: {c['pannello']}; color: {c['testo']};
                             font-weight: 650; }}

    {frecce_qss}

    QToolTip {{
        background: {c['pannello2']}; color: {c['testo']};
        border: 1px solid {c['bordo']}; padding: 8px 10px; border-radius: 12px;
    }}
    QCheckBox::indicator {{
        width: 18px; height: 18px; border-radius: 6px;
        border: 1px solid {c['bordo']}; background: {c['pannello2']};
    }}
    QCheckBox::indicator:hover {{ border-color: {c['accento']}; }}
    QCheckBox::indicator:checked {{ background: {c['accento']};
                                    border-color: {c['accento']}; }}

    /* ------------------------------------------------------- etichette varie */
    QLabel#Pillola {{
        background: {c['pannello2']}; border: none; border-radius: 15px;
        padding: 8px 14px; color: {c['testo2']};
    }}
    /* il binario del tempo: le scelte stanno dentro un unico fondo, come
       l'interruttore segmentato di One UI, e non come pastiglie sparse */
    QWidget#Segmentato {{
        background: {c['pannello2']}; border: none; border-radius: 15px;
    }}
    QWidget#Segmentato QPushButton#Scelta {{
        background: transparent; border: none; border-radius: 12px;
        padding: 5px 14px; color: {c['testo2']}; font-size: {p(12)};
        font-weight: 600;
    }}
    QWidget#Segmentato QPushButton#Scelta:hover {{
        background: {tocco}; color: {c['testo']};
    }}
    QWidget#Segmentato QPushButton#Scelta:checked {{
        background: {c['accento']}; color: {su_accento}; font-weight: 700;
    }}
    QWidget#Segmentato QPushButton#Scelta:disabled {{ color: {c['bordo']}; }}
    /* le frecce stanno nel binario come le scelte, ma quadrate: con il
       margine laterale delle scelte il segno «‹» finirebbe tagliato */
    QWidget#Segmentato QPushButton#Freccia {{
        background: transparent; border: none; border-radius: 12px;
        padding: 0; color: {c['testo2']}; font-size: {p(15)}; font-weight: 700;
    }}
    QWidget#Segmentato QPushButton#Freccia:hover {{
        background: {tocco}; color: {c['testo']};
    }}
    QWidget#Segmentato QPushButton#Freccia:disabled {{ color: {c['bordo']}; }}
    QLabel#Quando {{
        color: {c['testo']}; font-size: {p(12)}; font-weight: 650;
        background: transparent; padding: 0 2px;
    }}

    /* ------------------------------------------- il navigatore dei periodi */
    /* Sta sulla riga del titolo, dove One UI mette le frecce dei grafici:
       una pastiglia piena con le frecce tonde agli estremi e il periodo in
       mezzo, poi il modo e «Oggi». Niente cornici: si distingue per tinta. */
    QWidget#NavPeriodo {{
        background: {c['pannello2']}; border: none; border-radius: {q(19)};
    }}
    QWidget#NavPeriodo QPushButton#NavFreccia {{
        background: transparent; border: none; border-radius: {q(17)};
        padding: 0; color: {c['testo2']}; font-size: {p(14)}; font-weight: 700;
    }}
    QWidget#NavPeriodo QPushButton#NavFreccia:hover {{
        background: {trasparente(c['accento'], 0.18)}; color: {c['accento']};
    }}
    QWidget#NavPeriodo QPushButton#NavFreccia:pressed {{
        background: {trasparente(c['accento'], 0.30)};
    }}
    QWidget#NavPeriodo QPushButton#NavFreccia:disabled {{ color: {c['bordo']}; }}
    QLabel#NavQuando {{
        color: {c['testo']}; font-size: {p(11.5)}; font-weight: 650;
        background: transparent; padding: 0 2px;
    }}
    /* il modo è l'unico pezzo che apre qualcosa: la punta in giù lo dice */
    QPushButton#NavModo {{
        background: transparent; border: none; border-radius: {q(16)};
        padding: {q(5)} {q(10)}; color: {c['testo2']}; font-size: {p(11.5)};
        font-weight: 650;
    }}
    QPushButton#NavModo:hover {{
        background: {trasparente(c['accento'], 0.16)}; color: {c['accento']};
    }}
    QPushButton#NavModo:pressed {{ background: {c['pannello2']}; }}
    /* «Oggi» compare solo se te ne sei andato: è un invito, e si vede */
    QPushButton#NavOggi {{
        background: {trasparente(c['accento'], 0.16)}; border: none;
        border-radius: {q(16)}; padding: {q(5)} {q(11)};
        color: {c['accento']}; font-size: {p(11.5)}; font-weight: 700;
    }}
    QPushButton#NavOggi:hover {{
        background: {trasparente(c['accento'], 0.28)};
    }}

    QPushButton#Segmento {{
        background: {c['pannello2']}; border: none; border-radius: 16px;
        padding: 8px 18px; color: {c['testo2']};
    }}
    QPushButton#Segmento:hover {{ background: {tocco}; }}
    QPushButton#Segmento:checked {{
        background: {c['accento']}; color: {su_accento}; font-weight: 650;
    }}
    QPushButton#Suggerita {{
        background: {c['pannello2']}; border: 1px dashed {c['bordo']};
        border-radius: 15px; padding: 6px 14px; color: {c['testo2']};
        font-size: {p(11.5)};
    }}
    QPushButton#Suggerita:hover {{
        border-color: {c['accento']}; color: {c['accento']}; border-style: solid;
    }}
    QPushButton#IconaCategoria {{
        background: {c['pannello2']}; border: none;
        border-radius: 15px; font-size: {p(19)};
    }}
    QPushButton#IconaCategoria:hover {{ background: {tocco}; }}
    QPushButton#CampioneColore {{ border-radius: 14px; }}
    QToolButton#CampioneIcone {{
        background: {c['pannello2']}; border: 2px solid transparent;
        border-radius: 16px; padding: 10px 12px 7px 12px; color: {c['testo2']};
        font-size: {p(11.5)};
    }}
    QToolButton#CampioneIcone:hover {{ background: {tocco}; }}
    QToolButton#CampioneIcone:checked {{
        border-color: {c['accento']}; color: {c['accento']}; font-weight: 700;
    }}
    QWidget#TestataBarra {{ background: transparent; }}
    /* Il marchio non ha mai un fondo suo: su un pannello di tinta diversa
       sembrerebbe un francobollo incollato sopra. Nemmeno da «aperto»: che
       si sia nel cruscotto lo dice il titolo della pagina. */
    QPushButton#LogoApp, QPushButton#LogoApp:checked {{
        background: transparent; border: none; border-radius: 14px; padding: 0;
    }}
    QPushButton#LogoApp:hover {{ background: {trasparente(c['testo'], 0.06)}; }}

    /* --------------------------------------------------- compositore voce */
    QFrame#Compositore {{
        background: {c['pannello2']}; border: none; border-radius: 18px;
    }}
    QFrame#Compositore QLineEdit#CampoCompositore {{
        background: transparent; border: none; border-radius: 0;
        padding: 0 4px; font-size: {p(14)};
    }}
    QFrame#DivisoreCompositore {{ background: {c['testo2']}; border: none; }}
    QPushButton#IconaCompositore {{
        background: {c['pannello']}; border: none;
        border-radius: 14px; font-size: {p(18)}; padding: 0;
    }}
    QPushButton#IconaCompositore:hover {{ background: {tocco}; }}
    QPushButton#ColoreCompositore {{ border: none; border-radius: 14px; }}
    QPushButton#AggiungiAccanto {{
        background: {c['pannello2']}; border: none;
        border-radius: 14px; font-size: {p(15)}; font-weight: 700;
        color: {c['testo2']}; padding: 0;
    }}
    QPushButton#AggiungiAccanto:hover {{ background: {tocco}; color: {c['accento']}; }}

    QLabel#Buono {{ color: {c['entrata']}; font-weight: 650; }}
    QMenu {{ background: {c['pannello']}; border: 1px solid {c['bordo']};
             border-radius: 16px; padding: 8px; }}
    QMenu::item {{ padding: 9px 20px; border-radius: 12px; }}
    QMenu::item:selected {{ background: {c['accento']}; color: {su_accento}; }}
    QMenu::separator {{ height: 1px; background: {c['bordo']}; margin: 6px 10px; }}
    """
