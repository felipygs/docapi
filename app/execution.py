"""Execução de consultas: sessão, observabilidade e recuperação limitada.

Não interpreta resultados fiscais. O chamador fornece aquisição e validação.
Os dois escopos de prazo são deliberados: cadastro limpa fora do prazo da
aquisição; recuperação mantém o prazo compartilhado entre tentativas.
"""
import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager

from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from .browser import create_browser, fechar_browser
from .errors import CaptchaBloqueadoError, FalhaTransitoriaError

logger = logging.getLogger('app.consultar')
TRANSITORIOS = (CaptchaBloqueadoError, FalhaTransitoriaError, PlaywrightTimeoutError, TimeoutError)
Consulta = Callable[..., Awaitable[dict]]
Validador = Callable[[dict], None]


def _codigo_erro(erro: BaseException | None) -> str:
    if erro is None:
        return 'ok'
    if isinstance(erro, (TimeoutError, PlaywrightTimeoutError)):
        return 'timeout'
    if isinstance(erro, asyncio.CancelledError):
        return 'cancelado'
    return getattr(type(erro), 'codigo', 'erro_inesperado')


class Tentativa:
    """Recursos de uma tentativa; abrir deve ocorrer dentro do prazo do chamador."""

    def __init__(self, playwright, criar_browser):
        self.playwright = playwright
        self.criar_browser = criar_browser
        self.browser = None

    async def abrir_pagina(self):
        self.browser, context = await self.criar_browser(self.playwright)
        return await context.new_page()


@asynccontextmanager
async def _tentativa(playwright, modulo, numero, criar_browser, fechar):
    recursos = Tentativa(playwright, criar_browser)
    inicio = asyncio.get_running_loop().time()
    erro = None
    logger.info('modulo=%s tentativa=%d evento=inicio', modulo, numero)
    try:
        yield recursos
    except BaseException as exc:
        erro = exc
        raise
    finally:
        codigo = _codigo_erro(erro)
        try:
            if recursos.browser is not None:
                await fechar(recursos.browser, preservar_erro=erro is not None)
        except BaseException:
            if codigo == 'ok':
                codigo = 'cleanup_falhou'
            raise
        finally:
            logger.info('modulo=%s tentativa=%d duracao=%.3f codigo=%s',
                        modulo, numero, asyncio.get_running_loop().time() - inicio, codigo)


async def esperar(segundos: float) -> None:
    """Ponto de substituição do backoff sem alterar asyncio globalmente."""
    await asyncio.sleep(segundos)


async def executar_com_recuperacao(
    playwright, modulo: str, cnpj: str, consultar: Consulta, validar: Validador, *,
    max_tentativas=3, prazo_total=180, criar_browser=create_browser, fechar=fechar_browser,
) -> dict:
    if not 1 <= max_tentativas <= 3 or not 0 < prazo_total <= 180:
        raise ValueError('Recuperação exige 1 a 3 tentativas e prazo de até 180 segundos')
    prazo = asyncio.timeout(prazo_total)
    try:
        async with prazo:
            for numero in range(1, max_tentativas + 1):
                try:
                    async with _tentativa(playwright, modulo, numero, criar_browser, fechar) as tentativa:
                        page = await tentativa.abrir_pagina()
                        resultado = await consultar(page, cnpj)
                        validar(resultado)
                        return resultado
                except TRANSITORIOS:
                    if numero == max_tentativas:
                        raise
                await esperar(2 if numero == 1 else 5)
    except TimeoutError:
        if prazo.expired():
            raise TimeoutError(f'{modulo} - prazo total de recuperação esgotado') from None
        raise


async def executar_cadastro(
    playwright, cnpj: str, consultar: Consulta, *, prazo_total=180,
    criar_browser=create_browser, fechar=fechar_browser,
) -> dict:
    prazo = asyncio.timeout(prazo_total)
    async with _tentativa(playwright, 'CNPJ', 1, criar_browser, fechar) as tentativa:
        try:
            async with prazo:
                page = await tentativa.abrir_pagina()
                return await consultar(page, cnpj)
        except (TimeoutError, PlaywrightTimeoutError):
            if prazo.expired():
                raise TimeoutError('CNPJ - prazo total de consulta esgotado') from None
            raise
