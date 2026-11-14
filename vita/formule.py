"""LaTeX dentro la chat di Tess, scritto come si scrive a mano.

Qwen scrive la fisica come l'ha imparata: `$v = \\frac{1}{2}at^2$`. In una
`QLabel` di solo testo quello resta tale e quale — dollari, backslash,
graffe — ed è più difficile da leggere della formula che doveva sostituire.

Qt sa disegnare apici, pedici e sopralineature dentro il **sottoinsieme di
HTML** che il suo motore di testo ricco capisce (`QTextDocument`): bastano
`<sup>`, `<sub>` e uno `style="text-decoration:overline"`. Non serve
MathJax, non serve una libreria esterna, non serve internet — e questa è
un'app che gira sul PC di chi la usa, senza dipendenze oltre a PySide6.

Quello che c'è qui dentro non è un motore LaTeX completo: è un traduttore
del sottoinsieme che un fisico scrive davvero — frazioni, apici, pedici,
radici, lettere greche, gli operatori e i simboli più comuni — verso quel
sottoinsieme di HTML. Un comando che non riconosce non manda in errore:
perde solo il backslash e resta leggibile come testo.
"""
from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from functools import lru_cache

# ---------------------------------------------------------------- i simboli
# Comandi senza argomenti: si sostituiscono con un carattere o una manciata.
# Lettere greche comprese — è la parte più usata in fisica.
SIMBOLI: dict[str, str] = {
    # operatori e relazioni
    "times": "×", "cdot": "·", "div": "÷", "pm": "±", "mp": "∓",
    "leq": "≤", "le": "≤", "geq": "≥", "ge": "≥", "neq": "≠", "ne": "≠",
    "approx": "≈", "equiv": "≡", "propto": "∝", "sim": "∼", "simeq": "≃",
    "cong": "≅", "perp": "⊥", "parallel": "∥", "angle": "∠",
    "forall": "∀", "exists": "∃", "in": "∈", "notin": "∉",
    "subset": "⊂", "supset": "⊃", "subseteq": "⊆", "supseteq": "⊇",
    "cup": "∪", "cap": "∩", "wedge": "∧", "vee": "∨", "neg": "¬", "lnot": "¬",
    "oplus": "⊕", "otimes": "⊗",
    # frecce
    "rightarrow": "→", "to": "→", "leftarrow": "←", "leftrightarrow": "↔",
    "Rightarrow": "⇒", "Leftarrow": "⇐", "Leftrightarrow": "⇔",
    "mapsto": "↦",
    # analisi, insiemi, infinito
    "infty": "∞", "partial": "∂", "nabla": "∇",
    "sum": "∑", "prod": "∏", "int": "∫", "oint": "∮",
    "lfloor": "⌊", "rfloor": "⌋", "lceil": "⌈", "rceil": "⌉",
    "langle": "⟨", "rangle": "⟩",
    # puntini, spazi
    "ldots": "…", "cdots": "…", "dots": "…", "vdots": "⋮", "ddots": "⋱",
    "quad": " ", "qquad": "  ",
    # varie da fisica
    "hbar": "ℏ", "ell": "ℓ", "deg": "°", "degree": "°", "circ": "∘",
    "star": "⋆", "ast": "∗", "dagger": "†", "top": "⊤", "bot": "⊥",
    "Re": "ℜ", "Im": "ℑ", "AA": "Å",
    # graffe sfuggite, già consumate da \left \right quando ci sono
    "{": "{", "}": "}",
    # vuoto: \left e \right servono solo a scalare le parentesi, che
    # restano dov'erano come caratteri normali
    "left": "", "right": "",
    # lettere greche minuscole
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ε",
    "varepsilon": "ε", "zeta": "ζ", "eta": "η", "theta": "θ",
    "vartheta": "ϑ", "iota": "ι", "kappa": "κ", "lambda": "λ", "mu": "μ",
    "nu": "ν", "xi": "ξ", "pi": "π", "varpi": "ϖ", "rho": "ρ",
    "varrho": "ϱ", "sigma": "σ", "varsigma": "ς", "tau": "τ",
    "upsilon": "υ", "phi": "φ", "varphi": "ϕ", "chi": "χ", "psi": "ψ",
    "omega": "ω",
    # maiuscole (solo quelle che non sono identiche a una lettera latina)
    "Gamma": "Γ", "Delta": "Δ", "Theta": "Θ", "Lambda": "Λ", "Xi": "Ξ",
    "Pi": "Π", "Sigma": "Σ", "Upsilon": "Υ", "Phi": "Φ", "Psi": "Ψ",
    "Omega": "Ω",
}

# Nomi di funzione: in LaTeX servono solo a scrivere il nome dritto, non
# corsivo come farebbe una variabile — qui basta toglierne il backslash.
OPERATORI = ("sin", "cos", "tan", "cot", "sec", "csc", "sinh", "cosh",
            "tanh", "log", "ln", "exp", "lim", "max", "min", "sup", "inf",
            "det", "dim", "ker", "gcd", "arg", "mod")

# Comandi con un argomento solo (una graffa, o un carattere se non c'è):
# ognuno dice come vestire il contenuto già trasformato.
UN_ARGOMENTO: dict[str, callable] = {
    "sqrt": lambda c: f"√({c})",
    "text": lambda c: c, "mathrm": lambda c: c, "operatorname": lambda c: c,
    "boxed": lambda c: c,
    "mathbf": lambda c: f"<b>{c}</b>", "bf": lambda c: f"<b>{c}</b>",
    "mathit": lambda c: f"<i>{c}</i>", "emph": lambda c: f"<i>{c}</i>",
    "vec": lambda c: c + "⃗", "overrightarrow": lambda c: c + "⃗",
    "hat": lambda c: c + "̂",
    "bar": lambda c: c + "̄", "overline": lambda c:
        f'<span style="text-decoration:overline">{c}</span>',
    "dot": lambda c: c + "̇",
    "underline": lambda c: f'<span style="text-decoration:underline">{c}</span>',
}

# Il carattere della matematica: quello dei libri, non quello della chat
# intorno. FreeSerif prima di tutti: è l'unico serif di questo sistema (visto
# con `fc-list`) che si disegna
# **da sé** ∂, ∮, ∫ e il resto dei segni matematici. Con Noto Serif quei
# segni mancano e Qt va a prenderli dove li trova, un font diverso per
# simbolo: arrivano di corpo sbagliato e con lo spazio intorno che non torna,
# ed è la ragione per cui le formule sembravano scritte a macchina invece che
# composte. Gli altri restano dietro come rete di sicurezza.
FAMIGLIA_MATEMATICA = ("'FreeSerif', 'Noto Serif', 'Times New Roman', "
                       "Georgia, serif")

# In matematica le variabili si scrivono in corsivo e tutto il resto dritto:
# numeri, parentesi, segni, e i nomi delle funzioni (sin, cos, log). È la
# regola che distingue «at» — a per t — da «at», la parola. Queste sono le
# scatole dove invece il corsivo non va messo: `\mathrm` e `\text` chiedono
# il dritto per definizione, `\mathbf` è il grassetto dritto dei vettori.
DRITTI = frozenset({"text", "mathrm", "operatorname", "boxed", "mathbf", "bf"})

_RE_COMANDO = re.compile(r"[a-zA-Z]+")

# Un backslash seguito da un carattere che non è una lettera: comandi
# simbolo di un carattere solo. `\,` `\;` `\!` sono spazi di misure
# diverse in LaTeX — qui contano tutti uguale, uno spazio normale basta.
SFUGGITI: dict[str, str] = {
    "\\": "<br>", "$": "$", "%": "%", "#": "#", "_": "_",
    " ": " ", ",": " ", ";": " ", "!": "",
}


def _leggi_gruppo(testo: str, i: int) -> tuple[str, int]:
    """`testo[i]` è una graffa aperta: torna (il suo contenuto, dove riprendere).

    Conta le graffe annidate — `\\frac{\\frac{1}{2}}{3}` ne ha dentro altre —
    così non si ferma alla prima `}` che trova, che sarebbe quella sbagliata.
    Una graffa mai chiusa (il modello si è fermato a metà) prende tutto il
    resto, invece di restare a guardare per sempre.
    """
    profondita = 0
    j = i
    while j < len(testo):
        if testo[j] == "{":
            profondita += 1
        elif testo[j] == "}":
            profondita -= 1
            if profondita == 0:
                return testo[i + 1:j], j + 1
        j += 1
    return testo[i + 1:], len(testo)


@dataclass(frozen=True)
class Aspetto:
    """Colore e misura: quello che serve per disegnare una frazione **vera**,
    con la sua barra orizzontale, invece del trucco apice-barra-pedice che
    resta leggibile ma si vede che è ripiegato.

    Il colore è quello del tema — scuro o chiaro — perché quello cambia
    pagina per pagina; il carattere no, è sempre `FAMIGLIA_MATEMATICA`: la
    matematica si scrive in corsivo da libro, non nel carattere della chat.

    Senza un `Aspetto` (`None`) il traduttore ripiega sul trucco: succede
    nelle prove che non passano da un tema vero, e in un contesto senza
    bisogno del disegno esatto.
    """
    colore: str
    punti: int


@lru_cache(maxsize=256)
def _frazione_immagine(numeratore: str, denominatore: str, aspetto: Aspetto) -> str:
    """Una frazione disegnata — barra compresa — come farebbe la lavagna.

    Qt sa disegnare tabelle con bordi, ma solo come **blocchi**: infilarne
    una dentro una riga di prosa la spezza in tre righe separate, con
    `V = 1 +` su una riga, la frazione sulla sua, `= 1` sulla prossima —
    altro che in riga con il resto dell'equazione.

    Il giro qui è: si disegna la frazione in un documento tutto suo, isolato
    — lì dentro la tabella può stare quanto vuole — e si fotografa il
    risultato in un PNG. L'immagine, quella sì, scorre dentro la riga come
    farebbe una lettera: è questo — non la tabella — il pezzo che Qt lascia
    stare in mezzo al testo.

    `lru_cache`: durante lo streaming lo stesso testo si riformatta a ogni
    pezzo che arriva, e una frazione già completa non cambia più finché la
    risposta continua — ridisegnarla ogni volta sarebbe lavoro buttato.
    """
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
    from PySide6.QtGui import QImage, QPainter, QTextDocument

    punti_interni = max(8, round(aspetto.punti * 0.84))
    doc = QTextDocument()
    # Un documento Qt nasce con quattro pixel di margine per lato, e qui
    # finivano **dentro l'immagine**: una frazione da 26 pixel ne veniva 42,
    # tutta aria. In riga quell'aria alzava l'interlinea di mezza riga e
    # scentrava la barra rispetto all'«=» accanto; fra un'equazione e
    # l'altra diventava un buco grande come una riga vuota.
    doc.setDocumentMargin(0)
    doc.setHtml(
        f'<body style="margin:0;font-family:{FAMIGLIA_MATEMATICA};'
        f'color:{aspetto.colore};">'
        f'<table cellspacing="0" cellpadding="0" style="border-collapse:collapse;">'
        f'<tr><td style="text-align:center;border-bottom:1.3px solid '
        f'{aspetto.colore};padding:0 3px 1px 3px;font-size:{punti_interni}px;">'
        f'{numeratore}</td></tr>'
        f'<tr><td style="text-align:center;padding:1px 3px 0 3px;'
        f'font-size:{punti_interni}px;">{denominatore}</td></tr>'
        f'</table></body>')
    doc.setTextWidth(-1)
    dimensione = doc.size().toSize()
    if dimensione.width() <= 0 or dimensione.height() <= 0:
        return f"({numeratore})/({denominatore})"       # non dovrebbe succedere
    immagine = QImage(dimensione, QImage.Format_ARGB32)
    immagine.fill(Qt.transparent)
    pittore = QPainter(immagine)
    doc.drawContents(pittore)
    pittore.end()
    dati = QByteArray()
    buffer = QBuffer(dati)
    buffer.open(QIODevice.WriteOnly)
    immagine.save(buffer, "PNG")
    base64_png = base64.b64encode(dati.data()).decode("ascii")
    # vertical-align:middle non basta da solo a centrare sulla riga di testo
    # intorno — qui conta meno che il risultato resti leggibile, non perfetto
    return (f'<img src="data:image/png;base64,{base64_png}" '
            f'width="{dimensione.width()}" height="{dimensione.height()}" '
            f'style="vertical-align:middle;">')


def _trasforma(testo: str, aspetto: Aspetto | None = None,
               corsivo: bool = True) -> str:
    """Il cuore del traduttore: scorre il testo un carattere alla volta.

    Non è una `re.sub`: le graffe si annidano (una frazione dentro una
    radice dentro un apice) e un sostituto a regex singola non le conta. Qui
    invece ogni comando con argomenti richiama se stesso sul contenuto, già
    sgraffato, prima di vestirlo.

    `corsivo` dice se le lettere che incontra sono variabili — e allora si
    scrivono in corsivo, come vuole la composizione matematica — oppure no,
    perché siamo dentro un `\\mathrm` o un `\\mathbf` (vedi `DRITTI`).
    """
    fuori = []
    i, n = 0, len(testo)
    while i < n:
        carattere = testo[i]

        # una fila di lettere è una fila di variabili: in corsivo, tutta
        # insieme invece che una per una, che in HTML è lo stesso disegno
        # con un quarto dei tag
        if corsivo and carattere.isascii() and carattere.isalpha():
            inizio = i
            while i < n and testo[i].isascii() and testo[i].isalpha():
                i += 1
            fuori.append(f"<i>{testo[inizio:i]}</i>")
            continue

        if carattere == "\\" and i + 1 < n:
            seguente = testo[i + 1]
            if not seguente.isalpha():
                # un simbolo sfuggito: \{ \} \\ \$ \% \, \; \! eccetera
                i += 2
                fuori.append(SFUGGITI.get(seguente, seguente))
                continue
            corrisp = _RE_COMANDO.match(testo, i + 1)
            nome = corrisp.group(0)
            i = corrisp.end()

            if nome == "frac":
                if i < n and testo[i] == "{":
                    arg1, i = _leggi_gruppo(testo, i)
                elif i < n:
                    arg1, i = testo[i], i + 1
                else:
                    arg1 = ""
                while i < n and testo[i] == " ":
                    i += 1
                if i < n and testo[i] == "{":
                    arg2, i = _leggi_gruppo(testo, i)
                elif i < n:
                    arg2, i = testo[i], i + 1
                else:
                    arg2 = ""
                num = _trasforma(arg1, aspetto, corsivo)
                den = _trasforma(arg2, aspetto, corsivo)
                if aspetto is not None:
                    fuori.append(_frazione_immagine(num, den, aspetto))
                else:
                    # senza un Aspetto (prove, o nessun tema a disposizione)
                    # il trucco col taglio resta leggibile uguale
                    fuori.append(f"<sup>{num}</sup>⁄<sub>{den}</sub>")
            elif nome in UN_ARGOMENTO:
                dentro = corsivo and nome not in DRITTI
                if i < n and testo[i] == "{":
                    arg, i = _leggi_gruppo(testo, i)
                    contenuto = _trasforma(arg, aspetto, dentro)
                elif i < n:
                    contenuto = _trasforma(testo[i], aspetto, dentro)
                    i += 1
                else:
                    contenuto = ""
                fuori.append(UN_ARGOMENTO[nome](contenuto))
            elif nome in SIMBOLI:
                fuori.append(SIMBOLI[nome])
                # In LaTeX lo spazio dopo il nome di un comando serve solo a
                # dire dove finisce il nome: non si stampa. Qui si toglie
                # **solo** dopo `\partial`, che è il caso che si vede —
                # «\partial \mathbf{B}» è «∂B», non «∂ B». Dopo `\nabla`
                # invece il prossimo segno è quasi sempre un operatore
                # («∇ · E»), e lì lo spazio ci vuole.
                if nome == "partial":
                    while i < n and testo[i] == " ":
                        i += 1
            elif nome in OPERATORI:
                fuori.append(nome)
            else:
                # comando sconosciuto: meglio il nome nudo che una raffica
                # di backslash — resta leggibile anche senza sapere cos'era
                fuori.append(nome)
            continue

        if carattere in ("^", "_"):
            tag = "sup" if carattere == "^" else "sub"
            i += 1
            if i < n and testo[i] == "{":
                arg, i = _leggi_gruppo(testo, i)
                contenuto = _trasforma(arg, aspetto, corsivo)
            elif i < n and testo[i] == "\\":
                corrisp = _RE_COMANDO.match(testo, i + 1)
                fine = corrisp.end() if corrisp else i + 2
                contenuto = _trasforma(testo[i:fine], aspetto, corsivo)
                i = fine
            elif i < n:
                contenuto = _trasforma(testo[i], aspetto, corsivo)
                i += 1
            else:
                contenuto = ""
            fuori.append(f"<{tag}>{contenuto}</{tag}>")
            continue

        if carattere == "{":
            # graffe di solo raggruppamento, senza un comando davanti:
            # non stampano niente di loro, conta solo quel che c'è dentro
            arg, i = _leggi_gruppo(testo, i)
            fuori.append(_trasforma(arg, aspetto, corsivo))
            continue
        if carattere == "}":
            i += 1       # chiusura orfana: non dovrebbe arrivare qui, si salta
            continue

        # Dentro una formula il trattino del tastierino è il segno meno, e
        # si scrive più lungo: «−∂B/∂t», non «-∂B/∂t». È la differenza fra
        # una formula composta e una scritta a macchina.
        fuori.append("−" if carattere == "-" else carattere)
        i += 1
    return "".join(fuori)


# ------------------------------------------------------------- il confine
# `$$...$$` prima di `$...$`: con l'alternanza provata nell'ordine giusto,
# due dollari di fila non vengono letti come due formule vuote incollate.
_RE_MATEMATICA = re.compile(
    r"(?<!\\)\$\$(?P<blocco>.+?)(?<!\\)\$\$"
    r"|(?<!\\)\$(?P<riga>.+?)(?<!\\)\$", re.DOTALL)


def _scappa_html(testo: str) -> str:
    return (testo.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;"))


def _sostituisci_matematica(testo: str, aspetto: Aspetto | None) -> str:
    """La stessa cosa che faceva `formatta()` da sola, prima che ci fosse
    anche il markdown: scappa la prosa, traduce quello che sta fra dollari.
    Non tocca gli «a capo» — quelli li legge il markdown subito dopo, per
    sapere dove finisce un paragrafo e comincia un elenco.
    """
    pezzi = []
    cursore = 0
    for m in _RE_MATEMATICA.finditer(testo):
        pezzi.append(_scappa_html(testo[cursore:m.start()]))
        blocco = m.group("blocco")
        if blocco is not None:
            dentro = _trasforma(_scappa_html(blocco.strip()), aspetto)
            # Un'equazione fuori dalla frase sta in mezzo, come su un libro.
            # Il centraggio una volta qui non c'era: con le frazioni fatte di
            # apici e pedici Qt sbagliava il conto della larghezza e il
            # blocco finiva spostato a destra. Da quando la frazione è
            # un'immagine — una cosa di larghezza nota — il conto torna.
            pezzi.append(f'<div align="center" style="margin:7px 0;">'
                         f'{dentro}</div>')
        else:
            pezzi.append(_trasforma(_scappa_html(m.group("riga")), aspetto))
        cursore = m.end()
    pezzi.append(_scappa_html(testo[cursore:]))
    return "".join(pezzi)


# --------------------------------------------------------------- markdown
# Qwen scrive anche questo da solo — **grassetto**, elenchi puntati,
# titoli — e prima restava tale e quale, asterischi compresi. Qui sotto il
# sottoinsieme che un fisico scrive davvero, verso lo stesso sottoinsieme di
# HTML che già capisce `_trasforma`: <b> <i> <ul> <ol> niente di più.
_RE_RECINTO = re.compile(r"^```[^\n]*\n(.*?)\n```[ \t]*$", re.MULTILINE | re.DOTALL)
_RE_CODICE_IN_RIGA = re.compile(r"`([^`\n]+)`")

# Il grassetto prima del corsivo: una volta che `**forte**` è diventato
# `<b>forte</b>` non restano più asterischi lì per il giro dopo a scambiarli
# per corsivo — i due passaggi non si pestano i piedi da soli.
_RE_GRASSETTO_CORSIVO = re.compile(r"\*\*\*(?!\s)(.+?)(?<!\s)\*\*\*")
_RE_GRASSETTO = re.compile(r"\*\*(?!\s)(.+?)(?<!\s)\*\*")
_RE_CORSIVO_STELLA = re.compile(r"\*(?!\s)(.+?)(?<!\s)\*")
# Il corsivo con `_sottolineato_` solo a un confine di parola: senza questo
# «a_b_c» — un nome qualunque — diventerebbe «a<i>b</i>c».
_RE_CORSIVO_TRATTINO = re.compile(r"(?<![\w*])_(?!\s)(.+?)(?<!\s)_(?![\w*])")

_RE_INTESTAZIONE = re.compile(r"^(#{1,6})\s+(.*)$")
_RE_PUNTO = re.compile(r"^[-*]\s+(.*)$")
_RE_NUMERO = re.compile(r"^\d+[.)]\s+(.*)$")


def _enfasi(testo: str) -> str:
    """Grassetto e corsivo, dentro un pezzo di riga già passato dalla
    matematica — che però non ha asterischi né trattini bassi suoi: quelli
    li consuma `_trasforma` trasformandoli in `<sup>`/`<sub>`, quindi quello
    che resta a questo giro è solo markdown vero, non matematica scambiata.
    """
    testo = _RE_GRASSETTO_CORSIVO.sub(r"<b><i>\1</i></b>", testo)
    testo = _RE_GRASSETTO.sub(r"<b>\1</b>", testo)
    testo = _RE_CORSIVO_STELLA.sub(r"<i>\1</i>", testo)
    testo = _RE_CORSIVO_TRATTINO.sub(r"<i>\1</i>", testo)
    return testo


def _markdown_a_html(testo: str) -> str:
    """Righe → paragrafi, elenchi, titoli. Lavora **dopo** la matematica:
    quello che vede è già `<sup>`/`<img>` dove serviva, mai un dollaro vero.
    """
    blocchi: list[str] = []
    paragrafo: list[str] = []
    lista: list | None = None            # ["ul" o "ol", [voci]]

    def chiudi_paragrafo() -> None:
        if paragrafo:
            corpo = "<br>".join(_enfasi(r) for r in paragrafo)
            blocchi.append(f'<div style="margin:3px 0;">{corpo}</div>')
            paragrafo.clear()

    def chiudi_lista() -> None:
        """Le voci a mano, non con `<ul>`: di quelle Qt disegna il pallino da
        sé, appiccicato alla prima lettera e spinto a destra di una
        tabulazione, e non c'è verso di staccarlo. Un segno scritto da noi
        invece si stacca quanto vogliamo, e col rientro appeso la seconda
        riga di una voce lunga si allinea sotto il testo e non sotto il
        pallino — come in un elenco stampato.
        """
        nonlocal lista
        if not lista:
            return
        tag, voci = lista
        for posto, voce in enumerate(voci, 1):
            segno = "•" if tag == "ul" else f"{posto}."
            blocchi.append(
                f'<div style="margin:2px 0 2px 20px;text-indent:-13px;">'
                f'{segno}&nbsp;&nbsp;{_enfasi(voce)}</div>')
        lista = None

    for riga in testo.split("\n"):
        if not riga.strip():
            chiudi_paragrafo()
            chiudi_lista()
            continue
        titolo = _RE_INTESTAZIONE.match(riga)
        if titolo:
            chiudi_paragrafo()
            chiudi_lista()
            # più cancelletti, titolo più piccolo — ma mai sotto il testo
            # normale: resta comunque un titolo, non un rimpicciolimento
            scala = max(1.0, 1.32 - 0.07 * len(titolo.group(1)))
            blocchi.append(f'<div style="font-weight:700;font-size:'
                           f'{scala:.2f}em;margin:6px 0 3px 0;">'
                           f'{_enfasi(titolo.group(2))}</div>')
            continue
        punto = _RE_PUNTO.match(riga)
        if punto:
            chiudi_paragrafo()
            if lista and lista[0] != "ul":
                chiudi_lista()
            if not lista:
                lista = ["ul", []]
            lista[1].append(punto.group(1))
            continue
        numero = _RE_NUMERO.match(riga)
        if numero:
            chiudi_paragrafo()
            if lista and lista[0] != "ol":
                chiudi_lista()
            if not lista:
                lista = ["ol", []]
            lista[1].append(numero.group(1))
            continue
        chiudi_lista()
        paragrafo.append(riga)
    chiudi_paragrafo()
    chiudi_lista()
    return "".join(blocchi)


_RE_PROTETTO = re.compile(r"\x00(\d+)\x00")


def formatta(testo: str, colore: str = "", punti: int = 13) -> str:
    """Il testo di un messaggio, pronto per una `QLabel` in `Qt.RichText`.

    Tutto nel carattere da libro (`FAMIGLIA_MATEMATICA`) — testo compreso,
    non solo la matematica: è il carattere che fa sembrare una risposta una
    pagina scritta, non un messaggio con dentro qualche simbolo.

    In ordine: prima si mette al sicuro il codice — un blocco fra tre
    apici, o `in riga` — perché un `$` dentro non è una formula a metà,
    è letteralmente un dollaro; poi la matematica; poi markdown — righe,
    elenchi, titoli, **grassetto** — su quello che resta. Un comando o una
    formula non chiusi (il modello si è fermato a metà) restano testo,
    niente si rompe.
    """
    aspetto = Aspetto(colore, punti) if colore else None
    protetti: list[str] = []

    def proteggi(html: str) -> str:
        protetti.append(html)
        return f"\x00{len(protetti) - 1}\x00"

    testo = _RE_RECINTO.sub(
        lambda m: proteggi(f'<pre style="white-space:pre-wrap;'
                           f'font-family:monospace;margin:4px 0;">'
                           f'{_scappa_html(m.group(1))}</pre>'),
        testo)
    testo = _RE_CODICE_IN_RIGA.sub(
        lambda m: proteggi(f'<span style="font-family:monospace;">'
                           f'{_scappa_html(m.group(1))}</span>'),
        testo)

    testo = _sostituisci_matematica(testo, aspetto)
    corpo = _markdown_a_html(testo)
    corpo = _RE_PROTETTO.sub(lambda m: protetti[int(m.group(1))], corpo)
    return f'<div style="font-family:{FAMIGLIA_MATEMATICA};">{corpo}</div>'
