"""Validacao e transformacao puras das declaracoes DASN."""
import re
import unicodedata
from ..errors import DadosIncompletosError, IdentidadeDivergenteError
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


def validar_identidade(cnpj_origem: str | None, cnpj: str) -> None:
    if cnpj_origem is not None and re.sub(r'[^0-9]', '', cnpj_origem) != cnpj:
        raise IdentidadeDivergenteError('DASN - identidade do CNPJ divergente')


def transformar_snapshot_dasn(snapshot: dict, cnpj: str) -> dict:
    validar_identidade(snapshot['cnpj_origem'], cnpj)
    razao_social = snapshot['razao_social']
    declaracoes = snapshot['declaracoes']
    _validar_declaracoes(razao_social, declaracoes)
    mei_baixada = any(d["baixada"] for d in declaracoes)
    data_baixa_raw = next(
        (d["data_baixa"] for d in declaracoes
         if d["data_baixa"] != "-" and _normalizar(d["situacao_especial"]) == "extincao"),
        None,
    )
    pendentes = [int(d["ano"]) for d in declaracoes if d["pendente"]]

    return {
        "razao_social": parse_nome_empresarial(razao_social) if razao_social else None,
        "mei_baixada": mei_baixada,
        "data_baixa": data_br_para_iso(data_baixa_raw),
        "declaracoes": [_transformar_declaracao(d) for d in declaracoes],
        "pendentes": pendentes,
        "alertas": [],
    }


def _transformar_declaracao(d: dict) -> dict:
    sit = d["situacao_especial"] if d["situacao_especial"] != "-" else None
    db_raw = d["data_baixa"] if d["data_baixa"] != "-" else None
    status_norm, data_apresentacao = parse_status_declaracao(d["status"] or None)
    tipo_decl = (d["tipo_declaracao"] or "").strip()
    return {
        "ano": int(d["ano"]),
        "retificadora": tipo_decl.lower() == "retificadora",
        "status": status_norm,
        "data_apresentacao": data_apresentacao,
        "pendente": d["pendente"],
        "baixada": d["baixada"],
        "situacao_especial": sit,
        "data_baixa": data_br_para_iso(db_raw),
    }
