"""Fila supervisionada. Recebimento nunca aguarda transporte ou delays."""
import asyncio
import json
import logging
import random
import time
import uuid
from .repository import encode
from .models import is_group_jid
from .rules import decide, select_post

log = logging.getLogger('respostas')


class Runtime:
    def __init__(self, repository, bridge, changed=lambda: None, clock=time.time, rng=None):
        self.repo, self.bridge, self.changed, self.clock = repository, bridge, changed, clock
        self.rng = rng or random.Random()
        self.running = False
        self.session = ''
        self.started = 0
        self.inbox = asyncio.Queue(maxsize=256)
        self.wake = asyncio.Event()
        self.tasks = []

    async def start(self):
        if self.running:
            return
        if any(not t.done() for t in self.tasks):
            raise ValueError('Aguarde a conclusão do envio anterior antes de reiniciar.')
        if not self.bridge.connected:
            raise ValueError('Conecte o WhatsApp na área compartilhada antes de iniciar.')
        self.session, self.started = uuid.uuid4().hex, self.clock()
        self.inbox = asyncio.Queue(maxsize=256)
        self.running = True
        self.bridge.responses_active = True
        try:
            await self.subscribe()
        except Exception:
            self.running = False
            self.bridge.responses_active = False
            raise
        self.tasks = [asyncio.create_task(self.consume()), asyncio.create_task(self.work())]
        config = self.repo.config()
        log.info('Respondedor iniciado em %s; %s automação(ões) ativa(s). O bot de ofertas permanece independente.',
                 'simulação (sem enviar)' if config['settings']['dryRun'] else 'modo real',
                 len([g for g in config['groups'] if g['enabled']]))
        self.changed()

    async def subscribe(self):
        groups = [g['externalId'] for g in self.repo.config()['groups'] if g['enabled']] if self.running else []
        await self.bridge.configure_responses(groups, self.started)

    async def resubscribe(self):
        if not self.running:
            return
        try:
            await self.subscribe()
            log.info('Recebimento de respostas retomado; mensagens antigas não serão processadas.')
        except Exception as exc:
            log.warning('Não foi possível restaurar o recebimento de respostas: %s', exc)

    def disconnected(self):
        if not self.running:
            return
        with self.repo.connect() as db:
            changed = db.execute("UPDATE jobs SET state='CANCELLED',reason='Conexão interrompida; não reenviar automaticamente.' WHERE state='QUEUED'").rowcount
        if changed:
            log.warning('%s resposta(s) aguardando foram canceladas após a queda da conexão.', changed)
            self.changed()

    async def stop(self):
        self.running = False
        with self.repo.connect() as db:
            db.execute("UPDATE jobs SET state='CANCELLED',reason='Respondedor parado.' WHERE state='QUEUED'")
        # Não cancelar a confirmação de um envio que já entrou no transporte.
        if self.tasks:
            self.tasks[0].cancel()
        self.wake.set()
        if not any(not t.done() for t in self.tasks[1:]):
            self.bridge.responses_active = False
        try:
            if self.bridge.connected:
                await self.subscribe()
        except Exception:
            log.warning('Conexão indisponível; respostas locais já estão bloqueadas.')
        self.changed()

    async def close(self):
        await self.stop()
        if self.tasks:
            try:
                await asyncio.wait_for(asyncio.gather(*self.tasks, return_exceptions=True), 5)
            except asyncio.TimeoutError:
                for task in self.tasks:
                    task.cancel()
                with self.repo.connect() as db:
                    db.execute("UPDATE jobs SET state='UNCERTAIN',reason='Aplicativo encerrou antes da confirmação. Não repetir automaticamente.' WHERE state='SENDING'")

    def receive(self, payload):
        if not self.running:
            return
        received = 0
        for message in payload.get('messages', []):
            try:
                self.inbox.put_nowait(message)
                received += 1
            except asyncio.QueueFull:
                log.warning('Fila de entrada cheia; mensagem descartada com segurança.')
                break
        if received:
            log.info('%s mensagem(ns) nova(s) de grupo recebida(s) para avaliação.', received)

    async def consume(self):
        while self.running:
            message = await self.inbox.get()
            try:
                self.evaluate(message)
            except Exception:
                log.exception('Não foi possível avaliar uma mensagem. As ofertas não foram interrompidas.')

    def context(self, config, group_id, post_id=None):
        group = next((g for g in config['groups'] if g['id'] == group_id.split('|', 1)[0] and g['enabled']), None)
        campaign = next((c for c in config['campaigns'] if group and c['id'] == group['campaignId'] and c['enabled']), None)
        posts = [p for p in config['posts'] if campaign and p['id'] in campaign['postIds'] and p['enabled']]
        if not group or not campaign or not posts or (post_id and not any(p['id'] == post_id for p in posts)):
            raise ValueError('Grupo, campanha ou post desativado/indisponível.')
        return group, campaign, posts

    def evaluate(self, message, simulation=False):
        now, config = self.clock(), self.repo.config()
        group = next((g for g in config['groups'] if g['externalId'] == message.get('chat') and g['enabled']), None)
        if not group:
            group = next((g for g in config['groups'] if g['externalId'] == '*' and g['enabled']), None)
        if not group or (group['externalId'] == '*' and not is_group_jid(message.get('chat'))) or (not simulation and (not self.running or message.get('at', 0) < self.started or message.get('fromMe'))):
            return dict(state='IGNORED', reason='Mensagem antiga, própria ou grupo não habilitado.')
        simulated = simulation or config['settings']['dryRun']
        try:
            group, campaign, posts = self.context(config, group['id'])
        except ValueError as exc:
            return dict(state='IGNORED', reason=str(exc))
        identity = uuid.uuid4().hex
        group_key = f"{group['id']}|{message['chat']}" if group['externalId'] == '*' else group['id']
        with self.repo.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if not simulation:
                added = db.execute('INSERT OR IGNORE INTO messages VALUES(?,?,?,?,?)',
                                   (message['account'], message['chat'], message['id'], self.session, now)).rowcount
                if not added:
                    return dict(state='IGNORED', reason='Mensagem duplicada.')
            count = db.execute('SELECT COUNT(*) FROM messages WHERE session=? AND chat=?', (self.session, message['chat'])).fetchone()[0]
            rows = self.repo.records(db, simulated, min(self.started or now, now - 604800))
            reason = decide(group['rule'], config['settings'], rows, group=group_key, session=self.session,
                            now=now, message_count=max(1, count), chance=self.rng.random())
            recent = self.repo.recent_posts(db, group_key, simulated, campaign['noRepeatCount'])
            post = select_post(posts, recent, campaign['noRepeatCount'], self.rng.choice)
            delay = group['rule']['delay']
            wait = config['settings']['globalDelaySeconds'] + (delay['fixedSeconds'] if delay['mode'] == 'FIXED' else
                    self.rng.randint(delay['minSeconds'], delay['maxSeconds']) if delay['mode'] == 'RANDOM' else 0)
            state = 'IGNORED' if reason else 'SIMULATED' if simulation else 'QUEUED'
            if state == 'QUEUED' and db.execute("SELECT COUNT(*) FROM jobs WHERE state='QUEUED'").fetchone()[0] >= 256:
                state, reason = 'IGNORED', 'Fila de respostas cheia.'
            payload = dict(message=message, campaignId=campaign['id'], groupName=group['name'], postName=post['name'],
                           preview=post.get('content') or post.get('caption', ''))
            db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                       (identity, group_key, post['id'], self.session, message.get('account', 'simulation'),
                        now, now + wait, state, int(simulated), reason or ('Simulação: nenhum envio externo.' if simulation else 'Aguardando atraso configurado.'), encode(payload)))
        self.wake.set()
        self.changed()
        return dict(id=identity, state=state, reason=reason or f'Post selecionado: {post["name"]}. Atraso: {wait}s.', post=post)

    def validate_job(self, job):
        if not self.running or job['session'] != self.session:
            raise ValueError('Respondedor parado ou execução encerrada.')
        with self.repo.connect() as db:
            status = db.execute('SELECT state FROM jobs WHERE id=?', (job['id'],)).fetchone()
            rows = self.repo.records(db, job['simulated'], min(self.started or self.clock(), self.clock() - 604800), job['id'])
        if not status or status[0] != 'QUEUED':
            raise ValueError('Tarefa cancelada.')
        cfg, now = self.repo.config(), self.clock()
        group, campaign, posts = self.context(cfg, job['group_id'], job['post_id'])
        data = json.loads(job['data'])
        if campaign['id'] != data['campaignId'] or (group['externalId'] != '*' and data['message']['chat'] != group['externalId']):
            raise ValueError('Campanha ou grupo alterado durante a espera.')
        if group['externalId'] == '*' and job['group_id'] != f"{group['id']}|{data['message']['chat']}":
            raise ValueError('Grupo alterado durante a espera.')
        if group['externalId'] == '*' and any(g['enabled'] and g['externalId'] == data['message']['chat'] for g in cfg['groups']):
            raise ValueError('Este grupo passou a usar uma regra específica durante a espera.')
        if now - job['at'] > 10800:
            raise ValueError('Resposta expirada; não será recuperada automaticamente.')
        if bool(job['simulated']) != cfg['settings']['dryRun']:
            raise ValueError('Modo de simulação alterado; gere um novo gatilho.')
        # Reservas posteriores não invalidam a reserva mais antiga.
        rows = [r for r in rows if r['state'] not in ('QUEUED', 'SENDING') or r['at'] < job['at']]
        reason = decide(group['rule'], cfg['settings'], rows, group=job['group_id'], session=self.session,
                        now=now, message_count=1, revalidate=True)
        if reason:
            raise ValueError(reason)
        return next(p for p in posts if p['id'] == job['post_id']), data['message']

    async def work(self):
        try:
            while self.running:
                self.wake.clear()
                with self.repo.connect() as db:
                    row = db.execute("SELECT * FROM jobs WHERE state='QUEUED' ORDER BY due,at LIMIT 1").fetchone()
                job = dict(row) if row else None
                if job and job['due'] <= self.clock():
                    await self.deliver(job)
                    continue
                try:
                    await asyncio.wait_for(self.wake.wait(), min(30, max(.1, job['due'] - self.clock())) if job else 30)
                except asyncio.TimeoutError:
                    pass
        finally:
            if not self.running:
                self.bridge.responses_active = False

    async def deliver(self, job):
        entered = False
        def prepare():
            nonlocal entered
            post, message = self.validate_job(job)
            self.repo.finish(job['id'], 'SENDING', 'Aguardando confirmação do WhatsApp.')
            entered = True
            return post, message
        try:
            if job['simulated']:
                self.validate_job(job)
                self.repo.finish(job['id'], 'SIMULATED', 'Simulação concluída: nada enviado.', self.clock())
            else:
                await self.bridge.send_reply(prepare)
                self.repo.finish(job['id'], 'SENT', 'WhatsApp confirmou o recebimento pelo servidor.', self.clock())
            log.info('Resposta %s: %s.', job['id'][:8], 'simulada' if job['simulated'] else 'confirmada')
        except Exception as exc:
            before_send = getattr(exc, 'code', '') in ('CONTEXT_MISSING', 'GROUP_UNAVAILABLE', 'MEDIA_INVALID', 'NOT_CONNECTED')
            state = 'UNCERTAIN' if entered and not before_send else 'CANCELLED'
            self.repo.finish(job['id'], state, str(exc))
            log.warning('Resposta %s: %s. Sem repetição automática.', job['id'][:8], exc)
        except asyncio.CancelledError:
            self.repo.finish(job['id'], 'UNCERTAIN' if entered else 'CANCELLED',
                             'Envio interrompido pelo encerramento. Não repetir automaticamente.')
            raise
        finally:
            self.changed()
