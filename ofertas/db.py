import datetime as dt
import sqlite3

from .config import DATA_DIR
from .models import Oferta

_DB = DATA_DIR / "ofertas.db"


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(_DB)
    c.execute(
        "CREATE TABLE IF NOT EXISTS postadas ("
        " uid TEXT PRIMARY KEY,"
        " plataforma TEXT,"
        " titulo TEXT,"
        " preco REAL,"
        " postada_em TEXT)"
    )
    return c


def ja_postada(uid: str, dentro_de_dias: int) -> bool:
    with _conn() as c:
        row = c.execute("SELECT postada_em FROM postadas WHERE uid = ?", (uid,)).fetchone()
    if not row:
        return False
    postada = dt.datetime.fromisoformat(row[0])
    return (dt.datetime.now() - postada) < dt.timedelta(days=dentro_de_dias)


def registrar(oferta: Oferta) -> None:
    with _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO postadas (uid, plataforma, titulo, preco, postada_em)"
            " VALUES (?, ?, ?, ?, ?)",
            (oferta.uid, oferta.plataforma, oferta.titulo, oferta.preco,
             dt.datetime.now().isoformat(timespec="seconds")),
        )


def total_postadas() -> int:
    with _conn() as c:
        return c.execute("SELECT COUNT(*) FROM postadas").fetchone()[0]


def listar(limit: int = 100, offset: int = 0) -> list[dict]:
    limit = min(max(int(limit), 1), 500)
    offset = max(int(offset), 0)
    with _conn() as c:
        c.row_factory = sqlite3.Row
        rows = c.execute(
            "SELECT uid, plataforma, titulo, preco, postada_em "
            "FROM postadas ORDER BY postada_em DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return [dict(row) for row in rows]
