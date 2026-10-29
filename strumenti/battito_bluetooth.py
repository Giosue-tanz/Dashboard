#!/usr/bin/env python3
"""Legge il battito dal braccialetto via Bluetooth, finché sta misurando.

Il Galaxy Fit2 espone il servizio standard **Heart Rate** (0x180D): il PC può
riceverne le misure solo *mentre* il braccialetto misura. Lo storico (passi,
sonno, allenamenti) viaggia invece col protocollo chiuso di Samsung verso il
telefono e non è leggibile da qui: per quello c'è l'importazione da Samsung
Health dentro l'app.

Uso tipico:

    1. sul braccialetto apri «Frequenza cardiaca» e avvia una misura
    2. python3 strumenti/battito_bluetooth.py --secondi 60 --salva

Con --salva il valore più basso letto finisce nel campo «battito a riposo»
del giorno corrente dell'archivio di Dashboard.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SERVIZIO_BATTITO = "0000180d-0000-1000-8000-00805f9b34fb"
MISURA = "00002a37-0000-1000-8000-00805f9b34fb"


def _bluetoothctl(comando: list[str], attesa: int = 10) -> str:
    """Esegue un comando di bluetoothctl e restituisce l'uscita.

    Il comando va passato diretto (non su stdin): così bluetoothctl aspetta
    l'esito invece di uscire subito.
    """
    try:
        esito = subprocess.run(
            ["bluetoothctl", *comando], capture_output=True, text=True,
            timeout=attesa)
    except (subprocess.TimeoutExpired, FileNotFoundError) as errore:
        return (getattr(errore, "output", "") or "") if isinstance(
            errore, subprocess.TimeoutExpired) else ""
    return esito.stdout + esito.stderr


def _scansione(secondi: int = 8) -> None:
    """Una scansione breve: senza, la prima connessione spesso viene rifiutata."""
    try:
        subprocess.run(["bluetoothctl", "--timeout", str(secondi), "scan", "le"],
                       capture_output=True, text=True, timeout=secondi + 10)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass


def _connetti(mac: str, tentativi: int = 3) -> bool:
    """Prova a collegarsi al braccialetto, con una scansione fra un colpo e l'altro."""
    for tentativo in range(tentativi):
        uscita = _bluetoothctl(["connect", mac], 25)
        if "Connection successful" in uscita or "Connected: yes" in uscita:
            return True
        if tentativo == 0:
            print("  nessuna risposta, cerco il braccialetto…")
            _scansione()
    return "Connected: yes" in _bluetoothctl(["info", mac], 10)


def trova_braccialetto(nome_cercato: str = "fit") -> tuple[str, str] | None:
    """Primo dispositivo accoppiato il cui nome contiene la parola cercata."""
    for riga in _bluetoothctl(["devices", "Paired"], 8).splitlines():
        trovato = re.match(r"Device ([0-9A-F:]{17}) (.+)", riga.strip())
        if trovato and nome_cercato.lower() in trovato.group(2).lower():
            return trovato.group(1), trovato.group(2).strip()
    return None


def percorso_caratteristica(mac: str) -> str | None:
    """Percorso D-Bus della caratteristica «Heart Rate Measurement»."""
    uscita = _bluetoothctl(["gatt.list-attributes", mac], 30)
    righe = [r.strip() for r in uscita.splitlines()]
    for i, riga in enumerate(righe):
        if MISURA in riga:
            for indietro in range(i - 1, max(-1, i - 4), -1):
                if "/org/bluez/" in righe[indietro]:
                    return righe[indietro].split()[-1]
    return None


def ascolta(mac: str, percorso: str, secondi: int) -> list[int]:
    """Sottoscrive le notifiche e raccoglie le misure ricevute."""
    ingresso = ("menu gatt\n"
                f"select-attribute {percorso}\n"
                "notify on\n")
    processo = subprocess.Popen(
        ["bluetoothctl"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, bufsize=1)
    processo.stdin.write(ingresso)
    processo.stdin.flush()

    import threading
    battiti: list[int] = []

    def leggi():
        atteso = False
        for riga in processo.stdout:
            pulita = re.sub(r"\x1b\[[0-9;]*m", "", riga).strip()
            if percorso.split("/")[-1] in pulita and "Value" in pulita:
                atteso = True
                continue
            if atteso:
                ottetti = re.findall(r"\b([0-9a-f]{2})\b", pulita.lower())
                atteso = False
                if len(ottetti) >= 2:
                    bandiere = int(ottetti[0], 16)
                    if bandiere & 0x01:          # valore a 16 bit
                        valore = int(ottetti[2] + ottetti[1], 16) if len(ottetti) > 2 \
                            else int(ottetti[1], 16)
                    else:
                        valore = int(ottetti[1], 16)
                    if 25 <= valore <= 230:
                        battiti.append(valore)
                        print(f"  battito: {valore} bpm", flush=True)

    filo = threading.Thread(target=leggi, daemon=True)
    filo.start()
    try:
        processo.wait(timeout=secondi)
    except subprocess.TimeoutExpired:
        pass
    try:
        processo.stdin.write("notify off\nback\nquit\n")
        processo.stdin.flush()
        processo.wait(timeout=5)
    except Exception:
        processo.kill()
    return battiti


def main() -> int:
    argomenti = argparse.ArgumentParser(description=__doc__)
    argomenti.add_argument("--mac", default="", help="indirizzo del braccialetto")
    argomenti.add_argument("--secondi", type=int, default=60,
                           help="quanto restare in ascolto (predefinito: 60)")
    argomenti.add_argument("--salva", action="store_true",
                           help="scrive il battito più basso nell'archivio di Dashboard")
    opzioni = argomenti.parse_args()

    mac, nome = opzioni.mac, opzioni.mac
    if not mac:
        trovato = trova_braccialetto()
        if not trovato:
            print("Nessun braccialetto accoppiato trovato "
                  "(cerco un dispositivo con «Fit» nel nome).")
            return 1
        mac, nome = trovato
    print(f"Braccialetto: {nome}  ({mac})")

    print("Connessione…")
    if not _connetti(mac):
        print("Non riesco a connettermi: il braccialetto è forse già collegato "
              "al telefono. Allontana il telefono o spegnine il Bluetooth e riprova.")
        return 1
    print("  connesso.")

    percorso = percorso_caratteristica(mac)
    if not percorso:
        print("Il servizio «Heart Rate» non risponde su questo dispositivo.")
        _bluetoothctl(["disconnect", mac], 10)
        return 1

    print(f"In ascolto per {opzioni.secondi} s.")
    print("Avvia una misura del battito sul braccialetto: "
          "senza misura in corso non manda nulla.")
    battiti = ascolta(mac, percorso, opzioni.secondi)
    _bluetoothctl(["disconnect", mac], 10)

    if not battiti:
        print("\nNessuna misura ricevuta. Il braccialetto manda il battito solo "
              "mentre sta misurando: aprilo su «Frequenza cardiaca» e riprova.")
        return 2

    minimo, massimo = min(battiti), max(battiti)
    media = sum(battiti) / len(battiti)
    print(f"\n{len(battiti)} misure · minimo {minimo} · media {media:.0f} · "
          f"massimo {massimo} bpm")

    if opzioni.salva:
        from vita.db import Database
        db = Database()
        oggi = date.today().isoformat()
        precedente = db.salute_giorno(oggi)
        valori = dict(precedente) if precedente else {}
        valori.update({"data": oggi, "battito": minimo})
        valori.setdefault("note", "")
        db.salva_salute({k: valori.get(k, 0) or 0 for k in (
            "passi", "km", "kcal", "sonno", "sonno_profondo", "sonno_rem",
            "sonno_sveglio", "battito", "hrv", "peso", "acqua")} |
            {"data": oggi, "note": valori.get("note", "")})
        db.chiudi()
        print(f"Scritto nell'archivio: battito {minimo} bpm per il {oggi}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
