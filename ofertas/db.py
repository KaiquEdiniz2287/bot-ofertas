import datetime as dt
import json
import sqlite3
from contextlib import closing
from dataclasses import asdict

from .config import DATA_DIR
from .models import Oferta

_DB = DATA_DIR / "ofertas.db"


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(_DB)
    c.row_factory = sqlite3.Row
    c.execute(
        "CREATE TABLE IF NOT EXISTS postadas ("
        " uid TEXT PRIMARY KEY,"
        " plataforma TEXT,"
        " titulo TEXT,"
        " preco REAL,"
        " postada_em TEXT)"
    )
    c.execute(
        "CREATE TABLE IF NOT EXISTS publicacoes ("
        " uid TEXT PRIMARY KEY,"
        " oferta_json TEXT NOT NULL,"
        " criada_em TEXT NOT NULL,"
        " expira_em TEXT NOT NULL)"
    )
    c.execute(
        "CREATE TABLE IF NOT EXISTS entregas ("
        " uid TEXT NOT NULL,"
        " canal TEXT NOT NULL,"
        " destino TEXT NOT NULL,"
        " status TEXT NOT NULL,"
        " tentativas INTEGER NOT NULL DEFAULT 0,"
        " tentativas_manuais INTEGER NOT NULL DEFAULT 0,"
        " enviada_em TEXT,"
        " ultimo_erro TEXT,"
        " message_id TEXT,"
        " PRIMARY KEY (uid, canal, destino))"
    )
    columns = {row[1] for row in c.execute("PRAGMA table_info(entregas)")}
    if "tentativas_manuais" not in columns:
        c.execute("ALTER TABLE entregas ADD COLUMN tentativas_manuais INTEGER NOT NULL DEFAULT 0")
    return c


def ja_postada(uid: str, dentro_de_dias: int) -> bool:
    with closing(_conn()) as c, c:
        row = c.execute("SELECT postada_em FROM postadas WHERE uid = ?", (uid,)).fetchone()
    if not row:
        return False
    postada = dt.datetime.fromisoformat(row[0])
    return (dt.datetime.now() - postada) < dt.timedelta(days=dentro_de_dias)


def registrar(oferta: Oferta) -> None:
    with closing(_conn()) as c, c:
        c.execute(
            "INSERT OR REPLACE INTO postadas (uid, plataforma, titulo, preco, postada_em)"
            " VALUES (?, ?, ?, ?, ?)",
            (oferta.uid, oferta.plataforma, oferta.titulo, oferta.preco,
             dt.datetime.now().isoformat(timespec="seconds")),
        )


def total_postadas() -> int:
    with closing(_conn()) as c, c:
        return c.execute("SELECT COUNT(*) FROM postadas").fetchone()[0]


def listar(limit: int = 100, offset: int = 0) -> list[dict]:
    limit = min(max(int(limit), 1), 500)
    offset = max(int(offset), 0)
    with closing(_conn()) as c, c:
        c.row_factory = sqlite3.Row
        rows = c.execute(
            "SELECT uid, plataforma, titulo, preco, postada_em "
            "FROM postadas ORDER BY postada_em DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return [dict(row) for row in rows]


def preparar_entrega_whatsapp(oferta: Oferta, destino: str, validade_horas: int = 6) -> bool:
    agora = dt.datetime.now()
    expira = agora + dt.timedelta(hours=validade_horas)
    with closing(_conn()) as c, c:
        c.execute(
            "INSERT OR IGNORE INTO publicacoes (uid, oferta_json, criada_em, expira_em) VALUES (?, ?, ?, ?)",
            (oferta.uid, json.dumps(asdict(oferta), ensure_ascii=False),
             agora.isoformat(timespec="seconds"), expira.isoformat(timespec="seconds")),
        )
        inserted = c.execute(
            "INSERT OR IGNORE INTO entregas (uid, canal, destino, status) VALUES (?, 'whatsapp', ?, 'pending')",
            (oferta.uid, destino),
        )
        return inserted.rowcount == 1


def marcar_entrega_whatsapp(
    uid: str, destino: str, sucesso: bool, detalhe: str = "", tentativa_manual: bool = False
) -> None:
    with closing(_conn()) as c, c:
        c.execute(
            "UPDATE entregas SET status = ?, tentativas = tentativas + 1, "
            "tentativas_manuais = tentativas_manuais + ?, enviada_em = ?, "
            "ultimo_erro = ?, message_id = ? WHERE uid = ? AND canal = 'whatsapp' AND destino = ?",
            (
                "sent" if sucesso else "failed",
                1 if tentativa_manual else 0,
                dt.datetime.now().isoformat(timespec="seconds") if sucesso else None,
                None if sucesso else detalhe[:500],
                detalhe[:200] if sucesso else None,
                uid,
                destino,
            ),
        )


def listar_pendentes_whatsapp() -> list[dict]:
    agora = dt.datetime.now().isoformat(timespec="seconds")
    with closing(_conn()) as c, c:
        rows = c.execute(
            "SELECT e.uid, e.destino, e.status, e.tentativas_manuais, e.ultimo_erro, "
            "p.oferta_json, p.criada_em, p.expira_em "
            "FROM entregas e JOIN publicacoes p ON p.uid = e.uid "
            "WHERE e.canal = 'whatsapp' AND e.status != 'sent' AND p.expira_em > ? "
            "ORDER BY p.criada_em DESC",
            (agora,),
        ).fetchall()
    items = []
    for row in rows:
        oferta = json.loads(row["oferta_json"])
        items.append({
            "uid": row["uid"], "destination": row["destino"], "status": row["status"],
            "attempts": row["tentativas_manuais"], "lastError": row["ultimo_erro"] or "",
            "createdAt": row["criada_em"], "expiresAt": row["expira_em"],
            "title": oferta.get("titulo", "Oferta"),
        })
    return items


def obter_entrega_whatsapp(uid: str, destino: str) -> tuple[Oferta, dict] | None:
    with closing(_conn()) as c, c:
        row = c.execute(
            "SELECT e.status, e.tentativas_manuais, p.oferta_json, p.expira_em "
            "FROM entregas e JOIN publicacoes p ON p.uid = e.uid "
            "WHERE e.uid = ? AND e.canal = 'whatsapp' AND e.destino = ?",
            (uid, destino),
        ).fetchone()
    if not row:
        return None
    return Oferta(**json.loads(row["oferta_json"])), dict(row)


def total_pendentes_whatsapp() -> int:
    return len(listar_pendentes_whatsapp())
