"""Motor puro: relógio e sorteio fornecidos pelo chamador."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

MODES = ('ALWAYS', 'COOLDOWN', 'ONCE_PER_SESSION', 'ONCE_PER_DAY',
         'PERIOD_LIMIT', 'EVERY_X_MESSAGES', 'PROBABILITY')
DEFAULT_SETTINGS = dict(dryRun=True, autoStart=False, globalCooldownSeconds=5,
                        hourlyLimit=30, dailyLimit=150, globalDelaySeconds=0,
                        timezone='America/Manaus')
DEFAULT_RULE = dict(mode='COOLDOWN', cooldownSeconds=60, everyXMessages=1,
                    probabilityPercent=100, dailyLimit=100,
                    periodLimit=dict(maxResponses=1, periodSeconds=60),
                    delay=dict(mode='NONE', fixedSeconds=0, minSeconds=0, maxSeconds=0),
                    schedules=[])


def day_start(now, timezone):
    return datetime.fromtimestamp(now, ZoneInfo(timezone)).replace(
        hour=0, minute=0, second=0, microsecond=0).timestamp()


def inside_schedule(schedules, now, timezone):
    windows = [w for w in schedules if w.get('enabled', True)]
    if not windows:
        return True
    current = datetime.fromtimestamp(now, ZoneInfo(timezone))
    day, minute = (current.weekday() + 1) % 7, current.hour * 60 + current.minute
    for w in windows:
        start, end = w['startMinute'], w['endMinute']
        if start < end and day == w['dayOfWeek'] and start <= minute < end:
            return True
        if start >= end and ((day == w['dayOfWeek'] and minute >= start)
                             or ((day - 1) % 7 == w['dayOfWeek'] and minute < end)):
            return True
    return False


def decide(rule, settings, rows, *, group, session, now, message_count, chance=0, revalidate=False):
    """Rows incluem reservas; o job atual deve ser excluído ao revalidar."""
    if not inside_schedule(rule['schedules'], now, settings['timezone']):
        return 'Fora do horário permitido.'
    today = day_start(now, settings['timezone'])
    own = [r for r in rows if r['group_id'] == group]
    for records, seconds, maximum, label in (
        (rows, 3600, settings['hourlyLimit'], 'Limite global por hora'),
        (rows, now - today, settings['dailyLimit'], 'Limite global diário'),
        (own, now - today, rule['dailyLimit'], 'Limite diário do grupo'),
    ):
        if maximum and sum(r['at'] >= now - seconds for r in records) >= maximum:
            return label + ' atingido.'
    for records, interval, label in ((rows, settings['globalCooldownSeconds'], 'Intervalo global'),
                                     (own, rule['cooldownSeconds'], 'Cooldown do grupo')):
        if records and interval and now - max(r['at'] for r in records) < interval:
            return label + ' ainda ativo.'
    mode = rule['mode']
    if mode == 'ONCE_PER_SESSION' and any(r['session'] == session for r in own):
        return 'O grupo já respondeu nesta execução.'
    if mode == 'ONCE_PER_DAY' and any(r['at'] >= today for r in own):
        return 'O grupo já respondeu hoje.'
    if mode == 'PERIOD_LIMIT' and sum(r['at'] >= now - rule['periodLimit']['periodSeconds'] for r in own) >= rule['periodLimit']['maxResponses']:
        return 'Limite do período atingido.'
    if not revalidate and mode == 'EVERY_X_MESSAGES' and message_count % rule['everyXMessages']:
        return 'Aguardando a próxima mensagem do intervalo.'
    if not revalidate and mode == 'PROBABILITY' and chance >= rule['probabilityPercent'] / 100:
        return 'Mensagem não sorteada pela probabilidade.'
    return ''


def select_post(posts, recent, no_repeat, choose):
    count = min(no_repeat, max(0, len(posts) - 1))
    blocked = set(recent[:count]) if count else set()
    available = [p for p in posts if p['id'] not in blocked]
    return choose(available) if available else None
