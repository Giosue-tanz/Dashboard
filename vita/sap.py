"""Il protocollo con cui parla il braccialetto Samsung: SAP su Bluetooth LE.

SAP sta per *Samsung Accessory Protocol*: è il dialogo che il Galaxy Fit2 fa
col telefono. Non è documentato da Samsung, ma non è nemmeno cifrato, e sul
Fit2 viaggia tutto dentro un solo servizio GATT:

    servizio   0000**1a1a**-0000-1000-8000-00805f9b34fb
    notifica   797ae4e9-…   il braccialetto parla a noi
    scrittura  63e30bad-…   noi parliamo al braccialetto

**Come comincia.** Appena qualcuno si iscrive alle notifiche, il braccialetto
si presenta ogni quarantacinque secondi con 105 byte in chiaro che cominciano
con `68 14` e contengono la scritta `SAMSUNG_ACCESSARY__`, il suo nome, il suo
MAC e la dimensione massima dei messaggi. Per stringergli la mano si rimandano
indietro gli stessi 105 byte col secondo messo a `0x15`. Da lì in poi la
sessione è aperta e si parla a trame.

**La trama.**

    [lunghezza 2B] [CRC della lunghezza 2B] [corpo] [CRC del corpo 2B]

tutto in big endian, e il CRC è il CRC-16/ARC (polinomio 0xa001 riflesso,
partenza 0 — su «123456789» dà 0xbb3d). La lunghezza conta il solo corpo. Se
il braccialetto dichiarasse meno di 256 byte di capienza il prefisso sarebbe
invece la lunghezza ripetuta due volte; il Fit2 dichiara 500, quindi qui si
usa sempre la forma lunga.

    corpo = [bandiere] [sequenza] [servizio] [servizio] [messaggio…]

Il servizio è ripetuto due volte (è così che risponde il braccialetto). Le
bandiere dicono se la trama è intera o un pezzo di una più lunga.

**Il messaggio.** Il primo byte è `(variabile << 7) | (risposta << 6) | id`:
`03` è la richiesta numero 3, `43` la sua risposta. Poi vengono i parametri,
ognuno col suo numero davanti.

Questo file è solo il protocollo — byte dentro, byte fuori, niente Bluetooth e
niente Qt — così si può provare senza braccialetto. Il collegamento vero sta
in `vita/banda.py`.

Il protocollo è stato ricostruito guardando cosa dice davvero il braccialetto,
con l'aiuto del lavoro già fatto da altri sul Galaxy Fit3:
<https://github.com/Vinizera-ai/samsung-app-for-ios> e
<https://github.com/VoidQubex/Galaxy-Fit-3>.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

# ------------------------------------------------------------------ indirizzi
SERVIZIO_SAP = "00001a1a-0000-1000-8000-00805f9b34fb"
CAR_NOTIFICA = "797ae4e9-2e58-4fe8-b48d-b5c79599fb9b"
CAR_SCRITTURA = "63e30bad-4206-4596-839f-e47cbf7a4b5d"

# il battito, quello sì, è standard: lo stesso di qualunque fascia cardio
SERVIZIO_BATTITO = "0000180d-0000-1000-8000-00805f9b34fb"
CAR_BATTITO = "00002a37-0000-1000-8000-00805f9b34fb"
CAR_POSIZIONE = "00002a38-0000-1000-8000-00805f9b34fb"

# ------------------------------------------------------------------- servizi
# A ogni funzione del braccialetto corrisponde un numero di servizio.
SERVIZI = {
    "avvio": 1,            # ora, lingua, primo accordo
    "chiamate": 3,
    "posizione": 4,
    "meteo": 5,
    "notifiche": 7,
    "musica": 9,
    "salute": 10,          # passi, sonno, battito, stress, ossigeno
    "impostazioni": 11,    # batteria, lingua
}

# ------------------------------------------------------------------- saluto
SALUTO_LUNGHEZZA = 105
SALUTO_RICHIESTA = 0x14        # il braccialetto si presenta
SALUTO_RISPOSTA = 0x15         # noi rispondiamo
FIRMA_SALUTO = b"SAMSUNG_ACCESSARY"

# tipi di trama (bit 1-2 delle bandiere)
INTERA, PRIMA, SEGUITO, ULTIMA = 0, 1, 2, 3

EPOCA_SAMSUNG = datetime(1990, 1, 1, tzinfo=timezone.utc)


# --------------------------------------------------------------------- CRC
def crc16(dati: bytes) -> int:
    """CRC-16/ARC: polinomio 0xa001 riflesso, partenza 0.

    È lo stesso che usa il kernel Linux (`crc16`): su «123456789» dà 0xbb3d.
    """
    resto = 0
    for byte in dati:
        resto ^= byte
        for _ in range(8):
            resto = (resto >> 1) ^ 0xA001 if resto & 1 else resto >> 1
    return resto


# ------------------------------------------------------------------- trame
class Trama:
    """Una trama letta dal braccialetto."""

    __slots__ = ("servizio", "messaggio", "bandiere", "sequenza", "intera")

    def __init__(self, servizio: int, messaggio: bytes, bandiere: int,
                 sequenza: int, intera: bool = True):
        self.servizio = servizio
        self.messaggio = messaggio
        self.bandiere = bandiere
        self.sequenza = sequenza
        self.intera = intera

    @property
    def tipo(self) -> int:
        """Se la trama è intera o un pezzo di una più lunga."""
        return (self.bandiere >> 1) & 0x03

    @property
    def id_messaggio(self) -> int:
        return self.messaggio[0] & 0x3F if self.messaggio else -1

    @property
    def risposta(self) -> bool:
        return bool(self.messaggio and self.messaggio[0] & 0x40)

    def __repr__(self) -> str:
        return (f"Trama(servizio={self.servizio}, messaggio="
                f"{self.messaggio.hex(' ')}, crc={'ok' if self.intera else 'no'})")


def inquadra(servizio: int, messaggio: bytes, sequenza: int = 0,
             bandiere: int = 0, capienza: int = 500) -> bytes:
    """Mette un messaggio dentro una trama, prefisso e CRC compresi."""
    corpo = bytes([bandiere & 0xFF, sequenza & 0xFF,
                   servizio & 0xFF, servizio & 0xFF]) + messaggio
    if capienza >= 256:
        testa = len(corpo).to_bytes(2, "big")
        prefisso = testa + crc16(testa).to_bytes(2, "big")
    else:
        prefisso = bytes([len(corpo) & 0xFF, len(corpo) & 0xFF])
    return prefisso + corpo + crc16(corpo).to_bytes(2, "big")


def spacchetta(dati: bytes) -> Trama | None:
    """Legge una trama. Torna `None` se non è una trama (per esempio il saluto)."""
    if len(dati) < 8:
        return None
    lunghezza = int.from_bytes(dati[0:2], "big")
    if crc16(dati[0:2]) != int.from_bytes(dati[2:4], "big"):
        return None
    if len(dati) < 6 + lunghezza or lunghezza < 4:
        return None
    corpo = dati[4:4 + lunghezza]
    coda = int.from_bytes(dati[4 + lunghezza:6 + lunghezza], "big")
    return Trama(corpo[2], bytes(corpo[4:]), corpo[0], corpo[1],
                 intera=crc16(corpo) == coda)


def e_saluto(dati: bytes) -> bool:
    """Riconosce la presentazione del braccialetto."""
    return (len(dati) >= 2 and dati[0] == len(dati) - 1
            and dati[1] == SALUTO_RICHIESTA and FIRMA_SALUTO in dati)


def risposta_al_saluto(dati: bytes) -> bytes:
    """La stretta di mano: gli stessi byte, col secondo cambiato."""
    risposta = bytearray(dati)
    risposta[1] = SALUTO_RISPOSTA
    return bytes(risposta)


def capienza_dichiarata(saluto: bytes, difetto: int = 500) -> int:
    """Quanti byte per messaggio accetta il braccialetto (dal saluto)."""
    if len(saluto) < 0x2E:
        return difetto
    valore = int.from_bytes(saluto[0x2C:0x2E], "big")
    return valore if 20 <= valore <= 4096 else difetto


def nome_dal_saluto(saluto: bytes) -> str:
    """Il nome che il braccialetto si dà, scritto dentro il saluto."""
    pezzo = saluto[49:65] if len(saluto) >= 65 else b""
    return pezzo.split(b"\x00")[0].decode("ascii", "ignore").strip()


# --------------------------------------------------------------- messaggi
def messaggio(numero: int, risposta: bool = False, variabile: bool = False) -> int:
    """Il primo byte di un messaggio: formato, verso e numero."""
    return (int(variabile) << 7) | (int(risposta) << 6) | (numero & 0x3F)


def coppie(messaggio_: bytes) -> dict[int, int]:
    """I parametri a un byte di un messaggio corto, come `42 06 00 05 01`.

    Serve per le risposte semplici (la batteria). I messaggi di salute hanno
    parametri di lunghezza diversa e si leggono con le funzioni apposite.
    """
    corpo = messaggio_[1:]
    return {corpo[i]: corpo[i + 1] for i in range(0, len(corpo) - 1, 2)}


# batteria: servizio 11, messaggio 2
RICHIESTA_BATTERIA = bytes([messaggio(2)])
PARAM_LIVELLO, PARAM_CARICA = 5, 6


def batteria(trama: Trama) -> tuple[int, int] | None:
    """Legge la risposta della batteria: (livello, stato di carica)."""
    if trama.servizio != SERVIZI["impostazioni"] or trama.id_messaggio != 2:
        return None
    valori = coppie(trama.messaggio)
    if PARAM_LIVELLO not in valori:
        return None
    return valori[PARAM_LIVELLO], valori.get(PARAM_CARICA, 0)


# --------------------------------------------------------------------- ore
def da_samsung(secondi: int) -> datetime:
    """I secondi dal 1990 (come li conta il braccialetto) in data e ora."""
    return EPOCA_SAMSUNG + timedelta(seconds=int(secondi))


def a_samsung(quando: datetime | None = None) -> int:
    quando = quando or datetime.now(timezone.utc)
    if quando.tzinfo is None:
        quando = quando.astimezone()
    return int((quando - EPOCA_SAMSUNG).total_seconds())


# ------------------------------------------------------------------ salute
# La richiesta dello storico: «dammi quello che hai fino a adesso».
PARAM_SEQUENZA = 0xE0


def richiesta_salute(sequenza: int = 1, quando: datetime | None = None) -> bytes:
    """Chiede al braccialetto i dati di salute che tiene in pancia."""
    return (bytes([messaggio(3), PARAM_SEQUENZA])
            + (sequenza & 0xFFFF).to_bytes(2, "little")
            + bytes([0x05, 0x19, 0x01, 0x00, 0x02, 0x00, 0x00,
                     0x03, 0x04, 0x33, 0x04, 0x00, 0x05, 0x00, 0x06])
            + a_samsung(quando).to_bytes(4, "little")
            + bytes([0x07, 0x01]))


def conferma_salute(sequenza: bytes) -> bytes:
    """Conferma un lotto di dati: senza, il braccialetto lo rimanda e si blocca."""
    return (bytes([messaggio(2, risposta=True), 0x02, PARAM_SEQUENZA])
            + bytes(sequenza[:2]).ljust(2, b"\x00")
            + bytes([0x04, 0x02, 0x01, 0x01]))


def sequenza_di(messaggio_: bytes) -> bytes:
    """Il numero di lotto scritto dentro un messaggio di salute."""
    posizione = messaggio_.find(bytes([PARAM_SEQUENZA]))
    if posizione < 0 or posizione + 3 > len(messaggio_):
        return b"\x00\x00"
    return messaggio_[posizione + 1:posizione + 3]


# ------------------------------------------------------------- l'adozione
# Il servizio 1 è quello dell'adozione: è lì che il compagno dice al
# braccialetto «da oggi ci sono io». La sequenza è di quattro passi, e il
# braccialetto serve gli altri canali solo dopo averla vista tutta.
#
#   1. chi sei            → risponde 0x41 con la versione del firmware
#   2. come stai          → risponde 0x42
#   3. impostazioni       → risponde 0x43   ← questo SCRIVE sul braccialetto
#   4. accordo            → risponde 0x44   ← e anche questo
#
# I primi due chiedono e basta: si possono mandare senza cambiare niente.

CHI_SEI = bytes([0x01, 0x04, 0x02, 0x00, 0x00, 0x00, 0x05, 0x00, 0x0E])
COME_STAI = bytes([0x02, 0x01, 0x00])
ACCORDO = bytes([0x84, 0x01, 0x01])

# La lingua è un numero dell'elenco di Samsung: di documentato c'è poco
# (en=13, en-US=100, hi=24) e il 57 del vettore di prova era il russo. Meglio
# partire dall'inglese, che è sicuro: sbagliare numero vuol dire ritrovarsi i
# menù in una lingua che non si legge.
LINGUA_INGLESE = 13
LINGUA_PREDEFINITA = LINGUA_INGLESE
EPOCA_UNIX = datetime(1970, 1, 1, tzinfo=timezone.utc)


def impostazioni_iniziali(quando: datetime | None = None,
                          lingua: int = LINGUA_PREDEFINITA,
                          fuso: int | None = None, ore24: bool = True) -> bytes:
    """Il terzo passo: ora, fuso, lingua e formato dell'orologio.

    **Scrive sul braccialetto.** Da sola serve anche a rimettergli l'ora
    giusta quando ci si ricollega, senza rifare tutta l'adozione.

    L'ora viaggia come secondi dal 1970 *scritti in cifre* (ASCII), con la
    lunghezza davanti; il fuso in secondi, col segno in un byte a parte.
    """
    quando = quando or datetime.now(timezone.utc)
    if quando.tzinfo is None:
        quando = quando.astimezone()
    if fuso is None:
        locale = quando.astimezone()
        fuso = int(locale.utcoffset().total_seconds()) if locale.utcoffset() else 0
    secondi = str(int((quando - EPOCA_UNIX).total_seconds())).encode("ascii")
    return (bytes([messaggio(3, variabile=True), 0x01])
            + (lingua & 0xFFFF).to_bytes(2, "little")
            + bytes([0x02, 0x00, 0x03, len(secondi)]) + secondi
            + bytes([0x04, 1 if fuso < 0 else 0])
            + (abs(fuso) & 0xFFFF).to_bytes(2, "little")
            + bytes([0x05, 1 if ore24 else 0]))


def firmware(trama: "Trama") -> str:
    """La versione del firmware, dalla risposta al primo passo."""
    if trama.servizio != SERVIZI["avvio"] or trama.messaggio[:1] != b"\x41":
        return ""
    leggibile = bytes(c for c in trama.messaggio if 32 <= c < 127)
    return leggibile.decode("ascii", "ignore").strip()


# il battito standard: due byte, o tre se il valore è grande
def battito(dati: bytes) -> int | None:
    """Legge una misura del servizio «Heart Rate» standard."""
    if len(dati) < 2:
        return None
    valore = (int.from_bytes(dati[1:3], "little") if dati[0] & 0x01
              else dati[1])
    return valore if 25 <= valore <= 240 else None
