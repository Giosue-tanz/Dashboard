"""Il salvataggio dell'archivio su una chiavetta o un disco esterno.

Qui c'è il motore: la copia, la pulizia delle vecchie e il giro automatico di
ogni sera (un timer di systemd dell'utente, niente root). Lo usano sia la
pagina Impostazioni sia il comando `strumenti/salvataggio.py`.

Due scelte che contano:

* **la copia non è un `cp`.** Si passa dall'API di backup di SQLite, così
  l'archivio copiato è coerente anche se la Dashboard ci sta scrivendo dentro.
* **la chiavetta staccata non è un guasto.** Se la destinazione non c'è, lo
  dice e basta: il giro di domani riproverà.
"""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from datetime import datetime

SERVIZIO = "vita-salvataggio"
QUANTE_RECENTI = 14           # le copie degli ultimi giorni che si tengono
QUANTI_MESI = 12              # più la prima di ogni mese, per un anno
ORA_PREDEFINITA = "22:30"


# --------------------------------------------------------------- la copia
def copia_sicura(sorgente: str, destinazione: str) -> int:
    """Copia un archivio SQLite anche se qualcuno ci sta scrivendo dentro.

    Torna i byte scritti. L'API di backup di SQLite fa una copia coerente:
    `cp` invece può prendere l'archivio a metà di una scrittura.
    """
    with sqlite3.connect(f"file:{sorgente}?mode=ro", uri=True) as da, \
            sqlite3.connect(destinazione) as a:
        da.backup(a)
    return os.path.getsize(destinazione)


def ripulisci(cartella: str, prefisso: str) -> int:
    """Via le copie vecchie, tenendo le recenti e la prima di ogni mese."""
    copie = sorted(f for f in os.listdir(cartella)
                   if f.startswith(prefisso) and f.endswith(".db"))
    if len(copie) <= QUANTE_RECENTI:
        return 0
    da_tenere = set(copie[-QUANTE_RECENTI:])
    primi_del_mese: dict[str, str] = {}
    for nome in copie:                      # nome: prefisso-AAAAMMGG-HHMM.db
        mese = nome[len(prefisso) + 1:len(prefisso) + 7]
        primi_del_mese.setdefault(mese, nome)
    da_tenere |= set(sorted(primi_del_mese.values())[-QUANTI_MESI:])
    tolte = 0
    for nome in copie:
        if nome not in da_tenere:
            try:
                os.remove(os.path.join(cartella, nome))
                tolte += 1
            except OSError:
                pass
    return tolte


def archivi(db: Database) -> list[tuple[str, str]]:
    """Gli archivi da salvare: (percorso, nome della copia)."""
    elenco = [(db.percorso, "vita")]
    from .fonti import PERCORSO_FINANCE
    finance = db.leggi("percorso_finance", PERCORSO_FINANCE)
    if finance and os.path.exists(finance):
        elenco.append((finance, "finance"))
    return elenco


def salva(cartella: str, db: Database, parlato: bool = True) -> tuple[bool, str]:
    """Fa il salvataggio. Torna (riuscito, cosa dire all'utente)."""
    if not cartella:
        return False, "nessuna cartella scelta"
    # la chiavetta potrebbe non essere infilata: non è un errore, è la vita
    if not os.path.isdir(cartella):
        return False, f"destinazione assente ({cartella})"
    if not os.access(cartella, os.W_OK):
        return False, f"destinazione in sola lettura ({cartella})"

    quando = datetime.now()
    fatti, byte = [], 0
    for sorgente, nome in archivi(db):
        if not os.path.exists(sorgente):
            continue
        copia = os.path.join(cartella, f"{nome}-{quando:%Y%m%d-%H%M}.db")
        try:
            byte += copia_sicura(sorgente, copia)
            ripulisci(cartella, nome)
            fatti.append(nome)
        except (sqlite3.Error, OSError) as errore:
            return False, f"non riesco a copiare {nome}: {errore}"
        if parlato:
            print(f"  {nome} → {copia}")

    if not fatti:
        return False, "non ho trovato niente da salvare"
    misura = f"{byte / 1_048_576:.1f} MB".replace(".", ",")
    return True, f"{' e '.join(fatti)} · {misura}"


# ------------------------------------------------------- il giro automatico
def cartella_unita() -> str:
    return os.path.expanduser("~/.config/systemd/user")


def installa(ora: str = ORA_PREDEFINITA) -> str:
    """Scrive le unità systemd e accende il giro di ogni sera."""
    cartella = cartella_unita()
    os.makedirs(cartella, exist_ok=True)
    # il timer lancia il comando da terminale, non questo modulo
    io_stesso = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "strumenti", "salvataggio.py")
    servizio = f"""[Unit]
Description=Salvataggio dell'archivio di Dashboard

[Service]
Type=oneshot
ExecStart={sys.executable} {io_stesso} --silenzioso
"""
    timer = f"""[Unit]
Description=Salvataggio di Dashboard ogni sera

[Timer]
OnCalendar=*-*-* {ora}
# se il computer era spento, appena si riaccende recupera il giro saltato
Persistent=true
AccuracySec=1min

[Install]
WantedBy=timers.target
"""
    with open(os.path.join(cartella, f"{SERVIZIO}.service"), "w") as f:
        f.write(servizio)
    with open(os.path.join(cartella, f"{SERVIZIO}.timer"), "w") as f:
        f.write(timer)
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
    subprocess.run(["systemctl", "--user", "enable", "--now", f"{SERVIZIO}.timer"],
                   check=False, capture_output=True)
    return f"acceso: ogni sera alle {ora}"


def disinstalla() -> str:
    subprocess.run(["systemctl", "--user", "disable", "--now", f"{SERVIZIO}.timer"],
                   check=False, capture_output=True)
    for nome in (f"{SERVIZIO}.timer", f"{SERVIZIO}.service"):
        percorso = os.path.join(cartella_unita(), nome)
        if os.path.exists(percorso):
            os.remove(percorso)
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
    return "spento"


def acceso() -> bool:
    esito = subprocess.run(
        ["systemctl", "--user", "is-enabled", f"{SERVIZIO}.timer"],
        capture_output=True, text=True, check=False)
    return esito.stdout.strip() == "enabled"


def prossimo_giro() -> str:
    """Quando scatterà la prossima volta, come lo racconta systemd."""
    esito = subprocess.run(
        ["systemctl", "--user", "list-timers", f"{SERVIZIO}.timer", "--no-pager"],
        capture_output=True, text=True, check=False)
    for riga in esito.stdout.splitlines():
        if SERVIZIO in riga:
            return " ".join(riga.split()[:3])
    return ""


