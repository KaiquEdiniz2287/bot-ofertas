"""Banco exclusivo do respondedor. Nenhuma escrita no banco de ofertas."""
import json
import sqlite3
from contextlib import contextmanager
from .rules import DEFAULT_SETTINGS


def encode(value):
    return json.dumps(value, ensure_ascii=False)


class Repository:
    def __init__(self, path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS settings(id INTEGER PRIMARY KEY CHECK(id=1), data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS posts(id TEXT PRIMARY KEY, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS campaigns(id TEXT PRIMARY KEY, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS groups(id TEXT PRIMARY KEY, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS messages(account TEXT, chat TEXT, external_id TEXT, session TEXT, at REAL,
                    PRIMARY KEY(account,chat,external_id));
                CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, group_id TEXT, post_id TEXT, session TEXT,
                    account TEXT, at REAL, due REAL, state TEXT, simulated INTEGER, reason TEXT, data TEXT);
                CREATE INDEX IF NOT EXISTS jobs_due ON jobs(state,due);
                CREATE INDEX IF NOT EXISTS jobs_count ON jobs(simulated,state,at,group_id);
                CREATE INDEX IF NOT EXISTS messages_session ON messages(session,chat);
                PRAGMA user_version=1;
            ''')
            db.execute('UPDATE jobs SET state=?,reason=? WHERE state=?', ('CANCELLED', 'Aplicativo reiniciado; não será reenviado.', 'QUEUED'))
            db.execute('UPDATE jobs SET state=?,reason=? WHERE state=?', ('UNCERTAIN', 'Aplicativo encerrou durante o envio. Não repetir automaticamente.', 'SENDING'))

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def config(self):
        with self.connect() as db:
            row = db.execute('SELECT data FROM settings WHERE id=1').fetchone()
            return dict(settings=DEFAULT_SETTINGS | (json.loads(row[0]) if row else {}), **{
                kind: [json.loads(r[0]) for r in db.execute(f'SELECT data FROM {kind} ORDER BY rowid')]
                for kind in ('posts', 'campaigns', 'groups')})

    def save(self, kind, data):
        if kind not in ('settings', 'posts', 'campaigns', 'groups'):
            raise ValueError('Cadastro inválido.')
        with self.connect() as db:
            db.execute(f'INSERT OR REPLACE INTO {kind}(id,data) VALUES(?,?)',
                       (1 if kind == 'settings' else data['id'], encode(data)))

    def delete(self, kind, identity):
        if kind not in ('posts', 'campaigns', 'groups'):
            raise ValueError('Cadastro inválido.')
        with self.connect() as db:
            db.execute(f'DELETE FROM {kind} WHERE id=?', (identity,))

    def finish(self, identity, state, reason, at=None):
        with self.connect() as db:
            db.execute('UPDATE jobs SET state=?,reason=?,at=COALESCE(?,at) WHERE id=?', (state, reason, at, identity))

    def records(self, db, simulated, since, exclude=''):
        return [dict(r) for r in db.execute("SELECT group_id,post_id,session,at,state FROM jobs WHERE simulated=? AND at>=? AND id<>? AND state IN ('QUEUED','SENDING','SENT','SIMULATED','UNCERTAIN')", (int(simulated), since, exclude))]

    def recent_posts(self, db, group, simulated, limit):
        if not limit:
            return []
        return [r[0] for r in db.execute("SELECT post_id FROM jobs WHERE group_id=? AND simulated=? AND state IN ('QUEUED','SENDING','SENT','SIMULATED','UNCERTAIN') ORDER BY at DESC LIMIT ?", (group, int(simulated), limit))]

    def history(self, offset=0):
        with self.connect() as db:
            return dict(items=[dict(r) for r in db.execute('SELECT * FROM jobs ORDER BY at DESC LIMIT 100 OFFSET ?', (offset,))],
                        total=db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0],
                        counts={r[0]: r[1] for r in db.execute('SELECT state,COUNT(*) FROM jobs GROUP BY state')},
                        queue=[dict(r) for r in db.execute("SELECT * FROM jobs WHERE state IN ('QUEUED','SENDING') ORDER BY due LIMIT 100")])
