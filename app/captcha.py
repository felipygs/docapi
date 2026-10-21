import time
import requests
from .config import NONECAP_API_KEY, NOPECHA_API_KEY

API_TOKEN_URL = "https://api.nopecha.com/token"
NONECAP_SOLVES_URL = "https://api.nonecap.com/v1/solves"


def resolver_hcaptcha_nonecap(website_url: str, site_key: str, *,
                            user_agent: str | None = None, timeout_s: int = 180) -> dict:
    """Obter token e user agent sem expor respostas externas em erros."""
    if not NONECAP_API_KEY:
        raise RuntimeError('NONECAP_API_KEY nao configurada')
    headers = {'Authorization': f'Bearer {NONECAP_API_KEY}'}
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
                response = requests.post(NONECAP_SOLVES_URL, json=payload, **kwargs)
            else:
                response = requests.get(f'{NONECAP_SOLVES_URL}/{solve_id}', **kwargs)
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


def _submit_job(captcha_type: str, website_url: str, site_key: str, enterprise: bool = False) -> str:
    """Submete job ao NoPeCHA e retorna o job_id."""
    if not NOPECHA_API_KEY:
        raise RuntimeError("NOPECHA_API_KEY nao configurada")

    payload = {
        "key": NOPECHA_API_KEY,
        "type": captcha_type,
        "sitekey": site_key,
        "url": website_url,
    }
    if enterprise:
        payload["enterprise"] = True

    r = requests.post(API_TOKEN_URL, json=payload, timeout=30)

    if not r.text.strip():
        raise RuntimeError(f"NoPeCHA retornou resposta vazia (HTTP {r.status_code})")

    resp = r.json()
    if "data" not in resp:
        raise RuntimeError(f"NoPeCHA submit erro: {resp.get('message', r.text[:200])}")
    return resp["data"]


def _poll_token(job_id: str, timeout_s: int = 180) -> str:
    """Aguarda resolucao do token pelo NoPeCHA."""
    for _ in range(timeout_s):
        time.sleep(1)
        r = requests.get(API_TOKEN_URL, params={
            "key": NOPECHA_API_KEY,
            "id": job_id,
        }, timeout=30)

        if not r.text.strip():
            continue

        data = r.json()
        if r.status_code == 200 and isinstance(data.get("data"), str) and len(data["data"]) > 100:
            return data["data"]
        if r.status_code == 409 or data.get("error") == 14:
            continue
        raise RuntimeError(f"NoPeCHA solve erro: {data.get('message', r.text[:200])}")
    raise RuntimeError(f"NoPeCHA timeout ({timeout_s}s)")


def _resolver_token(captcha_type: str, website_url: str, site_key: str,
                    enterprise: bool = False, timeout_s: int = 180) -> str:
    job_id = _submit_job(captcha_type, website_url, site_key, enterprise=enterprise)
    return _poll_token(job_id, timeout_s)


def submit_recaptcha_v2(website_url: str, site_key: str, enterprise: bool = False) -> str:
    """Submete job reCAPTCHA v2 e retorna job_id (nao-bloqueante)."""
    return _submit_job("recaptcha2", website_url, site_key, enterprise=enterprise)


def poll_recaptcha_token(job_id: str, timeout_s: int = 180) -> str:
    """Aguarda token do job reCAPTCHA (bloqueante)."""
    return _poll_token(job_id, timeout_s)


def resolver_hcaptcha(website_url: str, site_key: str) -> str:
    return _resolver_token("hcaptcha", website_url, site_key)


def resolver_recaptcha_v2(website_url: str, site_key: str, enterprise: bool = False) -> str:
    return _resolver_token("recaptcha2", website_url, site_key, enterprise=enterprise)
