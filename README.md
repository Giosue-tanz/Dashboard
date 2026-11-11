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
ambra per Abitudini, rosa per Tess, ardesia per Impostazioni. **Le icone
della barra stanno sempre nella loro tinta** — anche a barra chiusa, dove
restano loro sole a dire dove si va — la scritta si colora sotto il mouse e la
pastiglia si riempie quando la pagina è aperta (lì l'icona passa in negativo);
gli anelli dei punteggi in fondo alla barra usano la stessa tavolozza
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
  conserva la Dashboard, nella tabella `tess_chat` del suo archivio. La
  conversazione sta libera sulla pagina — nessuna scatola intorno: le risposte
  di Tess hanno un filo rosa a sinistra, le tue domande una bolla grigia — e
  **a destra** c'è il pannello con tutte le chat («oggi · 15:23» più la prima
  domanda), che si apre e si chiude dal bottone in cima. Un clic e torni lì,
  **«+ Nuova»** ne comincia un'altra, tasto destro per eliminarne una.
  Riaprendo l'app ritrovi l'ultima dov'era.
* **I messaggi si correggono e si tolgono.** Passando il mouse su un messaggio
  compaiono **Copia**, **Elimina** e, sulle tue domande, **Modifica**: la
  domanda diventa una casella lì dov'è, e «Salva e richiedi» la riscrive e
  rifà la risposta — quelle che venivano dopo rispondevano a un'altra domanda,
  quindi se ne vanno. «Elimina» toglie un messaggio solo, dalla pagina e
  dall'archivio, dopo averlo chiesto.
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
* **I dati li tiene sott'occhio, non li recita.** Nelle istruzioni c'è scritto
  di tenerseli lì e di tirarli in ballo quando glieli chiedi o quando c'entrano
  con il discorso — nei momenti opportuni, non a ogni risposta.
* **Tess si fa su misura** in *Impostazioni → Tess*: il nome che vuoi darle, il
  tono (asciutta, incoraggiante, diretta, ironica, professionale), quanto
  lunghe le risposte, e soprattutto le **istruzioni tue** — una casella di
  testo libero che vale più di tutto il resto («dammi sempre una cosa concreta
  da fare domani», «non parlarmi di soldi se non te lo chiedo», «scrivimi in
  inglese»). L'interruttore **«solo le mie istruzioni»**, in cima alla sezione,
  manda a Tess **soltanto** quello che hai scritto: niente nome, niente tono,
  niente lunghezza e nemmeno le due righe di prudenza sui dati — se le vuoi,
  te le scrivi tu. Prima quelle righe restavano dentro lo stesso, e chi se
  l'era già scritte nelle proprie istruzioni se le ritrovava **due volte di
  fila** nello stesso prompt. Sette caselle decidono poi **che cosa può vedere**: salute,
  punteggi, università, lavoro, abitudini, finanza, scadenze — spenta una, quel
  pezzo di riassunto non le arriva proprio. In fondo alla pagina c'è
  l'anteprima di quello che Tess riceverà, parola per parola.

Se Tess sta altrove, il percorso si cambia con l'impostazione `percorso_tess`
nell'archivio; di suo cerca `~/Scrivania/WORK/AI-Locale` e ne legge
`config/env` per sapere indirizzo del motore e nome del modello.

## Salute, in tre righe

La pagina risponde a tre domande, dall'immediato al lento.

**La giornata** — *Oggi*, *Sonno*, *Battito*. Il riquadro **Oggi** è il
sommario: l'anello dell'obiettivo dei passi e sei numeri. Sopra quello che hai
fatto — passi, calorie attive, distanza — sotto quello che il corpo dice di sé:
**sonno, battito e stress**. I primi tre si contano oggi e basta; gli altri tre
li consegna il braccialetto quando gli pare, e se oggi non è ancora arrivato
niente il riquadro mostra l'ultimo valore che c'è scrivendo di quando è
(«battito · 01/11»), perché un trattino non direbbe niente. Doppio clic su un
numero apre l'andamento di quel dato.

**Nel tempo** — *Passi*, *Costanza*, *Indicatori*: la settimana che si sfoglia,
i quadretti dei giorni centrati, le misure col loro scarto dall'obiettivo.

**Il corpo** — *Composizione*, *Stress*, *Braccialetto*: quello che
cambia lentamente, e in fondo chi lo misura. **Composizione** tiene dentro
anche la curva del peso, che prima era un riquadro a parte: senza la massa
grassa quel riquadro mostrava un numero e una barra finta tutta di un colore,
e non diceva niente. Adesso c'è il peso, di quanto si è mosso nel periodo, la
curva, e — quando la massa grassa c'è — la barra di com'è diviso il peso con
la sua legenda.

**Stress** mostra due cose che non sono la stessa: il numero grande è quello
che misura il braccialetto dal battito — da 0 a 100, e qui **più basso vuol
dire meglio**, per questo le barre prendono il colore del livello (sotto 30
basso, sopra 80 molto alto) invece del verde di casa. La riga sotto dice
invece lo stress **sentito**, quello che hai scritto tu in Emozioni da 1 a
10. Quando i due non vanno d'accordo è proprio quella la cosa da guardare. Se
nella finestra che stai guardando il braccialetto non ha misurato, il riquadro
non mette un trattino: dice l'ultima misura che c'è, e di quando è.

La tabella degli allenamenti non sta più in pagina — gli allenamenti si
contano nella mappa della **Costanza**, e da lì si aprono: con 💪 acceso, un
clic su un quadretto apre l'allenamento di quel giorno per correggerlo o
buttarlo via, e se quel giorno non ce n'è ne comincia uno nuovo.

In **Costanza** i tre dati si scelgono con tre segni sulla riga del titolo
(👟 passi, 🌙 sonno, 💪 allenamenti): il nome per esteso è nel suggerimento, e
il riassunto sta sotto i quadretti. I quadretti si ridisegnano alla misura che
trovano — lato, distanze, angoli e lettere dei giorni seguono tutti la stessa
proporzione — e si riempiono a gradini invece che a sfumatura: fra il 40% e il
45% dell'obiettivo, in dieci pixel, non vedrebbe la differenza nessuno.

I riquadri restano trascinabili: questa è solo la disposizione di partenza, e
«Riquadri → Ripristina disposizione predefinita» ci riporta.

## La chat di Tess

La pagina è fatta come l'app di Tess, con molto meno dentro.

**I messaggi.** Tess parla senza bolla: il tondo con la sua iniziale, il
nome, e il testo largo quanto la colonna — una risposta lunga si legge come
un testo, non come un cartello. Le tue domande restano in una bolla a
destra, così l'occhio capisce subito di chi è la riga. Al passaggio del
mouse compare «Copia», e il posto è già suo anche quando non si vede: la
chat non salta su e giù.

Sotto ogni messaggio, al passaggio del mouse, compaiono le azioni come **icone disegnate** — matita, fogli, cestino — invece di tre parole in fila: la figura la fa il pennello su una griglia di cento per cento, quindi è nitida a ogni dimensione del testo e prende da sé il colore del tema. Copiando, i due fogli diventano un segno di spunta.

**La conversazione sta in una colonna larga al massimo novecento pixel**, in
mezzo alla pagina, con la barra in fondo allineata sotto: una riga di testo
lunga due schermi non si legge, si scansiona.

**L'elenco a sinistra** raggruppa le conversazioni per quando le hai fatte
(oggi, ieri, ultimi 7 giorni, ultimi 30, prima) e ognuna ha il suo **«⋯»**:
riapri, rinomina, elimina — con una domanda prima di eliminare, perché non
si torna indietro. Il menu c'era anche prima, ma solo sul tasto destro, e
non lo trovava nessuno. Il nome si riscrive lì dov'è, e quella aperta si
riconosce dalla tinta.

**Il bottone che apre e chiude l'elenco** disegna un pannello con la colonna
piena da una parte: si capisce da che parte sta, e cresce col testo. A
elenco chiuso si sposta in cima alla conversazione, dov'è il suo posto.

### Due cervelli: Low e Hard

In testata, accanto al nome, c'è il livello che sta rispondendo e una
freccina per cambiarlo. I due si chiamano per quello che costano, non per il
nome del file, e la tendina dice una cosa sola di ciascuno — quanto è svelto:

| livello | modello | scrive a | quando serve |
|---|---|---|---|
| **Low** | `qwen3:4b-instruct` | 28 token al secondo | quasi sempre |
| **Hard** | `qwen3:8b` | 5 token al secondo | quando la domanda è difficile |

I numeri sono **misurati su questa macchina** (GTX 1650 da 4 GB) col
contesto vero della Dashboard dentro, duemila token di riassunto: a vuoto
Low farebbe 39 token al secondo, ma quello è un numero che non vedrà mai
nessuno. Hard è lento per un motivo solo: 5,2 GB in una scheda da 4 non ci
stanno, quindi metà del modello gira sul processore. Non è un difetto da
aggiustare, è aritmetica.

**All'accensione si carica sempre il più svelto**, come faceva il vecchio
Tess che ne aveva uno solo: quando accendi non hai ancora chiesto niente, e
far aspettare mezzo minuto per un cervello che magari non serve è il modo
peggiore di cominciare. Hard te lo prendi dalla tendina quando sai di averne
bisogno, e vale per quella sessione.

**Al cambio di livello si muove una strisciolina in testata**, accanto al
nome, finché i giga non sono in scheda: svuotare la VRAM e riempirla sono
due viaggi lenti, e si fanno in un filo a parte perché la finestra non si
pianti. Per quei secondi la tendina resta chiusa a chiave — un secondo
cambio a metà del primo lascerebbe due modelli in quattro giga.

Tre cose, imparate rompendole:

- **`/api/ps` va confrontato sul nome intero.** Low e Hard sono tutti e due
  «qwen3»: guardando solo la famiglia, il motore credeva Hard già in scheda
  perché c'era Low, non precaricava niente, e i venti secondi arrivavano
  addosso alla prima domanda.
- **`keep_alive: -1` non scade mai.** Il vecchio Tess su gemma3, caricato
  così in una sessione di settimane prima, si teneva 2,7 dei 4 giga della
  scheda: Low entrava a metà sul processore e Hard quasi tutto, e sembravano
  rotti quando era solo la scheda piena di un modello di ieri. Adesso
  l'accensione **sfratta tutto quello che non è il modello scelto**.
- **`think: false`.** Qwen3 di suo ragiona ad alta voce prima di rispondere,
  e quei pensieri li paghi a token. Su Hard la prima prova vera è finita con
  1.264 caratteri di ragionamento, zero parole visibili e la risposta
  tagliata. Chi vuole il ragionamento lungo lo chiede nella domanda.

**Sull'isolamento, per non raccontarlo meglio di com'è.** Il motore ascolta
su `172.28.0.1` — la rete isolata di AI-Locale — con `OLLAMA_NO_CLOUD=1`, e
i tuoi dati non escono di qui. Ma questo è *come è configurato*, non una
gabbia: un filtro di rete messo in un servizio `--user` di systemd viene
accettato e **non applicato** (provato due volte: `IPAddressDeny=any` e il
traffico passa lo stesso). L'unica garanzia vera la dà il kernel, e si
accende da fuori:

```bash
sudo bin/isola-rete.sh          # in ~/Scrivania/WORK/AI-Locale
sudo bin/isola-rete.sh --apri   # riapre, per scaricare un modello nuovo
```

**Dopo quel comando il motore è un servizio di sistema acceso dal boot**, e
questo cambia due cose qui dentro:

- **«Accesa» vuol dire che l'hai accesa tu.** Legando lo stato a «il
  processo risponde», la pagina si apriva già accesa senza aver precaricato
  niente, e bastava cambiare pagina e tornare per riaccendersi da sé subito
  dopo averla spenta. Ora `sincronizza()` guarda una cosa sola: se il motore
  è morto mentre eri acceso, si torna alla schermata di avvio.
- **Spegnere vuol dire svuotare la scheda video.** Fermare un servizio di
  sistema richiede root, e una finestra non deve chiedere la password: così
  «Spegni» — e anche la chiusura della Dashboard — scarica i modelli dalla
  VRAM, che è la cosa che pesa davvero. Il processo che resta a vuoto occupa
  **12 MiB su 4096**, misurati. La pagina lo dice com'è, senza far finta di
  aver fermato qualcosa che è ancora lì.

Una nota su `systemctl`: `--user stop` risponde «0» anche su un servizio già
spento. Fidandosi di quel codice la pagina annunciava «fermato» di un motore
vivissimo, quindi adesso dopo lo stop **si guarda** se risponde ancora.

### I quindici secondi della prima domanda

Il riassunto dei dati che Tess riceve è lungo **2.100 token**, e leggerli
costa quindici secondi — poi il motore li tiene in cache e la domanda dopo
costa 0,4 s. Quell'attesa cadeva tutta sulla prima domanda, dove sembrava
che Tess fosse rotta:

| | prima | adesso |
|---|---|---|
| prima domanda | 16,6 s | **1,2 s** |
| domande dopo | 1,5 s | 1,5 s |

Adesso il blocco lo si fa leggere **all'accensione**, dove l'attesa è
prevista e c'è già la barra che si muove, e di nuovo a ogni cambio di
livello — la cache è del modello, non della chat, e passando a Hard si
ricomincerebbe da capo con trentun secondi.

Perché funzioni, il testo scaldato dev'essere **identico** a quello che la
chat manda davanti a ogni domanda: un carattere di differenza e il motore
rilegge tutto. Per questo lo costruisce un metodo solo, `blocco_sistema()`,
e c'è una prova che i due combacino.

## Il sonno, dal braccialetto

Il braccialetto manda la notte in due pezzi: la **sessione** (da quando ti sei
addormentato a quando ti sei alzato) e le **fasi** in cui l'ha divisa —
leggero, profondo, REM, sveglio, con gli stessi codici che usa Samsung Health
(40001…40004). I due lotti portano lo stesso identificatore di sessione, ed è
così che si rimettono insieme. **La notte vale per il giorno in cui ti
svegli**, come nell'importazione dal telefono.

Arrivano anche l'ora in cui sei andato a letto e quella della sveglia, che
finiscono nei campi di «Inserimento dati».

**Le fasi si scrivono solo se coprono quasi tutta la notte.** I lotti grandi
arrivano a pezzi e un pezzo ogni tanto si perde per strada: con metà delle
fasi la divisione che ne verrebbe fuori sarebbe falsa, e allora si tiene la
sola durata. Dove un pezzo manca, il lettore non butta via il resto: cerca il
prossimo record credibile — un'ora che può essere vera, numeri dentro i
limiti del possibile — e riprende da lì. Accanto a ogni lotto grezzo viene
salvata la mappa dei pezzi (`.pezzi.txt`), per arrivare in fondo alla
faccenda con i prossimi dati.

## Quando premi «Cerca dati»

Il riquadro racconta la consegna mentre succede: «Chiedo al braccialetto
quello che ha…», poi «Sto ricevendo… 7 lotti», e alla fine cosa è entrato —
**«3 giorni aggiornati: 06/11, 07/11, 08/11 · 41 ore di battito»**. Se non
c'era niente di nuovo lo dice lo stesso: «13 lotti ricevuti: era già tutto in
archivio».

Prima quel racconto si perdeva: il messaggio «ho finito» arriva più volte
durante una consegna, e ogni volta copriva quello precedente con un «13 lotti
di dati» che non diceva se nell'archivio fosse entrato qualcosa. **E i grafici
si rifanno comunque**, anche quando non è cambiato niente: hai chiesto i dati,
è giusto che la pagina risponda.

**I lotti si leggono quando smettono di arrivare, non quando il braccialetto
dice «ho finito».** Quella parola la dice quando gli pare — a volte *prima*
dell'ultimo lotto — e aspettare solo lei vuol dire perdere tutto quello che
arriva dopo: scritto su disco, e mai letto. È così che una notte intera di
sonno e le ore di battito di una giornata sono rimaste fuori dall'archivio
pur essendo già state consegnate. Adesso ogni lotto fa ripartire un timer
breve: quando passa senza che ne arrivino altri, si legge quello che c'è.

E «Cerca dati» comincia **rileggendo i lotti già scaricati**. I lotti grezzi
restano tutti in `~/.local/share/Vita/banda/`, rileggerli non costa niente e
non crea doppioni: è la rete che recupera quello che al primo colpo, per un
motivo o per l'altro, nell'archivio non era entrato. Lo stesso fa a mano
`python3 strumenti/importa_lotti.py --scrivi`.

## Lo stress che arriva a zero

Il braccialetto registra la misura appena la fai al polso, ma il **punteggio
a volte è zero**: la sessione c'è, il numero no. Uno zero nell'archivio
vorrebbe dire «sereno», che è il contrario di quello che è successo — quindi
non ci va. Il guaio è che così misuri lo stress e nell'app non succede
niente, e sembra un guasto.

Adesso il riquadro del braccialetto lo dice: **«4 misure di stress senza
punteggio»**, e il suggerimento sotto il mouse spiega cosa è successo.

**Non è un guasto, ed è una misura che a volte non riesce.** Il punteggio lo
calcola il braccialetto da solo, dalla variabilità del battito: se il
cinturino è lento, se ti muovi, se la pelle è fredda, la lettura non viene e
lui scrive la sessione con zero dentro invece di inventarsi un numero. Il 9
novembre ha dato zero cinque volte di fila e il 10 alle 02:42, nel sonno, ha
dato 12: il motore c'è, è la singola misura che può andare a vuoto. Rifarla
da fermo, con il cinturino aderente, è tutto quello che serve.

## I pezzi dei lotti grandi, ricuciti anche dopo

Un lotto grande arriva a pezzi da 484 byte, `3f <stato> <indice>`. Le prime
versioni di Dashboard li mettevano da parte uno per uno **senza rimetterli
insieme**: su disco c'erano ventuno pezzi che nessuno aveva mai letto, e
dentro una giornata intera di passi. Adesso `lotti_salvati` li ricuce
rileggendoli, con la stessa regola che usa il braccialetto mentre arrivano —
una sola, in `lotti.cuci`, non due gemelle che prima o poi divergono.

Così sono tornati i passi del 30 ottobre (4.226, erano zero) e sedici ore di
battito.

## «Rimetti l'ora»: l'unica cosa che gli scriviamo

Dashboard **legge** dal braccialetto e basta: chiede i lotti, li conferma,
chiede la batteria. Non tocca né le sue impostazioni né quello che ha in
pancia. L'unica eccezione è il bottone **«Rimetti l'ora»** nel riquadro del
braccialetto, e parte solo se glielo chiedi tu, con una conferma davanti:
manda ora, fuso e lingua — lo stesso messaggio che il telefono gli manda a
ogni collegamento, il passo 3 dell'adozione.

Serve perché da quando il compagno è questo PC quel messaggio non glielo
manda più nessuno. Il giorno del braccialetto se lo conta lui, col suo
orologio, quindi non è detto che rimetta a posto un contatore impuntato — ma
è l'unica leva che abbiamo, e non rischia niente.

## Quello che scrive il braccialetto, e quello che scrivi tu

Un giorno non è finito finché non è mezzanotte: i passi delle sei del
pomeriggio non sono quelli delle undici di sera, e il braccialetto consegna a
pezzi. Perciò un numero che viene da lui **si rifà** alla sincronizzazione
dopo, mentre quello che hai scritto tu **non si tocca mai**. Per distinguerli
l'archivio tiene nota di cosa ha scritto il braccialetto (tabella
`banda_scritti`): se nella casella c'è ancora quel valore è suo e lo può
aggiornare, se è cambiato l'hai cambiato tu e vince il tuo. I conti che
crescono — passi, chilometri, calorie, minuti di sonno — non tornano mai
indietro: fra il vecchio e il nuovo resta il più grande.

Lo stesso vale per `strumenti/importa_lotti.py`, che rilegge i lotti già
scaricati. Con `--sovrascrivi` passa sopra anche ai tuoi valori, ma solo se
glielo chiedi.

## Il battito, ora per ora

Il braccialetto non manda un numero al giorno: di **ogni ora** manda la media,
la più bassa e la più alta. Dashboard le tiene tutte, nella tabella `battiti`,
e il riquadro **Battito** (in Salute e nel cruscotto) le disegna come capsule:
ogni capsula va dal minimo al massimo di quell'ora, e il puntino chiaro dentro
è la media. Una barra che parte da zero direbbe una bugia — il cuore non fa
mai un numero solo.

La pastiglia del periodo sceglie cosa guardare: **oggi** e **ieri** mostrano le
ore di quella giornata, `7 · 14 · 30 · 90 giorni` una capsula per giornata. Se
oggi il braccialetto non ha ancora misurato niente — la mattina presto capita
— il riquadro mostra gli ultimi sette giorni e lo dice, invece di restare
vuoto. Il numero grande è sempre il **battito a riposo**: il più basso della
giornata, o la media dei più bassi nel periodo.

Nella riga di mezzo c'è **Indicatori**: battito a riposo, variabilità (HRV),
acqua e stress, con la media del periodo e quanto sei lontano dall'obiettivo.
Lo stesso riquadro sta sia in Salute sia nel cruscotto.

Le ore arrivano con la sincronizzazione del braccialetto. Se un lotto è già
stato scaricato ma non ancora letto, lo recupera

```bash
python3 strumenti/importa_lotti.py --scrivi
```

## Sfogliare le settimane

Nei riquadri che si sfogliano — **Passi**, **Sonno**, **Ore di studio** — il
comando del tempo non ha una riga sua: sta **sulla riga del titolo**, in
fondo, dove One UI mette le frecce dei grafici. Le frecce col nome in mezzo
(`‹ questa settimana ›`), la pastiglia del modo (`giorni ▾`) e «Oggi», che
compare solo quando ti sei allontanato dal presente — e solo dove c'è posto
anche per lui, se no la riga si riassetterebbe a metà di una scorsa. Quei
quaranta pixel tornano al disegno: il grafico dei passi è passato da 200 a
238 pixel, quello del sonno da 114 a 154, le ore di studio da 120 a 158.

Dove il riquadro è stretto il nome del periodo si accorcia coi puntini (per
intero nel suggerimento); dove è strettissimo il comando torna sotto al
titolo da solo, invece di farsi tagliare.

In modo **giorni** la finestra è la settimana del calendario, da lunedì a
domenica: sette candele larghe invece di quattordici sottili, e le frecce
scorrono **da una settimana all'altra**. Scorre anche la rotellina del mouse
quando il puntatore sta sul grafico.

**L'obiettivo non schiaccia più le candele.** La riga dell'obiettivo alzava la
scala: con 10.000 passi di traguardo e giornate da tremila, le candele
finivano tutte nel quinto basso. Adesso l'obiettivo alza la scala solo se è a
portata (meno del doppio del giorno migliore); altrimenti comanda il dato e
l'obiettivo resta una riga tratteggiata in cima, con scritto quant'è.

In `mockup/grafici-settimana.html` ci sono quattro forme alternative per le
candele, se un giorno si vorrà cambiare disegno.

## «Cosa ti muove l'umore»

Il riquadro in Emozioni non cerca correlazioni statistiche: fa una cosa sola,
e la fa in chiaro. Per ogni domanda («nei giorni in cui ti alleni…») divide i
giorni del periodo in **due mucchi** — quelli in cui la cosa è successa e
quelli in cui non è successa — e confronta la **media** di umore, energia o
stress fra i due. La differenza è quello che vedi scritto.

Tre regole tengono lontane le sciocchezze:

* i giorni **senza quel dato** restano fuori da tutti e due i mucchi: un
  giorno in cui il sonno non è registrato non è un giorno in cui hai dormito
  poco;
* servono **almeno tre giorni da una parte e tre dall'altra**, se no la riga
  non compare;
* la differenza dev'essere di almeno **0,25 punti su dieci**.

Quando non esce niente, il riquadro dice perché: se i mucchi sono troppo
piccoli lo scrive, e se le differenze sono tutte piccole dice qual è la più
grande. Il periodo adesso scende fino a **14 giorni**: più è corto, meno
giorni stanno dietro a ogni riga — e infatti ogni riga finisce con «5 giorni
su 14», così si vede su quanto poggia.

Sono confronti fra medie, non cause: dicono dove guardare.

## Il primo piano è oggi

In modo «giorni» la finestra è la settimana del calendario, da lunedì a
domenica: **l'ultima barra è la domenica**, che di mercoledì deve ancora
arrivare. I riquadri però accendevano proprio quella, e il numero grande
parlava di lei: di fatto raccontavano un giorno futuro e vuoto al posto di
oggi. Adesso la barra accesa e il numero grande sono quelli di **oggi**
quando oggi è nella finestra (Passi, Sonno, Ore di studio, Ore di lavoro); se
guardi una settimana passata è l'ultimo giorno di quella settimana, e la nota
dice sempre di che giorno si tratta — «oggi», «ieri», «25/10».

**Passi** adesso ha il suo numero grande, come il Sonno: quanti passi oggi e
a che punto sei dell'obiettivo.

**Battito** con «oggi» resta su **un giorno**. Se oggi non ci sono ancora
misure mostra l'ultimo giorno che ne ha, dicendolo («ieri · 8 ore misurate ·
da 58 a 132 bpm»): prima in quel caso passava di nascosto agli ultimi sette
giorni, e la pastiglia diceva «oggi» sopra al grafico di una settimana.

**Indicatori** scrive a destra **di quando è** il numero — «ieri», «5 giorni
fa» — invece di ripetere la lunghezza del periodo, che è già nella pastiglia
in cima: un battito di tre giorni fa non è il battito di adesso.

## Giorno per giorno, dove serve

Ogni riquadro che mostra un andamento lascia scendere fino al giorno singolo:
Passi, Sonno e Ore di studio col navigatore, Battito con le ore di oggi e di
ieri, Costanza con un quadretto per giorno, Emozioni e Finanza con «Oggi» fra
i periodi, Abitudini con la griglia dei giorni.

**Ore di lavoro** era l'unico rimasto a sole settimane: per sapere quanto
avevi lavorato *martedì* bisognava andare nella tabella sotto. Adesso ha lo
stesso navigatore degli altri — giorni, settimane, mesi.

E dentro una giornata sola, in **Andamento** delle Emozioni, non si fa più la
media delle voci: si disegnano una per una, all'ora in cui le hai scritte. La
media nascondeva proprio quello che interessa, cioè se la mattina è andata
diversa dalla sera.

## Modificare ed eliminare: due icone, non un gesto segreto

Nelle tabelle — *Prossimi impegni* nel cruscotto, *Ore registrate*, *Incassi*
e *Scadenze* in Carriera — correggere e buttare via c'erano già, ma solo col
doppio clic e col tasto destro: due gesti che non si vedono, e che infatti
non trovava nessuno. Adesso sulla riga del titolo ci sono **una matita e un
cestino**, spenti finché non scegli una riga — così si capisce anche *che
bisogna sceglierla*. Il doppio clic e il tasto destro restano dov'erano.

Il cestino della riga del titolo **chiede conferma**; quello del menu sul
tasto destro no, perché lì ci sei arrivato apposta — un'icona sempre in vista
invece si clicca anche per sbaglio.

In *Prossimi impegni* finiscono tre cose diverse — scadenze, esami e consegne
di progetti — e ognuna si corregge nella sua finestra: ogni riga si ricorda da
dove viene.

## Scegliere il periodo

Il tempo si cambia in un modo solo, uguale dappertutto.

**Su ogni grafico nel tempo c'è il navigatore**, sulla riga del titolo: le
frecce `‹ ›` con in mezzo l'intervallo che stai guardando, la pastiglia del
modo — `giorni`, `settimane`, `mesi` — e «Oggi», che compare solo quando ti
sei allontanato dal presente. La rotellina del mouse **sul grafico** scorre i
periodi senza cercare le frecce.

Ce l'hanno tutti e sono gli stessi gesti: Passi, Sonno, Stress e Composizione
in Salute; Ore di lavoro in Carriera; Ore di studio in Accademica; Andamento
del saldo ed Entrate e uscite in Finanza; Costanza nel tempo in Abitudini;
Andamento in Emozioni; Andamento emotivo e Finanza nel cruscotto. Prima metà
di loro aveva un menu a tendina con delle durate fisse — `30 giorni ▾`, `12
mesi ▾` — che diceva *quanto* ma non permetteva di andare **indietro**: per
guardare il mese scorso non c'era modo.

Quando una finestra non ha niente dentro il grafico **lo dice e dice perché**
— «Una voce sola, oggi: per disegnare una linea ce ne vogliono almeno due»,
«Niente scritto ultime 12 settimane» — invece di un «nessun dato» che lascia
a chiedersi se si è rotto qualcosa.

Resta la pastiglia a tendina dove il periodo non è un arco da sfogliare ma
una **durata**: i quadretti della costanza e del calendario (che si contano a
settimane piene, da lunedì), le ciambelle, le tabelle, i totali di Finanza.
Lì però la pastiglia è **stretta** e sta sulla riga del titolo accanto agli
altri comandi, non a destra di tutto: in Costanza è «8 sett ▾» prima dei tre
segni 👟🌙💪, e la stessa forma ce l'hanno la griglia delle Abitudini e il
calendario delle abitudini nel cruscotto.

## I quadretti riempiono la larghezza

Il calendario a quadretti teneva il lato massimo a 44 pixel e si metteva in
mezzo: in un riquadro largo restavano due bande vuote ai lati. Adesso sono
sette colonne che arrivano da un bordo all'altro, e il quadretto è largo
quanto la sua colonna.

L'altezza la prende uguale finché ce n'è. Quando le settimane sono tante e il
riquadro è basso si schiaccia — meglio pastiglie distese che quadretti
piccoli in mezzo al vuoto — ma non oltre una volta e mezza più largo che
alto: più in là smetterebbe di essere un quadretto, e allora si stringe un
po' lasciandosi aria intorno. La griglia continua a toccare i due bordi, che
è quello che si vedeva.

Le quattro strade provate prima di scegliere questa stanno in
`mockup/quadretti.html`, con due cursori per la larghezza del riquadro e per
quante settimane guardare.

**Via i «⋯».** Erano tre puntini che comparivano al passaggio del mouse a
destra del titolo e aprivano lo stesso menu del tasto destro: una seconda
strada per la stessa cosa, che rubava posto proprio dove adesso sta il
navigatore. Il menu resta sul tasto destro sull'intestazione, e i riquadri si
nascondono dal pulsante «Riquadri» in testa alla pagina.

Quando lo spazio è poco il riquadro rinuncia nell'ordine: prima la nota, poi
la pastiglia, per ultimo il titolo — e il navigatore, se non ci sta accanto al
titolo, si rimette sulla riga sotto invece di farsi tagliare. La nota o ci sta
intera, o ne resta abbastanza da capirla: un moncone come «6/28 centr…» non si
vede più.

## I colori non si scelgono

In **Impostazioni → Aspetto** si sceglie il tema (scuro o chiaro, `Ctrl+T`) e
la dimensione del testo. Il colore principale **non si sceglie più**: c'era
una fila di campioni, e serviva solo a rompere l'accordo con le tinte delle
aree, che sono fisse per un motivo — rosso Emozioni, blu Carriera, viola
Accademica, turchese Salute, verde Finanza, rosa Tess, ambra Abitudini. Il
verde di casa è l'unico accento, e il resto è costruito per andarci d'accordo.

Da questo discende una regola: **ogni pagina indossa il suo colore**. La
pagina di Tess era rosa nella barra e verde dentro — il bottone che manda, la
conversazione aperta, l'interruttore. Adesso è rosa anche la chat: il filo dei
messaggi di Tess (che ce l'ha sempre avuto), la bolla di quello che scrivi tu,
la conversazione aperta nell'elenco, il tondo dell'invio e i due interruttori.
L'interruttore del braccialetto, in Salute, è turchese.

## Il testo grande non taglia niente

La dimensione del testo si cambia in **Impostazioni → Aspetto** e arriva fino
a `molto grande` (1,3×). Perché a quella misura non resti niente tagliato, chi
ha un'altezza fissa se la ricalcola dal carattere invece di tenersi un numero:
l'intestazione dei riquadri (le code delle «g» di «Oggi», «Progetti»,
«Prossimi impegni»), le righe lineari di Accademica e Abitudini, i numeri
grandi. I titoli lunghi si accorciano coi puntini — e si accorcia prima la
riga di spiegazione, che conta meno del titolo.

Vale anche per le voci dell'elenco delle conversazioni di Tess: il foglio di
stile mette quattro pixel di stacco fra una voce e l'altra, e chi chiedeva
l'altezza non li contava — così la riga ne riceveva quattro in meno di quelli
che le servivano, e a `molto grande` i nomi restavano tagliati di sotto.

A controllare che sia vero c'è un programma, che apre tutte le pagine e tutte
le finestre a ognuna delle quattro dimensioni e cerca le scritte che non
ci stanno:

```bash
python3 strumenti/prova_viste.py
```

## Installazione

Su un PC nuovo bastano tre righe:

```bash
git clone git@github.com:Giosue-tanz/Dashboard.git Vita
cd Vita
./installa.sh
```

`installa.sh` crea la voce nel menu applicazioni e l'icona sul Desktop puntando
alla cartella in cui si trova il progetto. Requisiti: Python 3 e PySide6
(`sudo pacman -S pyside6` su Arch, `sudo apt install python3-pyside6` su Debian).

**Il repository contiene solo l'applicazione.** L'archivio — tutto quello che
scrivi — vive in `~/.local/share/Vita/vita.db` e non esce mai da questo
computer: appena installata, l'app parte vuota, con le sole emozioni,
categorie e abitudini di partenza da cui poi fai le tue. Per ritrovare i dati
su un PC nuovo si copia quel file a mano, oppure si usa il backup di
**Impostazioni → Dati e backup**.

> **Copiare `vita.db` e basta non basta.** L'archivio sta in modalità WAL:
> quello che è stato scritto di recente vive ancora nel file `vita.db-wal`
> accanto, e un `cp` del solo `.db` porta via un archivio **vecchio di ore** —
> un backup che sembra fatto e non contiene la giornata. Il backup
> dell'applicazione non lo fa più: usa l'API di SQLite, che si fa una copia
> coerente e completa anche con l'app aperta. Se copi a mano, prendi tutti e
> tre i file (`vita.db`, `vita.db-wal`, `vita.db-shm`) oppure chiudi l'app
> prima.

## Il salvataggio automatico

L'archivio sta su un solo computer, e un computer si rompe. In *Impostazioni →
Dati e backup* c'è **Salvataggio automatico**: si sceglie la chiavetta (o il
disco esterno), si accende l'interruttore e ogni sera all'ora scelta le copie
ci finiscono da sole.

* copia **Dashboard e Finance** insieme, con l'API di backup di SQLite — non un
  `cp`: la copia è coerente anche se l'app è aperta e ci sta scrivendo;
* **la chiavetta staccata non è un guasto**: lo scrive e riprova la sera dopo;
* se il computer era spento all'ora giusta, il giro **si recupera** appena si
  riaccende (`Persistent=true`);
* restano le **ultime quattordici copie** più la **prima di ogni mese**: un anno
  di storia in pochi megabyte.

Sotto c'è un timer di systemd dell'utente — niente root, niente demoni. Si
comanda anche da terminale:

```bash
python3 strumenti/salvataggio.py --cartella /run/media/giosue/VITA --installa
python3 strumenti/salvataggio.py --stato
```

## La password

In *Impostazioni → Sicurezza* si può mettere una password d'ingresso: senza,
la Dashboard non si apre nemmeno. Dopo qualche tentativo sbagliato aspetta,
così a tentare a caso non si arriva.

**È una porta, non una cassaforte**, e val la pena dirlo chiaro: l'archivio
resta un file SQLite leggibile da altri programmi. Serve contro l'occhiata di
chi passa, non contro chi si porta via il portatile — per quello si cifra il
disco. La password non viene salvata: se ne conserva solo l'impronta (PBKDF2,
240.000 giri, con sale). Se la dimentichi:

```bash
sqlite3 ~/.local/share/Vita/vita.db "DELETE FROM impostazioni WHERE chiave LIKE 'blocco_%';"
```

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
| **Salute** | impostata come un'app per la salute: anello dell'attività, composizione corporea (peso, massa grassa, muscolare e secca), costanza, passi, fasi del sonno, battito, HRV, **stress**, acqua, allenamenti, più la finestra **«Andamento»** per scorrere i dati passati | la finestra «Inserimento dati» in alto (anche per i giorni passati), gli allenamenti, oppure un'importazione da Samsung Health |
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

## Il braccialetto (Galaxy Fit2)

In *Salute* c'è il riquadro **Braccialetto**, con un interruttore come quello
di Tess: finché non lo accendi tu non si collega niente. Acceso, in un paio di
secondi il braccialetto saluta e comincia a rispondere.

| Cosa | Com'è andata |
|---|---|
| Stretta di mano SAP | **funziona** — il braccialetto manda 105 byte `68 14 … SAMSUNG_ACCESSARY`, si risponde col `0x15` |
| Domande e risposte | **funzionano** — trame con CRC-16/ARC, servizi numerati (10 salute, 11 impostazioni) |
| Batteria | **funziona** — servizio 11, messaggio `02`: il parametro 5 è la percentuale (provato a 1% e a 99%) |
| Ora del braccialetto | **funziona** — la manda nelle risposte, contata in secondi dal 1990 |
| Battito in diretta | **funziona** — servizio standard, mentre il braccialetto misura |
| Storico di passi e sonno | **non ancora**: vedi qui sotto |

**Perché lo storico non arriva.** La richiesta parte e il braccialetto
risponde — ma risponde «non ho niente», anche chiedendo tutto dall'inizio
(cursore a zero) o da un anno fa. Il Fit2 non è un archivio: è una staffetta.
Tiene i dati finché il compagno non se li prende, e il compagno è il telefono,
che lo svuota a ogni sincronizzazione.

Resta una strada da provare, e richiede solo pazienza: **spegnere il Bluetooth
del telefono** per qualche ora — una camminata, una notte — così il
braccialetto accumula, e poi chiedergli i dati da qui. Se arrivano, sono lotti
col loro formato (tipo 7 passi al minuto, 10 battito, 16 e 17 sonno) e si
mettono da parte grezzi in `~/.local/share/Vita/banda/` per imparare a
leggerli.

## L'adozione: il PC al posto del telefono

Il braccialetto consegna i suoi dati a **un compagno solo**. Finché il
compagno è il telefono, passi, sonno, battito e stress arrivano qui soltanto
con l'esportazione di Samsung Health. Per farne a meno davvero bisogna che il
compagno diventi questo computer — e l'adozione ha una sequenza precisa, che
Dashboard adesso sa fare (`vita/sap.py`, servizio 1):

| Passo | Cosa manda | Cosa fa |
|---|---|---|
| 1 | `01 04 02 00 00 00 05 00 0e` | chiede chi è; risponde con la versione del firmware |
| 2 | `02 01 00` | chiede come sta |
| 3 | `83 01 …` ora, fuso, lingua, formato | **scrive** sul braccialetto |
| 4 | `84 01 01` | l'accordo; **scrive** |

I primi due chiedono e basta. Gli ultimi due scrivono, e per questo
`Braccialetto.adotta()` non parte senza `conferma=True`: non deve poter
succedere per un clic distratto.

```bash
python3 strumenti/adotta_banda.py            # solo le domande, non scrive
python3 strumenti/adotta_banda.py --adotta   # l'adozione vera
```

Il messaggio del passo 3 è provato contro un vettore reale documentato
(14/11/2023 22:13:20Z, Mosca, lingua 57): i byte che Dashboard costruisce sono
identici a quelli che manda il telefono. Lo verifica
`python3 strumenti/prova_sap.py`.

**Il prezzo, detto chiaro.** L'adozione parte da un **reset del braccialetto**,
che cancella quello che ha in pancia e le sue impostazioni; dopo il reset va
riaccoppiato col PC dalle impostazioni Bluetooth. Se l'adozione dal PC non
riesce, per rimetterlo in piedi serve una volta Galaxy Wearable. Non è una
strada da imboccare di fretta.

**I dati arrivano davvero.** Dopo l'adozione il braccialetto consegna quello
che ha raccolto, in «lotti» che cominciano con `82 03 E0`. Dentro, un byte
dice di che si tratta — 7 passi (con metri e calorie, un record al minuto),
10 battito (col minimo e il massimo), 16 e 17 sonno, **19 stress**, 112
ossigeno — e poi i record, ognuno con la sua lunghezza e i campi etichettati.
I lotti grandi arrivano a pezzi da 490 byte (`3f`, con l'indice) e si
rimettono insieme. Li legge `vita/lotti.py`, che è solo byte dentro e numeri
fuori: si prova senza braccialetto con `python3 strumenti/prova_lotti.py`.

Ogni lotto grezzo viene messo da parte in `~/.local/share/Vita/banda/` prima
di essere letto, perché **il braccialetto i dati li consegna una volta sola**:
se qualcosa va storto nella scrittura, `python3 strumenti/importa_lotti.py
--scrivi` li rilegge da lì. Nell'archivio finiscono solo i campi che il
braccialetto ha misurato, e solo dove non c'è già un valore scritto a mano:
quello che metti tu vince sempre.

**I dati hanno già una casa.** Passi, sonno (con le fasi), battito e
**stress** hanno il loro posto nell'archivio, nella finestra d'inserimento,
negli indicatori di Salute e in «Andamento»: quando il braccialetto comincerà
a consegnarli, non c'è altro da costruire. Lo stress si legge come lo conta
lui, da 0 a 100, e negli indicatori la barra è rovesciata — piena vuol dire
sereno.

**Com'è fatto dentro.** `vita/sap.py` è il protocollo — byte dentro, byte
fuori, nessun Bluetooth: si prova senza braccialetto con
`python3 strumenti/prova_sap.py`. `vita/banda.py` è il collegamento vero via
BlueZ. Non c'è nessun thread, ed è una scelta: su Linux Qt possiede già il
ciclo di GLib, quindi un secondo ciclo dentro un filo nostro resta lì ad
aspettare di poterlo prendere. Le notifiche di BlueZ entrano dritte nel ciclo
di Qt e ogni chiamata che potrebbe far aspettare parte asincrona.

Il servizio di aggiornamento del firmware (Dialog, `0xfef5`) non viene toccato
mai: da lì si scrive il firmware del braccialetto, e non è un posto dove
sperimentare.

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

### Portare dentro Finance, una volta per tutte

**Impostazioni → Finanza → «Porta dentro tutto»** copia qui dentro l'intero
archivio di Finance: conti, categorie (col loro colore), movimenti, budget,
obiettivi e ricorrenti. Poi la sorgente passa da sola all'archivio interno —
che è quello che rende i movimenti modificabili — e Finance non serve più
aprirla. Da riga di comando:

```bash
python3 strumenti/importa_finance.py --scrivi
```

Si può rilanciare quante volte si vuole: quello che è già entrato non entra
due volte. Il confronto si fa su data, tipo, importo, categoria e
descrizione, **contando i doppioni**: due caffè identici lo stesso giorno
sono due movimenti, non uno, e cercare «ne esiste uno uguale?» ne avrebbe
lasciato fuori uno — col saldo che non tornava più con quello di Finance.

### Più categorie per un movimento

Un movimento può portarne quante ne vuoi. La **prima** — quella scelta in
alto nella finestra — è la padrona dell'importo: è lei che finisce nel budget
e nella ciambella delle uscite. Le altre si accendono come pastiglie e
servono a ritrovarlo.

È una scelta, non una mancanza: contare venti euro di pranzo sia in
«Ristoranti» sia in «Tempo libero» vorrebbe dire quaranta euro di uscite che
non hai mai speso. Nell'elenco dei movimenti la categoria principale porta un
`+2` accanto quando ce ne sono altre, e il suggerimento le dice tutte.

### I conti

Ogni movimento dice su che conto è passato — contante, carta, conto corrente.
Il saldo di un conto è quello di partenza più quello che ci è entrato meno
quello che ne è uscito, e **Saldo dei conti** in Finanza li mostra tutti.
Scrivendo un conto nuovo nella finestra del movimento, quello entra
nell'elenco; il saldo di partenza si mette in **Impostazioni → Finanza → I
conti**. I movimenti senza conto si contano a parte, sotto «Senza conto», se
no la somma dei conti non tornerebbe col saldo totale.

### Movimenti che tornano da soli

Affitto, abbonamenti, stipendio: in **Impostazioni → Finanza → Movimenti che
tornano da soli** si dice cosa, quanto, ogni quanto e da quando. Si scrivono
all'apertura di Dashboard, uno per ogni scadenza passata — se hai tenuto
l'app chiusa due mesi, all'apertura arrivano le due rate che mancano, ognuna
col suo giorno. Quelli già scritti non tornano: `ultima_generazione` si
ricorda dov'era arrivata, quindi cancellarne uno a mano lo cancella davvero.

### Le icone delle categorie

Ogni categoria porta un'icona, e la propone il suo nome: «Benzina» arriva con
la pompa, «Stipendio» con la ventiquattrore, «Netflix» con la televisione —
e non con il grafico degli ETF, perché il confronto parte da un confine di
parola. Sono emoji: nessun file da distribuire, nessuna dipendenza, e le
colora il sistema. Doppio clic su una categoria in **Impostazioni → Finanza →
Categorie dei movimenti** apre il catalogo, 174 icone divise per gruppi e
cercabili per nome. L'icona scelta a mano non se la riprende più nessun
suggerimento.

Il catalogo (`vita/icone_categorie.py`) è **lo stesso dell'app Finance**,
copiato parola per parola di proposito: le due applicazioni devono proporre
la stessa icona per lo stesso nome, se no un movimento portato dentro si
vedrebbe diverso da uno scritto qui. Sono due repository separati e non c'è
un pacchetto in comune — se il catalogo di Finance cambia, questo va
ricopiato, e una prova lo controlla.

Le icone compaiono nell'elenco dei movimenti, nella ciambella delle uscite,
nella finestra del movimento e nell'elenco delle categorie.

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
della barra laterale. Quando i riquadri di una pagina cambiano, la disposizione
vecchia non serve più: all'avvio quelle righe se ne vanno da sole
dall'archivio, insieme ai periodi di riquadri spariti e ai valori non più
previsti. **Impostazioni → Dati e backup → Archivio** dice quante impostazioni
sono memorizzate e quante ne ha tolte l'ultima pulizia; si toccano solo quelle
che l'app scrive da sé (`layout_…`, `periodo_…`), mai le tue scelte.

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
