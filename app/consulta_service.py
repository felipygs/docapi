"""Sequencia e composicao das consultas, separadas da execucao de sessoes."""
from playwright.async_api import async_playwright
from .browser import create_browser, fechar_browser
from .errors import CnpjInvalidoError, NaoOptanteError
from .identity import normalizar_cnpj
from .scrapers import consultar_cnpj, consultar_dasn, consultar_optantes
from .consulta_validation import validar_dasn, validar_optantes
from .dasn_outcome import confirmar_nao_optante
from .execution import executar_cadastro, executar_com_recuperacao

_CADASTRO_TIMEOUT_SECONDS = 180


def _limpar_cnpj(cnpj: str) -> str:
    try:
        return normalizar_cnpj(cnpj)
    except ValueError:
        raise CnpjInvalidoError(f"CNPJ invalido: {cnpj}") from None


async def _consultar_com_recuperacao(
    playwright, modulo, cnpj, consultar, *, max_tentativas=3, prazo_total=180,
):
    # Compatibilidade do helper existente; o executor recebe apenas um validador.
    validadores = {'DASN': validar_dasn, 'Optantes': validar_optantes}
    if modulo not in validadores:
        raise ValueError('Módulo de recuperação desconhecido')
    return await executar_com_recuperacao(
        playwright, modulo, cnpj, consultar, validadores[modulo],
        max_tentativas=max_tentativas, prazo_total=prazo_total,
        criar_browser=create_browser, fechar=fechar_browser,
    )


async def _consultar_cadastro(playwright, cnpj_limpo):
    return await executar_cadastro(
        playwright, cnpj_limpo, consultar_cnpj, prazo_total=_CADASTRO_TIMEOUT_SECONDS,
        criar_browser=create_browser, fechar=fechar_browser,
    )


async def _consultar_dasn_com_situacao(playwright, cnpj):
    try:
        return await _consultar_com_recuperacao(playwright, 'DASN', cnpj, consultar_dasn), None
    except NaoOptanteError:
        optantes = await _consultar_com_recuperacao(playwright, 'Optantes', cnpj, consultar_optantes)
        return confirmar_nao_optante(cnpj, optantes), optantes


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
