import asyncio
import json
import tempfile
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock
from ofertas.autoresponder.models import validate_entity
from ofertas.autoresponder.repository import Repository
from ofertas.autoresponder.rules import decide, inside_schedule, select_post, DEFAULT_RULE, DEFAULT_SETTINGS
from ofertas.autoresponder.runtime import Runtime
from ofertas.autoresponder.service import Service
from ofertas.whatsapp_bridge import WhatsAppBridge


class RulesTests(unittest.TestCase):
    def setUp(self):
        self.settings = dict(DEFAULT_SETTINGS, globalCooldownSeconds=0)
        self.rule = dict(DEFAULT_RULE, cooldownSeconds=0)

    def test_night_window_uses_previous_weekday(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        t = datetime(2026, 10, 6, 1, tzinfo=ZoneInfo('America/Manaus')).timestamp()  # terça
        self.assertTrue(inside_schedule([dict(dayOfWeek=1, startMinute=22*60, endMinute=2*60)], t, 'America/Manaus'))
        self.assertFalse(inside_schedule([dict(dayOfWeek=2, startMinute=22*60, endMinute=2*60)], t, 'America/Manaus'))

    def test_zero_no_repeat_does_not_block_all_posts(self):
        posts = [dict(id='a'), dict(id='b')]
        self.assertEqual(select_post(posts, ['b','a'], 0, lambda options: options[0])['id'], 'a')
        self.assertEqual(select_post(posts, ['a'], 1, lambda options: options[0])['id'], 'b')

    def test_seven_modes_and_real_limits(self):
        now, rows = 1_800_000_000, [dict(group_id='g', at=1_800_000_000-100, session='one')]
        for mode in ('ALWAYS','COOLDOWN','ONCE_PER_SESSION','ONCE_PER_DAY','PERIOD_LIMIT','EVERY_X_MESSAGES','PROBABILITY'):
            rule = dict(self.rule, mode=mode)
            outcome = decide(rule, self.settings, rows, group='g', session='one', now=now, message_count=1, chance=0)
            self.assertEqual(bool(outcome), mode in ('ONCE_PER_SESSION','ONCE_PER_DAY'), mode)
        self.assertIn('hora', decide(self.rule, dict(self.settings,hourlyLimit=1), rows, group='g', session='two', now=now, message_count=1))
        self.assertIn('período', decide(dict(self.rule,mode='PERIOD_LIMIT'), self.settings,
                   [dict(group_id='g',at=now-1,session='other')], group='g',session='one',now=now,message_count=1))


class ProtocolEncodingTests(unittest.TestCase):
    def test_desktop_ndjson_preserves_utf8_in_windows_pipe(self):
        with tempfile.TemporaryDirectory() as directory:
            rows = [dict(id='1',command='autoresponder',payload=dict(action='save',kind='posts',
                value=dict(id='p1',name='Família 🎉',enabled=True,type='TEXT',content='Olá, ação! 🎉'))),
                dict(id='2',command='shutdown',payload={})]
            raw = ''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in rows).encode('utf-8')
            result = subprocess.run([sys.executable,'-m','ofertas','desktop'],input=raw,
                                    capture_output=True,env=os.environ|{'BOT_OFERTAS_HOME':directory},timeout=20)
            self.assertEqual(result.returncode,0,result.stderr.decode('utf-8',errors='replace'))
            response = next(json.loads(line) for line in result.stdout.decode('utf-8').splitlines() if '"id":"1"' in line)
            self.assertEqual(response['result']['posts'][0]['name'],'Família 🎉')
            self.assertEqual(response['result']['posts'][0]['content'],'Olá, ação! 🎉')


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.bridge = type('Bridge', (), dict(connected=True, responses_active=False,
                          configure_responses=AsyncMock(), send_reply=AsyncMock()))()
        self.service = Service(Path(self.temp.name), self.bridge)
        self.repo = self.service.repo
        self.repo.save('settings', dict(DEFAULT_SETTINGS, dryRun=False, globalCooldownSeconds=0))
        self.repo.save('posts', validate_entity('posts',dict(id='p',name='Oferta ✨',type='TEXT',content='Olá, ação! 🎉',enabled=True)))
        self.repo.save('campaigns', validate_entity('campaigns',dict(id='c',name='Campanha',postIds=['p'],enabled=True)))
        self.repo.save('groups', validate_entity('groups',dict(id='g',name='Amigos 🎉',externalId='12345@g.us',campaignId='c',enabled=True,
                       rule=dict(DEFAULT_RULE,mode='ALWAYS',cooldownSeconds=0))))

    async def asyncTearDown(self):
        await self.service.runtime.close()
        self.temp.cleanup()

    async def test_duplicate_self_old_and_delayed_revalidation(self):
        rt = self.service.runtime
        await rt.start()
        rt.work_task = rt.tasks[1]
        rt.tasks[1].cancel()  # fila controlada pelo teste
        await asyncio.gather(rt.tasks[1],return_exceptions=True)
        message=dict(account='123@s.whatsapp.net',chat='12345@g.us',id='msg1',at=rt.started,cacheId='ctx')
        first = rt.evaluate(message)
        self.assertEqual(first['state'],'QUEUED')
        self.assertEqual(rt.evaluate(message)['reason'],'Mensagem duplicada.')
        self.assertEqual(rt.evaluate(dict(message,id='old',at=rt.started-60))['state'],'IGNORED')
        self.assertEqual(rt.evaluate(dict(message,id='self',fromMe=True))['state'],'IGNORED')
        self.repo.save('posts',validate_entity('posts',dict(id='p',name='Oferta ✨',type='TEXT',content='Olá, ação! 🎉',enabled=False)))
        with self.repo.connect() as db:
            job=dict(db.execute('SELECT * FROM jobs WHERE id=?',(first['id'],)).fetchone())
        with self.assertRaisesRegex(ValueError,'desativado'):
            rt.validate_job(job)
        await rt.stop()
        self.assertEqual(self.repo.history()['counts']['CANCELLED'],1)
        self.bridge.send_reply.assert_not_awaited()

    async def test_live_group_message_reaches_shared_transport(self):
        rt = self.service.runtime
        await rt.start()
        rt.receive({'messages': [dict(account='me@s.whatsapp.net', chat='12345@g.us',
                                      id='nova-mensagem', at=rt.started + 1, cacheId='ctx')]})
        await asyncio.wait_for(self.bridge.send_reply.wait_until_awaited(), 2)
        for _ in range(20):
            if self.repo.history()['counts'].get('SENT'):
                break
            await asyncio.sleep(.01)
        self.assertEqual(self.repo.history()['counts'].get('SENT'), 1)
        self.assertEqual(self.repo.history()['total'], 1)

    async def test_import_keeps_simulation_and_accents(self):
        data=dict(version=1,settings=dict(DEFAULT_SETTINGS,dryRun=False,autoStart=True),
                  posts=self.repo.config()['posts'],campaigns=self.repo.config()['campaigns'],
                  groups=self.repo.config()['groups'])
        preview=await self.service.handle(dict(action='import_preview',text=json.dumps(data,ensure_ascii=False)))
        self.assertEqual(preview['counts']['groups'],1)
        result=await self.service.handle(dict(action='import',text=json.dumps(data,ensure_ascii=False)))
        self.assertTrue(result['settings']['dryRun'])
        self.assertFalse(result['settings']['autoStart'])
        self.assertFalse(result['groups'][0]['enabled'])
        self.assertEqual(result['posts'][0]['content'],'Olá, ação! 🎉')

    async def test_simulator_never_calls_transport_even_with_real_mode_saved(self):
        result=await self.service.handle(dict(action='simulate',groupId='g'))
        self.assertEqual(result['state'],'SIMULATED')
        self.bridge.send_reply.assert_not_awaited()

    async def test_recent_posts_remain_visible_after_a_week(self):
        import time
        with self.repo.connect() as db:
            db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                       ('old','g','p','old','simulation',time.time()-8*86400,0,'SIMULATED',1,'','{}'))
            self.assertEqual(self.repo.recent_posts(db,'g',True,1),['p'])

    async def test_backup_restore_is_scoped_and_requires_review(self):
        backup=(await self.service.handle(dict(action='backup')))['path']
        self.repo.delete('posts','p')
        restored=await self.service.handle(dict(action='restore',path=backup))
        self.assertTrue(restored['restored'])
        state=self.service.snapshot()
        self.assertEqual(state['posts'][0]['name'],'Oferta ✨')
        self.assertFalse(state['groups'][0]['enabled'])
        self.assertTrue(state['settings']['dryRun'])
        self.assertFalse(state['settings']['autoStart'])

    async def test_all_groups_uses_independent_limits_and_specific_override(self):
        self.repo.delete('groups','g')
        all_groups = dict(id='all',name='Todos os grupos',externalId='*',campaignId='c',enabled=True,
                          rule=dict(DEFAULT_RULE,mode='ONCE_PER_SESSION',cooldownSeconds=0))
        await self.service.handle(dict(action='save',kind='groups',value=all_groups))
        rt=self.service.runtime
        await rt.start()
        self.bridge.configure_responses.assert_awaited_with(['*'],rt.started)
        rt.tasks[1].cancel()
        await asyncio.gather(rt.tasks[1],return_exceptions=True)
        def message(chat,identifier):
            return dict(account='me@s.whatsapp.net',chat=chat,id=identifier,at=rt.started,cacheId=identifier)
        self.assertEqual(rt.evaluate(message('123@g.us','first'))['state'],'QUEUED')
        self.assertEqual(rt.evaluate(message('123@g.us','second'))['state'],'IGNORED')
        self.assertEqual(rt.evaluate(message('456@g.us','third'))['state'],'QUEUED')
        self.assertEqual(rt.evaluate(message('123@s.whatsapp.net','private'))['state'],'IGNORED')
        self.assertEqual(rt.evaluate(message('123@newsletter','channel'))['state'],'IGNORED')
        with self.repo.connect() as db:
            keys=[row[0] for row in db.execute("SELECT group_id FROM jobs WHERE state='QUEUED' ORDER BY at")]
        self.assertCountEqual(keys,['all|123@g.us','all|456@g.us'])
        self.repo.save('groups',validate_entity('groups',dict(id='g',name='Específico',externalId='123@g.us',campaignId='c',enabled=True,
                         rule=dict(DEFAULT_RULE,mode='ALWAYS',cooldownSeconds=0))))
        self.assertEqual(rt.evaluate(message('123@g.us','fourth'))['state'],'QUEUED')
        with self.repo.connect() as db:
            old=dict(db.execute("SELECT * FROM jobs WHERE group_id='all|123@g.us' AND state='QUEUED'").fetchone())
        with self.assertRaisesRegex(ValueError,'regra específica'):
            rt.validate_job(old)
        self.assertEqual((await self.service.handle(dict(action='simulate',groupId='all',chat='789@g.us')))['state'],'SIMULATED')
        with self.assertRaisesRegex(ValueError,'grupo real'):
            await self.service.handle(dict(action='simulate',groupId='all',chat='123@newsletter'))


class SharedTransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_offer_waiting_has_priority_before_reply(self):
        bridge = WhatsAppBridge()
        bridge.status = 'CONNECTED'
        order = []
        async def fake_request(action, **payload):
            order.append(action)
            await asyncio.sleep(.03)
            return {'messageId':'ok'}
        bridge._request = fake_request
        offer = asyncio.create_task(bridge.send_offer('123@g.us','Oferta'))
        await asyncio.sleep(0)
        reply = asyncio.create_task(bridge.send_reply(lambda: (
            dict(type='TEXT',content='Resposta'),dict(chat='123@g.us',cacheId='ctx'))))
        await asyncio.gather(offer,reply)
        self.assertEqual(order,['send_offer','send_reply'])


if __name__ == '__main__':
    unittest.main()
