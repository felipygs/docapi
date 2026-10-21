import asyncio
import logging

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from pydantic import ValidationError

from .browser import create_browser, fechar_browser
from .errors import CaptchaBloqueadoError, CnpjInvalidoError, DadosIncompletosError, FalhaTransitoriaError, NaoOptanteError
from .models import DasnResponse, DasnNaoOptanteResponse, OptantesResponse
from .scrapers import consultar_cnpj, consultar_dasn, consultar_optantes

logger = logging.getLogger(__name__)
_CADASTRO_TIMEOUT_SECONDS = 180


def _limpar_cnpj(cnpj: str) -> str:
    cnpj_limpo = cnpj.replace(".", "").replace("/", "").replace("-", "")
    if len(cnpj_limpo) != 14 or not cnpj_limpo.isdigit():
        raise CnpjInvalidoError(f"CNPJ invalido: {cnpj}")
    return cnpj_limpo


async def _consultar_com_recuperacao(
    playwright, modulo, cnpj, consultar, *, max_tentativas=3, prazo_total=180,
):
    """Repetir somente falhas transitórias, sempre com uma sessão independente.

    O prazo monotônico inclui abertura, aquisição, validação e espera. Cada
    fechamento tem tolerância adicional de até cinco segundos para limpeza.
    Os scrapers classificam bloqueios e respostas inválidas; erros genéricos
    não são evidência suficiente para repetir a consulta.
    """
    modelos = {'DASN': DasnResponse, 'Optantes': OptantesResponse}
    if modulo not in modelos:
        raise ValueError('Módulo de recuperação desconhecido')
    if not 1 <= max_tentativas <= 3 or not 0 < prazo_total <= 180:
        raise ValueError('Recuperação exige 1 a 3 tentativas e prazo de até 180 segundos')

    loop = asyncio.get_running_loop()
    prazo = asyncio.timeout(prazo_total)
    try:
        async with prazo:
            for tentativa in range(1, max_tentativas + 1):
                browser = None
                inicio = loop.time()
                codigo = 'erro_inesperado'
                preservar_erro = True
                logger.info('modulo=%s tentativa=%d evento=inicio', modulo, tentativa)
                try:
                    browser, context = await create_browser(playwright)
                    page = await context.new_page()
                    resultado = await consultar(page, cnpj)
                    try:
                        validado = modelos[modulo].model_validate(resultado)
                    except ValidationError:
                        raise DadosIncompletosError(
                            f'{modulo} - resposta incompatível com o contrato'
                        ) from None
                    if modulo == 'DASN' and (
                        not validado.razao_social or not validado.razao_social.strip()
                        or not validado.declaracoes
                    ):
                        raise DadosIncompletosError(f'{modulo} - resposta incompleta')
                    codigo = 'ok'
                    preservar_erro = False
                    return resultado
                except (CaptchaBloqueadoError, FalhaTransitoriaError, PlaywrightTimeoutError, TimeoutError) as exc:
                    if isinstance(exc, CaptchaBloqueadoError):
                        codigo = 'captcha_bloqueado'
                    elif isinstance(exc, FalhaTransitoriaError):
                        codigo = 'falha_transitoria'
                    else:
                        codigo = 'timeout'
                    if tentativa == max_tentativas:
                        raise
                except asyncio.CancelledError:
                    codigo = 'cancelado'
                    raise
                except Exception as exc:
                    # Somente códigos definidos localmente, nunca mensagem,
                    # URL, CNPJ, cookie, token ou traceback externo.
                    codigo = getattr(type(exc), 'codigo', 'erro_inesperado')
                    raise
                finally:
                    try:
                        if browser is not None:
                            await fechar_browser(browser, preservar_erro=preservar_erro)
                    except BaseException:
                        if codigo == 'ok':
                            codigo = 'cleanup_falhou'
                        raise
                    finally:
                        logger.info(
                            'modulo=%s tentativa=%d duracao=%.3f codigo=%s',
                            modulo, tentativa, loop.time() - inicio, codigo,
                        )
                await asyncio.sleep(2 if tentativa == 1 else 5)
    except TimeoutError:
        if prazo.expired():
            raise TimeoutError(f'{modulo} - prazo total de recuperação esgotado') from None
        raise


async def _consultar_dasn_com_situacao(playwright, cnpj):
    try:
        return await _consultar_com_recuperacao(playwright, 'DASN', cnpj, consultar_dasn), None
    except NaoOptanteError:
        optantes = await _consultar_com_recuperacao(playwright, 'Optantes', cnpj, consultar_optantes)
        evidencia = OptantesResponse.model_validate(optantes)
        if evidencia.cnpj_consultado != cnpj or evidencia.cnpj_matriz[:8] != cnpj[:8]:
            raise DadosIncompletosError('DASN - divergencia de identidade na conferencia Optantes') from None
        if evidencia.simei.enquadrado or evidencia.simei.periodos_anteriores or evidencia.simei.eventos_futuros:
            raise DadosIncompletosError('DASN - divergencia entre resposta 33001 e situacao ou historico SIMEI; conferir') from None
        resultado = DasnNaoOptanteResponse(
            status='nao_optante_simei_confirmado_por_optantes', codigo_origem='33001',
            cnpj=cnpj, razao_social=evidencia.nome_empresarial,
            situacao_declaracoes='nao_consultadas', declaracoes=None, pendentes=None,
            mei_baixada=None, data_baixa=None, optantes_consultado_em=evidencia.consultado_em,
            mensagem='Receita informou nao optante pelo SIMEI (33001); Optantes confirmou ausencia de enquadramento atual e periodos anteriores. Declaracoes e pendencias DASN nao verificadas.',
        )
        return resultado.model_dump(mode='json'), optantes


async def _consultar_cadastro(playwright, cnpj_limpo):
    """Limitar todo o cadastro, inclusive abertura e tentativas de captcha."""
    browser = None
    preservar_erro = True
    inicio = asyncio.get_running_loop().time()
    codigo = 'erro_inesperado'
    prazo = asyncio.timeout(_CADASTRO_TIMEOUT_SECONDS)
    logger.info('modulo=CNPJ tentativa=1 evento=inicio')
    try:
        async with prazo:
            browser, context = await create_browser(playwright)
            page = await context.new_page()
            resultado = await consultar_cnpj(page, cnpj_limpo)
        codigo = 'ok'
        preservar_erro = False
        return resultado
    except (TimeoutError, PlaywrightTimeoutError):
        codigo = 'timeout'
        if prazo.expired():
            raise TimeoutError('CNPJ - prazo total de consulta esgotado') from None
        raise
    except asyncio.CancelledError:
        codigo = 'cancelado'
        raise
    except Exception as exc:
        codigo = getattr(type(exc), 'codigo', 'erro_inesperado')
        raise
    finally:
        try:
            if browser is not None:
                await fechar_browser(browser, preservar_erro=preservar_erro)
        except BaseException:
            if codigo == 'ok':
                codigo = 'cleanup_falhou'
            raise
        finally:
            logger.info(
                'modulo=CNPJ tentativa=1 duracao=%.3f codigo=%s',
                asyncio.get_running_loop().time() - inicio, codigo,
            )


async def consultar_mei(cnpj: str) -> dict:
    cnpj_limpo = _limpar_cnpj(cnpj)

    async with async_playwright() as p:
        cadastro = await _consultar_cadastro(p, cnpj_limpo)
        dasn, optantes = await _consultar_dasn_com_situacao(p, cnpj_limpo)
        if optantes is None:
            optantes = await _consultar_com_recuperacao(p, 'Optantes', cnpj_limpo, consultar_optantes)

    return {
        "cnpj": cnpj,
        "cadastro": cadastro,
        "dasn": dasn,
        "optantes": optantes,
    }


async def consultar_apenas_cnpj(cnpj: str) -> dict:
    cnpj_limpo = _limpar_cnpj(cnpj)

    async with async_playwright() as p:
        resultado = await _consultar_cadastro(p, cnpj_limpo)

    return resultado


async def consultar_apenas_dasn(cnpj: str) -> dict:
    cnpj_limpo = _limpar_cnpj(cnpj)

    async with async_playwright() as p:
        resultado, _ = await _consultar_dasn_com_situacao(p, cnpj_limpo)
        return resultado


async def consultar_apenas_optantes(cnpj: str) -> dict:
    cnpj_limpo = _limpar_cnpj(cnpj)

    async with async_playwright() as p:
        return await _consultar_com_recuperacao(p, 'Optantes', cnpj_limpo, consultar_optantes)



