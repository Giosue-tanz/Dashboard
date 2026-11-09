"""Il braccialetto collegato alla Dashboard.

Parla con BlueZ attraverso D-Bus — nessuna libreria Bluetooth in più: su Arch
`python-dbus` c'è già, e il resto lo fa il sistema.

**Niente fili separati, e c'è un motivo.** Su Linux Qt usa il ciclo di GLib per
i suoi eventi: il contesto principale di GLib è già suo. Un secondo ciclo GLib
dentro un thread nostro non riesce a prenderselo e resta fermo ad aspettare —
le notifiche arrivano lo stesso (le smista Qt) ma tutto il resto si impunta, e
un filo che non finisce fa abortire l'applicazione in uscita.

Quindi si fa il contrario: le notifiche di BlueZ entrano dritte nel ciclo di
Qt, e ogni chiamata che potrebbe far aspettare — collegarsi, iscriversi,
scrivere — parte **asincrona**, con la risposta che torna quando torna. Così
l'interfaccia non si ferma mai e alla chiusura non c'è niente da aspettare.

Cosa sa fare oggi:

* **trovarlo e collegarsi** al braccialetto già accoppiato col PC;
* **stringergli la mano** col protocollo SAP (vedi `vita/sap.py`), dopo di che
  il braccialetto ci parla come parlerebbe al telefono;
* **batteria** e ora che segna il braccialetto;
* **battito in diretta**, dal servizio standard, mentre lo sta misurando;
* **chiedere lo storico** di passi e sonno: per ora risponde «non ho niente»,
  perché il telefono lo svuota prima. I lotti, se arrivano, si mettono da
  parte grezzi in `~/.local/share/Vita/banda/`.

Il servizio di aggiornamento del firmware (Dialog, `0xfef5`) non lo tocchiamo
nemmeno di striscio.
"""
from __future__ import annotations

import os
import time
from datetime import datetime

from PySide6.QtCore import QObject, QTimer, Signal

from . import lotti as decodifica
from . import sap
from .db import DATA_DIR

CARTELLA_LOTTI = os.path.join(DATA_DIR, "banda")

try:                              # su un PC senza stack Bluetooth l'app vive lo stesso
    import dbus
    import dbus.mainloop.glib
    # prima di qualunque connessione: così i segnali di BlueZ finiscono nel
    # ciclo di GLib, che su Linux è quello che Qt fa già girare
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    DISPONIBILE = True
except ImportError:               # pragma: no cover - dipende dal sistema
    dbus = None
    DISPONIBILE = False

BLUEZ = "org.bluez"
DISPOSITIVO = "org.bluez.Device1"
CARATTERISTICA = "org.bluez.GattCharacteristic1"
SERVIZIO_GATT = "org.bluez.GattService1"
PROPRIETA = "org.freedesktop.DBus.Properties"


def _bus():
    return dbus.SystemBus()


def cerca_braccialetto(nome: str = "fit") -> tuple[str, str] | None:
    """Il primo dispositivo accoppiato col nome giusto: (indirizzo, nome)."""
    if not DISPONIBILE:
        return None
    try:
        gestore = dbus.Interface(_bus().get_object(BLUEZ, "/"),
                                 "org.freedesktop.DBus.ObjectManager")
        for _percorso, interfacce in gestore.GetManagedObjects().items():
            dati = interfacce.get(DISPOSITIVO)
            if not dati:
                continue
            etichetta = str(dati.get("Alias") or dati.get("Name") or "")
            if nome.lower() in etichetta.lower() and bool(dati.get("Paired")):
                return str(dati.get("Address")), etichetta
    except Exception:             # BlueZ assente o fermo: nessun braccialetto
        return None
    return None


class Braccialetto(QObject):
    """Il braccialetto, visto dall'applicazione.

    Si accende e si spegne a comando; da acceso manda un segnale Qt per ogni
    cosa che il braccialetto racconta.
    """

    stato = Signal(str, str)              # codice, frase da mostrare
    battito = Signal(int)
    batteria = Signal(int, int)           # livello 0-100, carica
    orologio = Signal(str)                # l'ora che segna il braccialetto
    sincronia = Signal(int, str)          # lotti ricevuti, esito
    lotto = Signal(int, bytes)            # dati di salute, ancora grezzi
    giorni_pronti = Signal(dict)          # i giorni già messi in ordine
    battiti_pronti = Signal(list)         # il battito ora per ora
    stress_pronto = Signal(list)          # le misure di stress, punteggio o no
    firmware = Signal(str)                # che versione porta dentro
    adozione = Signal(str)                # a che punto è l'adozione

    def __init__(self, parent=None):
        super().__init__(parent)
        self.indirizzo = ""
        self.nome = ""
        self.percorso = ""
        self.acceso = False
        self.pronta = False
        self._scrittura = ""
        self._notifica = ""
        self._cuore = ""
        self._capienza = 500
        self._lotti = 0
        self._sequenza = 1
        self._ascolto = None
        self._attesa_saluto = False
        self._ultima_notifica = ("", b"", 0.0)
        self._raccolti: list[bytes] = []      # i lotti di questa sincronizzazione
        self._pezzi: dict[int, bytes] = {}    # i frammenti di un lotto grande
        self._mappa_pezzi: list[tuple] = []   # com'erano fatti i pezzi
        self._arrivi: list[tuple] = []        # e in che ordine sono arrivati
        self._buchi = 0                       # quanti byte mancano all'appello
        # il braccialetto chiude il collegamento se nessuno gli parla: il
        # telefono lo tiene sveglio chiedendogli cose ogni tanto, e qui si fa
        # lo stesso. Senza, cade dopo qualche minuto.
        self._battito_presenza = QTimer(self)
        self._battito_presenza.setInterval(40000)
        self._battito_presenza.timeout.connect(self._tieni_sveglio)
        # Appena i lotti smettono di arrivare, si leggono. Prima si aspettava
        # il «ho finito» del braccialetto, che però lo dice quando gli pare —
        # a volte **prima** dell'ultimo lotto: e quei lotti restavano lì,
        # scritti su disco e mai letti. È così che il sonno di una notte e le
        # ore di battito di una giornata non sono mai entrati nell'archivio.
        self._sgranatura = QTimer(self)
        self._sgranatura.setSingleShot(True)
        self._sgranatura.setInterval(900)
        self._sgranatura.timeout.connect(lambda: self._consegna(False))
        self._cadute = 0

    # --------------------------------------------------------- D-Bus comodo
    def _oggetto(self, percorso: str, interfaccia: str):
        return dbus.Interface(_bus().get_object(BLUEZ, percorso), interfaccia)

    def _prop(self, percorso: str, interfaccia: str, nome: str):
        try:
            return self._oggetto(percorso, PROPRIETA).Get(interfaccia, nome)
        except Exception:
            return None

    @staticmethod
    def _zitto(*_a, **_k) -> None:
        """La risposta non ci serve: sta qui solo per non doverla aspettare."""

    def _caratteristiche(self) -> dict:
        """Le caratteristiche del braccialetto, per (servizio, caratteristica)."""
        gestore = dbus.Interface(_bus().get_object(BLUEZ, "/"),
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

    # ------------------------------------------------------------- accendi
    def accendi(self) -> bool:
        """Si collega al braccialetto. Torna False se non c'è niente da fare."""
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
        self.percorso = "/org/bluez/hci0/dev_" + self.indirizzo.replace(":", "_")
        self.acceso = True
        self._lotti = 0
        self._attese = 0
        if self._prop(self.percorso, DISPOSITIVO, "ServicesResolved"):
            self._pronto_a_parlare()
            return True
        self.stato.emit("collego", "Mi collego al braccialetto…")
        try:
            # asincrona: collegarsi può prendere qualche secondo, e la pagina
            # non deve restare ferma ad aspettare
            self._oggetto(self.percorso, DISPOSITIVO).Connect(
                reply_handler=self._collegato, error_handler=self._non_collegato)
        except Exception as errore:
            self._non_collegato(errore)
            return False
        QTimer.singleShot(20000, self._controlla_collegamento)
        return True

    def _collegato(self) -> None:
        """Collegati sì, ma i servizi arrivano un istante dopo: si aspetta."""
        self._attese = 0
        self._aspetta_servizi()

    def _aspetta_servizi(self) -> None:
        if not self.acceso:
            return
        if self._prop(self.percorso, DISPOSITIVO, "ServicesResolved"):
            self._pronto_a_parlare()
            return
        if not self._prop(self.percorso, DISPOSITIVO, "Connected"):
            self.acceso = False
            self.stato.emit("assente",
                            "Si è scollegato. Sveglialo (tocca lo schermo) e "
                            "riprova.")
            return
        self._attese += 1
        if self._attese > 25:                       # una decina di secondi
            self.acceso = False
            self.stato.emit("assente",
                            "Collegato, ma non espone i suoi servizi. Sveglialo "
                            "e riprova fra un momento.")
            return
        QTimer.singleShot(400, self._aspetta_servizi)

    def _non_collegato(self, _errore=None) -> None:
        self.acceso = False
        self.stato.emit("assente",
                        "Non risponde. È al polso ed è sveglio? Il telefono "
                        "potrebbe tenerlo occupato: spegnigli il Bluetooth un "
                        "attimo.")

    def _controlla_collegamento(self) -> None:
        if self.acceso and not self.pronta and not self._prop(
                self.percorso, DISPOSITIVO, "ServicesResolved"):
            self._non_collegato()

    def _pronto_a_parlare(self) -> None:
        """Collegato: ci si iscrive alle notifiche e si aspetta il saluto.

        Ci si può arrivare da due strade (la risposta di Connect e l'attesa
        dei servizi): se il lavoro è già fatto non lo si rifà, se no ogni
        domanda tornerebbe indietro in doppia e tripla copia.
        """
        if self._ascolto is not None and self._notifica:
            if self.pronta:
                return
            self._aspetta_saluto()
            return
        caratteristiche = self._caratteristiche()
        self._notifica = caratteristiche.get((sap.SERVIZIO_SAP, sap.CAR_NOTIFICA), "")
        self._scrittura = caratteristiche.get((sap.SERVIZIO_SAP,
                                               sap.CAR_SCRITTURA), "")
        self._cuore = caratteristiche.get((sap.SERVIZIO_BATTITO,
                                           sap.CAR_BATTITO), "")
        if not self._notifica or not self._scrittura:
            # può essere che si sia scollegato mentre guardavamo: allora non è
            # il protocollo sbagliato, è che non c'è più nessuno dall'altra parte
            if not self._prop(self.percorso, DISPOSITIVO, "Connected"):
                self.acceso = False
                self.stato.emit("assente",
                                "Si è scollegato prima di dire chi è. "
                                "Sveglialo e riprova.")
                return
            self.acceso = False
            self.stato.emit("sconosciuto",
                            "Questo braccialetto non parla il protocollo che "
                            "conosco.")
            return
        if self._ascolto is None:
            self._ascolto = _bus().add_signal_receiver(
                self._arrivato, dbus_interface=PROPRIETA,
                signal_name="PropertiesChanged", path_keyword="percorso")
        for percorso in (self._notifica, self._cuore):
            if percorso:
                try:
                    self._oggetto(percorso, CARATTERISTICA).StartNotify(
                        reply_handler=self._zitto, error_handler=self._zitto)
                except Exception:
                    pass
        self.stato.emit("saluto", "Collegato. Aspetto che si presenti…")
        self._cadute = 0
        if not self._battito_presenza.isActive():
            self._battito_presenza.start()
        self._aspetta_saluto()

    def _aspetta_saluto(self) -> None:
        """Il saluto arriva solo quando la sessione nasce: se il braccialetto
        ci parlava già non lo rimanda, e allora si riprende da dov'era."""
        if self._attesa_saluto:
            return
        self._attesa_saluto = True
        QTimer.singleShot(9000, self._sessione_gia_aperta)

    def _sessione_gia_aperta(self) -> None:
        self._attesa_saluto = False
        if self.acceso and not self.pronta:
            self.pronta = True
            self.stato.emit("pronta", "Braccialetto pronto.")
            self.chiedi_batteria()

    def _tieni_sveglio(self) -> None:
        """Una domanda ogni tanto: se cade, si riprova una volta da soli."""
        if not self.acceso:
            self._battito_presenza.stop()
            return
        if self._prop(self.percorso, DISPOSITIVO, "Connected"):
            self.chiedi_batteria()
            self._cadute = 0
            return
        self._cadute += 1
        if self._cadute > 3:
            self.stato.emit("assente", "Si è staccato e non torna. "
                                       "Sveglialo e riaccendi l'interruttore.")
            self.spegni()
            return
        self.stato.emit("collego", "Si era staccato: lo richiamo…")
        self.pronta = False
        try:
            self._oggetto(self.percorso, DISPOSITIVO).Connect(
                reply_handler=self._collegato, error_handler=self._zitto)
        except Exception:
            pass

    # ------------------------------------------------------------ ricezione
    def _arrivato(self, _interfaccia, cambiamenti, _rimosse, percorso=None) -> None:
        if not self.acceso or "Value" not in cambiamenti:
            return
        percorso = str(percorso)
        dati = bytes(cambiamenti["Value"])
        # ogni notifica arriva in doppia copia (lo fa già BlueZ, l'ho visto
        # anche con un ascoltatore solo): la seconda, identica e a ridosso
        # della prima, si butta. Un battito ripetuto non dice niente di nuovo.
        adesso = time.monotonic()
        ultimo_percorso, ultimi_dati, quando = self._ultima_notifica
        if (percorso, dati) == (ultimo_percorso, ultimi_dati) and adesso - quando < 0.4:
            return
        self._ultima_notifica = (percorso, dati, adesso)
        if percorso == self._cuore:
            valore = sap.battito(dati)
            if valore:
                self.battito.emit(valore)
            return
        if percorso != self._notifica:
            return
        if sap.e_saluto(dati):
            self._stringi_mano(dati)
            return
        trama = sap.spacchetta(dati)
        if trama is not None and trama.intera:
            self._messaggio(trama)

    def _stringi_mano(self, saluto: bytes) -> None:
        self._attesa_saluto = False
        self._capienza = sap.capienza_dichiarata(saluto)
        if self._scrivi(sap.risposta_al_saluto(saluto)):
            self.pronta = True
            self.stato.emit("pronta", "Braccialetto pronto.")
            QTimer.singleShot(2000, self.chiedi_batteria)

    def _rimetti_insieme(self, messaggio: bytes) -> bytes | None:
        """I lotti grandi arrivano a pezzi: `3f <stato> <indice>` e poi il pezzo.

        Lo stato dice a che punto siamo — 8 il primo, 9 quelli in mezzo, 10
        l'ultimo. Finché non arriva l'ultimo non c'è niente da leggere.

        A rimetterli insieme è `lotti.cuci`, che sa anche distinguere gli
        indici-scostamento dai numeri d'ordine: è la stessa regola che usa
        chi rilegge da disco i pezzi messi da parte. La mappa dei pezzi
        finisce accanto al lotto, per capirci qualcosa di più la prossima
        volta.
        """
        if len(messaggio) < 6:
            return None
        stato = messaggio[1]
        indice = int.from_bytes(messaggio[2:6], "little")
        if stato == 0x08:                      # primo pezzo: si ricomincia
            self._pezzi = {}
            self._arrivi = []
        pezzo = messaggio[6:]
        if indice in self._pezzi:
            # due pezzi con lo stesso numero: il secondo non deve cancellare
            # il primo, o sparisce mezzo lotto
            indice = max(self._pezzi) + 1
        self._pezzi[indice] = pezzo
        # testa e coda di ogni pezzo: servono a capire se l'uno continua
        # davvero l'altro, o se per strada si perde qualcosa
        self._arrivi.append((stato, indice, len(pezzo),
                             pezzo[:12].hex(), pezzo[-12:].hex()))
        if stato != 0x0A:                      # non è l'ultimo: si aspetta
            return None
        pezzi = list(self._pezzi.items())
        self._pezzi = {}
        self._mappa_pezzi = list(self._arrivi)
        self._arrivi = []
        # la cucitura sta in `vita/lotti.py`, perché la fa anche chi rilegge i
        # pezzi messi da parte su disco: una regola sola, non due gemelle
        intero, self._buchi = decodifica.cuci(pezzi)
        return intero

    def _messaggio(self, trama) -> None:
        if trama.servizio == sap.SERVIZI["avvio"]:
            self._risposta_adozione(trama)
            return
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
        if numero == 0x3F:                        # un pezzo di un lotto grande
            intero = self._rimetti_insieme(messaggio)
            if intero is None:
                return
            messaggio = intero
            numero = messaggio[0] if messaggio else 0
            sequenza = sap.sequenza_di(messaggio)
        if numero in (0x82, 0x83):                # un lotto di dati veri
            self._lotti += 1
            self._conserva(messaggio)
            self._raccolti.append(messaggio)
            self.lotto.emit(self._lotti, messaggio)
            self._sgranatura.start()      # fra un attimo, se non ne arrivano altri
            self._scrivi(sap.inquadra(sap.SERVIZI["salute"],
                                      sap.conferma_salute(sequenza),
                                      capienza=self._capienza))
        elif numero == 0x43:                      # risposta alla richiesta
            vuoto = messaggio[4:8] == bytes([0x04, 0x02, 0x01, 0x01])
            if len(messaggio) >= 4:
                try:
                    quando = sap.da_samsung(int.from_bytes(messaggio[-4:], "little"))
                    if 2020 < quando.year < 2100:
                        self.orologio.emit(quando.astimezone().strftime("%d/%m %H:%M"))
                except Exception:
                    pass
            giorni = self._consegna(True)
            self.sincronia.emit(
                self._lotti,
                "non ha ancora niente da dare" if vuoto and not self._lotti
                else f"{len(giorni)} giorni" if giorni else "fatto")

    def _consegna(self, finita: bool) -> dict:
        """Legge tutti i lotti arrivati finora e li manda a chi li scrive.

        I lotti **non si buttano via**: il braccialetto risponde «ho finito»
        anche in mezzo a una consegna — e a volte prima dell'ultimo lotto.
        Si ricontano tutti ogni volta: i totali possono solo crescere, e chi
        li scrive sa già come rifare i suoi numeri senza toccare i tuoi.
        """
        if finita:
            self._sgranatura.stop()
        if not self._raccolti:
            return {}
        giorni = decodifica.per_giorno(self._raccolti)
        ore = decodifica.misure_battito(self._raccolti)
        stress = decodifica.misure_stress(self._raccolti)
        if ore:
            self.battiti_pronti.emit(ore)
        if stress:
            self.stress_pronto.emit(stress)
        if giorni:
            self.giorni_pronti.emit(giorni)
        return giorni

    # ------------------------------------------------------------ adozione
    PASSI_ADOZIONE = {0x41: "si è presentato", 0x42: "ha detto come sta",
                      0x43: "ha preso ora e lingua", 0x44: "ha accettato: "
                      "da adesso il compagno è questo computer"}

    def _risposta_adozione(self, trama) -> None:
        """Le risposte del servizio 1, una per ogni passo dell'adozione."""
        primo = trama.messaggio[0] if trama.messaggio else 0
        if primo == 0x41:
            versione = sap.firmware(trama)
            if versione:
                self.firmware.emit(versione)
        nota = self.PASSI_ADOZIONE.get(primo)
        if nota:
            self.adozione.emit(nota)

    def presentati(self) -> None:
        """I due passi che chiedono e basta: «chi sei» e «come stai».

        Non cambiano niente sul braccialetto: servono a capire se parla la
        lingua dell'adozione prima di provare quelli che scrivono.
        """
        if not self.pronta:
            self.adozione.emit("il braccialetto non si è ancora presentato")
            return
        self.adozione.emit("gli chiedo chi è…")
        self._scrivi(sap.inquadra(sap.SERVIZI["avvio"], sap.CHI_SEI,
                                  capienza=self._capienza))
        QTimer.singleShot(1500, lambda: self._scrivi(sap.inquadra(
            sap.SERVIZI["avvio"], sap.COME_STAI, capienza=self._capienza)))

    def sistema_ora(self) -> bool:
        """Rimette l'ora, il fuso e la lingua. **Scrive sul braccialetto.**"""
        if not self.pronta:
            return False
        self.adozione.emit("gli do l'ora giusta…")
        return self._scrivi(sap.inquadra(sap.SERVIZI["avvio"],
                                         sap.impostazioni_iniziali(),
                                         capienza=self._capienza))

    def adotta(self, conferma: bool = False) -> bool:
        """Tutti e quattro i passi: questo computer diventa il compagno.

        **Scrive sul braccialetto** (ora, fuso, lingua, accordo), perciò non
        parte senza `conferma=True`: non deve poter succedere per sbaglio, né
        per un clic distratto né per una chiamata di troppo.
        """
        if not conferma:
            self.adozione.emit("adozione non confermata: non ho scritto niente")
            return False
        if not self.pronta:
            self.adozione.emit("il braccialetto non si è ancora presentato")
            return False
        self.presentati()
        QTimer.singleShot(4000, self.sistema_ora)
        QTimer.singleShot(6500, lambda: self._scrivi(sap.inquadra(
            sap.SERVIZI["avvio"], sap.ACCORDO, capienza=self._capienza)))
        return True

    def _conserva(self, messaggio: bytes) -> None:
        """Mette da parte il lotto grezzo: serve a capire il resto del formato."""
        try:
            os.makedirs(CARTELLA_LOTTI, exist_ok=True)
            nome = datetime.now().strftime("lotto-%Y%m%d-%H%M%S-%f.bin")
            with open(os.path.join(CARTELLA_LOTTI, nome), "wb") as f:
                f.write(messaggio)
            if self._mappa_pezzi:
                # com'era spezzettato: indici e lunghezze, più i byte mancanti
                with open(os.path.join(CARTELLA_LOTTI,
                                       nome[:-4] + ".pezzi.txt"), "w") as f:
                    f.write(f"buchi {self._buchi}\n")
                    f.write("stato indice lunghezza testa coda\n")
                    for voce in self._mappa_pezzi:
                        f.write(" ".join(str(x) for x in voce) + "\n")
                self._mappa_pezzi, self._buchi = [], 0
        except OSError:
            pass

    # -------------------------------------------------------------- comandi
    def _scrivi(self, dati: bytes) -> bool:
        if not self._scrittura:
            return False
        try:
            self._oggetto(self._scrittura, CARATTERISTICA).WriteValue(
                [dbus.Byte(b) for b in dati], {"type": dbus.String("command")},
                reply_handler=self._zitto, error_handler=self._zitto)
            return True
        except Exception:
            return False

    def chiedi_batteria(self) -> None:
        if self.pronta:
            self._scrivi(sap.inquadra(sap.SERVIZI["impostazioni"],
                                      sap.RICHIESTA_BATTERIA,
                                      capienza=self._capienza))

    def sincronizza(self, cursore: int = 0) -> None:
        """Chiede lo storico. Cursore a zero vuol dire «dammi tutto»."""
        if not self.pronta:
            self.sincronia.emit(0, "il braccialetto non si è ancora presentato")
            return
        self._sequenza = (self._sequenza % 0xFFFF) + 1
        self._raccolti = []
        messaggio = sap.richiesta_salute(self._sequenza)
        if cursore:
            messaggio = messaggio[:-6] + cursore.to_bytes(4, "little") + messaggio[-2:]
        self._scrivi(sap.inquadra(sap.SERVIZI["salute"], messaggio,
                                  capienza=self._capienza))

    def spegni(self) -> None:
        """Smette di ascoltare e lascia il braccialetto al telefono."""
        if not self.acceso:
            return
        self.acceso = False
        self.pronta = False
        self._battito_presenza.stop()
        for percorso in (self._notifica, self._cuore):
            if not percorso:
                continue
            try:
                self._oggetto(percorso, CARATTERISTICA).StopNotify(
                    reply_handler=self._zitto, error_handler=self._zitto)
            except Exception:
                pass
        if self._ascolto is not None:
            try:
                _bus().remove_signal_receiver(
                    self._arrivato, dbus_interface=PROPRIETA,
                    signal_name="PropertiesChanged")
            except Exception:
                pass
            self._ascolto = None
        try:
            self._oggetto(self.percorso, DISPOSITIVO).Disconnect(
                reply_handler=self._zitto, error_handler=self._zitto)
        except Exception:
            pass
        self.stato.emit("spento", "Braccialetto lasciato libero.")
