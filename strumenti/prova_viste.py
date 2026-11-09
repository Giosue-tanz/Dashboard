#!/usr/bin/env python3
"""Apre tutta l'applicazione fuori schermo e la rigira: niente deve rompersi.

Gira su una **copia** dell'archivio, mai su quello vero, e non tocca mai il
braccialetto né accende Tess. Serve dopo ogni modifica:

    python3 strumenti/prova_viste.py            prova tutto
    python3 strumenti/prova_viste.py --scatti CARTELLA   e lascia le immagini

Alla fine stampa quante combinazioni ha provato e quanti errori ha trovato.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
import traceback

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
RADICE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RADICE)

from PySide6.QtCore import QElapsedTimer, QLocale, Qt                  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QLineEdit          # noqa: E402
from PySide6.QtTest import QTest                                       # noqa: E402

import vita.tess as tess                                               # noqa: E402
# il motore vero non si tocca mai: nessun servizio parte durante le prove
tess.Motore.accendi = lambda self: (False, "prova: motore non toccato")
tess.Motore.attiva = lambda self: False

from vita.andamento import AMPIEZZE, MISURE, FinestraAndamento         # noqa: E402
from vita.db import DB_PATH, Database                                  # noqa: E402
from vita.dialoghi import DialogoGiorno                                # noqa: E402
from vita.finestra import VISTE, FinestraPrincipale                    # noqa: E402
from vita.tema import SCALE                                            # noqa: E402

errori: list[str] = []


def prova(nome, azione):
    try:
        azione()
    except Exception:
        errori.append(f"{nome}\n{traceback.format_exc()}")


def main() -> int:
    argomenti = argparse.ArgumentParser(description=__doc__)
    argomenti.add_argument("--scatti", default="", help="dove lasciare le immagini")
    argomenti.add_argument("--archivio", default=DB_PATH,
                           help="da quale archivio partire (se ne fa una copia)")
    opzioni = argomenti.parse_args()

    QLocale.setDefault(QLocale(QLocale.Italian, QLocale.Italy))
    app = QApplication([])
    app.setStyle("Fusion")

    def posa(ms=300):
        tempo = QElapsedTimer(); tempo.start()
        while tempo.elapsed() < ms:
            app.processEvents()

    banco = tempfile.mkdtemp(prefix="prova-dashboard-")
    copia = os.path.join(banco, "prova.db")
    if os.path.exists(opzioni.archivio):
        shutil.copy2(opzioni.archivio, copia)
    scatti = opzioni.scatti or banco

    db = Database(copia)
    db.esegui("DELETE FROM impostazioni WHERE chiave LIKE 'layout_%'")
    f = FinestraPrincipale(db)
    f.resize(1500, 950)
    f.show()

    # ---- ogni vista, nei due temi, più le finestre che si aprono da lì
    for tema in ("scuro", "chiaro"):
        prova(f"tema {tema}", lambda t=tema: f.applica_tema(t))
        for i, (nome, _) in enumerate(VISTE):
            prova(f"{nome} [{tema}]", lambda i=i: (f.vai(i), posa(120), f.grab()))
        prova(f"inserimento dati [{tema}]",
              lambda: DialogoGiorno(db, f.c, parent=f).grab())
        prova(f"andamento [{tema}]",
              lambda: FinestraAndamento(db, f.c, "passi", parent=f).grab())

    # ---- ogni periodo di ogni riquadro
    periodi = 0
    for i, (nome, _) in enumerate(VISTE):
        f.vai(i)
        vista = f.viste[i]
        for chiave, (voci, _pre) in getattr(vista, "PERIODI_SEZIONE", {}).items():
            for valore in voci:
                periodi += 1
                prova(f"{nome}/{chiave}={valore}",
                      lambda v=vista, k=chiave, x=valore:
                      (v._imposta_periodo(k, x), app.processEvents(), f.grab()))

    # ---- la finestra dell'andamento, misura per misura
    w = FinestraAndamento(db, f.c, "passi", parent=f)
    w.show(); posa(150)
    andamenti = 0
    for campo in MISURE:
        for ampiezza in AMPIEZZE:
            for indietro in (0, 1, 3):
                andamenti += 1

                def passo(c=campo, a=ampiezza, n=indietro):
                    w.campo, w.ampiezza, w.indietro = c, a, n
                    w.aggiorna(); app.processEvents(); w.grab()
                prova(f"andamento {campo}/{ampiezza}/{indietro}", passo)

    # ---- Tess: attesa, chat conservate, elenco, rinomina
    i_tess = [k for k, (n, _) in enumerate(VISTE) if n == "tess"][0]
    f.vai(i_tess); posa(200)
    r = f.viste[i_tess].riquadro

    def attesa():
        r._attesa(True); posa(700)
        assert r.barra_attesa.isVisible(), "barra assente"
        assert r.et_tempo.text().endswith("s"), f"cronometro: {r.et_tempo.text()!r}"
        r._attesa(False); posa(200)
        assert r.b_attiva.isVisible(), "il pulsante doveva tornare"
    prova("Tess: barra e cronometro", attesa)

    chat = "2026-10-29T09:30:00"
    db.salva_messaggio_tess(chat, "user", "Quanto ho dormito?")
    db.salva_messaggio_tess(chat, "assistant", "8h02 di media, su sei notti.")
    r._mostra_stato(True)
    prova("Tess: ricarico la conversazione",
          lambda: (r._svuota_bolle(), r.carica_chat(chat)))
    prova("Tess: due bolle",
          lambda: (_ for _ in ()).throw(AssertionError(f"bolle {len(r.bolle)}"))
          if len(r.bolle) != 2 else None)

    def voce_di(chat_id):
        return [r.elenco.item(i) for i in range(r.elenco.count())
                if r.elenco.item(i).data(Qt.UserRole) == chat_id][0]

    def rinomina():
        r.aggiorna_elenco()
        r.rinomina_chat(voce_di(chat)); app.processEvents()
        casella = r.elenco.viewport().findChildren(QLineEdit)[0]
        casella.setText("Sonno di ottobre")
        QTest.keyClick(casella, Qt.Key_Return); posa(150)
        riga = [x for x in db.conversazioni_tess() if x["conversazione"] == chat][0]
        assert riga["titolo"] == "Sonno di ottobre", riga["titolo"]
    prova("Tess: rinomino una chat", rinomina)

    def leggere_i_dati():
        """Il riassunto che Tess riceve deve costruirsi, sempre.

        Un errore qui non si vede da nessuna parte se non nella chat, dove
        Tess dice «non sono riuscita a leggere i tuoi dati»: ed è successo
        per giorni per una riga sbagliata.
        """
        from vita.tess import aree_scelte, contesto
        testo = contesto(db, None, aree_scelte(db), "quanti passi ho fatto ieri?")
        assert len(testo) > 80, f"riassunto troppo corto: {testo!r}"
        assert "Dati veri" in testo, testo[:120]
    prova("Tess: il riassunto dei dati si costruisce", leggere_i_dati)

    def elimina():
        prima = len(db.conversazioni_tess())
        usa_e_getta = "2020-01-01T00:00:00"
        db.salva_messaggio_tess(usa_e_getta, "user", "prova")
        r.aggiorna_elenco()
        assert usa_e_getta in r.voci, "la conversazione non è nell'elenco"
        r._elimina_chat(usa_e_getta)
        assert len(db.conversazioni_tess()) == prima, "non l'ha eliminata"
        assert usa_e_getta not in r.voci, "resta nell'elenco"
    prova("Tess: elimino una chat", elimina)

    def istruzioni_solo_mie():
        """«Solo le mie» vuol dire solo le mie, e l'anteprima non mente.

        La cornice (nome, righe sui dati, tono, lunghezza) va fuori: chi se
        l'è già scritta nelle sue istruzioni se la ritrovava due volte.
        """
        from vita.tess import RIGA_DATI, componi_istruzioni, istruzioni
        sue = "Rispondi in rima, e chiamami capo."
        acceso = componi_istruzioni("Tess", sue, "asciutta", "normali", True)
        assert acceso == sue, acceso
        spento = componi_istruzioni("Tess", sue, "asciutta", "normali", False)
        assert RIGA_DATI in spento and sue in spento, spento[:120]
        # l'anteprima delle impostazioni e quello che arriva a Tess sono la
        # stessa frase: prima erano due pezzi di codice gemelli
        indice = [k for k, (nome, _) in enumerate(VISTE)
                  if nome == "impostazioni"][0]
        vista = f.viste[indice]        # senza cambiare pagina: basta il testo
        vista._anteprima_tess(False)
        assert vista.tess_anteprima.text() == istruzioni(db)
    prova("Tess: «solo le mie» non ripete la cornice", istruzioni_solo_mie)

    def colonna():
        # il pannello non sparisce di colpo: si stringe in 170 ms, e si
        # nasconde a corsa finita. Si aspetta che abbia finito.
        r.piega_colonna(False); posa(300)
        assert not r.colonna_chat.isVisible(), "colonna ancora aperta"
        assert r.linguetta.isVisible(), "linguetta assente"
        r.piega_colonna(True); posa(300)
        assert r.colonna_chat.isVisible(), "colonna non riaperta"
    prova("Tess: chiudo e riapro l'elenco", colonna)
    db.elimina_conversazione_tess(chat)

    # ---- il braccialetto: il riquadro esiste e non si collega da solo
    i_salute = [k for k, (n, _) in enumerate(VISTE) if n == "salute"][0]
    f.vai(i_salute); posa(200)

    def braccialetto():
        riquadro = f.viste[i_salute].riquadro_banda
        assert not riquadro.banda.acceso, "si è collegato da solo!"
        assert riquadro.interruttore is not None
    prova("Braccialetto: sta fermo finché non glielo dici", braccialetto)

    def oggi_in_primo_piano():
        """In «giorni» il numero grande è quello di oggi, non della domenica.

        La finestra è la settimana del calendario: l'ultima barra è la
        domenica, che di mercoledì deve ancora arrivare. Accendere quella, o
        raccontarla come «il periodo scelto», era una bugia.
        """
        from datetime import date as _d
        vista = f.viste[i_salute]
        for nav in (vista.nav_passi, vista.nav_sonno):
            nav.imposta_modo("giorni")
            nav.torna_a_oggi()
            finestre = nav.finestre()
            indice = nav.indice_adesso()
            assert indice >= 0, "oggi non è nella settimana corrente?"
            assert finestre[indice][1] == _d.today().isoformat(), finestre[indice]
            assert nav.scelto()[0] == _d.today().isoformat(), nav.scelto()
            assert nav.nome_scelto() == "oggi", nav.nome_scelto()
        posa(80)
        assert vista.et_passi_nota.text().startswith("oggi"), \
            vista.et_passi_nota.text()
        assert vista.g_passi.evidenziata == vista.nav_passi.indice_adesso()
        # e una settimana indietro oggi non c'è: nessuna barra «di adesso»
        vista.nav_passi.scorri(1)
        assert vista.nav_passi.indice_adesso() == -1
        vista.nav_passi.torna_a_oggi()
    prova("Salute: in «giorni» il primo piano è oggi", oggi_in_primo_piano)

    def battito_di_un_giorno():
        """Con «oggi» il riquadro resta su **un giorno**, e dice quale.

        Prima, se oggi non c'erano misure, passava di nascosto agli ultimi
        sette giorni: la pastiglia diceva «oggi» sopra al grafico della
        settimana.
        """
        from vita.componenti import dati_battito
        dati, _riposo, nota = dati_battito(db, "oggi")
        if not dati:
            return                      # archivio senza battiti: niente da dire
        ore = all(":" in e for e, *_ in dati)
        assert ore, f"non sono ore di una giornata: {[e for e, *_ in dati][:4]}"
        assert nota.split(" ·")[0] in ("oggi", "ieri") or "/" in nota.split(" ·")[0], nota
    prova("Battito: «oggi» resta su un giorno", battito_di_un_giorno)

    def consegna():
        """Una consegna di dati deve finire in archivio **e** nei grafici.

        È tutta la catena: lotti → giorni → archivio → `dati_cambiati` →
        la pagina si rifà. Se si rompe in mezzo non se ne accorge nessuno,
        perché i numeri restano quelli di prima e sembra solo che il
        braccialetto non abbia trovato niente.
        """
        from datetime import date as _d
        vista = f.viste[i_salute]
        riquadro = vista.riquadro_banda
        giorno = _d.today().isoformat()
        prima = vista.et_sonno.text()
        giorni = {giorno: {"passi": 9999, "km": 7.7, "kcal": 333,
                           "sonno": 456, "battito": 52}}
        ore = [{"quando": f"{giorno}T0{h}:00", "valore": 60 + h,
                "minimo": 50, "massimo": 90} for h in range(1, 6)]
        riquadro._giorni_scritti, riquadro._ore_scritte = set(), 0
        riquadro._scrivi_battiti(ore)
        riquadro._scrivi_giorni(giorni)
        riquadro._sincronia(13, "fatto")
        posa(120)
        riga = db.salute_giorno(giorno)
        assert riga and int(riga["sonno"]) == 456, "l'archivio non l'ha preso"
        assert vista.et_sonno.text() != prima, (
            f"il grafico non si è rifatto: resta «{prima}»")
        assert "aggiornato" in riquadro.et_stato.text(), riquadro.et_stato.text()
        # la seconda volta non c'è niente di nuovo, e lo deve dire
        riquadro._giorni_scritti, riquadro._ore_scritte = set(), 0
        riquadro._scrivi_battiti(ore)
        riquadro._scrivi_giorni(giorni)
        riquadro._sincronia(13, "fatto")
        assert "già tutto" in riquadro.et_stato.text(), riquadro.et_stato.text()
    prova("Braccialetto: i dati entrano e i grafici si rifanno", consegna)

    # ---- le quattro dimensioni del testo: niente deve restare tagliato
    strette = []
    for scala in SCALE:
        db.imposta("scala", scala)
        prova(f"testo {scala}", lambda s=scala: f.applica_tema(
            db.leggi("tema", "scuro")))
        for i, (nome, _) in enumerate(VISTE):
            f.vai(i)
            posa(60)
            f.grab()
            for et in f.viste[i].findChildren(QLabel):
                testo = et.text()
                if not et.isVisible() or not testo or testo.endswith("…"):
                    continue
                # i quadretti del calendario delle abitudini sono stretti per
                # scelta: non sono scritte tagliate, sono caselle
                if et.width() < 48 or "\n" in testo:
                    continue
                if et.wordWrap():
                    # chi va a capo si misura alla larghezza che ha davvero,
                    # non a quella che vorrebbe
                    serve = et.heightForWidth(max(1, et.width()))
                    if serve > et.height() + 1:
                        strette.append(f"{nome}/{scala}: «{et.text()[:30]}» "
                                       f"alta {et.height()} invece di {serve}")
                    continue
                metriche = et.fontMetrics()
                if metriche.horizontalAdvance(et.text()) > et.width() + 2:
                    strette.append(f"{nome}/{scala}: «{et.text()[:30]}» "
                                   f"larga {et.width()} invece di "
                                   f"{metriche.horizontalAdvance(et.text())}")
                elif metriche.height() > et.height() + 1:
                    strette.append(f"{nome}/{scala}: «{et.text()[:30]}» "
                                   f"alta {et.height()} invece di {metriche.height()}")
    db.imposta("scala", "normale")
    f.applica_tema(db.leggi("tema", "scuro"))

    f.grab().save(os.path.join(scatti, "salute.png"))
    fuori = [x for x in app.topLevelWidgets() if x.isVisible() and x not in (f, w)]
    print(f"{periodi} periodi · {andamenti} andamenti · {len(fuori)} finestrelle "
          f"· {len(strette)} scritte strette · {len(errori)} errori")
    for stretta in strette[:6]:
        print(f"  {stretta}")
    for e in errori[:4]:
        print(e)
    if not opzioni.scatti:
        shutil.rmtree(banco, ignore_errors=True)
    else:
        print(f"immagini in {scatti}")
    return 1 if errori else 0


if __name__ == "__main__":
    raise SystemExit(main())
