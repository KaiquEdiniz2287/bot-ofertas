"""Validação da interface e de backups não confiáveis; nomes em UTF-8/NFC."""
import copy
import math
import re
import unicodedata
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from .rules import DEFAULT_RULE, DEFAULT_SETTINGS, MODES


def text(value, limit=4096):
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError(f'Texto inválido (máximo de {limit} caracteres).')
    return unicodedata.normalize('NFC', value).strip()


def number(value, low, high):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not low <= value <= high or value != int(value):
        raise ValueError(f'Informe um número inteiro entre {low} e {high}.')
    return int(value)


def flag(value):
    if not isinstance(value, bool):
        raise ValueError('Opção de ativação inválida.')
    return value


def is_group_jid(value):
    return isinstance(value, str) and re.fullmatch(r'\d+(?:-\d+)?@g\.us', value) is not None


def validate_settings(data):
    if not isinstance(data, dict):
        raise ValueError('Configurações inválidas.')
    result = DEFAULT_SETTINGS | data
    result = {k: result[k] for k in DEFAULT_SETTINGS}
    for k in ('dryRun', 'autoStart'):
        result[k] = flag(result[k])
    for k in ('globalCooldownSeconds', 'globalDelaySeconds'):
        result[k] = number(result[k], 0, 3600)
    for k in ('hourlyLimit', 'dailyLimit'):
        result[k] = number(result[k], 1, 10000)
    result['timezone'] = text(result['timezone'], 100)
    try:
        ZoneInfo(result['timezone'])
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError('Fuso horário IANA inválido.') from None
    return result


def validate_rule(data):
    if not isinstance(data, dict):
        raise ValueError('Regras do grupo inválidas.')
    r = copy.deepcopy(DEFAULT_RULE)
    r.update(data)
    if r['mode'] not in MODES:
        raise ValueError('Modo de resposta inválido.')
    for key, low, high in [('cooldownSeconds', 0, 86400), ('dailyLimit', 0, 10000),
                           ('everyXMessages', 1, 10000), ('probabilityPercent', 0, 100)]:
        r[key] = number(r[key], low, high)
    p = r['periodLimit'] or DEFAULT_RULE['periodLimit']
    r['periodLimit'] = dict(maxResponses=number(p['maxResponses'], 1, 10000),
                            periodSeconds=number(p['periodSeconds'], 1, 604800))
    d = DEFAULT_RULE['delay'] | (r['delay'] or {})
    if d['mode'] not in ('NONE', 'FIXED', 'RANDOM'):
        raise ValueError('Tipo de atraso inválido.')
    for k in ('fixedSeconds', 'minSeconds', 'maxSeconds'):
        d[k] = number(d[k], 0, 3600)
    if d['minSeconds'] > d['maxSeconds']:
        raise ValueError('O atraso mínimo deve ser menor que o máximo.')
    r['delay'] = d
    if not isinstance(r['schedules'], list) or len(r['schedules']) > 100:
        raise ValueError('Lista de horários inválida.')
    try:
        r['schedules'] = [dict(dayOfWeek=number(w['dayOfWeek'], 0, 6),
                               startMinute=number(w['startMinute'], 0, 1439),
                               endMinute=number(w['endMinute'], 0, 1440),
                               enabled=flag(w.get('enabled', True))) for w in r['schedules']]
    except (KeyError, TypeError) as exc:
        raise ValueError('Janela de horário incompleta ou inválida.') from exc
    return {k: r[k] for k in DEFAULT_RULE}


def validate_entity(kind, data):
    if not isinstance(data, dict):
        raise ValueError('Cadastro inválido.')
    result = dict(id=text(data.get('id', ''), 100), name=text(data.get('name', ''), 200),
                  enabled=flag(data.get('enabled', False)))
    if not result['id'] or not result['name']:
        raise ValueError('Nome e identificador são obrigatórios.')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', result['id']):
        raise ValueError('Identificador de cadastro inválido.')
    if kind == 'posts':
        typ = data.get('type', 'TEXT')
        if typ not in ('TEXT', 'LINK', 'IMAGE', 'VIDEO'):
            raise ValueError('Tipo de post inválido.')
        result.update(type=typ, content=text(data.get('content', '')), caption=text(data.get('caption', '')),
                      mediaPath=text(data.get('mediaPath', ''), 2048))
        if typ in ('TEXT', 'LINK') and not result['content']:
            raise ValueError('Preencha o texto do post.')
    elif kind == 'campaigns':
        ids = data.get('postIds', [])
        if not isinstance(ids, list) or len(ids) > 1000:
            raise ValueError('Lista de posts inválida.')
        result.update(postIds=list(dict.fromkeys(text(i, 100) for i in ids)),
                      noRepeatCount=number(data.get('noRepeatCount', 0), 0, 1000))
    elif kind == 'groups':
        jid = text(data.get('externalId', ''), 100)
        if jid != '*' and not is_group_jid(jid):
            raise ValueError('Selecione um grupo válido do WhatsApp.')
        result.update(externalId=jid, campaignId=text(data.get('campaignId') or '', 100),
                      rule=validate_rule(data.get('rule') or {}))
    else:
        raise ValueError('Cadastro não permitido.')
    return result
