"""Operações locais, arquivos autorizados pelo usuário e importação validada."""
import asyncio
import json
import shutil
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from .models import validate_entity, validate_settings, number, is_group_jid
from .repository import Repository, encode
from .runtime import Runtime


class Service:
    def __init__(self, directory, bridge, changed=lambda: None):
        self.directory, self.bridge = directory, bridge
        self.media = directory / 'autoresponder-media'
        self.repo = Repository(directory / 'autoresponder.db')
        self.runtime = Runtime(self.repo, bridge, changed)

    def copy_media(self, source):
        path = Path(source).resolve(strict=True)
        if not path.is_file() or path.suffix.lower() not in ('.jpg', '.jpeg', '.png', '.webp', '.mp4'):
            raise ValueError('Selecione uma imagem JPG/PNG/WebP ou um vídeo MP4.')
        if not 0 < path.stat().st_size <= 64 * 1024 * 1024:
            raise ValueError('A mídia deve ter entre 1 byte e 64 MB.')
        self.media.mkdir(parents=True, exist_ok=True)
        if path.parent == self.media.resolve():
            return str(path)
        target = self.media / (uuid.uuid4().hex + path.suffix.lower())
        shutil.copy2(path, target)
        return str(target)

    def snapshot(self, offset=0):
        config = self.repo.config()
        with self.repo.connect() as db:
            last = {row[0]: row[1] for row in db.execute("SELECT group_id,MAX(at) FROM jobs WHERE simulated=0 AND state IN ('QUEUED','SENDING','SENT','UNCERTAIN') GROUP BY group_id")}
        for group in config['groups']:
            group['nextAllowedAt'] = last.get(group['id'], 0) + group['rule']['cooldownSeconds']
        return dict(**config, **self.repo.history(offset), running=self.runtime.running,
                    session=self.runtime.session, connected=self.bridge.connected)

    def validate_import(self, data):
        if not isinstance(data, dict) or data.get('version') != 1:
            raise ValueError('Selecione um backup JSON versão 1 do SendAiPlus/respondedor.')
        result = dict(settings=validate_settings(data.get('settings') or {}))
        result['settings'].update(dryRun=True, autoStart=False)
        for kind in ('posts', 'campaigns', 'groups'):
            items = data.get(kind, [])
            if not isinstance(items, list) or len(items) > 1000:
                raise ValueError('Backup excede o limite de 1.000 cadastros por tipo.')
            # O SendAiPlus inclui um grupo fictício de demonstração em backups virgens.
            usable = [item for item in items if kind != 'groups' or not isinstance(item, dict) or item.get('externalId') != 'simulador@g.us']
            result[kind] = [validate_entity(kind, item) for item in usable]
            if len({v['id'] for v in result[kind]}) != len(usable):
                raise ValueError('Backup com identificadores repetidos.')
        if sum(g['externalId'] == '*' for g in result['groups']) > 1:
            raise ValueError('Backup contém mais de uma automação para todos os grupos.')
        posts = {p['id'] for p in result['posts']}
        campaigns = {c['id'] for c in result['campaigns']}
        for c in result['campaigns']:
            if not set(c['postIds']) <= posts:
                raise ValueError('Campanha referencia post inexistente.')
        for g in result['groups']:
            g['enabled'] = False
            if g['campaignId'] and g['campaignId'] not in campaigns:
                raise ValueError('Grupo referencia campanha inexistente.')
        for p in result['posts']:
            if p['type'] in ('IMAGE', 'VIDEO') and not Path(p['mediaPath']).is_file():
                raise ValueError(f'Mídia não encontrada para o post {p["name"]}.')
        return result

    async def handle(self, payload):
        action = payload.get('action', 'status')
        if action == 'status':
            return self.snapshot(number(payload.get('offset', 0), 0, 10000000))
        if action == 'start':
            await self.runtime.start()
        elif action == 'stop':
            await self.runtime.stop()
        elif action == 'groups':
            return dict(groups=await self.bridge.list_groups())
        elif action == 'save':
            kind, value = payload['kind'], payload['value']
            if not isinstance(value, dict):
                raise ValueError('Cadastro inválido.')
            if kind == 'settings':
                data = validate_settings(value)
            else:
                data = validate_entity(kind, value)
                if kind == 'posts' and data['type'] in ('IMAGE', 'VIDEO'):
                    data['mediaPath'] = await asyncio.to_thread(self.copy_media, data['mediaPath'])
                cfg = self.repo.config()
                if kind == 'campaigns' and not set(data['postIds']) <= {p['id'] for p in cfg['posts']}:
                    raise ValueError('Selecione posts existentes.')
                if kind == 'groups' and data['campaignId'] and data['campaignId'] not in {c['id'] for c in cfg['campaigns']}:
                    raise ValueError('Selecione uma campanha existente.')
                if kind == 'groups' and data['externalId'] == '*' and any(
                    g['externalId'] == '*' and g['id'] != data['id'] for g in cfg['groups']
                ):
                    raise ValueError('Já existe uma automação para todos os grupos. Edite a existente.')
                if kind == 'groups' and data['enabled']:
                    campaign = next((c for c in cfg['campaigns'] if c['id'] == data['campaignId'] and c['enabled']), None)
                    if not campaign or not any(p['id'] in campaign['postIds'] and p['enabled'] for p in cfg['posts']):
                        raise ValueError('Ative uma campanha com pelo menos um post ativo antes de ativar o grupo.')
            self.repo.save(kind, data)
            if self.runtime.running and kind == 'groups':
                await self.runtime.subscribe()
            self.runtime.wake.set()
        elif action == 'delete':
            self.repo.delete(payload['kind'], payload['id'])
            self.runtime.wake.set()
            if self.runtime.running and payload['kind'] == 'groups':
                await self.runtime.subscribe()
        elif action == 'cancel':
            with self.repo.connect() as db:
                db.execute("UPDATE jobs SET state='CANCELLED',reason='Cancelado manualmente.' WHERE id=? AND state='QUEUED'", (payload['id'],))
        elif action == 'simulate':
            group = next((g for g in self.repo.config()['groups'] if g['id'] == payload.get('groupId')), None)
            if not group:
                raise ValueError('Selecione um grupo cadastrado.')
            chat = payload.get('chat') if group['externalId'] == '*' else group['externalId']
            if not is_group_jid(chat):
                raise ValueError('Selecione um grupo real para simular a regra geral.')
            return self.runtime.evaluate(dict(chat=chat, id=uuid.uuid4().hex,
                account='simulation', at=self.runtime.clock(), fromMe=False), simulation=True)
        elif action == 'export':
            config = self.repo.config()
            return dict(text=encode(dict(version=1, exportedAt=datetime.now(timezone.utc).isoformat(),
                                         rules=[g['rule'] for g in config['groups']], **config)))
        elif action in ('import_preview', 'import'):
            content = payload.get('text', '')
            if not isinstance(content, str) or len(content) > 4_000_000:
                raise ValueError('Backup JSON muito grande.')
            data = self.validate_import(json.loads(content))
            if action == 'import_preview':
                return dict(counts={k: len(data[k]) for k in ('groups', 'posts', 'campaigns')},
                            message='Substitui somente os cadastros do respondedor. Grupos desativados e simulação ligada.')
            if self.runtime.running or any(not t.done() for t in self.runtime.tasks):
                raise ValueError('Pare o respondedor e aguarde o envio atual antes de importar.')
            for post in data['posts']:
                if post['type'] in ('IMAGE', 'VIDEO'):
                    post['mediaPath'] = await asyncio.to_thread(self.copy_media, post['mediaPath'])
            with self.repo.connect() as db:
                for kind in ('groups', 'campaigns', 'posts'):
                    db.execute(f'DELETE FROM {kind}')
                    db.executemany(f'INSERT INTO {kind} VALUES(?,?)', [(v['id'], encode(v)) for v in data[kind]])
                db.execute('INSERT OR REPLACE INTO settings VALUES(1,?)', (encode(data['settings']),))
        elif action == 'backup':
            target = self.directory / f'autoresponder-backup-{uuid.uuid4().hex[:8]}.db'
            def backup():
                with self.repo.connect() as source, closing(sqlite3.connect(target)) as dest:
                    source.backup(dest)
            await asyncio.to_thread(backup)
            return dict(path=str(target))
        elif action == 'restore':
            if self.runtime.running or any(not t.done() for t in self.runtime.tasks):
                raise ValueError('Pare o respondedor e aguarde o envio atual antes de restaurar.')
            source_path = Path(payload.get('path', '')).resolve(strict=True)
            if not source_path.is_file() or not 0 < source_path.stat().st_size <= 512 * 1024 * 1024:
                raise ValueError('Arquivo de backup SQLite inválido.')
            if source_path == self.repo.path.resolve():
                raise ValueError('Selecione um backup externo, não o banco atual.')
            def restore():
                with closing(sqlite3.connect(source_path.as_uri() + '?mode=ro', uri=True)) as source:
                    if source.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or source.execute('PRAGMA user_version').fetchone()[0] != 1:
                        raise ValueError('Backup incompatível ou corrompido.')
                    names = {r[0] for r in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                    if not {'settings', 'posts', 'campaigns', 'groups', 'messages', 'jobs'} <= names:
                        raise ValueError('Este arquivo não é um backup do respondedor.')
                    if source.execute("SELECT COUNT(*) FROM sqlite_master WHERE type IN ('trigger','view')").fetchone()[0]:
                        raise ValueError('Backup contém objetos SQL não permitidos.')
                    row = source.execute('SELECT data FROM settings WHERE id=1').fetchone()
                    data = dict(version=1,settings=json.loads(row[0]) if row else {},
                        **{kind:[json.loads(r[0]) for r in source.execute(f'SELECT data FROM {kind}')] for kind in ('posts','campaigns','groups')})
                    self.validate_import(data)
                    safety = self.directory / f'autoresponder-before-restore-{uuid.uuid4().hex[:8]}.db'
                    with self.repo.connect() as current, closing(sqlite3.connect(safety)) as old:
                        current.backup(old)
                    with self.repo.connect() as current:
                        source.backup(current)
                return safety
            safety = await asyncio.to_thread(restore)
            self.repo = Repository(self.repo.path)
            self.runtime.repo = self.repo
            config = self.repo.config()
            self.repo.save('settings', validate_settings(config['settings'] | dict(dryRun=True, autoStart=False)))
            for group in config['groups']:
                group['enabled'] = False
                self.repo.save('groups', group)
            return dict(path=str(safety), restored=True,
                        message='Backup restaurado com grupos desativados e simulação ligada. Revise antes de ativar.')
        else:
            raise ValueError('Operação do respondedor não permitida.')
        self.runtime.changed()
        return self.snapshot()
