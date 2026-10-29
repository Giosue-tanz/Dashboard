# Dashboard

![licenza](https://img.shields.io/badge/licenza-MIT-green) ![python](https://img.shields.io/badge/python-3.10%2B-blue) ![offline](https://img.shields.io/badge/rete-nessuna-success) ![piattaforma](https://img.shields.io/badge/piattaforma-Linux-orange)

Applicazione desktop nativa per tenere insieme le cinque cose che si muovono
ogni giorno: **emozioni, carriera, accademica, salute, finanza**.
**Funziona interamente offline**: nessuna connessione di rete, nessun account,
nessun servizio esterno. I dati restano in un unico file SQLite dentro
`~/.local/share/Vita/`.

Stesso impianto dell'app [Finance](../Finance): PySide6, tema scuro o chiaro,
barra laterale richiudibile, riquadri che si trascinano e si ridimensionano.

L'aspetto segue il linguaggio di **One UI**: angoli larghi, schede senza
cornice, pulsanti a pastiglia, numeri grandi e didascalie piccole. Le candele
dei grafici sono pastiglie tonde, senza spigoli. Gli anelli si riempiono e le
barre crescono quando i dati cambiano, e il cambio pagina fa una dissolvenza
breve: movimenti corti, mai d'intralcio. In `mockup/` c'è la pagina HTML usata
per decidere lo stile.

**Niente tinta unica: ogni sezione ha il suo colore.** Rosso per Emozioni, blu
per Carriera, viola per Accademica, turchese per Salute, verde per Finanza,
ambra per Abitudini, rosa per Tess, ardesia per Impostazioni. Il colore si
accende sotto il mouse e riempie la pastiglia quando la pagina è aperta; gli
anelli dei punteggi in fondo alla barra usano la stessa tavolozza
(`AREE` in `vita/tema.py`).

**Le icone si muovono quando le scegli.** Mezzo secondo, una volta sola: il
cuore batte, il battito cardiaco si scrive da sinistra, la spunta delle
abitudini si disegna, il tocco di laurea si inclina, la linea della finanza
sale e la punta fa un saltello, la scintilla di Tess gira, i cursori delle
impostazioni scorrono. Sono gli stessi disegni di sempre (`vita/icone_nav.py`),
ridisegnati fotogramma per fotogramma con una «fase» da 0 a 1.

## Tess, se la accendi tu

**Tess ha una pagina sua**, nella barra accanto ad Abitudini: la chat della tua
AI locale (`~/Scrivania/WORK/AI-Locale`) con in mano i numeri della Dashboard —
salute, esami, progetti, abitudini, finanza — così risponde sui tuoi dati
invece che in generale. Nel cruscotto resta solo l'**interruttore** in alto:
accende il motore e ti porta alla pagina.

Tre cose, perché sono il punto:

* **Non parte niente finché non giri l'interruttore.** Nessun servizio,
  nessun modello in memoria, nessuna GPU occupata all'avvio della Dashboard.
  Lo stesso interruttore poi spegne il motore e libera la VRAM; sta sia nel
  cruscotto sia in cima alla pagina di Tess, e i due si allineano da soli
  anche se accendi il motore da fuori.
* **Accendere vuol dire anche caricare.** Il motore risponde in meno di un
  secondo, ma il modello entra in VRAM solo alla prima domanda: sarebbero
  secondi di attesa dopo aver scritto. L'interruttore quindi lo precarica
  subito (`/api/generate` a vuoto, `keep_alive -1`) e diventa verde solo a
  modello caricato — misurati **3,9 s** sulla GTX 1650, e la prima risposta
  arriva poi in **0,3 s**. Con `OLLAMA_KEEP_ALIVE=-1` resta in memoria finché
  non spegni.
* **Tutto resta sul PC.** La Dashboard parla con il motore di Tess sulla sua
  porta locale, nella rete isolata in cui già vive: nessuna connessione verso
  internet, né qui né là.
* **L'attesa si vede.** Mentre si accende, la pagina mostra la stessa barra
  di caricamento dell'app Tess, il cronometro dei secondi e a che punto è
  («accendo il motore» → «carico il modello nella scheda video»). Dopo mezzo
  minuto avvisa che ci sta mettendo più del solito.
* **Le conversazioni restano, e si vedono.** Il motore non ha memoria — a
  ogni domanda gli si rimanda l'intera conversazione — quindi le chat le
  conserva la Dashboard, nella tabella `tess_chat` del suo archivio. Nella
  pagina di Tess la colonna di sinistra le elenca tutte («oggi · 15:23» più la
  prima domanda): un clic e torni lì, **«+ Nuova»** ne comincia un'altra,
  tasto destro per eliminarne una. Riaprendo l'app ritrovi l'ultima dov'era.
  Sono separate dalle chat fatte nell'interfaccia web di Tess, che restano
  nel database di quella.
* **Ogni chat può avere un nome.** Doppio clic su una voce dell'elenco (o
  tasto destro → «Rinomina…») e il nome si riscrive lì, al posto suo: il
  titolo finisce nella tabella `tess_titoli`. Cancellandolo torna a chiamarsi
  con la prima domanda.
* **L'elenco si chiude.** La freccia accanto a «CONVERSAZIONI» lo ritira e
  lascia tutta la larghezza alla chat; resta una linguetta per riaprirlo, e la
  scelta si ricorda fra un avvio e l'altro. In poco spazio — per esempio se il
  riquadro di Tess finisce nel cruscotto — si ritira comunque da solo.
* **Il riassunto dei dati si può spegnere.** L'interruttore «dati» nella barra
  della chat decide se mandare i numeri a Tess. Il testo del diario non viene
  mandato mai: nel riassunto ci sono solo medie, conteggi e scadenze.

Se Tess sta altrove, il percorso si cambia con l'impostazione `percorso_tess`
nell'archivio; di suo cerca `~/Scrivania/WORK/AI-Locale` e ne legge
`config/env` per sapere indirizzo del motore e nome del modello.

## Installazione

```bash
cd Vita
./installa.sh
```

`installa.sh` crea la voce nel menu applicazioni e l'icona sul Desktop puntando
alla cartella in cui si trova il progetto. Requisiti: Python 3 e PySide6
(`sudo pacman -S pyside6` su Arch, `sudo apt install python3-pyside6` su Debian).

## Avvio

- Doppio clic sull'icona **Dashboard** sul Desktop, oppure
- dal menu applicazioni (categoria Ufficio), oppure
- da terminale: `./avvia.sh`

## I tre indicatori

Stanno in fondo alla barra laterale, sempre sott'occhio in ogni pagina.
I punteggi vanno da 0 a 100 e non sono voti calati dall'alto: ognuno è una
somma di voci dichiarate, e il suggerimento che compare passandoci sopra
mostra da dove arriva ogni punto.

La **finanza** fa eccezione nel numero che mostra: lì si legge il
**patrimonio**, cioè il saldo di tutti i conti; il punteggio dei conti resta
nell'anello e nel suggerimento, insieme al saldo di ogni conto.

In barra c'è il valore e basta: niente frecce, niente confronti con la
settimana o il mese prima.

| Indicatore | Com'è fatto |
|---|---|
| **Emotività** | umore medio (45), energia (15), calma cioè stress basso (20), costanza del diario (20) — ultimi 7 giorni |
| **Finanza** | quota risparmiata (40), budget rispettati (30), avanzamento degli obiettivi (20), movimenti registrati (10) — mese corrente |
| **Salute** | passi (30), sonno (30), allenamenti (25), giorni registrati (15) — ultimi 7 giorni |

Gli obiettivi di riferimento (passi al giorno, ore di sonno, allenamenti a
settimana, ore di studio) si cambiano in **Impostazioni → Obiettivi**.
Un clic su un indicatore porta all'area corrispondente; da barra chiusa
restano i soli anelli, con il dettaglio nel suggerimento.

## Le sezioni

| Sezione | Cosa fa | Cosa ci scrivi |
|---|---|---|
| **Cruscotto** | la giornata in un colpo d'occhio: umore di oggi, andamento emotivo, salute, progetti in corso, prossimi esami, abitudini, saldo e prossimi impegni di tutte le aree | niente: legge dalle altre |
| **Emozioni** | il diario vero e proprio: la voce di oggi in breve, calendario dell'umore, emozioni più frequenti e **correlazioni** fra umore e sonno, allenamento, lavoro, studio | la finestra «Scrivi voce» in alto (o un giorno del calendario, o una riga dell'elenco): umore, energia, stress, lucidità, emozioni e testo libero |
| **Carriera** | lavagna dei progetti (idee, in corso, in pausa, fatti), ore lavorate, **tariffa oraria reale**, da dove arrivano i soldi, scadenze | progetti, ore di lavoro, incassi — che diventano anche un'**entrata in Finanza**, con la loro categoria |
| **Accademica** | libretto con CFU, media ponderata e base di laurea; ore di studio per materia; **percorsi "da imparare"** separati dagli esami | esami, sessioni di studio, percorsi, scadenze |
| **Salute** | impostata come un'app per la salute: anello dell'attività, composizione corporea (peso, massa grassa, muscolare e secca), costanza, passi, fasi del sonno, battito, HRV, acqua, allenamenti, più la finestra **«Andamento»** per scorrere i dati passati | la finestra «Inserimento dati» in alto (anche per i giorni passati), gli allenamenti, oppure un'importazione da Samsung Health |
| **Finanza** | gli stessi riquadri del cruscotto di Finance: saldo, entrate, uscite, risparmio, andamento, uscite per categoria, conti, barre mensili, budget, ultimi movimenti | movimenti e obiettivi, se la sorgente è l'archivio interno |
| **Abitudini** | griglia dei giorni: un clic segna, un clic toglie; elenco con i nomi riscrivibili sul posto, serie in corso e costanza settimana per settimana | le abitudini e i segni quotidiani |
| **Impostazioni** | aspetto, obiettivi, sorgente della finanza, archivio e backup | — |

## Scrivere i dati a mano

La finestra **«Inserimento dati»** (Salute, in alto) è fatta come una
schermata del telefono: la data è una pastiglia con le frecce ai lati, i campi
sono pastiglie piene che si cingono di un anello quando ci scrivi dentro, e i
comandi stanno in fondo in un'unica pastiglia — *Chiudi | Salva giorno* — al
centro.

Il **sonno non si scrive più a cifre**: c'è la ghiera delle ventiquattr'ore,
come nella sveglia del telefono. Si trascina la maniglia del letto o quella
della sveglia (scattano di cinque minuti in cinque minuti); prendendo la
fascia in mezzo si sposta tutta la dormita senza cambiarne la durata. Sotto si
legge quanto dura — «Dormi 7h30 · 23:00 → 06:30». Il totale in ore e minuti
resta lì accanto e i due si tengono allineati: muovi la ghiera e il totale
cambia, scrivi il totale e si sposta la sveglia. Le due ore finiscono
nell'archivio (`a_letto`, `sveglia`), il totale in minuti resta in `sonno`
come prima, così widget, Andamento e Tess continuano a leggerlo.

## Dati dal braccialetto (Galaxy Fit2)

**Lavoro in corso: il braccialetto parla anche col PC.** Il canale c'è ed è
aperto — quello che manca è capire fino in fondo come racconta i suoi dati.

Il Fit2 pubblica il servizio standard **Heart Rate** (`0x180D`) e poi i servizi
proprietari di Samsung (`0x1a1a`, `0x1901`, `1ab7c24d-…`) più quello di
aggiornamento del firmware (Dialog, `0xfef5` — da non toccare mai). Dentro
`0x1a1a` viaggia **SAP**, il *Samsung Accessory Protocol*: non è cifrato, e il
braccialetto si presenta da solo a chiunque si iscriva alle notifiche.

Quello che è stato provato sul braccialetto vero, e che adesso sta in
`vita/sap.py` (protocollo) e `vita/banda.py` (collegamento via BlueZ):

| Cosa | Si può? | Come |
|---|---|---|
| Stretta di mano SAP | **sì, riuscita** | il braccialetto manda 105 byte `68 14 … SAMSUNG_ACCESSARY`, si risponde col `0x15` |
| Fare domande e avere risposte | **sì** | trame con CRC-16/ARC, servizi numerati (10 salute, 11 impostazioni) |
| Batteria e ora del braccialetto | **sì** | servizio 11, messaggio `02` (il significato del livello è ancora da decifrare) |
| Battito **mentre il braccialetto misura** | sì, dal PC | servizio standard, `strumenti/battito_bluetooth.py` |
| Storico di passi e sonno | **non ancora** | il braccialetto risponde «non ho niente»: il telefono lo svuota prima |
| Storico completo | sì, **dal telefono** | esportazione di Samsung Health → importazione in Vita |

Le prove del protocollo (con le trame vere registrate) si lanciano senza
braccialetto: `python3 strumenti/prova_sap.py`.

### Importare da Samsung Health

1. Sul telefono: **Samsung Health → Impostazioni → Scarica dati personali**.
2. Porta sul PC la cartella (o lo zip) che ne esce: dentro ci sono file `.csv`.
3. In Dashboard: **Salute → Importa dati…** (o Impostazioni → Dati e backup).

Nella finestra che si apre puoi **trascinare dentro** la cartella o lo zip —
il riquadro tratteggiato diventa verde e mostra che cosa hai preso — oppure
sceglierlo a mano con «Scegli una cartella…» / «Scegli uno zip…». Se ne
ha già trovata qualcuna sul PC te la propone nell'elenco a fianco, ma decidi
tu: niente viene importato finché non premi **Importa**.

Lo zip si può lasciar cadere anche direttamente sulla pagina **Salute**: la
finestra si apre già con quel file dentro. Se quello che trascini non è
un'esportazione di Samsung Health, te lo dice e non importa niente.

Vengono letti passi, distanza, calorie, durata del sonno e le sue fasi
(profondo, REM, sveglio), battito, peso, massa grassa e muscolare (se la
bilancia le manda), acqua e allenamenti. Il battito a
riposo viene approssimato con il minimo della giornata. Di base l'importazione
**riempie solo i campi vuoti**, così non cancella quello che hai scritto a
mano; una casella permette di sovrascrivere. Reimportare la stessa cartella
non crea doppioni.

### Tenere i dati aggiornati

L'esportazione di Samsung Health è un'operazione manuale: nessuno la fa ogni
sera. Il ritmo che funziona è doppio.

**Ogni giorno, a mano (20 secondi).** In Salute il pulsante **«Inserimento
dati»** in alto apre una finestra con quattro schede — attività, sonno, corpo,
composizione: scrivi le due o tre cose che ti interessano davvero — passi,
sonno, peso — e salvi con `Ctrl+S`. Le frecce accanto alla data scorrono i
giorni, così ne recuperi diversi senza chiudere nulla; la stessa finestra si
apre cliccando un giorno nella mappa «Costanza». I punteggi in fondo alla
barra laterale si muovono subito.

**Guardare indietro.** Il pulsante **«Andamento»** in alto apre la finestra che
funziona come la scheda di dettaglio di Samsung Health: si sceglie il dato
(passi, battito, sonno, peso, massa grassa, calorie, distanza, HRV, acqua) e
l'ampiezza — settimana, mese, 3 mesi, anno — e con le frecce `‹ ›` (o i tasti
← →) si torna indietro un periodo alla volta. Sotto il grafico c'è l'elenco
giorno per giorno con lo scostamento dalla media: doppio clic su una riga e si
corregge quel giorno. La stessa finestra si apre con un doppio clic su un
grafico o su una riga degli indicatori.

**Ogni settimana o ogni mese, l'importazione.** Rifai l'esportazione sul
telefono, portala sul PC e importala: riempie tutti i giorni rimasti scoperti
e completa quelli già scritti a mano senza sovrascriverli. Reimportare la
stessa esportazione non crea doppioni, quindi non devi tenere il conto di
dove eri arrivato.

Dashboard ti dà una mano a non dimenticartene:

- cerca da sola in **Scaricati**, **Scrivania** e **Documenti** le esportazioni
  di Samsung Health (cartelle o zip) e le propone già selezionate nella
  finestra di importazione;
- quando ne trova una più recente dell'ultima importata, il pulsante in alto
  diventa **«Importa dati… ●»** con il nome e la data nel suggerimento;
- ricorda che cosa ha già letto, così «l'ho già importata?» non è un problema tuo.

Per chi preferisce il terminale (e per un'attività periodica):

```bash
python3 strumenti/importa_salute.py --elenco   # cosa c'è sul PC
python3 strumenti/importa_salute.py            # importa la più recente
```

Senza niente di nuovo esce senza toccare l'archivio, quindi si può mettere in
un timer di systemd o in `cron` senza paura.

**Portare lo zip dal telefono al PC:** cavo USB (il telefono compare nel
gestore file), invio via Bluetooth, oppure KDE Connect — comodo perché i file
arrivano diritti in `~/Scaricati`, ma va installato (`sudo pacman -S kdeconnect`)
e qui non c'è.

### Battito dal vivo

```bash
python3 strumenti/battito_bluetooth.py --secondi 60 --salva
```

Si collega al braccialetto, resta in ascolto e scrive il valore più basso nel
campo «battito a riposo» di oggi. Perché arrivi qualcosa devi avviare una
misura sul braccialetto (**Frequenza cardiaca**): a riposo non trasmette nulla.
Se il telefono è vicino e collegato, il braccialetto può rifiutare la
connessione del PC.

## Finanza: due sorgenti possibili

In **Impostazioni → Finanza** si sceglie da dove arrivano i movimenti:

- **Automatica** (predefinita): se trova `~/.local/share/Finance/finanze.db`
  usa quello, in **sola lettura** — i movimenti continui a inserirli in Finance
  e Dashboard li rilegge; altrimenti usa il proprio archivio.
- **Archivio di Finance**: sempre Finance, anche se l'archivio sta altrove
  (il percorso è impostabile).
- **Archivio interno**: i movimenti, i budget e gli obiettivi stanno dentro
  Dashboard e si inseriscono da qui.

Dashboard non scrive **mai** nell'archivio di Finance: lo apre in sola lettura.

### Categorie di entrata e di uscita

Gli elenchi sono due e distinti — «Lavoro» fra le entrate, «Bollette» fra le
uscite — e cambiando tipo nella finestra del movimento cambia l'elenco. Il
campo resta scrivibile: una categoria nuova entra nell'elenco al salvataggio.
Si gestiscono anche a mano in **Impostazioni → Finanza → Categorie dei
movimenti**; toglierne una non tocca i movimenti già scritti.

### Gli incassi di Carriera sono entrate di Finanza

Un incasso registrato in **Carriera** nasce con una categoria di entrata
(«Lavoro» di partenza) e, con la spunta accesa, diventa anche un movimento di
entrata nell'archivio interno. I due restano agganciati: correggendo l'importo
da una parte cambia anche l'altra, togliendo la spunta sparisce l'entrata e
l'incasso resta, cancellando l'incasso sparisce l'entrata. Nell'elenco degli
incassi il segno **⇄** accanto alla cifra indica quelli collegati; il menu col
tasto destro collega o scollega quelli vecchi.

Con la sorgente su **Finance** il collegamento non è disponibile: lì Dashboard
legge soltanto, e l'incasso resta in Carriera.

## La barra laterale

Il marchio **TANZ** in alto è il pulsante del cruscotto: un clic e si torna alla
panoramica. Il pulsante accanto (o `Ctrl+B`) riduce la barra a una colonna di
icone; da chiusa resta il solo marchio, e un clic su di esso riapre la barra.

Sopra la riga sottile stanno le cinque aree — **Emozioni**, **Carriera**,
**Accademica**, **Salute**, **Finanza** — sotto gli strumenti: **Abitudini**,
**Tess** e **Impostazioni**. Ogni voce ha la sua tinta e la sua icona animata,
e spiega sé stessa nel suggerimento: l'interfaccia non ripete a parole quello
che già si vede.

## I riquadri si spostano

Come nel cruscotto di Finance, ma in tutte le pagine:

- si trascina un riquadro dal titolo per spostarlo, anche su una riga nuova;
- i divisori fra i riquadri ne regolano le dimensioni;
- il testo accanto al titolo apre i **periodi** (7 giorni, 30 giorni, mese…);
- «⋯» apre gli altri comandi, fra cui nascondere il riquadro;
- il pulsante **Riquadri** in alto mostra e nasconde i singoli pannelli e
  ripristina la disposizione.

Ogni pagina si ricorda la propria disposizione, i periodi scelti e lo stato
della barra laterale.

## Il marchio

L'icona è il logo **TANZ**, in due versioni che seguono il tema:

| Dove | Tema scuro | Tema chiaro |
|---|---|---|
| Barra laterale (aperta) | scritta bianca | scritta nera |
| Barra laterale (chiusa) | quadrato nero | quadrato bianco |
| Finestra e barra delle applicazioni | bianco su nero | nero su bianco |
| Icona sul Desktop e nel menu | sempre bianco su nero | — |

I file sorgente stanno in `risorse/sorgente/`; tutte le misure si rigenerano con:

```bash
python3 strumenti/genera_icone.py --occupazione 0.74
```

`--occupazione` è quanta larghezza del quadrato occupa la scritta: `0.61` è
l'inquadratura dell'originale, `0.74` (quella in uso) la rende leggibile anche
a 24 px. Con `--provino prova.png` si ottiene un foglio di confronto invece
delle icone.

## Scorciatoie

| Tasti | Azione |
|---|---|
| `Ctrl+1` … `Ctrl+8` | Passa alla sezione corrispondente |
| `Ctrl+N` | Il comando «nuovo» della sezione attiva (voce, allenamento, progetto, esame, abitudine, movimento) |
| `Ctrl+S` | Salva la voce del diario o i dati di salute del giorno |
| `Ctrl+R` | Ricarica la vista corrente |
| `Ctrl+T` | Cambia tema chiaro/scuro |
| `Ctrl+B` | Apre o chiude il menu laterale |
| `Ctrl+Q` | Esci |

## Dove stanno i dati

La cartella del codice e quella dei dati portano ancora il vecchio nome
(`Vita`): rinominarle sposterebbe l'archivio, e i dati che hai già scritto
valgono più della coerenza del nome. Si cambia quando vuoi, con una migrazione.

| Cosa | Percorso |
|---|---|
| Archivio | `~/.local/share/Vita/vita.db` |
| Backup | `~/.local/share/Vita/backup/` |

Il codice e i dati sono separati: si può cancellare, spostare o riclonare la
cartella del progetto senza perdere nulla. Da **Impostazioni → Dati e backup**
si fa un backup, si ripristina un backup e si esporta tutto in CSV (un file per
tabella).

## Struttura del progetto

```
Vita/                       (la cartella del codice tiene il vecchio nome)
├── main.py                 avvio dell'applicazione
├── avvia.sh                lanciatore
├── installa.sh             crea icona e voce di menu
├── aggiorna.sh             aggiorna preservando i dati
├── risorse/                icone generate dal logo TANZ
├── mockup/                 la pagina HTML che ha deciso lo stile
│   └── sorgente/           il logo originale, scuro e chiaro
├── strumenti/
│   ├── dati_esempio.py     riempie un archivio di prova con dati finti
│   ├── genera_icone.py     rifà le icone dal logo TANZ
│   ├── importa_salute.py   importa Samsung Health da terminale
│   └── battito_bluetooth.py  legge il battito dal braccialetto via Bluetooth
└── vita/
    ├── db.py               schema e interrogazioni
    ├── fonti.py            sorgente della finanza (Finance o archivio interno)
    ├── importa.py          lettura delle esportazioni di Samsung Health
    ├── punteggi.py         come nascono i tre indicatori della barra
    ├── utils.py            date, durate, formattazione
    ├── tema.py             palette e foglio di stile
    ├── grafici.py          linea, barre, ciambella, anello, mappa di calore
    ├── componenti.py       widget riutilizzabili
    ├── dialoghi.py         le finestre di inserimento
    ├── andamento.py        la finestra che scorre i dati passati
    ├── tess.py             il ponte verso l'AI locale e il riquadro di chat
    ├── sezioni.py          riquadri trascinabili e ridimensionabili
    ├── icone_nav.py        icone della barra (QPainter) e il marchio
    ├── finestra.py         finestra principale, barra e indicatori
    └── views/              una vista per sezione, indipendenti fra loro
```

Ogni vista eredita da `VistaSezioni` (o da `VistaBase`) ed espone `aggiorna()`:
per aggiungere una sezione basta creare un modulo in `views/` e registrarlo
nella lista `VISTE` di `finestra.py`.

## Provare l'app piena di dati

```bash
python3 strumenti/dati_esempio.py /tmp/vita-prova.db
```

Scrive un archivio finto di quattro mesi (diario, salute, allenamenti,
progetti, ore, incassi, esami, studio, abitudini, movimenti) senza toccare
l'archivio vero.

## Licenza

MIT.
