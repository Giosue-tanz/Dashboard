"""Da dove arrivano i dati della finanza.

Due sorgenti con la stessa interfaccia: l'archivio dell'app **Finance**, letto
in sola lettura se è installata, oppure l'archivio interno di Dashboard. La vista
non sa quale delle due sta usando.
"""
from __future__ import annotations

import os
import sqlite3
from collections import Counter
from datetime import date

from .utils import mese_corrente

PERCORSO_FINANCE = os.path.join(
    os.environ.get("XDG_DATA_HOME", os.path.join(os.path.expanduser("~"), ".local", "share")),
    "Finance", "finanze.db")


def finance_presente(percorso: str = "") -> bool:
    return os.path.exists(percorso or PERCORSO_FINANCE)


class FonteLocale:
    """Archivio proprio di Dashboard: i movimenti si inseriscono qui dentro."""

    nome = "archivio interno"
    modificabile = True

    def __init__(self, db):
        self.db = db
        self.percorso = db.percorso

    def disponibile(self) -> bool:
        return True

    def _iniziale(self) -> float:
        """Da dove si parte: la somma dei conti, o il saldo iniziale di una volta.

        Finché i conti non ci sono, vale il numero unico scritto nelle
        impostazioni; appena ce n'è anche uno solo, comandano loro — se no
        il saldo verrebbe contato due volte.
        """
        conti = float(self.db.valore(
            "SELECT COALESCE(SUM(saldo_iniziale),0) FROM conti", default=0.0))
        quanti = int(self.db.valore("SELECT COUNT(*) FROM conti", default=0))
        return conti if quanti else self.db.leggi_num("saldo_iniziale", 0.0)

    def saldo(self) -> float:
        ent = self.db.valore("SELECT COALESCE(SUM(importo),0) FROM movimenti WHERE tipo='entrata'")
        usc = self.db.valore("SELECT COALESCE(SUM(importo),0) FROM movimenti WHERE tipo='uscita'")
        return float(ent) - float(usc) + self._iniziale()

    def totali_periodo(self, dal: str, al: str) -> tuple[float, float]:
        ent = self.db.valore(
            "SELECT COALESCE(SUM(importo),0) FROM movimenti "
            "WHERE tipo='entrata' AND data BETWEEN ? AND ?", (dal, al))
        usc = self.db.valore(
            "SELECT COALESCE(SUM(importo),0) FROM movimenti "
            "WHERE tipo='uscita' AND data BETWEEN ? AND ?", (dal, al))
        return float(ent), float(usc)

    def movimenti(self, dal: str = "", al: str = "", limite: int = 0):
        return [dict(r) for r in self.db.movimenti(dal, al, limite)]

    def per_categoria(self, tipo: str, dal: str, al: str) -> list[tuple[str, float]]:
        righe = self.db.query(
            "SELECT categoria, SUM(importo) t FROM movimenti WHERE tipo=? "
            "AND data BETWEEN ? AND ? GROUP BY categoria ORDER BY t DESC",
            (tipo, dal, al))
        return [(r["categoria"], float(r["t"])) for r in righe]

    def serie_mensile(self, mesi: int = 12) -> list[tuple[str, float, float]]:
        righe = self.db.query(
            "SELECT substr(data,1,7) m, "
            "SUM(CASE WHEN tipo='entrata' THEN importo ELSE 0 END) e, "
            "SUM(CASE WHEN tipo='uscita' THEN importo ELSE 0 END) u "
            "FROM movimenti GROUP BY m ORDER BY m DESC LIMIT ?", (mesi,))
        return [(r["m"], float(r["e"]), float(r["u"])) for r in reversed(righe)]

    def saldo_alla_data(self, giorno: str) -> float:
        m = self.db.valore(
            "SELECT COALESCE(SUM(CASE WHEN tipo='entrata' THEN importo ELSE -importo END),0) "
            "FROM movimenti WHERE data <= ?", (giorno,))
        return float(m) + self._iniziale()

    def budget(self) -> list[tuple[str, float, float]]:
        dal, al = mese_corrente()
        fuori = []
        for r in self.db.budget():
            speso = float(self.db.valore(
                "SELECT COALESCE(SUM(importo),0) FROM movimenti WHERE tipo='uscita' "
                "AND categoria=? AND data BETWEEN ? AND ?", (r["categoria"], dal, al)))
            fuori.append((r["categoria"], float(r["mensile"]), speso))
        return fuori

    def obiettivi(self) -> list[tuple[str, float, float, str]]:
        return [(r["nome"], float(r["obiettivo"]), float(r["accantonato"]), r["scadenza"])
                for r in self.db.obiettivi()]

    def conti(self) -> list[tuple[str, float]]:
        """I conti col loro saldo. Senza conti, uno solo con dentro tutto."""
        righe = [(r["nome"], float(r["saldo"])) for r in self.db.conti()]
        if not righe:
            return [("Archivio interno", self.saldo())]
        # i movimenti senza conto non stanno in nessun cassetto: si dicono
        # a parte, se no la somma dei conti non torna col saldo totale
        senza = float(self.db.valore(
            "SELECT COALESCE(SUM(CASE WHEN tipo='entrata' THEN importo "
            "ELSE -importo END),0) FROM movimenti WHERE conto=''", default=0.0))
        if abs(senza) >= 0.005:
            righe.append(("Senza conto", senza))
        return righe


class FonteFinance:
    """Archivio dell'app Finance, aperto in sola lettura."""

    nome = "Finance"
    modificabile = False

    def __init__(self, percorso: str = ""):
        self.percorso = percorso or PERCORSO_FINANCE
        self.conn: sqlite3.Connection | None = None
        if os.path.exists(self.percorso):
            try:
                self.conn = sqlite3.connect(
                    f"file:{self.percorso}?mode=ro", uri=True, check_same_thread=False)
                self.conn.row_factory = sqlite3.Row
            except sqlite3.Error:
                self.conn = None

    def disponibile(self) -> bool:
        return self.conn is not None

    def _valore(self, sql: str, par: tuple = (), default=0.0):
        if self.conn is None:
            return default
        try:
            r = self.conn.execute(sql, par).fetchone()
        except sqlite3.Error:
            return default
        return default if r is None or r[0] is None else r[0]

    def _righe(self, sql: str, par: tuple = ()) -> list[sqlite3.Row]:
        if self.conn is None:
            return []
        try:
            return self.conn.execute(sql, par).fetchall()
        except sqlite3.Error:
            return []

    def saldo(self) -> float:
        iniz = self._valore("SELECT COALESCE(SUM(saldo_iniziale),0) FROM conti")
        ent = self._valore("SELECT COALESCE(SUM(importo),0) FROM movimenti WHERE tipo='entrata'")
        usc = self._valore("SELECT COALESCE(SUM(importo),0) FROM movimenti WHERE tipo='uscita'")
        return float(iniz) + float(ent) - float(usc)

    def totali_periodo(self, dal: str, al: str) -> tuple[float, float]:
        ent = self._valore("SELECT COALESCE(SUM(importo),0) FROM movimenti "
                           "WHERE tipo='entrata' AND data BETWEEN ? AND ?", (dal, al))
        usc = self._valore("SELECT COALESCE(SUM(importo),0) FROM movimenti "
                           "WHERE tipo='uscita' AND data BETWEEN ? AND ?", (dal, al))
        return float(ent), float(usc)

    def movimenti(self, dal: str = "", al: str = "", limite: int = 0) -> list[dict]:
        sql = "SELECT * FROM movimenti WHERE 1=1"
        par: list = []
        if dal:
            sql += " AND data >= ?"; par.append(dal)
        if al:
            sql += " AND data <= ?"; par.append(al)
        sql += " ORDER BY data DESC, id DESC"
        if limite:
            sql += f" LIMIT {int(limite)}"
        return [dict(r) for r in self._righe(sql, tuple(par))]

    def per_categoria(self, tipo: str, dal: str, al: str) -> list[tuple[str, float]]:
        righe = self._righe(
            "SELECT categoria, SUM(importo) t FROM movimenti WHERE tipo=? "
            "AND data BETWEEN ? AND ? GROUP BY categoria ORDER BY t DESC", (tipo, dal, al))
        return [(r["categoria"], float(r["t"])) for r in righe]

    def serie_mensile(self, mesi: int = 12) -> list[tuple[str, float, float]]:
        righe = self._righe(
            "SELECT substr(data,1,7) m, "
            "SUM(CASE WHEN tipo='entrata' THEN importo ELSE 0 END) e, "
            "SUM(CASE WHEN tipo='uscita' THEN importo ELSE 0 END) u "
            "FROM movimenti GROUP BY m ORDER BY m DESC LIMIT ?", (mesi,))
        return [(r["m"], float(r["e"]), float(r["u"])) for r in reversed(righe)]

    def saldo_alla_data(self, giorno: str) -> float:
        iniz = self._valore("SELECT COALESCE(SUM(saldo_iniziale),0) FROM conti")
        m = self._valore(
            "SELECT COALESCE(SUM(CASE WHEN tipo='entrata' THEN importo ELSE -importo END),0) "
            "FROM movimenti WHERE data <= ?", (giorno,))
        return float(iniz) + float(m)

    def budget(self) -> list[tuple[str, float, float]]:
        dal, al = mese_corrente()
        fuori = []
        for r in self._righe("SELECT categoria, mensile FROM budget ORDER BY categoria"):
            speso = float(self._valore(
                "SELECT COALESCE(SUM(importo),0) FROM movimenti WHERE tipo='uscita' "
                "AND categoria=? AND data BETWEEN ? AND ?", (r["categoria"], dal, al)))
            fuori.append((r["categoria"], float(r["mensile"]), speso))
        return fuori

    def obiettivi(self) -> list[tuple[str, float, float, str]]:
        return [(r["nome"], float(r["obiettivo"]), float(r["accantonato"]), r["scadenza"])
                for r in self._righe("SELECT * FROM obiettivi ORDER BY nome")]

    def conti(self) -> list[tuple[str, float]]:
        righe = self._righe(
            "SELECT c.nome, c.saldo_iniziale + COALESCE(SUM(CASE m.tipo "
            "WHEN 'entrata' THEN m.importo WHEN 'uscita' THEN -m.importo END),0) s "
            "FROM conti c LEFT JOIN movimenti m ON m.conto=c.nome "
            "GROUP BY c.id ORDER BY s DESC")
        return [(r["nome"], float(r["s"])) for r in righe]

    def chiudi(self) -> None:
        if self.conn is not None:
            self.conn.close()
            self.conn = None


def porta_dentro_finance(db, percorso: str = "") -> dict:
    """Copia **tutto** l'archivio di Finance dentro quello di Dashboard.

    Conti, categorie (col colore), movimenti, budget, obiettivi e
    ricorrenti. Si può rilanciare quante volte si vuole: un movimento
    uguale a uno già portato dentro non entra due volte — stessa data,
    stesso tipo, stesso importo, stessa categoria e stessa descrizione.

    Non tocca l'archivio di Finance: lo apre in sola lettura. Finito,
    la finanza di Dashboard può vivere da sola, e i movimenti si scrivono
    qui dentro.
    """
    conto = {k: 0 for k in ("conti", "categorie", "movimenti", "budget",
                            "obiettivi", "ricorrenti")}
    fonte = FonteFinance(percorso)
    if not fonte.disponibile():
        return conto
    try:
        for r in fonte._righe("SELECT * FROM conti ORDER BY id"):
            if db.valore("SELECT COUNT(*) FROM conti WHERE nome=?", (r["nome"],)):
                continue
            db.salva_conto({"nome": r["nome"],
                            "saldo_iniziale": float(r["saldo_iniziale"] or 0),
                            "tipo": r["tipo"] or "Conto corrente"})
            conto["conti"] += 1

        for r in fonte._righe("SELECT * FROM categorie ORDER BY id"):
            tipo = r["tipo"] if r["tipo"] in ("entrata", "uscita") else "uscita"
            gia = db.valore("SELECT COUNT(*) FROM categorie WHERE nome=? AND tipo=?",
                            (r["nome"], tipo))
            db.aggiungi_categoria(r["nome"], tipo, (r["icona"] or "").strip())
            colore = (r["colore"] or "").strip()
            if colore:
                db.esegui("UPDATE categorie SET colore=? WHERE nome=? AND tipo=?",
                          (colore, r["nome"], tipo))
            if not gia:
                conto["categorie"] += 1

        # Quelli che ci sono già, contati: **due caffè identici nello stesso
        # giorno sono due movimenti**, non uno. Cercare «ne esiste uno
        # uguale?» ne avrebbe lasciato fuori uno dei due — e il saldo non
        # sarebbe più tornato con quello di Finance.
        gia = Counter(
            (r["data"], r["tipo"], round(float(r["importo"]), 2),
             r["categoria"], r["descrizione"])
            for r in db.query("SELECT data, tipo, importo, categoria, descrizione "
                              "FROM movimenti"))
        for r in fonte.movimenti():
            etichette = r.get("etichette") or ""
            chiave = (r["data"], r["tipo"], round(float(r["importo"]), 2),
                      r.get("categoria") or "Altro", r.get("descrizione") or "")
            if gia[chiave] > 0:
                gia[chiave] -= 1
                continue
            db.salva_movimento({
                "data": r["data"], "tipo": r["tipo"],
                "importo": float(r["importo"]),
                "categoria": r.get("categoria") or "Altro",
                "descrizione": r.get("descrizione") or "",
                # le etichette di Finance diventano le categorie in più:
                # sono la stessa idea, un movimento che sta in più caselle
                "categorie": etichette,
                "conto": r.get("conto") or ""})
            conto["movimenti"] += 1

        for r in fonte._righe("SELECT * FROM budget ORDER BY id"):
            if db.valore("SELECT COUNT(*) FROM budget WHERE categoria=?",
                         (r["categoria"],)):
                continue
            db.salva_budget(r["categoria"], float(r["mensile"] or 0))
            conto["budget"] += 1

        for r in fonte._righe("SELECT * FROM obiettivi ORDER BY id"):
            if db.valore("SELECT COUNT(*) FROM obiettivi WHERE nome=?", (r["nome"],)):
                continue
            db.salva_obiettivo({"nome": r["nome"],
                                "obiettivo": float(r["obiettivo"] or 0),
                                "accantonato": float(r["accantonato"] or 0),
                                "scadenza": r["scadenza"] or "",
                                "note": r["note"] or ""})
            conto["obiettivi"] += 1

        for r in fonte._righe("SELECT * FROM ricorrenti ORDER BY id"):
            if db.valore("SELECT COUNT(*) FROM ricorrenti WHERE descrizione=? "
                         "AND ABS(importo-?) < 0.005",
                         (r["descrizione"], float(r["importo"] or 0))):
                continue
            db.salva_ricorrente({
                "descrizione": r["descrizione"], "tipo": r["tipo"],
                "importo": float(r["importo"] or 0),
                "categoria": r["categoria"] or "Altro", "categorie": "",
                "conto": r["conto"] or "", "frequenza": r["frequenza"] or "mensile",
                "giorno": int(r["giorno"] or 1), "inizio": r["inizio"] or "",
                "ultima_generazione": r["ultima_generazione"] or "",
                "attiva": int(r["attiva"] or 0)})
            conto["ricorrenti"] += 1

        # il saldo iniziale di Dashboard non serve più: ce l'hanno i conti
        if conto["conti"]:
            db.imposta("saldo_iniziale", "0")
    finally:
        fonte.chiudi()
    return conto


def fonte_finanza(db):
    """La sorgente scelta nelle impostazioni, con ritorno automatico al locale."""
    scelta = db.leggi("fonte_finanza", "auto")
    percorso = db.leggi("percorso_finance", PERCORSO_FINANCE)
    if scelta in ("auto", "finance") and finance_presente(percorso):
        fonte = FonteFinance(percorso)
        if fonte.disponibile():
            return fonte
    return FonteLocale(db)
