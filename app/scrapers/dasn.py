import re
import unicodedata

from playwright.async_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError

from ..config import DASN_URL
from ..errors import (
    CaptchaBloqueadoError, CnpjInvalidoError, DadosIncompletosError,
    FalhaTransitoriaError, IdentidadeDivergenteError, NaoOptanteError,
)
from .utils import capturar_alertas
from .parsers import data_br_para_iso, parse_nome_empresarial, parse_status_declaracao


def _normalizar(texto):
    return ''.join(c for c in unicodedata.normalize('NFD', texto.strip().lower())
                   if not unicodedata.combining(c))


def _validar_declaracoes(nome, declaracoes):
    if not parse_nome_empresarial(nome) or not declaracoes:
        raise DadosIncompletosError('DASN - identificacao ou declaracoes ausentes')
    for declaracao in declaracoes:
        ano = declaracao['ano']
        if not re.fullmatch(r'[0-9]{4}', ano) or not 2009 <= int(ano) <= 9999:
            raise DadosIncompletosError('DASN - ano de declaracao invalido')
        status_normalizado = _normalizar(declaracao['status'])
        if not re.fullmatch(
            r'(?:nao apresentada|nao optante|baixada|apresentada em [0-9]{2}/[0-9]{2}/[0-9]{4})',
            status_normalizado,
        ):
            raise DadosIncompletosError('DASN - status de declaracao desconhecido')
        if status_normalizado.startswith('apresentada em '):
            _, data_apresentacao = parse_status_declaracao(declaracao['status'])
            if data_apresentacao is None:
                raise DadosIncompletosError('DASN - data de apresentacao invalida')
        data_baixa = declaracao['data_baixa']
        if data_baixa != '-' and (
            not re.fullmatch(r'[0-9]{2}/[0-9]{2}/[0-9]{4}', data_baixa)
            or data_br_para_iso(data_baixa) is None
        ):
            raise DadosIncompletosError('DASN - data de baixa invalida')
        if _normalizar(declaracao['situacao_especial']) == 'extincao' and data_baixa == '-':
            raise DadosIncompletosError('DASN - extincao sem data de baixa')


async def consultar_dasn(page, cnpj_limpo: str) -> dict:
    try:
        return await _consultar_dasn(page, cnpj_limpo)
    except (PlaywrightTimeoutError, TimeoutError):
        raise PlaywrightTimeoutError('DASN - timeout na consulta externa') from None
    except PlaywrightError as exc:
        if any(code in str(exc) for code in ('net::ERR_CONNECTION_', 'net::ERR_NETWORK_', 'net::ERR_NAME_NOT_RESOLVED', 'net::ERR_INTERNET_DISCONNECTED')):
            raise FalhaTransitoriaError('DASN - falha temporaria de rede') from None
        raise RuntimeError('DASN - falha externa de navegacao') from None


async def _consultar_dasn(page, cnpj_limpo: str) -> dict:
    await page.goto(f"{DASN_URL}/Identificacao", wait_until="domcontentloaded")
    await page.wait_for_selector("#identificacao-cnpj", timeout=10000)
    await page.fill("#identificacao-cnpj", cnpj_limpo)

    await page.click("#identificacao-continuar")
    try:
        # A Receita pode manter /Identificacao com um bloqueio explícito ou
        # redirecionar para /Erro. Esperar somente a URL de sucesso oculta
        # essas respostas durante 30 segundos.
        await page.wait_for_selector(
            "#iniciar-ano-calendario:visible, #identificacao-warning:visible, .template-erro:visible",
            timeout=30000,
        )
    except PlaywrightTimeoutError:
        alertas = await capturar_alertas(page)
        if alertas:
            raise RuntimeError(f"DASN - Falha: {' | '.join(alertas)[:300]}") from None
        raise PlaywrightTimeoutError("DASN - timeout ao aguardar resultado") from None

    if not await page.locator("#iniciar-ano-calendario").is_visible():
        mensagens = await page.locator("#identificacao-warning:visible, .template-erro:visible p").all_text_contents()
        detalhe = " | ".join(m.strip() for m in mensagens if m.strip()) or "Resposta inesperada"
        normalizado = _normalizar(detalhe)
        if '13896' in normalizado or 'captcha' in normalizado:
            raise CaptchaBloqueadoError('DASN - bloqueio Captcha da origem; consulta nao concluida (13896)')
        if 'cnpj invalido' in normalizado:
            raise CnpjInvalidoError('DASN - CNPJ rejeitado pela origem')
        if '33001' in normalizado:
            raise NaoOptanteError('DASN - 33001: Contribuinte nao optante pelo Simei')
        raise RuntimeError('DASN - origem retornou erro; consulta nao concluida')

    # Conferir a identidade exibida na origem, nunca o campo digitado.
    cnpj_origem = await page.evaluate('''() => {
        const ps = [...document.querySelectorAll('p')];
        for (let i = 0; i + 1 < ps.length; i++) {
            if (ps[i].querySelector('strong')?.textContent.trim() === 'CNPJ:')
                return ps[i + 1].textContent.trim();
        }
        return null;
    }''')
    if cnpj_origem is not None and re.sub(r'[^0-9]', '', cnpj_origem) != cnpj_limpo:
        raise IdentidadeDivergenteError('DASN - identidade do CNPJ divergente')

    razao_social = await page.evaluate("""() => {
        const ps = document.querySelectorAll('p');
        for (let i = 0; i < ps.length; i++) {
            const strong = ps[i].querySelector('strong');
            if (strong && strong.textContent.includes('Raz') && i + 1 < ps.length)
                return ps[i + 1].textContent.trim();
        }
        return '';
    }""")

    declaracoes = await page.evaluate("""() => {
        const container = document.querySelector('#iniciar-ano-calendario');
        if (!container) return [];
        const radios = container.querySelectorAll('input[type="radio"]');
        return Array.from(radios).map(radio => {
            const parent = radio.parentElement;
            const spans = parent.querySelectorAll('span');
            let statusTexto = '', acao = '';
            spans.forEach(span => {
                const cls = span.className || '';
                const text = span.textContent.trim();
                if (cls.includes('br-tag')) acao = text;
                else if (text) statusTexto = text;
            });
            const extincao = (radio.dataset.situacaoEspecialTipo || '').trim().toLowerCase() === 'extinção';
            const baixada = extincao || acao.toLowerCase() === 'baixada' || statusTexto.toLowerCase() === 'baixada';
            const pendente = !radio.disabled && statusTexto.toLowerCase().includes('não apresentada');
            return {
                ano: radio.value,
                tipo_declaracao: radio.dataset.tipoDeclaracao || '',
                situacao_especial: radio.dataset.situacaoEspecialTipo || '-',
                data_baixa: radio.dataset.situacaoEspecialEventobaixa || '-',
                status: statusTexto || acao,
                pendente, baixada,
            };
        });
    }""")

    _validar_declaracoes(razao_social, declaracoes)
    mei_baixada = any(d["baixada"] for d in declaracoes)
    data_baixa_raw = next(
        (d["data_baixa"] for d in declaracoes
         if d["data_baixa"] != "-" and _normalizar(d["situacao_especial"]) == "extincao"),
        None,
    )
    pendentes = [int(d["ano"]) for d in declaracoes if d["pendente"]]

    cleaned = []
    for d in declaracoes:
        sit = d["situacao_especial"] if d["situacao_especial"] != "-" else None
        db_raw = d["data_baixa"] if d["data_baixa"] != "-" else None
        status_norm, data_apresentacao = parse_status_declaracao(d["status"] or None)
        tipo_decl = (d["tipo_declaracao"] or "").strip()
        cleaned.append({
            "ano": int(d["ano"]),
            "retificadora": tipo_decl.lower() == "retificadora",
            "status": status_norm,
            "data_apresentacao": data_apresentacao,
            "pendente": d["pendente"],
            "baixada": d["baixada"],
            "situacao_especial": sit,
            "data_baixa": data_br_para_iso(db_raw),
        })

    alertas = await capturar_alertas(page)

    return {
        "razao_social": parse_nome_empresarial(razao_social) if razao_social else None,
        "mei_baixada": mei_baixada,
        "data_baixa": data_br_para_iso(data_baixa_raw),
        "declaracoes": cleaned,
        "pendentes": pendentes,
        "alertas": alertas,
    }
