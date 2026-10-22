from .dom import com_visibilidade
from .network import erro_rede_transitorio
from urllib.parse import urlsplit

from playwright.async_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError

from ..config import OPTANTES_URL
from ..errors import CaptchaBloqueadoError, CnpjInvalidoError, FalhaTransitoriaError
from .optantes_parser import adquirir_snapshot, falha, transformar_snapshot

_LOAD_TIMEOUT_MS = 10000

# O portal habilita o botão até iniciar AjaxMaisInfo, desabilita-o em
# beforeSend e oculta .loader em complete. Não basta esperar o primeiro h3.
_JS_ESTADO = com_visibilidade("""() => {
    /* visibilidade herdada */
    const errors = [...document.querySelectorAll('#spnMsgErro')];
    const erro = errors.some(el => visible(el) && el.textContent.trim());
    const loaders = [...document.querySelectorAll('.loader')];
    return {erro, loaders: loaders.length, carregando: loaders.some(visible)};
}""")
_JS_TERMINOU = com_visibilidade("""() => {
    /* visibilidade herdada */
    if ([...document.querySelectorAll('#spnMsgErro')].some(el => visible(el) && el.textContent.trim())) return true;
    return ![...document.querySelectorAll('.loader')].some(visible);
}""")


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
            if response.status >= 500 or response.status in (408, 429):
                raise FalhaTransitoriaError('Optantes - carregamento complementar: indisponibilidade temporaria')
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
        # A validação da consulta pode devolver o próprio formulário com erro
        # explícito (inclusive bloqueio Captcha), sem nenhum painel de resultado.
        rejeicao = '.validation-summary-errors li:visible, .field-validation-error[data-valmsg-for="Cnpj"]:visible'
        await page.wait_for_selector(
            f"#btnMaisInfo:visible, h3:has-text('Situação Atual'):visible, {rejeicao}",
            timeout=30000,
        )
        if await page.locator(rejeicao).count():
            mensagens = ' '.join(await page.locator(rejeicao).all_text_contents()).casefold()
            if 'captcha' in mensagens:
                raise CaptchaBloqueadoError('Optantes - consulta inicial: bloqueio Captcha da origem; consulta nao concluida')
            if 'cnpj' in mensagens and any(t in mensagens for t in ('inválido', 'invalido', 'cnpj válido', 'cnpj valido')):
                raise CnpjInvalidoError('Optantes - CNPJ rejeitado pela origem')
            falha('consulta inicial', 'consulta rejeitada pela origem')
        await _carregar_complemento(page)
        return transformar_snapshot(await adquirir_snapshot(page), cnpj_limpo)
    except (PlaywrightTimeoutError, TimeoutError):
        # Preservar 504 em _safe_call sem repassar URLs, inputs ou call logs.
        raise PlaywrightTimeoutError('Optantes - timeout na navegação ou carregamento complementar') from None
    except PlaywrightError as exc:
        if erro_rede_transitorio(exc):
            raise FalhaTransitoriaError('Optantes - falha temporaria de rede') from None
        raise RuntimeError('Optantes - navegação ou carregamento complementar: falha externa do navegador') from None
