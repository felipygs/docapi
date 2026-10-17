from urllib.parse import urlsplit

from playwright.async_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError

from ..config import OPTANTES_URL
from .optantes_parser import adquirir_snapshot, falha, transformar_snapshot

_LOAD_TIMEOUT_MS = 10000

# O portal habilita o botão até iniciar AjaxMaisInfo, desabilita-o em
# beforeSend e oculta .loader em complete. Não basta esperar o primeiro h3.
_JS_ESTADO = """() => {
    const visible = el => {
        for (let p = el; p; p = p.parentElement) {
            const style = getComputedStyle(p);
            if (p.hidden || style.display === 'none' || style.visibility === 'hidden') return false;
        }
        return true;
    };
    const errors = [...document.querySelectorAll('#spnMsgErro')];
    const erro = errors.some(el => visible(el) && el.textContent.trim());
    const loaders = [...document.querySelectorAll('.loader')];
    return {erro, loaders: loaders.length, carregando: loaders.some(visible)};
}"""
_JS_TERMINOU = """() => {
    const visible = el => {
        for (let p = el; p; p = p.parentElement) {
            const s = getComputedStyle(p);
            if (p.hidden || s.display === 'none' || s.visibility === 'hidden') return false;
        }
        return true;
    };
    if ([...document.querySelectorAll('#spnMsgErro')].some(el => visible(el) && el.textContent.trim())) return true;
    return ![...document.querySelectorAll('.loader')].some(visible);
}"""


def _resposta_mais_info(response) -> bool:
    url = urlsplit(response.url)
    origem = urlsplit(OPTANTES_URL)
    return url.netloc == origem.netloc and url.path.rstrip('/').endswith('/Home/AjaxMaisInfo')


async def _carregar_complemento(page) -> None:
    estado = await page.evaluate(_JS_ESTADO)
    if estado['erro']:
        falha('carregamento complementar', 'erro informado pela origem')
    if not estado['loaders']:
        falha('carregamento complementar', 'loader obrigatório ausente')
    botoes = page.locator('#btnMaisInfo')
    if await botoes.count() != 1:
        falha('carregamento complementar', 'botão obrigatório ausente ou duplicado')
    btn = botoes
    if not await btn.is_disabled():
        try:
            async with page.expect_response(_resposta_mais_info, timeout=_LOAD_TIMEOUT_MS) as pending:
                await btn.click()
            response = await pending.value
        except PlaywrightTimeoutError:
            # Falha de transporte pode chamar errorFunc sem produzir response.
            # A mensagem explícita prevalece sobre ausência de evento de rede.
            if (await page.evaluate(_JS_ESTADO))['erro']:
                falha('carregamento complementar', 'erro informado pela origem')
            raise
        if not response.ok:
            falha('carregamento complementar', 'AjaxMaisInfo retornou erro HTTP')
        # A resposta de rede pode anteceder success/complete e o DOM final.
        # O prazo desta espera cobre também um corpo de resposta não concluído.
        await page.wait_for_function(_JS_TERMINOU, timeout=_LOAD_TIMEOUT_MS)
    elif estado['carregando']:
        await page.wait_for_function(_JS_TERMINOU, timeout=_LOAD_TIMEOUT_MS)
    estado = await page.evaluate(_JS_ESTADO)
    if estado['erro']:
        falha('carregamento complementar', 'erro informado pela origem')
    if estado['carregando']:
        falha('carregamento complementar', 'carregamento não concluído')


async def consultar_optantes(page, cnpj_limpo: str, max_retries: int = 3) -> dict:
    """Consulta na mesma sessão e devolve somente o contrato JSON validado.

    max_retries é mantido na assinatura; não repetir captcha/origem nem trocar
    sessão para tentar converter falha externa em dados fiscais vazios.
    """
    try:
        await page.goto(OPTANTES_URL, wait_until='domcontentloaded')
        await page.wait_for_selector('#Cnpj', timeout=10000)
        await page.fill('#Cnpj', cnpj_limpo)
        await page.click('text=Consultar')
        await page.wait_for_selector("#btnMaisInfo, h3:has-text('Situação Atual')", timeout=30000)
        await _carregar_complemento(page)
        return transformar_snapshot(await adquirir_snapshot(page), cnpj_limpo)
    except (PlaywrightTimeoutError, TimeoutError):
        # Preservar 504 em _safe_call sem repassar URLs, inputs ou call logs.
        raise PlaywrightTimeoutError('Optantes - timeout na navegação ou carregamento complementar') from None
    except PlaywrightError:
        raise RuntimeError('Optantes - navegação ou carregamento complementar: falha externa do navegador') from None
