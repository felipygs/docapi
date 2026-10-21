"""Cadastro pela consulta publica atual, com validacao de captcha e QSA."""
import asyncio
import re

from playwright.async_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError

from ..captcha import resolver_hcaptcha, resolver_hcaptcha_nonecap
from ..config import CNPJ_URL, NONECAP_API_KEY, NOPECHA_API_KEY
from ..errors import CaptchaBloqueadoError, DadosIncompletosError, IdentidadeDivergenteError
from .parsers import data_br_para_iso, parse_cnae, parse_cep, parse_nome_empresarial, parse_telefone


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


def _limpar(valor) -> str | None:
    if valor is None:
        return None
    texto = str(valor).strip()
    return None if not texto or set(texto) == {'*'} else texto


def parse_cadastro(dados: dict, qsa: dict, cnpj: str) -> dict:
    """Converter a resposta da Receita para o contrato cadastral existente."""
    if not isinstance(dados, dict) or not isinstance(qsa, dict):
        raise DadosIncompletosError('CNPJ - resposta cadastral invalida')
    if dados.get('cnpj') != cnpj:
        raise IdentidadeDivergenteError('CNPJ - identidade divergente no cadastro')
    nome = parse_nome_empresarial(_limpar(dados.get('nomeEmpresarial')))
    abertura = data_br_para_iso(_limpar(dados.get('dataAbertura')))
    situacao = _limpar(dados.get('descricaoSituacaoCadastral'))
    tipos = {'ATIVA': 'ativa', 'BAIXADA': 'baixada', 'SUSPENSA': 'suspensa', 'INAPTA': 'inapta', 'NULA': 'nula'}
    tipo = dados.get('tipoEstabelecimento')
    secundarios = dados.get('cnaesSecundarias')
    socios = qsa.get('socios')
    data_situacao = data_br_para_iso(_limpar(dados.get('dataSituacaoCadastral')))
    if not nome or not abertura or situacao not in tipos or tipo not in ('MATRIZ', 'FILIAL') or not data_situacao:
        raise DadosIncompletosError('CNPJ - identificacao ou situacao cadastral incompleta')
    if not isinstance(secundarios, list) or not isinstance(socios, list):
        raise DadosIncompletosError('CNPJ - CNAEs secundarios ou QSA incompletos')

    def cnae(item):
        if not isinstance(item, dict) or not _limpar(item.get('cnaeFormatada')):
            raise DadosIncompletosError('CNPJ - atividade economica incompleta')
        return parse_cnae(item['cnaeFormatada'])

    quadro = []
    for socio in socios:
        if not isinstance(socio, dict) or not _limpar(socio.get('nome')):
            raise DadosIncompletosError('CNPJ - socio sem identificacao no QSA')
        qualificacao = '-'.join(v for v in (_limpar(socio.get('qualificacao')), _limpar(socio.get('qualificacaoExtenso'))) if v) or None
        quadro.append({'nome': socio['nome'].strip(), 'qualificacao': qualificacao})
    capital = _limpar(dados.get('valorCapitalSocial'))
    if capital is not None and not re.fullmatch(r'[0-9]+', capital):
        raise DadosIncompletosError('CNPJ - capital social invalido')
    email = _limpar(dados.get('email'))
    natureza = _limpar(dados.get('codigoNaturezaJuridica'))
    descricao_natureza = _limpar(dados.get('descricaoNaturezaJuridica'))
    if not natureza or not descricao_natureza:
        raise DadosIncompletosError('CNPJ - natureza juridica incompleta')
    return {
        'nome_empresarial': nome,
        'nome_fantasia': _limpar(dados.get('nomeFantasia')),
        'matriz': tipo == 'MATRIZ',
        'data_abertura': abertura,
        'porte': _limpar(dados.get('porteDescricao')),
        'atividade_principal': cnae(dados.get('cnaePrincipal')),
        'atividades_secundarias': [cnae(item) for item in secundarios],
        'natureza_juridica': {'codigo': natureza, 'descricao': descricao_natureza},
        'ente_federativo': _limpar(dados.get('descricaoEnteFederativoResponsavel')),
        'endereco': {
            'logradouro': _limpar(dados.get('nomeLogradouro')),
            'numero': _limpar(dados.get('numero')),
            'complemento': _limpar(dados.get('complemento')),
            'bairro': _limpar(dados.get('bairro')),
            'municipio': _limpar(dados.get('municipio')),
            'uf': _limpar(dados.get('uf')),
            'cep': parse_cep(_limpar(dados.get('cep'))),
        },
        'contato': {'email': email.lower() if email else None,
                    'telefone': parse_telefone(_limpar(dados.get('numerosTelefone')))},
        'situacao_cadastral': {
            **{campo: situacao == texto for texto, campo in tipos.items()},
            'data': data_situacao,
            'motivo': _limpar(dados.get('descricaoMotivoSituacao')),
        },
        'situacao_especial': _limpar(dados.get('nomeSituacaoEspecial')),
        'data_situacao_especial': data_br_para_iso(_limpar(dados.get('dataSituacaoEspecial'))),
        'capital_social': int(capital) if capital is not None else None,
        'socios': quadro,
        'alertas': [],
    }


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
