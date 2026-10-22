"""Transformação pura do cadastro e QSA da Receita."""
import re
from ..errors import DadosIncompletosError, IdentidadeDivergenteError
from .parsers import data_br_para_iso, parse_cnae, parse_cep, parse_nome_empresarial, parse_telefone


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
