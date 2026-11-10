"""Il riquadro del braccialetto dentro Salute.

Si comporta come Tess: finché non accendi l'interruttore non si collega
niente. Il braccialetto parla con un solo compagno alla volta, quindi
collegarlo al PC vuol dire togliere per un attimo il telefono di mezzo — ed è
giusto che a deciderlo sia tu, non l'app all'avvio.

Quello che mostra: la batteria, l'ora che segna il braccialetto e il **battito
in diretta** mentre lo stai misurando (si apre «Frequenza cardiaca» al polso).
Il battito più basso di una sessione si può salvare come battito a riposo del
giorno, che è poi il numero che conta.
"""
from __future__ import annotations

from datetime import date

from .utils import data_it

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (QHBoxLayout, QMessageBox, QPushButton,
                               QSizePolicy, QVBoxLayout, QWidget)

from .banda import CARTELLA_LOTTI, DISPONIBILE, Braccialetto, cerca_braccialetto
from .componenti import (DisposizioneFluida, EtichettaAlta,
                         Interruttore, etichetta)
from .grafici import Sparkline
from .lotti import (lotti_salvati, misure_battito, misure_stress,
                    per_giorno)


# Quello che si può dire di sicuro quando lo stress arriva a zero: cosa è
# successo, perché nell'archivio non ci va, e cosa si può provare. Il perché
# ultimo non lo sappiamo — il braccialetto il punteggio una volta lo mandava.
SPIEGA_STRESS = (
    "Il braccialetto ha registrato la misura ma al posto del punteggio ha "
    "mandato zero.\nUno zero vorrebbe dire «sereno», e non è quello che è "
    "successo: nell'archivio non ci va.\nSe capita sempre, prova a "
    "ricollegare il braccialetto al telefono una volta:\npotrebbe essere "
    "Samsung Health a calcolare il punteggio, non il braccialetto."
)


class RiquadroBraccialetto(QWidget):
    """Batteria, ora e battito in diretta del braccialetto."""

    dati_cambiati = Signal()

    def __init__(self, db, colori: dict, parent=None):
        super().__init__(parent)
        self.db = db
        self.c = colori
        self.banda = Braccialetto(self)
        self.battiti: list[int] = []
        self.setObjectName("ContenutoSezione")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        # ------------------------------------------------------- la testa
        testa = QHBoxLayout()
        testa.setSpacing(8)
        trovato = cerca_braccialetto()
        self.et_nome = etichetta(trovato[1] if trovato else "Nessun braccialetto",
                                 "TitoloRiga")
        self.interruttore = Interruttore(colori, area="salute")
        self.interruttore.setToolTip(
            "Collega il braccialetto a questo PC.\\nMentre è collegato qui, il "
            "telefono potrebbe non vederlo: spegnilo quando hai finito.")
        self.interruttore.cambiato.connect(self._commuta)
        testa.addWidget(self.et_nome)
        testa.addStretch(1)
        testa.addWidget(self.interruttore)
        lay.addLayout(testa)

        # ------------------------------------------------- il battito grande
        self.et_battito = EtichettaAlta("—")
        self.et_battito.setObjectName("ValoreScheda")
        self.et_battito.setAlignment(Qt.AlignCenter)
        self.et_battito.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lay.addWidget(self.et_battito)
        self.linea = Sparkline(colori)
        self.linea.setFixedHeight(28)
        self.linea.hide()            # compare al primo battito che arriva
        lay.addWidget(self.linea)

        self.et_stato = etichetta("", "NotaScheda")
        self.et_stato.setWordWrap(True)
        self.et_stato.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.et_stato)

        # --------------------------------------------------- numeri e comandi
        self.et_numeri = etichetta("", "NotaScheda")
        self.et_numeri.setWordWrap(True)
        lay.addStretch(1)
        lay.addWidget(self.et_numeri)

        fila = DisposizioneFluida(spaziatura=8)
        self.b_salva = QPushButton("Salva battito")
        self.b_salva.setObjectName("Segmento")
        self.b_salva.setMinimumHeight(34)
        self.b_salva.setEnabled(False)
        self.b_salva.clicked.connect(self._salva_battito)
        self.b_salva.setToolTip("Scrive il battito più basso di questa sessione "
                                "come battito a riposo di oggi.")
        self.b_sincronizza = QPushButton("Cerca dati")
        self.b_sincronizza.setObjectName("Segmento")
        self.b_sincronizza.setMinimumHeight(34)
        self.b_sincronizza.setEnabled(False)
        self.b_sincronizza.setToolTip(
            "Chiede al braccialetto i dati che ha raccolto da solo: passi, "
            "sonno, battito, stress.")
        self.b_sincronizza.clicked.connect(self._cerca_dati)
        # L'unico messaggio che Dashboard **scrive** sul braccialetto, e solo
        # se glielo chiedi tu. È quello che il telefono gli manda a ogni
        # collegamento: ora, fuso e lingua. Da quando il compagno è questo PC
        # nessuno glielo manda più, e il giorno del braccialetto si regge solo
        # sul suo orologio.
        self.b_ora = QPushButton("Rimetti l'ora")
        self.b_ora.setObjectName("Segmento")
        self.b_ora.setMinimumHeight(34)
        self.b_ora.setEnabled(False)
        self.b_ora.setToolTip(
            "Manda al braccialetto ora, fuso e lingua: è l'unica cosa che\n"
            "Dashboard gli scrive, ed è quella che gli manda il telefono\n"
            "a ogni collegamento. Chiede conferma prima di farlo.")
        self.b_ora.clicked.connect(self._rimetti_ora)
        fila.addWidget(self.b_salva)
        fila.addWidget(self.b_sincronizza)
        fila.addWidget(self.b_ora)
        lay.addLayout(fila)

        self._giorni_scritti: set[str] = set()
        self._ore_scritte = 0
        self._stress_vuote = 0       # misure di stress senza punteggio, di oggi
        # i lotti arrivano a ondate: il racconto si fa quando smettono, se no
        # la scritta cambierebbe dieci volte al secondo
        self._racconto = QTimer(self)
        self._racconto.setSingleShot(True)
        self._racconto.setInterval(700)
        self._racconto.timeout.connect(lambda: self._racconta(0, ""))
        self.banda.giorni_pronti.connect(self._scrivi_giorni)
        self.banda.battiti_pronti.connect(self._scrivi_battiti)
        self.banda.stress_pronto.connect(self._conta_stress)
        self.banda.lotto.connect(self._arriva_lotto)
        for segnale, gestore in (("stato", self._stato), ("battito", self._battito),
                                 ("batteria", self._batteria),
                                 ("orologio", self._orologio),
                                 ("sincronia", self._sincronia)):
            getattr(self.banda, segnale).connect(gestore)

        if not DISPONIBILE:
            self.interruttore.setEnabled(False)
            self.et_stato.setText("Su questo computer non c'è il Bluetooth di "
                                  "sistema.")
        elif not trovato:
            self.interruttore.setEnabled(False)
            self.et_stato.setText(
                "Accoppia il braccialetto dalle impostazioni Bluetooth del "
                "sistema: poi comparirà qui.")
        else:
            self.et_stato.setText("Spento. Accendi l'interruttore per collegarlo.")
        self._numeri()

    # ------------------------------------------------------------- comandi
    def _commuta(self, acceso: bool) -> None:
        if acceso:
            if not self.banda.accendi():
                self.interruttore.imposta(False)
        else:
            self.banda.spegni()
            self.et_battito.setText("—")
            self.b_sincronizza.setEnabled(False)
            self.b_ora.setEnabled(False)

    def _stato(self, codice: str, frase: str) -> None:
        self.et_stato.setText(frase)
        self.b_sincronizza.setEnabled(codice == "pronta")
        self.b_ora.setEnabled(codice == "pronta")
        if codice in ("assente", "sconosciuto", "spento"):
            self.interruttore.imposta(False)

    def _battito(self, valore: int) -> None:
        self.battiti.append(valore)
        self.et_battito.setText(str(valore))
        self.linea.show()
        self.linea.imposta_dati(self.battiti[-60:], self.c["uscita"])
        self.b_salva.setEnabled(True)
        minimo = min(self.battiti)
        medio = sum(self.battiti) / len(self.battiti)
        self.et_stato.setText(
            f"{len(self.battiti)} misure · minimo {minimo} · medio {medio:.0f} bpm")

    def _batteria(self, livello: int, carica: int) -> None:
        self.db.imposta("banda_batteria", str(livello))
        self.db.imposta("banda_carica", str(carica))
        self._numeri()

    def _orologio(self, quando: str) -> None:
        self.db.imposta("banda_orologio", quando)
        self._numeri()

    # ------------------------------------------------- la raccolta dei dati
    # Una consegna non è un colpo solo: i lotti arrivano a decine e il
    # braccialetto dice «ho finito» più di una volta. Quello che è entrato
    # nell'archivio si tiene da parte qui, e alla fine di ogni pezzo lo si
    # racconta tutto insieme — se no l'ultimo messaggio copriva il
    # precedente e sembrava che non fosse successo niente.
    def _cerca_dati(self) -> None:
        self._giorni_scritti: set[str] = set()
        self._ore_scritte = 0
        self._stress_vuote = 0
        self._ripesca()
        self.et_stato.setText("Chiedo al braccialetto quello che ha…")
        self.banda.sincronizza(0)

    def _rimetti_ora(self) -> None:
        """Ora, fuso e lingua al braccialetto. È l'unica cosa che gli scriviamo.

        Da quando il compagno è questo PC, il messaggio che il telefono manda
        a ogni collegamento non glielo manda più nessuno. Non è detto che
        serva a qualcosa — il giorno del braccialetto se lo conta lui — ma è
        l'unica leva che abbiamo, e non tocca né i dati né le impostazioni
        della sua schermata.
        """
        if QMessageBox.question(
                self, "Rimettere l'ora?",
                "Manda al braccialetto l'ora di questo computer, il fuso e la "
                "lingua.\n\nÈ l'unica cosa che Dashboard gli scrive, ed è lo "
                "stesso messaggio che gli manda il telefono a ogni "
                "collegamento. Non tocca i dati che ha in pancia.",
                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        if self.banda.sistema_ora():
            self.et_stato.setText("Ora, fuso e lingua mandati al braccialetto.")
        else:
            self.et_stato.setText("Non sono riuscito a scrivergli: riprova "
                                  "quando dice «pronto».")

    def _ripesca(self) -> None:
        """Rilegge i lotti già scaricati, prima di chiederne di nuovi.

        Il braccialetto i dati li consegna **una volta sola**: appena
        arrivano finiscono su disco, grezzi. Rileggerli non costa niente e
        non crea doppioni — ed è la rete che prende quello che al primo
        colpo, per un motivo o per l'altro, nell'archivio non era entrato.
        """
        salvati = lotti_salvati(CARTELLA_LOTTI)
        if not salvati:
            return
        self._scrivi_battiti(misure_battito(salvati))
        self._conta_stress(misure_stress(salvati))
        self._scrivi_giorni(per_giorno(salvati))

    def _arriva_lotto(self, quanti: int, _dati) -> None:
        self.et_stato.setText(f"Sto ricevendo… {quanti} lotti")

    def _scrivi_battiti(self, misure: list) -> None:
        """Le ore del battito: è quello che disegna la giornata nel riquadro."""
        # ogni lettura rilegge tutti i lotti della sessione: il conto cresce,
        # non si somma due volte
        self._ore_scritte = max(self._ore_scritte, self.db.salva_battiti(misure))
        self._racconto.start()

    def _conta_stress(self, misure: list) -> None:
        """Le misure di stress di oggi a cui il braccialetto non ha dato un voto.

        Il punteggio dello stress a volte arriva a zero: la sessione c'è, il
        numero no. Scriverlo come «0» vorrebbe dire «sereno» e sarebbe falso,
        quindi nell'archivio non entra — ma allora misuri lo stress al polso
        e nell'app non succede niente, che sembra un guasto. Qui si contano,
        e la riga di stato lo dice.
        """
        oggi = date.today().isoformat()
        self._stress_vuote = max(self._stress_vuote, sum(
            1 for m in misure
            if m["quando"][:10] == oggi and not m["valore"]))

    def _scrivi_giorni(self, giorni: dict) -> None:
        """Quello che il braccialetto ha raccontato finisce nell'archivio.

        Quello che hai scritto tu non si tocca mai; i numeri che aveva messo
        lui invece si rifanno, perché i conti di una giornata crescono fino a
        mezzanotte e la sincronizzazione dopo ne sa di più (vedi
        `Database.scrivi_da_banda`).
        """
        self._giorni_scritti |= set(self.db.scrivi_da_banda(giorni))
        self._racconto.start()

    def _sincronia(self, lotti: int, esito: str) -> None:
        """Fine di una consegna: cosa è entrato, e la pagina si rifà."""
        self._racconta(lotti, esito)

    def _racconta(self, lotti: int, esito: str) -> None:
        """Cosa è entrato nell'archivio, detto in una riga. E i grafici si rifanno.

        Si chiama due volte: quando i lotti smettono di arrivare, e quando il
        braccialetto dice «ho finito». Non sempre le due cose succedono in
        quest'ordine, e aspettare solo la seconda vuol dire perdere pezzi.
        """
        self._racconto.stop()
        giorni = sorted(self._giorni_scritti)
        pezzi = []
        if giorni:
            quanti = len(giorni)
            pezzi.append(f"{quanti} giorno aggiornato: " if quanti == 1
                         else f"{quanti} giorni aggiornati: ")
            pezzi[-1] += ", ".join(data_it(g)[:5] for g in giorni[-4:])
        if self._ore_scritte:
            pezzi.append(f"{self._ore_scritte} ore di battito"
                         if self._ore_scritte > 1 else "un'ora di battito")
        if self._stress_vuote:
            quante = self._stress_vuote
            pezzi.append(
                f"{quante} misure di stress senza punteggio" if quante > 1
                else "una misura di stress senza punteggio")
        self.et_stato.setToolTip(SPIEGA_STRESS if self._stress_vuote else "")
        if pezzi:
            self.et_stato.setText(" · ".join(pezzi))
        elif lotti:
            self.et_stato.setText(
                f"{lotti} lotti ricevuti: era già tutto in archivio.")
        elif esito:        # a consegna finita, e senza niente da dire
            self.et_stato.setText(f"Niente da prendere: {esito}")
        # i grafici si rifanno comunque: hai chiesto i dati, è giusto che la
        # pagina risponda anche quando non è cambiato niente
        self.dati_cambiati.emit()

    def _numeri(self) -> None:
        pezzi = []
        livello = self.db.leggi("banda_batteria", "")
        if livello:
            in_carica = self.db.leggi("banda_carica", "0") != "0"
            pezzi.append(f"batteria {livello}%" + (" in carica" if in_carica else ""))
        orologio = self.db.leggi("banda_orologio", "")
        if orologio:
            pezzi.append(f"segna {orologio}")
        self.et_numeri.setText("  ·  ".join(pezzi) or
                               "apri «Frequenza cardiaca» sul braccialetto per "
                               "vedere il battito arrivare qui")

    def _salva_battito(self) -> None:
        """Il più basso della sessione: è quello che somiglia al riposo."""
        if not self.battiti:
            return
        oggi = date.today().isoformat()
        riga = self.db.salute_giorno(oggi)
        valori = dict(riga) if riga else {}
        valori.update({"data": oggi, "battito": min(self.battiti), "note": ""})
        self.db.salva_salute(valori)
        self.et_stato.setText(f"Salvato: {min(self.battiti)} bpm come battito a "
                              "riposo di oggi.")
        self.dati_cambiati.emit()

    # -------------------------------------------------------------- tema
    def aggiorna_tema(self, colori: dict) -> None:
        self.c = colori
        self.interruttore.aggiorna_tema(colori)
        self.linea.aggiorna_tema(colori)

    def aggiorna(self) -> None:
        self._numeri()

    def chiudi(self) -> None:
        """Lascia libero il braccialetto quando l'app si chiude."""
        self.banda.spegni()
