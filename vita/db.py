"""Livello dati: un solo file SQLite in locale, nessuna connessione di rete."""
from __future__ import annotations

import os
import shutil
import sqlite3
from datetime import date, datetime

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# I dati vivono FUORI dalla cartella del codice: aggiornare l'applicazione
# (git pull, nuova copia, reinstallazione) non li tocca mai.
DATA_DIR = os.path.join(
    os.environ.get("XDG_DATA_HOME", os.path.join(os.path.expanduser("~"), ".local", "share")),
    "Vita")
DB_PATH = os.path.join(DATA_DIR, "vita.db")
BACKUP_DIR = os.path.join(DATA_DIR, "backup")

SCHEMA = """
CREATE TABLE IF NOT EXISTS impostazioni (
    chiave TEXT PRIMARY KEY,
    valore TEXT NOT NULL
);

-- ------------------------------------------------------------- emozioni --
CREATE TABLE IF NOT EXISTS voci (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT NOT NULL,                 -- YYYY-MM-DD
    ora TEXT NOT NULL DEFAULT '',       -- HH:MM
    umore REAL NOT NULL DEFAULT 5,      -- 1..10
    energia REAL NOT NULL DEFAULT 5,
    stress REAL NOT NULL DEFAULT 5,
    lucidita REAL NOT NULL DEFAULT 5,
    emozioni TEXT NOT NULL DEFAULT '',  -- nomi separati da virgola
    testo TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS emozioni (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL UNIQUE,
    colore TEXT NOT NULL DEFAULT '#6c8cff',
    tipo TEXT NOT NULL DEFAULT 'neutra'  -- positiva | negativa | neutra
);

-- --------------------------------------------------------------- salute --
CREATE TABLE IF NOT EXISTS salute (
    data TEXT PRIMARY KEY,
    passi INTEGER NOT NULL DEFAULT 0,
    km REAL NOT NULL DEFAULT 0,
    kcal INTEGER NOT NULL DEFAULT 0,
    sonno INTEGER NOT NULL DEFAULT 0,          -- minuti totali
    sonno_profondo INTEGER NOT NULL DEFAULT 0,
    sonno_rem INTEGER NOT NULL DEFAULT 0,
    sonno_sveglio INTEGER NOT NULL DEFAULT 0,
    battito INTEGER NOT NULL DEFAULT 0,        -- a riposo
    hrv INTEGER NOT NULL DEFAULT 0,
    peso REAL NOT NULL DEFAULT 0,
    grasso REAL NOT NULL DEFAULT 0,            -- massa grassa in %
    muscolo REAL NOT NULL DEFAULT 0,           -- massa muscolare in %
    acqua REAL NOT NULL DEFAULT 0,             -- litri
    note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS allenamenti (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT NOT NULL,
    tipo TEXT NOT NULL DEFAULT 'Palestra',
    minuti INTEGER NOT NULL DEFAULT 0,
    km REAL NOT NULL DEFAULT 0,
    kcal INTEGER NOT NULL DEFAULT 0,
    intensita TEXT NOT NULL DEFAULT 'media',   -- leggera | media | intensa
    note TEXT NOT NULL DEFAULT ''
);

-- ------------------------------------------------------------- carriera --
CREATE TABLE IF NOT EXISTS progetti (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    tipo TEXT NOT NULL DEFAULT 'personale',    -- cliente | personale | studio | passivo
    stato TEXT NOT NULL DEFAULT 'idea',        -- idea | corso | pausa | fatto
    cliente TEXT NOT NULL DEFAULT '',
    compenso REAL NOT NULL DEFAULT 0,
    inizio TEXT NOT NULL DEFAULT '',
    scadenza TEXT NOT NULL DEFAULT '',
    avanzamento INTEGER NOT NULL DEFAULT 0,    -- 0..100
    colore TEXT NOT NULL DEFAULT '#6c8cff',
    note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS lavoro (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT NOT NULL,
    progetto_id INTEGER,
    minuti INTEGER NOT NULL DEFAULT 0,
    note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS incassi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT NOT NULL,
    progetto_id INTEGER,
    importo REAL NOT NULL DEFAULT 0,
    descrizione TEXT NOT NULL DEFAULT ''
);

-- ----------------------------------------------------------- accademica --
CREATE TABLE IF NOT EXISTS esami (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    cfu INTEGER NOT NULL DEFAULT 6,
    voto INTEGER NOT NULL DEFAULT 0,           -- 0 = non ancora sostenuto
    lode INTEGER NOT NULL DEFAULT 0,
    stato TEXT NOT NULL DEFAULT 'previsto',    -- previsto | corso | superato
    anno INTEGER NOT NULL DEFAULT 1,
    data_esame TEXT NOT NULL DEFAULT '',
    avanzamento INTEGER NOT NULL DEFAULT 0,
    note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS studio (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT NOT NULL,
    materia TEXT NOT NULL DEFAULT '',
    minuti INTEGER NOT NULL DEFAULT 0,
    argomento TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS percorsi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    categoria TEXT NOT NULL DEFAULT 'università',
    avanzamento INTEGER NOT NULL DEFAULT 0,
    risorsa TEXT NOT NULL DEFAULT '',
    stato TEXT NOT NULL DEFAULT 'attivo',      -- attivo | attesa | finito
    colore TEXT NOT NULL DEFAULT '#35c4d7',
    note TEXT NOT NULL DEFAULT ''
);

-- -------------------------------------------------- scadenze e abitudini --
CREATE TABLE IF NOT EXISTS scadenze (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT NOT NULL,
    titolo TEXT NOT NULL,
    area TEXT NOT NULL DEFAULT 'accademica',
    fatta INTEGER NOT NULL DEFAULT 0,
    note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS abitudini (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    colore TEXT NOT NULL DEFAULT '#2ec27e',
    obiettivo INTEGER NOT NULL DEFAULT 7,      -- volte a settimana
    area TEXT NOT NULL DEFAULT 'salute',
    attiva INTEGER NOT NULL DEFAULT 1,
    ordine INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS registro (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT NOT NULL,
    abitudine_id INTEGER NOT NULL,
    UNIQUE(data, abitudine_id)
);

-- --------------------------------------------- finanza (archivio proprio) --
CREATE TABLE IF NOT EXISTS movimenti (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT NOT NULL,
    tipo TEXT NOT NULL,                        -- entrata | uscita
    importo REAL NOT NULL DEFAULT 0,
    categoria TEXT NOT NULL DEFAULT 'Altro',
    descrizione TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS categorie (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    tipo TEXT NOT NULL DEFAULT 'uscita',       -- entrata | uscita
    ordine INTEGER NOT NULL DEFAULT 0,
    UNIQUE(nome, tipo)
);
CREATE TABLE IF NOT EXISTS budget (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    categoria TEXT NOT NULL UNIQUE,
    mensile REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS obiettivi (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    obiettivo REAL NOT NULL DEFAULT 0,
    accantonato REAL NOT NULL DEFAULT 0,
    scadenza TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_voci_data ON voci(data);
CREATE INDEX IF NOT EXISTS idx_lavoro_data ON lavoro(data);
-- ----------------------------------------------------------------- Tess --
-- Le chat con l'AI locale restano qui, nell'archivio della Dashboard: Tess
-- non le conserva (il motore non ha memoria fra una domanda e l'altra).
CREATE TABLE IF NOT EXISTS tess_chat (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversazione TEXT NOT NULL,        -- quando è cominciata, in ISO
    ruolo TEXT NOT NULL,                -- user | assistant
    testo TEXT NOT NULL DEFAULT '',
    quando TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_tess_chat ON tess_chat(conversazione, id);

-- Il nome che dai a una conversazione. Sta in una tabella sua perché è della
-- chat intera, non di un suo messaggio: senza riga qui vale la prima domanda.
CREATE TABLE IF NOT EXISTS tess_titoli (
    conversazione TEXT PRIMARY KEY,
    titolo TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_studio_data ON studio(data);
CREATE INDEX IF NOT EXISTS idx_mov_data ON movimenti(data);
"""

# Colonne nate dopo la prima versione: si aggiungono all'avvio se mancano.
COLONNE_AGGIUNTE = (
    ("salute", "grasso", "REAL NOT NULL DEFAULT 0"),
    ("salute", "muscolo", "REAL NOT NULL DEFAULT 0"),
    # a che ora sei andato a letto e a che ora ti sei alzato, «HH:MM»: il
    # quadrante del sonno le scrive, il totale in minuti resta in `sonno`
    ("salute", "a_letto", "TEXT NOT NULL DEFAULT ''"),
    ("salute", "sveglia", "TEXT NOT NULL DEFAULT ''"),
    # un incasso sa in che categoria di entrata finisce e a quale movimento
    # corrisponde nell'archivio interno: è lo stesso denaro, scritto una volta
    ("incassi", "categoria", "TEXT NOT NULL DEFAULT 'Lavoro'"),
    ("incassi", "movimento_id", "INTEGER"),
)

# Categorie di partenza, divise per tipo: si aggiungono dalle impostazioni o
# scrivendone una nuova nella finestra del movimento.
CATEGORIE_DEFAULT = {
    "uscita": ["Spesa alimentare", "Trasporti", "Casa", "Bollette", "Abbonamenti",
               "Tempo libero", "Ristoranti", "Istruzione", "Salute", "Viaggi",
               "Regali", "Altro"],
    "entrata": ["Lavoro", "Stipendio", "Ripetizioni", "Borsa di studio",
                "Rimborsi", "Regali", "Interessi", "Altro"],
}


EMOZIONI_DEFAULT = [
    ("sereno", "#2ec27e", "positiva"), ("soddisfatto", "#4cc9a4", "positiva"),
    ("motivato", "#6ddfa0", "positiva"), ("concentrato", "#35c4d7", "positiva"),
    ("grato", "#86d39b", "positiva"), ("entusiasta", "#f2c14e", "positiva"),
    ("calmo", "#56cfe1", "neutra"), ("riflessivo", "#7f8cff", "neutra"),
    ("annoiato", "#9aa0a6", "neutra"), ("stanco", "#f7913a", "negativa"),
    ("ansioso", "#ef5f5c", "negativa"), ("teso", "#f06fb4", "negativa"),
    ("irritato", "#d64540", "negativa"), ("giù", "#8d99ae", "negativa"),
    ("solo", "#b388eb", "negativa"), ("insicuro", "#c77dff", "negativa"),
]

ABITUDINI_DEFAULT = [
    ("Scrivere il diario", "#b07cff", 7, "emozioni"),
    ("Studiare", "#35c4d7", 6, "accademica"),
    ("Allenarsi", "#2ec27e", 4, "salute"),
    ("Lavorare a un progetto", "#6c8cff", 5, "carriera"),
    ("Dormire 7 ore", "#56cfe1", 7, "salute"),
]

TIPI_ALLENAMENTO = ["Palestra", "Corsa", "Camminata", "Bicicletta", "Nuoto",
                    "Calcio", "Yoga", "Altro"]

STATI_PROGETTO = {"idea": "Idee", "corso": "In corso", "pausa": "In pausa", "fatto": "Fatti"}
TIPI_PROGETTO = ["cliente", "personale", "studio", "passivo"]
STATI_ESAME = {"previsto": "Previsto", "corso": "In corso", "superato": "Superato"}
AREE = {"emozioni": "Emozioni", "carriera": "Carriera", "accademica": "Accademica",
        "salute": "Salute", "finanza": "Finanza"}


class Database:
    """Tutte le interrogazioni dell'applicazione, divise per area."""

    def __init__(self, percorso: str = DB_PATH):
        os.makedirs(os.path.dirname(percorso), exist_ok=True)
        self.percorso = percorso
        self.conn = sqlite3.connect(percorso)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self._adegua_colonne()
        self._semina()
        self.conn.commit()

    # ------------------------------------------------------------------ base
    def query(self, sql: str, par: tuple = ()) -> list[sqlite3.Row]:
        return self.conn.execute(sql, par).fetchall()

    def uno(self, sql: str, par: tuple = ()):
        r = self.conn.execute(sql, par).fetchone()
        return r

    def valore(self, sql: str, par: tuple = (), default=0):
        r = self.conn.execute(sql, par).fetchone()
        if r is None or r[0] is None:
            return default
        return r[0]

    def esegui(self, sql: str, par: tuple = ()) -> int:
        cur = self.conn.execute(sql, par)
        self.conn.commit()
        return cur.lastrowid

    def elimina(self, tabella: str, id_: int) -> None:
        if tabella not in {"voci", "emozioni", "allenamenti", "progetti", "lavoro",
                           "incassi", "esami", "studio", "percorsi", "scadenze",
                           "abitudini", "movimenti", "budget", "obiettivi", "salute",
                           "categorie"}:
            raise ValueError("tabella non valida")
        if tabella == "incassi":
            # via l'incasso, via anche l'entrata gemella
            gemello = self.valore("SELECT movimento_id FROM incassi WHERE id=?",
                                  (id_,), default=None)
            if gemello:
                self.esegui("DELETE FROM movimenti WHERE id=?", (gemello,))
        elif tabella == "movimenti":
            # cancellato il movimento, l'incasso resta ma senza gemello
            self.esegui("UPDATE incassi SET movimento_id=NULL WHERE movimento_id=?",
                        (id_,))
        chiave = "data" if tabella == "salute" else "id"
        self.esegui(f"DELETE FROM {tabella} WHERE {chiave}=?", (id_,))

    def _adegua_colonne(self) -> None:
        """Aggiunge le colonne nate dopo la prima versione, senza toccare i dati.

        `CREATE TABLE IF NOT EXISTS` non modifica una tabella che esiste già:
        chi usa l'app da prima avrebbe un archivio senza le colonne nuove.
        """
        for tabella, colonna, tipo in COLONNE_AGGIUNTE:
            presenti = {r["name"] for r in
                        self.query(f"PRAGMA table_info({tabella})")}
            if colonna not in presenti:
                self.conn.execute(
                    f"ALTER TABLE {tabella} ADD COLUMN {colonna} {tipo}")

    def _semina(self) -> None:
        if self.valore("SELECT COUNT(*) FROM emozioni") == 0:
            self.conn.executemany(
                "INSERT INTO emozioni(nome, colore, tipo) VALUES (?,?,?)",
                EMOZIONI_DEFAULT)
        if self.valore("SELECT COUNT(*) FROM categorie") == 0:
            self.conn.executemany(
                "INSERT OR IGNORE INTO categorie(nome, tipo, ordine) VALUES (?,?,?)",
                [(nome, tipo, i) for tipo, nomi in CATEGORIE_DEFAULT.items()
                 for i, nome in enumerate(nomi)])
        if self.valore("SELECT COUNT(*) FROM abitudini") == 0:
            self.conn.executemany(
                "INSERT INTO abitudini(nome, colore, obiettivo, area, ordine) "
                "VALUES (?,?,?,?,?)",
                [(n, c, o, a, i) for i, (n, c, o, a) in enumerate(ABITUDINI_DEFAULT)])

    # ----------------------------------------------------------- impostazioni
    def leggi(self, chiave: str, default: str = "") -> str:
        r = self.uno("SELECT valore FROM impostazioni WHERE chiave=?", (chiave,))
        return r["valore"] if r else default

    def leggi_num(self, chiave: str, default: float) -> float:
        try:
            return float(self.leggi(chiave, str(default)).replace(",", "."))
        except ValueError:
            return default

    def imposta(self, chiave: str, valore) -> None:
        self.esegui(
            "INSERT INTO impostazioni(chiave,valore) VALUES(?,?) "
            "ON CONFLICT(chiave) DO UPDATE SET valore=excluded.valore",
            (chiave, str(valore)))

    # --------------------------------------------------------------- emozioni
    def voci(self, dal: str = "", al: str = "", testo: str = "",
             limite: int = 0) -> list[sqlite3.Row]:
        sql = "SELECT * FROM voci WHERE 1=1"
        par: list = []
        if dal:
            sql += " AND data >= ?"; par.append(dal)
        if al:
            sql += " AND data <= ?"; par.append(al)
        if testo:
            sql += " AND (testo LIKE ? OR emozioni LIKE ?)"
            par += [f"%{testo}%", f"%{testo}%"]
        sql += " ORDER BY data DESC, ora DESC, id DESC"
        if limite:
            sql += f" LIMIT {int(limite)}"
        return self.query(sql, tuple(par))

    def salva_voce(self, d: dict) -> int:
        campi = ("data", "ora", "umore", "energia", "stress", "lucidita",
                 "emozioni", "testo")
        if d.get("id"):
            self.esegui(
                "UPDATE voci SET data=?, ora=?, umore=?, energia=?, stress=?, "
                "lucidita=?, emozioni=?, testo=? WHERE id=?",
                tuple(d[c] for c in campi) + (d["id"],))
            return int(d["id"])
        return self.esegui(
            "INSERT INTO voci(data,ora,umore,energia,stress,lucidita,emozioni,testo) "
            "VALUES(?,?,?,?,?,?,?,?)", tuple(d[c] for c in campi))

    def medie_giorno(self, dal: str, al: str) -> list[sqlite3.Row]:
        """Una riga per giorno con le medie delle voci scritte quel giorno."""
        return self.query(
            "SELECT data, AVG(umore) umore, AVG(energia) energia, AVG(stress) stress, "
            "AVG(lucidita) lucidita, COUNT(*) n FROM voci "
            "WHERE data BETWEEN ? AND ? GROUP BY data ORDER BY data", (dal, al))

    def medie_periodo(self, dal: str, al: str) -> dict:
        r = self.uno(
            "SELECT AVG(umore) umore, AVG(energia) energia, AVG(stress) stress, "
            "AVG(lucidita) lucidita, COUNT(*) n FROM voci WHERE data BETWEEN ? AND ?",
            (dal, al))
        return {k: (r[k] or 0.0) for k in ("umore", "energia", "stress", "lucidita")} | \
               {"n": r["n"] or 0}

    def frequenza_emozioni(self, dal: str, al: str) -> list[tuple[str, int]]:
        conteggio: dict[str, int] = {}
        for r in self.query("SELECT emozioni FROM voci WHERE data BETWEEN ? AND ?",
                            (dal, al)):
            for nome in (x.strip() for x in r["emozioni"].split(",")):
                if nome:
                    conteggio[nome] = conteggio.get(nome, 0) + 1
        return sorted(conteggio.items(), key=lambda kv: -kv[1])

    def catalogo_emozioni(self) -> list[sqlite3.Row]:
        return self.query("SELECT * FROM emozioni ORDER BY "
                          "CASE tipo WHEN 'positiva' THEN 0 WHEN 'neutra' THEN 1 "
                          "ELSE 2 END, nome")

    def colori_emozioni(self) -> dict[str, str]:
        return {r["nome"]: r["colore"] for r in self.query("SELECT nome,colore FROM emozioni")}

    # ----------------------------------------------------------------- salute
    def salute_giorno(self, data: str) -> sqlite3.Row | None:
        return self.uno("SELECT * FROM salute WHERE data=?", (data,))

    def salva_salute(self, d: dict) -> None:
        campi = ("passi", "km", "kcal", "sonno", "sonno_profondo", "sonno_rem",
                 "sonno_sveglio", "battito", "hrv", "peso", "grasso", "muscolo",
                 "acqua", "note", "a_letto", "sveglia")
        testi = {"note", "a_letto", "sveglia"}
        self.esegui(
            "INSERT INTO salute(data," + ",".join(campi) + ") "
            "VALUES(?" + ",?" * len(campi) + ") "
            "ON CONFLICT(data) DO UPDATE SET " +
            ", ".join(f"{c}=excluded.{c}" for c in campi),
            (d["data"],) + tuple(d.get(c) or ("" if c in testi else 0)
                                  for c in campi))

    def serie_salute(self, campo: str, dal: str, al: str) -> list[tuple[str, float]]:
        if campo not in {"passi", "km", "kcal", "sonno", "battito", "hrv", "peso",
                         "grasso", "muscolo", "acqua"}:
            raise ValueError("campo non valido")
        righe = self.query(
            f"SELECT data, {campo} v FROM salute WHERE data BETWEEN ? AND ? "
            f"AND {campo} > 0 ORDER BY data", (dal, al))
        return [(r["data"], float(r["v"])) for r in righe]

    def giorni_salute(self, dal: str, al: str) -> dict[str, sqlite3.Row]:
        return {r["data"]: r for r in
                self.query("SELECT * FROM salute WHERE data BETWEEN ? AND ? ORDER BY data",
                           (dal, al))}

    def allenamenti(self, dal: str = "", al: str = "", limite: int = 0) -> list[sqlite3.Row]:
        sql = "SELECT * FROM allenamenti WHERE 1=1"
        par: list = []
        if dal:
            sql += " AND data >= ?"; par.append(dal)
        if al:
            sql += " AND data <= ?"; par.append(al)
        sql += " ORDER BY data DESC, id DESC"
        if limite:
            sql += f" LIMIT {int(limite)}"
        return self.query(sql, tuple(par))

    def salva_allenamento(self, d: dict) -> int:
        campi = ("data", "tipo", "minuti", "km", "kcal", "intensita", "note")
        if d.get("id"):
            self.esegui("UPDATE allenamenti SET " +
                        ", ".join(f"{c}=?" for c in campi) + " WHERE id=?",
                        tuple(d[c] for c in campi) + (d["id"],))
            return int(d["id"])
        return self.esegui(
            "INSERT INTO allenamenti(" + ",".join(campi) + ") VALUES(?,?,?,?,?,?,?)",
            tuple(d[c] for c in campi))

    # --------------------------------------------------------------- carriera
    def progetti(self, stato: str = "") -> list[sqlite3.Row]:
        sql = "SELECT * FROM progetti"
        par: tuple = ()
        if stato:
            sql += " WHERE stato=?"; par = (stato,)
        sql += (" ORDER BY CASE stato WHEN 'corso' THEN 0 WHEN 'idea' THEN 1 "
                "WHEN 'pausa' THEN 2 ELSE 3 END, scadenza='', scadenza, nome")
        return self.query(sql, par)

    def salva_progetto(self, d: dict) -> int:
        campi = ("nome", "tipo", "stato", "cliente", "compenso", "inizio",
                 "scadenza", "avanzamento", "colore", "note")
        if d.get("id"):
            self.esegui("UPDATE progetti SET " + ", ".join(f"{c}=?" for c in campi) +
                        " WHERE id=?", tuple(d[c] for c in campi) + (d["id"],))
            return int(d["id"])
        return self.esegui(
            "INSERT INTO progetti(" + ",".join(campi) + ") VALUES(" +
            ",".join("?" * len(campi)) + ")", tuple(d[c] for c in campi))

    def minuti_lavoro(self, dal: str, al: str, progetto_id: int | None = None) -> int:
        sql = "SELECT COALESCE(SUM(minuti),0) FROM lavoro WHERE data BETWEEN ? AND ?"
        par: list = [dal, al]
        if progetto_id:
            sql += " AND progetto_id=?"; par.append(progetto_id)
        return int(self.valore(sql, tuple(par)))

    def lavoro(self, dal: str = "", al: str = "", limite: int = 0) -> list[sqlite3.Row]:
        sql = ("SELECT l.*, p.nome progetto, p.colore FROM lavoro l "
               "LEFT JOIN progetti p ON p.id = l.progetto_id WHERE 1=1")
        par: list = []
        if dal:
            sql += " AND l.data >= ?"; par.append(dal)
        if al:
            sql += " AND l.data <= ?"; par.append(al)
        sql += " ORDER BY l.data DESC, l.id DESC"
        if limite:
            sql += f" LIMIT {int(limite)}"
        return self.query(sql, tuple(par))

    def incassi(self, dal: str = "", al: str = "", limite: int = 0) -> list[sqlite3.Row]:
        sql = ("SELECT i.*, p.nome progetto, p.colore FROM incassi i "
               "LEFT JOIN progetti p ON p.id = i.progetto_id WHERE 1=1")
        par: list = []
        if dal:
            sql += " AND i.data >= ?"; par.append(dal)
        if al:
            sql += " AND i.data <= ?"; par.append(al)
        sql += " ORDER BY i.data DESC, i.id DESC"
        if limite:
            sql += f" LIMIT {int(limite)}"
        return self.query(sql, tuple(par))

    def salva_incasso(self, d: dict) -> int:
        """Registra o aggiorna un incasso e la sua entrata in finanza.

        I soldi sono gli stessi: l'incasso di Carriera e l'entrata di Finanza
        restano agganciati con `movimento_id`, così non si scrivono due volte
        e una correzione vale per entrambi. Togliendo la spunta l'entrata
        sparisce e l'incasso resta.
        """
        campi = ("data", "progetto_id", "importo", "descrizione", "categoria")
        valori = (d.get("data", ""), d.get("progetto_id"),
                  float(d.get("importo", 0)), d.get("descrizione", ""),
                  d.get("categoria") or "Lavoro")
        id_ = d.get("id")
        if id_:
            self.esegui("UPDATE incassi SET " + ", ".join(f"{c}=?" for c in campi) +
                        " WHERE id=?", valori + (id_,))
        else:
            id_ = self.esegui(
                "INSERT INTO incassi(" + ",".join(campi) + ") VALUES(?,?,?,?,?)",
                valori)
        self.collega_incasso(int(id_), bool(d.get("in_finanza", True)))
        return int(id_)

    def collega_incasso(self, id_: int, acceso: bool = True) -> None:
        """Crea, aggiorna o toglie l'entrata gemella di un incasso."""
        r = self.uno("SELECT * FROM incassi WHERE id=?", (id_,))
        if r is None:
            return
        gemello = r["movimento_id"]
        if gemello and not self.uno("SELECT id FROM movimenti WHERE id=?", (gemello,)):
            gemello = None          # l'entrata è stata cancellata a mano
        if not acceso:
            if gemello:
                self.esegui("DELETE FROM movimenti WHERE id=?", (gemello,))
            self.esegui("UPDATE incassi SET movimento_id=NULL WHERE id=?", (id_,))
            return
        progetto = self.valore("SELECT nome FROM progetti WHERE id=?",
                               (r["progetto_id"],), default="")
        descrizione = r["descrizione"] or (f"Incasso · {progetto}" if progetto
                                           else "Incasso")
        nuovo = self.salva_movimento({
            "id": gemello, "data": r["data"], "tipo": "entrata",
            "importo": float(r["importo"]), "categoria": r["categoria"] or "Lavoro",
            "descrizione": descrizione})
        if nuovo != gemello:
            self.esegui("UPDATE incassi SET movimento_id=? WHERE id=?", (nuovo, id_))

    def totale_incassi(self, dal: str, al: str) -> float:
        return float(self.valore(
            "SELECT COALESCE(SUM(importo),0) FROM incassi WHERE data BETWEEN ? AND ?",
            (dal, al)))

    def incassi_per_progetto(self, dal: str, al: str) -> list[tuple[str, float, str]]:
        righe = self.query(
            "SELECT COALESCE(p.nome,'Senza progetto') nome, SUM(i.importo) tot, "
            "COALESCE(p.colore,'#9aa0a6') colore FROM incassi i "
            "LEFT JOIN progetti p ON p.id=i.progetto_id "
            "WHERE i.data BETWEEN ? AND ? GROUP BY nome ORDER BY tot DESC", (dal, al))
        return [(r["nome"], float(r["tot"]), r["colore"]) for r in righe]

    # ------------------------------------------------------------- accademica
    def esami(self) -> list[sqlite3.Row]:
        return self.query(
            "SELECT * FROM esami ORDER BY anno, CASE stato WHEN 'superato' THEN 0 "
            "WHEN 'corso' THEN 1 ELSE 2 END, data_esame='', data_esame, nome")

    def salva_esame(self, d: dict) -> int:
        campi = ("nome", "cfu", "voto", "lode", "stato", "anno", "data_esame",
                 "avanzamento", "note")
        if d.get("id"):
            self.esegui("UPDATE esami SET " + ", ".join(f"{c}=?" for c in campi) +
                        " WHERE id=?", tuple(d[c] for c in campi) + (d["id"],))
            return int(d["id"])
        return self.esegui(
            "INSERT INTO esami(" + ",".join(campi) + ") VALUES(" +
            ",".join("?" * len(campi)) + ")", tuple(d[c] for c in campi))

    def riepilogo_libretto(self) -> dict:
        r = self.uno(
            "SELECT COUNT(*) n, COALESCE(SUM(cfu),0) cfu, "
            "COALESCE(SUM(voto*cfu),0) pesata, COALESCE(SUM(voto),0) somma "
            "FROM esami WHERE stato='superato' AND voto > 0")
        n = r["n"] or 0
        cfu = int(r["cfu"] or 0)
        media = (r["somma"] / n) if n else 0.0
        ponderata = (r["pesata"] / cfu) if cfu else 0.0
        return {"n": n, "cfu": cfu, "media": media, "ponderata": ponderata,
                "base": ponderata * 110 / 30 if ponderata else 0.0}

    # -------------------------------------------------------------- Tess
    def salva_messaggio_tess(self, conversazione: str, ruolo: str, testo: str) -> None:
        self.esegui(
            "INSERT INTO tess_chat(conversazione, ruolo, testo, quando) "
            "VALUES(?,?,?,?)",
            (conversazione, ruolo, testo, datetime.now().isoformat(timespec="seconds")))

    def conversazione_tess(self, conversazione: str) -> list[sqlite3.Row]:
        return self.query(
            "SELECT * FROM tess_chat WHERE conversazione=? ORDER BY id",
            (conversazione,))

    def conversazioni_tess(self, limite: int = 30) -> list[sqlite3.Row]:
        """Le conversazioni, dalla più recente.

        `titolo` è il nome che le hai dato, `apertura` la prima domanda: chi
        legge usa il primo e ripiega sul secondo.
        """
        return self.query(
            "SELECT c.conversazione, COUNT(*) messaggi, MAX(c.quando) ultimo, "
            "       MIN(CASE WHEN c.ruolo='user' THEN c.testo END) apertura, "
            "       COALESCE(t.titolo, '') titolo "
            "FROM tess_chat c "
            "LEFT JOIN tess_titoli t ON t.conversazione = c.conversazione "
            "GROUP BY c.conversazione "
            "ORDER BY c.conversazione DESC LIMIT ?", (limite,))

    def rinomina_conversazione_tess(self, conversazione: str, titolo: str) -> None:
        """Dà un nome a una chat; con il titolo vuoto torna la prima domanda."""
        titolo = (titolo or "").strip()[:80]
        if titolo:
            self.esegui("INSERT INTO tess_titoli(conversazione, titolo) VALUES(?,?) "
                        "ON CONFLICT(conversazione) DO UPDATE SET titolo=excluded.titolo",
                        (conversazione, titolo))
        else:
            self.esegui("DELETE FROM tess_titoli WHERE conversazione=?",
                        (conversazione,))

    def ultima_conversazione_tess(self) -> str:
        r = self.uno("SELECT conversazione FROM tess_chat "
                     "ORDER BY id DESC LIMIT 1")
        return r["conversazione"] if r else ""

    def elimina_conversazione_tess(self, conversazione: str) -> None:
        self.esegui("DELETE FROM tess_chat WHERE conversazione=?", (conversazione,))
        self.esegui("DELETE FROM tess_titoli WHERE conversazione=?", (conversazione,))

    def studio(self, dal: str = "", al: str = "", limite: int = 0) -> list[sqlite3.Row]:
        sql = "SELECT * FROM studio WHERE 1=1"
        par: list = []
        if dal:
            sql += " AND data >= ?"; par.append(dal)
        if al:
            sql += " AND data <= ?"; par.append(al)
        sql += " ORDER BY data DESC, id DESC"
        if limite:
            sql += f" LIMIT {int(limite)}"
        return self.query(sql, tuple(par))

    def minuti_studio(self, dal: str, al: str) -> int:
        return int(self.valore(
            "SELECT COALESCE(SUM(minuti),0) FROM studio WHERE data BETWEEN ? AND ?",
            (dal, al)))

    def studio_per_materia(self, dal: str, al: str) -> list[tuple[str, int]]:
        righe = self.query(
            "SELECT materia, SUM(minuti) m FROM studio WHERE data BETWEEN ? AND ? "
            "GROUP BY materia ORDER BY m DESC", (dal, al))
        return [(r["materia"] or "senza materia", int(r["m"])) for r in righe]

    def percorsi(self) -> list[sqlite3.Row]:
        return self.query(
            "SELECT * FROM percorsi ORDER BY CASE stato WHEN 'attivo' THEN 0 "
            "WHEN 'attesa' THEN 1 ELSE 2 END, nome")

    def salva_percorso(self, d: dict) -> int:
        campi = ("nome", "categoria", "avanzamento", "risorsa", "stato", "colore", "note")
        if d.get("id"):
            self.esegui("UPDATE percorsi SET " + ", ".join(f"{c}=?" for c in campi) +
                        " WHERE id=?", tuple(d[c] for c in campi) + (d["id"],))
            return int(d["id"])
        return self.esegui(
            "INSERT INTO percorsi(" + ",".join(campi) + ") VALUES(?,?,?,?,?,?,?)",
            tuple(d[c] for c in campi))

    # --------------------------------------------------------------- scadenze
    def scadenze(self, dal: str = "", al: str = "", solo_aperte: bool = True,
                 limite: int = 0) -> list[sqlite3.Row]:
        sql = "SELECT * FROM scadenze WHERE 1=1"
        par: list = []
        if solo_aperte:
            sql += " AND fatta=0"
        if dal:
            sql += " AND data >= ?"; par.append(dal)
        if al:
            sql += " AND data <= ?"; par.append(al)
        sql += " ORDER BY data, id"
        if limite:
            sql += f" LIMIT {int(limite)}"
        return self.query(sql, tuple(par))

    def salva_scadenza(self, d: dict) -> int:
        campi = ("data", "titolo", "area", "fatta", "note")
        if d.get("id"):
            self.esegui("UPDATE scadenze SET " + ", ".join(f"{c}=?" for c in campi) +
                        " WHERE id=?", tuple(d[c] for c in campi) + (d["id"],))
            return int(d["id"])
        return self.esegui(
            "INSERT INTO scadenze(" + ",".join(campi) + ") VALUES(?,?,?,?,?)",
            tuple(d[c] for c in campi))

    # -------------------------------------------------------------- abitudini
    def abitudini(self, solo_attive: bool = True) -> list[sqlite3.Row]:
        sql = "SELECT * FROM abitudini"
        if solo_attive:
            sql += " WHERE attiva=1"
        return self.query(sql + " ORDER BY ordine, id")

    def salva_abitudine(self, d: dict) -> int:
        campi = ("nome", "colore", "obiettivo", "area", "attiva")
        if d.get("id"):
            self.esegui("UPDATE abitudini SET " + ", ".join(f"{c}=?" for c in campi) +
                        " WHERE id=?", tuple(d[c] for c in campi) + (d["id"],))
            return int(d["id"])
        ordine = int(self.valore("SELECT COALESCE(MAX(ordine),0)+1 FROM abitudini"))
        return self.esegui(
            "INSERT INTO abitudini(" + ",".join(campi) + ",ordine) VALUES(?,?,?,?,?,?)",
            tuple(d[c] for c in campi) + (ordine,))

    def rinomina_abitudine(self, id_: int, nome: str) -> None:
        """Cambia solo il nome: serve all'elenco modificabile sul posto."""
        self.esegui("UPDATE abitudini SET nome=? WHERE id=?",
                    (nome.strip() or "Abitudine", id_))

    def attiva_abitudine(self, id_: int, attiva: bool) -> None:
        """In pausa resta nello storico ma esce dalla griglia dei giorni."""
        self.esegui("UPDATE abitudini SET attiva=? WHERE id=?",
                    (1 if attiva else 0, id_))

    def segni_abitudine(self, id_: int) -> int:
        return int(self.valore(
            "SELECT COUNT(*) FROM registro WHERE abitudine_id=?", (id_,)))

    def registro(self, dal: str, al: str) -> set[tuple[str, int]]:
        return {(r["data"], r["abitudine_id"]) for r in self.query(
            "SELECT data, abitudine_id FROM registro WHERE data BETWEEN ? AND ?",
            (dal, al))}

    def commuta_abitudine(self, data: str, abitudine_id: int) -> bool:
        """Segna o toglie il segno: restituisce lo stato finale."""
        presente = self.uno(
            "SELECT id FROM registro WHERE data=? AND abitudine_id=?",
            (data, abitudine_id))
        if presente:
            self.esegui("DELETE FROM registro WHERE id=?", (presente["id"],))
            return False
        self.esegui("INSERT INTO registro(data, abitudine_id) VALUES(?,?)",
                    (data, abitudine_id))
        return True

    def serie_abitudine(self, abitudine_id: int) -> int:
        """Giorni consecutivi fino a oggi (o a ieri, se oggi non è ancora segnata)."""
        date_fatte = {r["data"] for r in self.query(
            "SELECT data FROM registro WHERE abitudine_id=? ORDER BY data DESC LIMIT 400",
            (abitudine_id,))}
        if not date_fatte:
            return 0
        from datetime import timedelta
        giorno = date.today()
        if giorno.isoformat() not in date_fatte:
            giorno -= timedelta(days=1)
        serie = 0
        while giorno.isoformat() in date_fatte:
            serie += 1
            giorno -= timedelta(days=1)
        return serie

    # -------------------------------------------------- finanza (archivio proprio)
    def movimenti(self, dal: str = "", al: str = "", limite: int = 0) -> list[sqlite3.Row]:
        sql = "SELECT * FROM movimenti WHERE 1=1"
        par: list = []
        if dal:
            sql += " AND data >= ?"; par.append(dal)
        if al:
            sql += " AND data <= ?"; par.append(al)
        sql += " ORDER BY data DESC, id DESC"
        if limite:
            sql += f" LIMIT {int(limite)}"
        return self.query(sql, tuple(par))

    def salva_movimento(self, d: dict) -> int:
        campi = ("data", "tipo", "importo", "categoria", "descrizione")
        if d.get("id"):
            self.esegui("UPDATE movimenti SET " + ", ".join(f"{c}=?" for c in campi) +
                        " WHERE id=?", tuple(d[c] for c in campi) + (d["id"],))
            # se il movimento è l'entrata gemella di un incasso, l'incasso
            # segue: correggere da una parte vale anche dall'altra
            self.esegui(
                "UPDATE incassi SET data=?, importo=?, categoria=? "
                "WHERE movimento_id=?",
                (d["data"], float(d["importo"]), d["categoria"], d["id"]))
            return int(d["id"])
        return self.esegui(
            "INSERT INTO movimenti(" + ",".join(campi) + ") VALUES(?,?,?,?,?)",
            tuple(d[c] for c in campi))

    def obiettivi(self) -> list[sqlite3.Row]:
        return self.query("SELECT * FROM obiettivi ORDER BY scadenza='', scadenza, nome")

    def salva_obiettivo(self, d: dict) -> int:
        campi = ("nome", "obiettivo", "accantonato", "scadenza", "note")
        if d.get("id"):
            self.esegui("UPDATE obiettivi SET " + ", ".join(f"{c}=?" for c in campi) +
                        " WHERE id=?", tuple(d[c] for c in campi) + (d["id"],))
            return int(d["id"])
        return self.esegui(
            "INSERT INTO obiettivi(" + ",".join(campi) + ") VALUES(?,?,?,?,?)",
            tuple(d[c] for c in campi))

    def categorie(self, tipo: str = "") -> list[str]:
        """I nomi delle categorie, di un tipo solo o di tutti e due."""
        if tipo:
            righe = self.query(
                "SELECT nome FROM categorie WHERE tipo=? ORDER BY ordine, nome",
                (tipo,))
        else:
            righe = self.query("SELECT DISTINCT nome FROM categorie ORDER BY nome")
        return [r["nome"] for r in righe]

    def aggiungi_categoria(self, nome: str, tipo: str) -> None:
        nome = (nome or "").strip()
        if not nome or tipo not in ("entrata", "uscita"):
            return
        ordine = int(self.valore(
            "SELECT COALESCE(MAX(ordine),0)+1 FROM categorie WHERE tipo=?", (tipo,)))
        self.esegui("INSERT OR IGNORE INTO categorie(nome, tipo, ordine) "
                    "VALUES(?,?,?)", (nome, tipo, ordine))

    def togli_categoria(self, nome: str, tipo: str) -> None:
        """Toglie la categoria dall'elenco; i movimenti già scritti non cambiano."""
        self.esegui("DELETE FROM categorie WHERE nome=? AND tipo=?", (nome, tipo))

    def budget(self) -> list[sqlite3.Row]:
        return self.query("SELECT * FROM budget ORDER BY categoria")

    def salva_budget(self, categoria: str, mensile: float) -> None:
        self.esegui(
            "INSERT INTO budget(categoria, mensile) VALUES(?,?) "
            "ON CONFLICT(categoria) DO UPDATE SET mensile=excluded.mensile",
            (categoria, float(mensile)))

    # ------------------------------------------------------------------ varie
    def conteggi(self) -> dict[str, int]:
        return {t: int(self.valore(f"SELECT COUNT(*) FROM {t}")) for t in
                ("voci", "salute", "allenamenti", "progetti", "lavoro", "incassi",
                 "esami", "studio", "percorsi", "scadenze", "movimenti")}

    def prima_data(self) -> str:
        date_ = [self.valore(f"SELECT MIN(data) FROM {t}", default="")
                 for t in ("voci", "salute", "lavoro", "studio", "movimenti")]
        valide = [d for d in date_ if d]
        return min(valide) if valide else date.today().isoformat()

    def cartella_backup(self) -> str:
        cartella = (BACKUP_DIR if self.percorso == DB_PATH
                    else os.path.join(os.path.dirname(self.percorso), "backup"))
        os.makedirs(cartella, exist_ok=True)
        return cartella

    def backup(self, destinazione: str) -> str:
        self.conn.commit()
        if os.path.isdir(destinazione):
            destinazione = os.path.join(
                destinazione, f"vita-backup-{datetime.now():%Y%m%d-%H%M%S}.db")
        shutil.copy2(self.percorso, destinazione)
        return destinazione

    def chiudi(self) -> None:
        self.conn.commit()
        self.conn.close()
