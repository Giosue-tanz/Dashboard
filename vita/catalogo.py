"""Quali pagine esistono e quali riquadri offrono, senza importarle subito.

`finestra.py` importa tutte le viste, quindi una vista non può importare
`finestra`: sarebbe un giro chiuso. Qui i nomi dei moduli stanno scritti come
testo e la classe si carica solo quando serve davvero — alla prima volta che
si chiede un riquadro in prestito, non all'avvio.

Serve alla Home per mostrare i riquadri delle altre pagine: l'elenco si
legge dalla classe (`SEZIONI` è un attributo di classe) senza costruire
niente, così aprire la finestra di scelta non costa nulla.
"""
from __future__ import annotations

import importlib

# nome della pagina → (titolo mostrato, modulo, classe)
# Impostazioni e Tess non ci sono: la prima è un pannello di comandi, la
# seconda è una conversazione. Nessuna delle due è fatta di riquadri da
# guardare accanto agli altri.
PAGINE: dict[str, tuple[str, str, str]] = {
    "emozioni":   ("Emozioni", "vita.views.emozioni", "VistaEmozioni"),
    "carriera":   ("Carriera", "vita.views.carriera", "VistaCarriera"),
    "accademica": ("Accademica", "vita.views.accademica", "VistaAccademica"),
    "salute":     ("Salute", "vita.views.salute", "VistaSalute"),
    "finanza":    ("Finanza", "vita.views.finanza", "VistaFinanza"),
    "abitudini":  ("Abitudini", "vita.views.abitudini", "VistaAbitudini"),
}

SEPARATORE = "·"          # «salute·sonno»: una chiave sola, due pezzi


def titolo(pagina: str) -> str:
    return PAGINE.get(pagina, (pagina, "", ""))[0]


def classe(pagina: str):
    """La classe della vista, caricata adesso."""
    _, modulo, nome = PAGINE[pagina]
    return getattr(importlib.import_module(modulo), nome)


def riquadri(pagina: str) -> dict[str, str]:
    """I riquadri che una pagina offre: chiave → nome, senza costruirla."""
    return dict(getattr(classe(pagina), "SEZIONI", {}))


def chiave_prestito(pagina: str, riquadro: str) -> str:
    """«salute» + «sonno» → «salute·sonno».

    Serve perché le chiavi devono restare distinte dentro la Home: «salute»
    esiste già lì come riquadro suo, e un riquadro preso dalla pagina Salute
    che si chiamasse uguale ne prenderebbe il posto.
    """
    return f"{pagina}{SEPARATORE}{riquadro}"


def spacchetta(chiave: str) -> tuple[str, str]:
    """L'inverso: «salute·sonno» → («salute», «sonno»). Senza separatore, («», chiave)."""
    if SEPARATORE not in chiave:
        return "", chiave
    pagina, riquadro = chiave.split(SEPARATORE, 1)
    return pagina, riquadro


def e_prestito(chiave: str) -> bool:
    return SEPARATORE in chiave
