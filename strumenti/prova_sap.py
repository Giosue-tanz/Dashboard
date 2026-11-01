#!/usr/bin/env python3
"""Prove del protocollo del braccialetto, con le trame vere.

Non serve il braccialetto: qui dentro ci sono i byte che ha davvero mandato,
copiati da una sessione registrata. Si lancia così:

    python3 strumenti/prova_sap.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vita import sap

# il saluto vero del Galaxy Fit2 (105 byte)
SALUTO = bytes.fromhex(
    "6814040104010353414d53554e475f4143434553534152595f5f"
    "003a113a223a333a443a550000000000000101f4000003d44761"
    "6c6178792046697432202835393153414d53554e470000000000"
    "000000004469616c6f6720424c45000000000000001122334455"
    "00")
# la risposta alla domanda sulla batteria, trama intera
BATTERIA = bytes.fromhex("000906c000400b0b42060005019c05")
# la risposta alla richiesta di salute: «non ho niente di nuovo»
SALUTE_VUOTA = bytes.fromhex("43e0010004020101050d010902432703043304ced64445")

errori = []


def prova(nome, condizione, dettaglio=""):
    if condizione:
        print(f"  ok   {nome}")
    else:
        errori.append(nome)
        print(f"  NO   {nome}   {dettaglio}")


print("CRC")
prova("CRC-16/ARC su «123456789»", sap.crc16(b"123456789") == 0xBB3D,
      hex(sap.crc16(b"123456789")))

print("il saluto")
prova("lo riconosce", sap.e_saluto(SALUTO))
prova("capienza 500", sap.capienza_dichiarata(SALUTO) == 500,
      sap.capienza_dichiarata(SALUTO))
prova("legge il nome", "Galaxy Fit2" in sap.nome_dal_saluto(SALUTO),
      repr(sap.nome_dal_saluto(SALUTO)))
risposta = sap.risposta_al_saluto(SALUTO)
prova("risponde col 0x15", risposta[1] == 0x15 and risposta[2:] == SALUTO[2:])
prova("non lo scambia per una trama", sap.spacchetta(SALUTO) is None)

print("le trame")
trama = sap.spacchetta(BATTERIA)
prova("legge la trama", trama is not None and trama.intera)
prova("servizio 11 (impostazioni)", trama.servizio == 11, trama.servizio)
prova("è la risposta al messaggio 2", trama.risposta and trama.id_messaggio == 2)
prova("legge la batteria", sap.batteria(trama) == (1, 0), sap.batteria(trama))
prova("una trama storpiata viene scartata",
      sap.spacchetta(BATTERIA[:-1] + b"\x00").intera is False)

mia = sap.inquadra(11, sap.RICHIESTA_BATTERIA)
prova("la richiesta batteria è quella che ha funzionato davvero",
      mia == bytes.fromhex("000503c000000b0b0233f7"), mia.hex(" "))

print("la salute")
andata = sap.spacchetta(sap.inquadra(10, SALUTE_VUOTA))
prova("andata e ritorno", andata is not None and andata.intera
      and andata.servizio == 10 and andata.messaggio == SALUTE_VUOTA)
prova("trova il numero di lotto", sap.sequenza_di(SALUTE_VUOTA) == b"\x01\x00",
      sap.sequenza_di(SALUTE_VUOTA))
prova("la conferma è quella mandata al braccialetto",
      sap.conferma_salute(b"\x01\x00") == bytes.fromhex("4202e0010004020101"),
      sap.conferma_salute(b"\x01\x00").hex(" "))
prova("la richiesta comincia col messaggio 3",
      sap.richiesta_salute(1)[0] == 0x03)

print("l'adozione (servizio 1)")
prova("«chi sei» è la domanda documentata",
      sap.CHI_SEI.hex() == "01040200000005000e", sap.CHI_SEI.hex())
prova("«come stai» è 02 01 00", sap.COME_STAI.hex() == "020100", sap.COME_STAI.hex())
prova("l'accordo è 84 01 01", sap.ACCORDO.hex() == "840101", sap.ACCORDO.hex())
# il vettore vero: 14/11/2023 22:13:20Z, Mosca (+3h), lingua 57, orologio a 24 ore
from datetime import datetime, timezone                                 # noqa: E402
prova("le impostazioni iniziali combaciano col vettore noto",
      sap.impostazioni_iniziali(
          datetime(2023, 11, 14, 22, 13, 20, tzinfo=timezone.utc),
          lingua=57, fuso=3 * 3600, ore24=True).hex()
      == "830139000200030a313730303030303030300400302a0501")
prova("il fuso negativo mette il segno",
      sap.impostazioni_iniziali(
          datetime(2023, 11, 14, 22, 13, 20, tzinfo=timezone.utc),
          lingua=57, fuso=-5 * 3600)[-6:-2].hex() == "04015046",
      sap.impostazioni_iniziali(
          datetime(2023, 11, 14, 22, 13, 20, tzinfo=timezone.utc),
          lingua=57, fuso=-5 * 3600)[-6:-2].hex())

print("le ore")
prova("il 1990 vale zero", sap.a_samsung(sap.EPOCA_SAMSUNG) == 0)
prova("1162127333 è un giorno del 2026", sap.da_samsung(1162127333).year == 2026,
      sap.da_samsung(1162127333))

print("il battito")
prova("06 54 sono 84 bpm", sap.battito(bytes.fromhex("0654")) == 84)
prova("scarta i valori impossibili", sap.battito(b"\x00\x00") is None)

print(f"\n{len(errori)} errori" if errori else "\ntutto a posto")
sys.exit(1 if errori else 0)
