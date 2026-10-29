"""Il braccialetto collegato alla Dashboard.

Parla con BlueZ attraverso D-Bus — nessuna libreria Bluetooth in più: su Arch
`python-dbus` c'è già, e il resto lo fa il sistema. Tutto il traffico sta in un
filo suo con un ciclo GLib; verso l'app escono solo segnali Qt, così
l'interfaccia non si blocca mai.

Cosa sa fare oggi:

* **trovarlo e collegarsi** al braccialetto già accoppiato col PC;
* **stringergli la mano** col protocollo SAP (vedi `vita/sap.py`), dopo di che
  il braccialetto ci parla come parlerebbe al telefono;
* **batteria**, e l'ora che segna il braccialetto;
* **battito in diretta**, dal servizio standard: arriva mentre il
  braccialetto misura;
* **chiedere lo storico** di passi, sonno e battito. Il braccialetto risponde
  «non ho niente» quando il telefono gliel'ha già svuotato: i lotti che manda
  vengono messi da parte grezzi in `~/.local/share/Vita/banda/` finché non li
  sappiamo leggere tutti.

Niente di tutto questo tocca il firmware: il servizio di aggiornamento (quello
di Dialog) non lo sfioriamo nemmeno.
"""
from __future__ import annotations

import os
import time
from datetime import datetime

from PySide6.QtCore import QObject, QThread, Signal

from . import sap
from .db import DATA_DIR

CARTELLA_LOTTI = os.path.join(DATA_DIR, "banda")

try:                              # su un PC senza stack Bluetooth l'app vive lo stesso
    import dbus
    import dbus.mainloop.glib
    from gi.repository import GLib
    DISPONIBILE = True
except ImportError:               # pragma: no cover - dipende dal sistema
    dbus = None
    GLib = None
    DISPONIBILE = False

BLUEZ = "org.bluez"
DISPOSITIVO = "org.bluez.Device1"
CARATTERISTICA = "org.bluez.GattCharacteristic1"
SERVIZIO_GATT = "org.bluez.GattService1"
PROPRIETA = "org.freedesktop.DBus.Properties"


def cerca_braccialetto(nome: str = "fit") -> tuple[str, str] | None:
    """Il primo dispositivo accoppiato col nome giusto: (indirizzo, nome)."""
    if not DISPONIBILE:
        return None
    try:
        bus = dbus.SystemBus()
        gestore = dbus.Interface(bus.get_object(BLUEZ, "/"),
                                 "org.freedesktop.DBus.ObjectManager")
        for percorso, interfacce in gestore.GetManagedObjects().items():
            dati = interfacce.get(DISPOSITIVO)
            if not dati:
                continue
            etichetta = str(dati.get("Alias") or dati.get("Name") or "")
            if nome.lower() in etichetta.lower() and bool(dati.get("Paired")):
                return str(dati.get("Address")), etichetta
    except Exception:             # BlueZ assente o fermo: nessun braccialetto
        return None
    return None


class Filo(QThread):
    """Il filo che tiene il Bluetooth: ciclo GLib dentro, segnali Qt fuori."""

    stato = Signal(str, str)              # codice, frase da mostrare
    battito = Signal(int)
    batteria = Signal(int, int)           # livello, carica
    orologio = Signal(str)                # l'ora che segna il braccialetto
    lotto = Signal(int, bytes)            # dati di salute, ancora grezzi
    sincronia = Signal(int, str)          # lotti ricevuti, esito

    def __init__(self, indirizzo: str, parent=None):
        super().__init__(parent)
        self.indirizzo = indirizzo
        self.percorso = "/org/bluez/hci0/dev_" + indirizzo.replace(":", "_")
        self.ciclo = None
        self.bus = None
        self._scrittura = None
        self._pronta = False
        self._capienza = 500
        self._lotti = 0
        self._sequenza = 1
        self._in_attesa = False
        self._ferma = False

    # ------------------------------------------------------------- utilità
    def _oggetto(self, percorso: str, interfaccia: str):
        return dbus.Interface(self.bus.get_object(BLUEZ, percorso), interfaccia)

    def _prop(self, percorso: str, interfaccia: str, nome: str):
        try:
            return self._oggetto(percorso, PROPRIETA).Get(interfaccia, nome)
        except Exception:
            return None

    def _caratteristiche(self) -> dict:
        gestore = dbus.Interface(self.bus.get_object(BLUEZ, "/"),
                                 "org.freedesktop.DBus.ObjectManager")
        oggetti = gestore.GetManagedObjects()
        servizi = {str(p): str(i[SERVIZIO_GATT]["UUID"])
                   for p, i in oggetti.items()
                   if SERVIZIO_GATT in i and str(p).startswith(self.percorso)}
        trovate = {}
        for percorso, interfacce in oggetti.items():
            car = interfacce.get(CARATTERISTICA)
            if not car or not str(percorso).startswith(self.percorso):
                continue
            padre = next((s for s in servizi if str(percorso).startswith(s)), "")
            trovate[(servizi.get(padre, ""), str(car["UUID"]))] = str(percorso)
        return trovate

    # ------------------------------------------------------------ il filo
    def run(self) -> None:
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        self.bus = dbus.SystemBus()
        self.stato.emit("collego", "Mi collego al braccialetto…")
        if not self._collega():
            self.stato.emit("assente",
                            "Non risponde. È al polso? Il telefono potrebbe "
                            "tenerlo occupato: spegnigli il Bluetooth un attimo.")
            return

        caratteristiche = self._caratteristiche()
        notifica = caratteristiche.get((sap.SERVIZIO_SAP, sap.CAR_NOTIFICA))
        self._scrittura = caratteristiche.get((sap.SERVIZIO_SAP, sap.CAR_SCRITTURA))
        cuore = caratteristiche.get((sap.SERVIZIO_BATTITO, sap.CAR_BATTITO))
        if not notifica or not self._scrittura:
            self.stato.emit("sconosciuto",
                            "Questo braccialetto non parla il protocollo che "
                            "conosco.")
            return

        self.bus.add_signal_receiver(
            self._arrivato, dbus_interface=PROPRIETA,
            signal_name="PropertiesChanged", path_keyword="percorso")
        self._percorso_notifica = notifica
        self._percorso_cuore = cuore or ""
        for percorso in (notifica, cuore):
            if not percorso:
                continue
            try:
                self._oggetto(percorso, CARATTERISTICA).StartNotify()
            except Exception:
                pass
        self.stato.emit("saluto", "Collegato. Aspetto che si presenti…")

        self.ciclo = GLib.MainLoop()
        GLib.timeout_add_seconds(1, self._controlla_fine)
        self.ciclo.run()
        self._chiudi(notifica, cuore)

    def _controlla_fine(self) -> bool:
        if self._ferma and self.ciclo is not None:
            self.ciclo.quit()
            return False
        return True

    def _collega(self) -> bool:
        if not self._prop(self.percorso, DISPOSITIVO, "Connected"):
            try:
                self._oggetto(self.percorso, DISPOSITIVO).Connect()
            except Exception:
                pass
        for _ in range(40):
            if self._prop(self.percorso, DISPOSITIVO, "ServicesResolved"):
                return True
            time.sleep(0.5)
        return bool(self._prop(self.percorso, DISPOSITIVO, "Connected"))

    def _chiudi(self, notifica: str, cuore: str) -> None:
        for percorso in (notifica, cuore):
            if not percorso:
                continue
            try:
                self._oggetto(percorso, CARATTERISTICA).StopNotify()
            except Exception:
                pass
        self.stato.emit("spento", "Braccialetto lasciato libero.")

    # --------------------------------------------------------- ricezione
    def _arrivato(self, _interfaccia, cambiamenti, _rimosse, percorso=None) -> None:
        if "Value" not in cambiamenti:
            return
        percorso = str(percorso)
        dati = bytes(cambiamenti["Value"])
        if percorso == getattr(self, "_percorso_cuore", ""):
            valore = sap.battito(dati)
            if valore:
                self.battito.emit(valore)
            return
        if percorso != getattr(self, "_percorso_notifica", ""):
            return
        if sap.e_saluto(dati):
            self._stringi_mano(dati)
            return
        trama = sap.spacchetta(dati)
        if trama is None or not trama.intera:
            return
        self._messaggio(trama)

    def _stringi_mano(self, saluto: bytes) -> None:
        self._capienza = sap.capienza_dichiarata(saluto)
        if self._scrivi(sap.risposta_al_saluto(saluto)):
            self._pronta = True
            self.stato.emit("pronta", "Braccialetto pronto.")
            GLib.timeout_add_seconds(2, self._chiedi_batteria)

    def _messaggio(self, trama) -> None:
        if trama.servizio == sap.SERVIZI["impostazioni"]:
            letta = sap.batteria(trama)
            if letta:
                self.batteria.emit(*letta)
            return
        if trama.servizio != sap.SERVIZI["salute"]:
            return
        messaggio = trama.messaggio
        numero = messaggio[0] if messaggio else 0
        sequenza = sap.sequenza_di(messaggio)
        if numero in (0x82, 0x83, 0x3F):          # un lotto di dati veri
            self._lotti += 1
            self._conserva(messaggio)
            self.lotto.emit(self._lotti, messaggio)
            self._scrivi(sap.inquadra(sap.SERVIZI["salute"],
                                      sap.conferma_salute(sequenza),
                                      capienza=self._capienza))
        elif numero == 0x43:                      # risposta alla richiesta
            vuoto = messaggio[4:8] == bytes([0x04, 0x02, 0x01, 0x01])
            # l'ora del braccialetto viaggia in coda, se c'è
            if len(messaggio) >= 4:
                try:
                    quando = sap.da_samsung(int.from_bytes(messaggio[-4:], "little"))
                    if 2020 < quando.year < 2100:
                        self.orologio.emit(quando.astimezone().strftime("%d/%m %H:%M"))
                except Exception:
                    pass
            self._in_attesa = False
            self.sincronia.emit(
                self._lotti,
                "niente di nuovo: il telefono l'ha già svuotato" if vuoto and not
                self._lotti else "fatto")

    def _conserva(self, messaggio: bytes) -> None:
        """Mette da parte il lotto grezzo: serve a capire il resto del formato."""
        try:
            os.makedirs(CARTELLA_LOTTI, exist_ok=True)
            nome = datetime.now().strftime("lotto-%Y%m%d-%H%M%S-%f.bin")
            with open(os.path.join(CARTELLA_LOTTI, nome), "wb") as f:
                f.write(messaggio)
        except OSError:
            pass

    # ----------------------------------------------------------- comandi
    def _scrivi(self, dati: bytes) -> bool:
        if not self._scrittura:
            return False
        try:
            self._oggetto(self._scrittura, CARATTERISTICA).WriteValue(
                [dbus.Byte(b) for b in dati], {"type": dbus.String("command")})
            return True
        except Exception:
            return False

    def _chiedi_batteria(self) -> bool:
        self._scrivi(sap.inquadra(sap.SERVIZI["impostazioni"],
                                  sap.RICHIESTA_BATTERIA, capienza=self._capienza))
        return False

    def _chiedi_salute(self, cursore: int = 0) -> bool:
        """Chiede lo storico. Cursore a zero vuol dire «dammi tutto»."""
        if not self._pronta:
            self.sincronia.emit(0, "il braccialetto non si è ancora presentato")
            return False
        self._in_attesa = True
        self._sequenza = (self._sequenza % 0xFFFF) + 1
        messaggio = sap.richiesta_salute(self._sequenza)
        if cursore:
            messaggio = messaggio[:-6] + cursore.to_bytes(4, "little") + messaggio[-2:]
        self._scrivi(sap.inquadra(sap.SERVIZI["salute"], messaggio,
                                  capienza=self._capienza))
        return False

    # chiamabili da fuori: entrano nel ciclo GLib senza rompere nulla
    def batteria_ora(self) -> None:
        if GLib:
            GLib.idle_add(self._chiedi_batteria)

    def sincronizza(self, cursore: int = 0) -> None:
        if GLib:
            GLib.idle_add(lambda: self._chiedi_salute(cursore))

    def ferma(self) -> None:
        self._ferma = True


class Braccialetto(QObject):
    """La faccia pulita del braccialetto: quello che l'app usa davvero."""

    stato = Signal(str, str)
    battito = Signal(int)
    batteria = Signal(int, int)
    orologio = Signal(str)
    sincronia = Signal(int, str)
    lotto = Signal(int, bytes)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.filo: Filo | None = None
        self.indirizzo = ""
        self.nome = ""

    @property
    def acceso(self) -> bool:
        return self.filo is not None and self.filo.isRunning()

    def accendi(self) -> bool:
        if self.acceso:
            return True
        if not DISPONIBILE:
            self.stato.emit("assente", "Qui non c'è il Bluetooth di sistema.")
            return False
        trovato = cerca_braccialetto()
        if not trovato:
            self.stato.emit("assente",
                            "Nessun braccialetto accoppiato con questo PC. "
                            "Accoppialo dalle impostazioni Bluetooth e riprova.")
            return False
        self.indirizzo, self.nome = trovato
        self.filo = Filo(self.indirizzo, self)
        for segnale in ("stato", "battito", "batteria", "orologio", "sincronia",
                        "lotto"):
            getattr(self.filo, segnale).connect(getattr(self, segnale))
        self.filo.start()
        return True

    def spegni(self) -> None:
        if self.filo is None:
            return
        self.filo.ferma()
        self.filo.wait(4000)
        self.filo = None

    def chiedi_batteria(self) -> None:
        if self.acceso:
            self.filo.batteria_ora()

    def sincronizza(self, cursore: int = 0) -> None:
        if self.acceso:
            self.filo.sincronizza(cursore)
