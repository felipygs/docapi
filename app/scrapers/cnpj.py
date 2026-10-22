"""Cadastro pela consulta publica atual, com validacao de captcha e QSA."""
import asyncio
import re

from playwright.async_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError

from ..captcha import resolver_hcaptcha, resolver_hcaptcha_nonecap
from ..config import CNPJ_URL, NONECAP_API_KEY, NOPECHA_API_KEY
from ..errors import CaptchaBloqueadoError, DadosIncompletosError
from .cnpj_parser import parse_cadastro


# Guardar o callback antes da carga evita depender de detalhes internos do Angular.
_JS_CAPTURAR_CALLBACK = """(() => {
    let api;
    Object.defineProperty(window, 'hcaptcha', {
        configurable: true,
        get: () => api,
        set: value => {
            api = value;
            const render = value.render;
            value.render = function(element, options) {
                window.__docapiCaptcha = options;
                return render.call(this, element, options);
            };
        }
    });
})()"""


async def _ler_resposta(response, etapa):
    if response.status != 200:
        raise RuntimeError(f'CNPJ - falha ao consultar {etapa} (HTTP {response.status})')
    try:
        dados = await response.json()
    except (ValueError, PlaywrightError):
        raise DadosIncompletosError(f'CNPJ - resposta invalida de {etapa}') from None
    if not isinstance(dados, dict):
        raise DadosIncompletosError(f'CNPJ - resposta incompleta de {etapa}')
    return dados


async def _resolver_captcha(page):
    await page.wait_for_function('window.__docapiCaptcha?.sitekey', timeout=15000)
    if NONECAP_API_KEY:
        sitekey = await page.evaluate('window.__docapiCaptcha.sitekey')
        user_agent = await page.evaluate('navigator.userAgent')
        solucao = await asyncio.to_thread(resolver_hcaptcha_nonecap, CNPJ_URL, sitekey, user_agent=user_agent)
        if solucao.get('user_agent'):
            await page.context.set_extra_http_headers({'User-Agent': solucao['user_agent']})
        token = solucao['token']
    elif NOPECHA_API_KEY:
        sitekey = await page.evaluate('window.__docapiCaptcha.sitekey')
        token = await asyncio.to_thread(resolver_hcaptcha, CNPJ_URL, sitekey)
    else:
        frame = page.frame_locator('iframe[title*="Widget contendo"]')
        await frame.locator('#checkbox').click(timeout=5000)
        try:
            await frame.locator('[aria-checked="true"]').wait_for(timeout=8000)
        except PlaywrightTimeoutError:
            raise CaptchaBloqueadoError('CNPJ - captcha nao resolvido; configure NONECAP_API_KEY') from None
        return
    await page.evaluate('(token) => window.__docapiCaptcha.callback(token)', token)


async def consultar_cnpj(page, cnpj_limpo: str, max_retries: int = 3) -> dict:
    if not 1 <= max_retries <= 3:
        raise ValueError('CNPJ - numero de tentativas deve estar entre 1 e 3')
    await page.add_init_script(_JS_CAPTURAR_CALLBACK)
    for tentativa in range(max_retries):
        resposta_cadastro = asyncio.get_running_loop().create_future()
        api_base = CNPJ_URL.rstrip('/') + '/api/v1/consultapublica/'

        def corresponde(response, sufixo):
            return response.url == api_base + sufixo

        def capturar(response):
            if corresponde(response, 'cnpj/' + cnpj_limpo) and not resposta_cadastro.done():
                resposta_cadastro.set_result(response)

        page.on('response', capturar)
        try:
            await page.goto(CNPJ_URL, wait_until='domcontentloaded', timeout=30000)
            await page.locator('#alert-cnpj input').fill(cnpj_limpo)
            await _resolver_captcha(page)
            async with page.expect_response(lambda r: corresponde(r, 'validar-captcha'), timeout=30000) as validacao:
                await page.get_by_role('button', name=re.compile(r'^\W*Consultar$', re.I)).click(timeout=10000)
            captcha = await _ler_resposta(await validacao.value, 'captcha')
            if captcha.get('valido') is not True:
                if tentativa + 1 < max_retries:
                    await asyncio.sleep(2)
                    continue
                raise CaptchaBloqueadoError('CNPJ - captcha rejeitado pela Receita')
            response = await asyncio.wait_for(resposta_cadastro, timeout=30)
            dados = await _ler_resposta(response, 'cadastro')
            # QSA depende do estado em memoria da SPA e da mesma sessao.
            await page.wait_for_url('**/comprovante', timeout=15000)
            async with page.expect_response(lambda r: corresponde(r, 'qsa/' + cnpj_limpo), timeout=15000) as resposta_qsa:
                await page.get_by_role('button', name=re.compile('Consultar QSA', re.I)).click(timeout=10000)
            qsa = await _ler_resposta(await resposta_qsa.value, 'QSA')
            await page.wait_for_url('**/qsa', timeout=15000)
            return parse_cadastro(dados, qsa, cnpj_limpo)
        except (PlaywrightTimeoutError, TimeoutError):
            raise TimeoutError('CNPJ - timeout na consulta externa') from None
        except PlaywrightError:
            raise RuntimeError('CNPJ - falha de comunicacao com a Receita') from None
        finally:
            page.remove_listener('response', capturar)
            if not resposta_cadastro.done():
                resposta_cadastro.cancel()
