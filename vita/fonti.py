"""Da dove arrivano i dati della finanza.

Due sorgenti con la stessa interfaccia: l'archivio dell'app **Finance**, letto
in sola lettura se è installata, oppure l'archivio interno di Dashboard. La vista
non sa quale delle due sta usando.
"""
from __future__ import annotations

import os
import sqlite3
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

    def saldo(self) -> float:
        ent = self.db.valore("SELECT COALESCE(SUM(importo),0) FROM movimenti WHERE tipo='entrata'")
        usc = self.db.valore("SELECT COALESCE(SUM(importo),0) FROM movimenti WHERE tipo='uscita'")
        return float(ent) - float(usc) + self.db.leggi_num("saldo_iniziale", 0.0)

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
        return float(m) + self.db.leggi_num("saldo_iniziale", 0.0)

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
        """Un conto solo: qui i movimenti non sono divisi per conto."""
        return [("Archivio interno", self.saldo())]


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


def fonte_finanza(db):
    """La sorgente scelta nelle impostazioni, con ritorno automatico al locale."""
    scelta = db.leggi("fonte_finanza", "auto")
    percorso = db.leggi("percorso_finance", PERCORSO_FINANCE)
    if scelta in ("auto", "finance") and finance_presente(percorso):
        fonte = FonteFinance(percorso)
        if fonte.disponibile():
            return fonte
    return FonteLocale(db)
