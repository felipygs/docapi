from .network import erro_rede_transitorio
from playwright.async_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError

from ..config import DASN_URL
from ..errors import (
    CaptchaBloqueadoError, CnpjInvalidoError, DadosIncompletosError,
    FalhaTransitoriaError, IdentidadeDivergenteError, NaoOptanteError,
)
from .utils import capturar_alertas
from .dasn_parser import _normalizar, _validar_declaracoes, transformar_snapshot_dasn, validar_identidade


async def consultar_dasn(page, cnpj_limpo: str) -> dict:
    try:
        return await _consultar_dasn(page, cnpj_limpo)
    except (PlaywrightTimeoutError, TimeoutError):
        raise PlaywrightTimeoutError('DASN - timeout na consulta externa') from None
    except PlaywrightError as exc:
        if erro_rede_transitorio(exc):
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

    snapshot = await adquirir_snapshot_dasn(page, cnpj_limpo)
    resultado = transformar_snapshot_dasn(snapshot, cnpj_limpo)
    resultado['alertas'] = await capturar_alertas(page)
    return resultado


async def adquirir_snapshot_dasn(page, cnpj_limpo: str) -> dict:
    # Conferir a identidade exibida na origem, nunca o campo digitado.
    cnpj_origem = await page.evaluate('''() => {
        const ps = [...document.querySelectorAll('p')];
        for (let i = 0; i + 1 < ps.length; i++) {
            if (ps[i].querySelector('strong')?.textContent.trim() === 'CNPJ:')
                return ps[i + 1].textContent.trim();
        }
        return null;
    }''')
    validar_identidade(cnpj_origem, cnpj_limpo)

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

    return {"cnpj_origem": cnpj_origem, "razao_social": razao_social, "declaracoes": declaracoes}
