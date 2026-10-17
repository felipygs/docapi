import asyncio
import logging

from .config import IS_LINUX

logger = logging.getLogger(__name__)
_CLEANUP_TIMEOUT_SECONDS = 5

LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-dev-shm-usage",
]


async def fechar_browser(browser, *, preservar_erro=False):
    """Liberar a sessão com tolerância máxima de cinco segundos para limpeza.

    Cancelamento não reinicia o prazo. Ao expirar, cancelar a operação de close
    sem aguardar indefinidamente; uma falha de limpeza nunca expõe sua mensagem
    nem substitui a falha principal da consulta.
    """
    fechamento = asyncio.create_task(browser.close())
    # Consumir também eventual erro posterior de uma operação que demore para
    # processar cancelamento, sem registrar mensagens externas.
    fechamento.add_done_callback(lambda task: None if task.cancelled() else task.exception())
    limite = asyncio.get_running_loop().time() + _CLEANUP_TIMEOUT_SECONDS
    cancelamento = None
    codigo = None
    try:
        while not fechamento.done():
            restante = limite - asyncio.get_running_loop().time()
            if restante <= 0:
                break
            try:
                await asyncio.wait({fechamento}, timeout=restante)
            except asyncio.CancelledError as exc:
                cancelamento = exc
        if not fechamento.done():
            codigo = 'cleanup_timeout'
            fechamento.cancel()
            # Dar à operação cooperativa um ciclo para liberar seus recursos.
            # asyncio.wait não aguarda indefinidamente a confirmação de cancel.
            try:
                await asyncio.wait({fechamento}, timeout=0)
            except asyncio.CancelledError as exc:
                cancelamento = exc
        else:
            try:
                fechamento.result()
            except BaseException:
                codigo = 'cleanup_falhou'
    finally:
        if not fechamento.done():
            fechamento.cancel()
    if codigo:
        logger.warning('codigo=%s', codigo)
    if cancelamento is not None:
        raise cancelamento from None
    if codigo and not preservar_erro:
        raise RuntimeError('Falha ao encerrar sessão do navegador') from None


async def create_browser(playwright):
    args = LAUNCH_ARGS.copy()
    if not IS_LINUX:
        args += ["--window-position=-32000,-32000", "--window-size=1,1"]

    browser = await playwright.chromium.launch(
        channel="chrome",
        headless=False,
        args=args,
    )
    try:
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            locale="pt-BR",
        )
    except BaseException:
        # Também liberar o processo se a criação do contexto for cancelada.
        await fechar_browser(browser, preservar_erro=True)
        raise
    return browser, context
