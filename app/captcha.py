"""Fachada compatível; seleção do fornecedor continua no scraper CNPJ."""
import time
import requests
from .config import NONECAP_API_KEY, NOPECHA_API_KEY
from .captcha_providers import nonecap, nopecha

API_TOKEN_URL = "https://api.nopecha.com/token"
NONECAP_SOLVES_URL = "https://api.nonecap.com/v1/solves"


def resolver_hcaptcha_nonecap(website_url: str, site_key: str, *,
                            user_agent: str | None = None, timeout_s: int = 180) -> dict:
    return nonecap.resolver_hcaptcha_nonecap(
        website_url, site_key, user_agent=user_agent, timeout_s=timeout_s,
        api_key=NONECAP_API_KEY, solves_url=NONECAP_SOLVES_URL,
    )


def _submit_job(captcha_type: str, website_url: str, site_key: str, enterprise: bool = False) -> str:
    return nopecha._submit_job(captcha_type, website_url, site_key, enterprise,
                              api_key=NOPECHA_API_KEY, token_url=API_TOKEN_URL)


def _poll_token(job_id: str, timeout_s: int = 180) -> str:
    return nopecha._poll_token(job_id, timeout_s,
                              api_key=NOPECHA_API_KEY, token_url=API_TOKEN_URL)


def _resolver_token(captcha_type: str, website_url: str, site_key: str,
                    enterprise: bool = False, timeout_s: int = 180) -> str:
    job_id = _submit_job(captcha_type, website_url, site_key, enterprise=enterprise)
    return _poll_token(job_id, timeout_s)


def resolver_hcaptcha(website_url: str, site_key: str) -> str:
    return _resolver_token("hcaptcha", website_url, site_key)
