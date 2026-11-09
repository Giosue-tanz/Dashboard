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
from PySide6.QtGui import QFontMetrics                                 # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QLineEdit          # noqa: E402
from PySide6.QtTest import QTest                                       # noqa: E402

import vita.tess as tess                                               # noqa: E402
# il motore vero non si tocca mai: nessun servizio parte durante le prove
tess.Motore.accendi = lambda self: (False, "prova: motore non toccato")
tess.Motore.attiva = lambda self: False

from vita.andamento import AMPIEZZE, MISURE, FinestraAndamento         # noqa: E402
from vita.db import DB_PATH, Database, copia_archivio                  # noqa: E402
from vita.dialoghi import DialogoGiorno                                # noqa: E402
from vita.finestra import VISTE, FinestraPrincipale                    # noqa: E402
from vita.componenti import NavigatorePeriodo                          # noqa: E402
from vita.tema import SCALE                                            # noqa: E402
from vita.utils import MODI_PERIODO                                    # noqa: E402

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
        copia_archivio(opzioni.archivio, copia)   # WAL compreso
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

    # ---- ogni navigatore: tutti i modi, avanti e indietro nel tempo
    # È il comando che adesso hanno quasi tutti i grafici: se uno di loro non
    # sa rispondere a «mesi» o a «tre settimane fa», si rompe qui e non in
    # mano a chi lo usa.
    navigatori = 0
    for i, (nome, _) in enumerate(VISTE):
        f.vai(i); posa(80)
        vista = f.viste[i]
        for attributo in sorted(a for a in dir(vista) if a.startswith("nav_")):
            nav = getattr(vista, attributo)
            if not isinstance(nav, NavigatorePeriodo):
                continue
            modo_prima, scarto_prima = nav.modo, nav.scarto
            for modo in MODI_PERIODO:
                for indietro in (0, 1, 5):
                    navigatori += 1

                    def passo(n=nav, m=modo, k=indietro):
                        n.imposta_modo(m)
                        n.torna_a_oggi()
                        n.scorri(k)
                        app.processEvents()
                        assert n.finestre(), "nessuna finestra da disegnare"
                        assert n.et_quando.text(), "il periodo non ha un nome"
                        f.grab()
                    prova(f"{nome}/{attributo} {modo} −{indietro}", passo)
            nav.imposta_modo(modo_prima)
            nav.scarto = scarto_prima
            nav._mostra()

    def grafico_vuoto_spiega():
        """Un grafico senza niente dentro deve dire **perché**.

        Col navigatore si può andare indietro fin dove si vuole, e prima o
        poi si finisce in una finestra vuota: «Nessun dato da mostrare» lì
        lascia a chiedersi se si è rotto qualcosa.
        """
        indice = [k for k, (nome, _) in enumerate(VISTE) if nome == "emozioni"][0]
        vista = f.viste[indice]
        f.vai(indice); posa(100)
        vista.nav_andamento.imposta_modo("settimane")
        vista.nav_andamento.scorri(60)        # un anno e passa fa: lì non c'è nulla
        app.processEvents()
        assert "Nessun dato da mostrare" != vista.g_andamento.vuoto, \
            "il grafico vuoto non spiega niente"
        vista.nav_andamento.torna_a_oggi()
        vista.nav_andamento.imposta_modo("giorni")
    prova("Grafici: quando sono vuoti dicono perché", grafico_vuoto_spiega)

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

    def nomi_interi():
        """Il nome di una conversazione ci deve stare tutto, in altezza.

        Il foglio di stile mette quattro pixel di stacco fra una voce e
        l'altra: se non si contano, la riga ne riceve quattro in meno di
        quelli che ha chiesto, e il nome resta tagliato di sotto. Con il
        testo molto grande si vedeva a occhio nudo.
        """
        r.aggiorna_elenco(); posa(150)
        for k in range(r.elenco.count()):
            voce = r.elenco.item(k)
            riga_voce = r.elenco.itemWidget(voce)
            if riga_voce is None:
                continue
            serve = QFontMetrics(riga_voce.et_nome.font()).height()
            assert riga_voce.et_nome.height() >= serve, (
                f"nome schiacciato: {riga_voce.et_nome.height()} invece di {serve}")
    prova("Tess: i nomi delle chat ci stanno tutti", nomi_interi)
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
        # la giornata di oggi si sgombra: nell'archivio vero il braccialetto
        # potrebbe averci già messo un sonno più lungo, e i conti di un
        # giorno non tornano indietro (vedi `Database.CRESCONO`)
        db.esegui("DELETE FROM salute WHERE data=?", (giorno,))
        db.esegui("DELETE FROM banda_scritti WHERE data=?", (giorno,))
        db.esegui("DELETE FROM battiti WHERE data=?", (giorno,))
        vista.aggiorna()
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

    def senza_ho_finito():
        """I lotti si leggono quando smettono di arrivare, non solo alla fine.

        Il braccialetto dice «ho finito» quando gli pare — a volte prima
        dell'ultimo lotto. Aspettare solo quella parola vuol dire perdere
        quello che arriva dopo: è così che il sonno di una notte intera e
        le ore di battito di una giornata sono rimasti fuori dall'archivio,
        scritti su disco e mai letti.
        """
        from vita.banda import Braccialetto
        # un lotto di passi vero, registrato dal Galaxy Fit2
        lotto = bytes.fromhex(
            "8203e00300070105 3ddb4845 01 00db4845 02 3bdb4845 03 80ee3600"
            "10 0d000000 11 d65b1f41 12 8ffb293e 13 82f0073f 14 00000000"
            "15 0d000000".replace(" ", ""))
        banda = Braccialetto()
        arrivati = []
        banda.giorni_pronti.connect(lambda g: arrivati.append(g))
        assert banda._consegna(False) == {}, "senza lotti non deve dire niente"
        banda._raccolti = [lotto]
        giorni = banda._consegna(False)      # nessun «ho finito» di mezzo
        assert giorni and arrivati, "i lotti arrivati non sono stati letti"
        assert banda._sgranatura.isActive() is False
    prova("Braccialetto: legge i lotti senza aspettare «ho finito»", senza_ho_finito)

    def stress_senza_punteggio():
        """«Ho misurato lo stress e nell'app non succede niente.»

        A volte il braccialetto manda la misura col punteggio a zero. Zero
        vorrebbe dire «sereno», quindi nell'archivio non ci va — ma il
        silenzio sembra un guasto: la riga di stato lo deve dire.
        """
        from datetime import date as _d
        riquadro = f.viste[i_salute].riquadro_banda
        oggi = _d.today().isoformat()
        riquadro._giorni_scritti, riquadro._ore_scritte = set(), 0
        riquadro._stress_vuote = 0
        riquadro._conta_stress([{"quando": f"{oggi}T18:31", "valore": 0},
                                {"quando": f"{oggi}T22:22", "valore": 0},
                                {"quando": "2020-01-01T10:00", "valore": 0},
                                {"quando": f"{oggi}T09:00", "valore": 44}])
        assert riquadro._stress_vuote == 2, riquadro._stress_vuote
        riquadro._racconta(3, "fatto")
        assert "senza punteggio" in riquadro.et_stato.text(), \
            riquadro.et_stato.text()
        assert riquadro.et_stato.toolTip(), "non spiega cosa è successo"
        riquadro._stress_vuote = 0

    prova("Braccialetto: lo stress a zero non resta in silenzio",
          stress_senza_punteggio)

    def pezzi_ricuciti():
        """I pezzi di un lotto grande, rimessi insieme leggendoli da disco.

        Le prime versioni li mettevano da parte uno per uno senza ricucirli:
        dentro c'era una giornata intera di passi che nessuno aveva mai
        letto.
        """
        from vita.lotti import cuci
        # i pezzi veri sono da 484 byte, ed è su quella misura che si capisce
        # se l'indice è uno scostamento o un numero d'ordine
        a, b, c = b"A" * 484, b"B" * 484, b"C" * 484
        intero, buchi = cuci([(0, a), (484, b)])
        assert intero == a + b and buchi == 0, (len(intero), buchi)
        # un pezzo mancante lascia un buco di zeri, non fa scivolare il resto
        intero, buchi = cuci([(0, a), (968, c)])
        assert intero == a + b"\x00" * 484 + c, len(intero)
        assert buchi == 484, buchi
        # numeri d'ordine invece che scostamenti: si incollano e basta
        assert cuci([(0, a), (1, b), (2, c)])[0] == a + b + c
    prova("Lotti: i pezzi si ricuciono", pezzi_ricuciti)

    def rete_su_disco():
        """«Cerca dati» rilegge prima quello che è già stato scaricato.

        I lotti grezzi restano su disco: rileggerli non costa niente e non
        crea doppioni, e recupera quello che al primo colpo non era entrato.
        """
        riquadro = f.viste[i_salute].riquadro_banda
        riquadro._giorni_scritti, riquadro._ore_scritte = set(), 0
        riquadro._ripesca()          # non deve rompersi nemmeno senza lotti
    prova("Braccialetto: rilegge i lotti già scaricati", rete_su_disco)

    def stress_al_posto_degli_allenamenti():
        """In Salute c'è lo stress, e la tabella degli allenamenti non c'è più.

        Gli allenamenti restano: si contano nella mappa della costanza, e da
        lì si aprono, si correggono e si buttano via.
        """
        vista = f.viste[i_salute]
        sezioni = vista.contenitore.sezioni
        assert "stress" in sezioni, sorted(sezioni)
        assert "allenamenti" not in sezioni, sorted(sezioni)
        assert vista.nav_stress is not None
        vista._aggiorna_stress()          # con o senza misure, non si rompe
        assert vista._livello_stress(12)[0] == "basso"
        assert vista._livello_stress(95)[0] == "molto alto"
    prova("Salute: al posto degli allenamenti c'è lo stress",
          stress_al_posto_degli_allenamenti)

    # ---- il cruscotto: gli impegni si modificano e si eliminano
    i_cruscotto = [k for k, (n, _) in enumerate(VISTE) if n == "cruscotto"][0]
    f.vai(i_cruscotto); posa(200)

    def impegni_modificabili():
        """Ogni riga degli impegni si ricorda da dove viene.

        Nella tabella finiscono scadenze, esami e consegne di progetti: senza
        sapere quale è quale, la matita e il cestino non saprebbero dove
        andare a scrivere.
        """
        from datetime import date as _d, timedelta as _t
        vista = f.viste[i_cruscotto]
        quando = (_d.today() + _t(days=3)).isoformat()
        db.salva_scadenza({"id": None, "data": quando, "titolo": "Prova impegno",
                           "area": "carriera", "note": "", "fatta": 0})
        vista._aggiorna_impegni(); posa(100)
        righe = [vista.tab.item(k, 0).data(Qt.UserRole)
                 for k in range(vista.tab.rowCount())]
        assert all(r and len(r) == 2 for r in righe), righe
        assert any(r[0] == "scadenza" for r in righe), (
            f"la scadenza appena scritta non è fra gli impegni: {righe}")
        # niente riga scelta: le icone sono spente, e non combinano guai
        vista.tab.clearSelection()
        vista.azioni_impegni.rivedi()
        assert not vista.azioni_impegni.b_elimina.isEnabled()
        vista._modifica_impegno()        # senza scelta non deve fare niente
        vista.tab.selectRow(0)
        vista.azioni_impegni.rivedi()
        assert vista.azioni_impegni.b_elimina.isEnabled()
    prova("Cruscotto: un impegno sa da dove viene", impegni_modificabili)

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
    print(f"{periodi} periodi · {navigatori} navigatori · {andamenti} andamenti "
          f"· {len(fuori)} finestrelle · {len(strette)} scritte strette "
          f"· {len(errori)} errori")
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
