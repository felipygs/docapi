"""Protocolo NoPeCHA; polling e exceções preservados por compatibilidade."""
import time
import requests


def _submit_job(captcha_type: str, website_url: str, site_key: str, enterprise: bool = False, *, api_key: str, token_url: str) -> str:
    """Submete job ao NoPeCHA e retorna o job_id."""
    if not api_key:
        raise RuntimeError("NOPECHA_API_KEY nao configurada")

    payload = {
        "key": api_key,
        "type": captcha_type,
        "sitekey": site_key,
        "url": website_url,
    }
    if enterprise:
        payload["enterprise"] = True

    r = requests.post(token_url, json=payload, timeout=30)

    if not r.text.strip():
        raise RuntimeError(f"NoPeCHA retornou resposta vazia (HTTP {r.status_code})")

    resp = r.json()
    if "data" not in resp:
        raise RuntimeError(f"NoPeCHA submit erro: {resp.get('message', r.text[:200])}")
    return resp["data"]


def _poll_token(job_id: str, timeout_s: int = 180, *, api_key: str, token_url: str) -> str:
    """Aguarda resolucao do token pelo NoPeCHA."""
    for _ in range(timeout_s):
        time.sleep(1)
        r = requests.get(token_url, params={
            "key": api_key,
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
