"""Protocolo síncrono NoneCap, incluindo seu deadline e erros atuais."""
import time
import requests


def resolver_hcaptcha_nonecap(website_url: str, site_key: str, *,
                            user_agent: str | None = None, timeout_s: int = 180, api_key: str, solves_url: str) -> dict:
    """Obter token e user agent sem expor respostas externas em erros."""
    if not api_key:
        raise RuntimeError('NONECAP_API_KEY nao configurada')
    headers = {'Authorization': f'Bearer {api_key}'}
    payload = {'type': 'hcaptcha', 'sitekey': site_key, 'url': website_url}
    if user_agent:
        payload['user_agent'] = user_agent
    limite = time.monotonic() + timeout_s
    solve_id = None
    codigos = {
        'unauthorized', 'insufficient_credits', 'key_credit_limit_exceeded',
        'account_locked', 'forbidden', 'validation_error', 'rate_limited',
        'sitekey_rate_limited', 'concurrency_limit_exceeded', 'rate_capped',
        'maintenance', 'challenge_not_loaded', 'token_not_granted',
        'challenge_expired', 'challenge_errored', 'target_unreachable',
        'vision_error', 'internal_error', 'unsolvable_variant',
        'capacity_exhausted', 'cancelled', 'expired', 'proxy_error',
    }
    while True:
        restante = limite - time.monotonic()
        if restante <= 0:
            raise TimeoutError('NoneCap - prazo de resolucao esgotado')
        kwargs = dict(headers=headers, params={'wait': max(1, min(30, int(restante)))},
                      timeout=min(40, restante))
        try:
            if solve_id is None:
                response = requests.post(solves_url, json=payload, **kwargs)
            else:
                response = requests.get(f'{solves_url}/{solve_id}', **kwargs)
            dados = response.json()
        except requests.Timeout:
            raise TimeoutError('NoneCap - timeout de comunicacao') from None
        except (requests.RequestException, ValueError):
            raise RuntimeError('NoneCap - falha de comunicacao ou resposta invalida') from None
        if not isinstance(dados, dict):
            raise RuntimeError('NoneCap - resposta invalida')
        if response.status_code not in (200, 202) or dados.get('status') in ('failed', 'cancelled', 'expired'):
            erro = dados.get('error')
            codigo = erro.get('code') if isinstance(erro, dict) else None
            detalhe = codigo if codigo in codigos else 'falha_externa'
            raise RuntimeError(f'NoneCap - {detalhe} (HTTP {response.status_code})')
        if dados.get('status') == 'solved':
            if not isinstance(dados.get('token'), str) or not dados['token'].strip():
                raise RuntimeError('NoneCap - resposta sem token')
            return {'token': dados['token'], 'user_agent': dados.get('user_agent')}
        solve_id = dados.get('id')
        if dados.get('status') not in ('pending', 'solving') or not isinstance(solve_id, str) or not solve_id.startswith('solve_') or not solve_id.replace('_', '').isalnum():
            raise RuntimeError('NoneCap - resposta de acompanhamento invalida')
