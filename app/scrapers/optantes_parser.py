"""Snapshot DOM local de Optantes e transformação pura, sem acesso à rede.

Títulos delimitam painéis; os rótulos delimitam intervalos no painel histórico.
Nenhum índice global de tabelas ou ID de evento identifica um regime.
"""
import re
import unicodedata
from datetime import datetime

from pydantic import ValidationError

from ..models import OptantesResponse
from ..errors import DadosIncompletosError, IdentidadeDivergenteError
from .optantes_snapshot import (
    IDENTIFICACAO, SITUACAO, HISTORICOS, EVENTOS_SIMPLES, EVENTOS_SIMEI,
    TRANSPORTADOR, ROTULOS, adquirir_snapshot,
)

def normalizar(texto: str) -> str:
    return " ".join("".join(c for c in unicodedata.normalize("NFD", texto) if not unicodedata.combining(c)).lower().split())


def falha(secao: str, campo: str) -> None:
    # Somente nomes de campos controlados pelo parser; nunca ecoar HTML, URL,
    # mensagens Ajax, cookies, tokens ou inputs rejeitados pelo Pydantic.
    raise DadosIncompletosError(f"Optantes - {secao}: {campo}")


def data_estrita(valor: str, secao: str, campo: str) -> str | None:
    if not valor.strip():
        return None
    if not re.fullmatch(r"[0-9]{2}/[0-9]{2}/[0-9]{4}", valor):
        falha(secao, f"{campo}: data inválida")
    try:
        return datetime.strptime(valor, "%d/%m/%Y").date().isoformat()
    except ValueError:
        falha(secao, f"{campo}: data inválida")


def _painel(snapshot: dict, titulo: str, complementar=False) -> dict:
    encontrados = [p for p in snapshot["paineis"] if normalizar(p["titulo"]) == normalizar(titulo)]
    if len(encontrados) != 1:
        falha(titulo, "painel obrigatório ausente ou duplicado")
    painel = encontrados[0]
    if painel["conteudo"] is None or painel["complementar"] != complementar:
        falha(titulo, "limites do painel inválidos")
    return painel


def _tabela_valida(tabela: dict, secao: str) -> None:
    headers = tabela["cabecalhos"]
    if tabela["invalida"] or not headers or not tabela["linhas"]:
        falha(secao, "tabela vazia ou estrutura inválida")
    if any(len(row) != len(headers) for row in tabela["linhas"]):
        falha(secao, "contagem de células diferente dos cabeçalhos")


def _validar_estado(conteudo: dict, secao: str) -> None:
    # Mensagens explícitas de execução, não substrings como "erro" em um
    # motivo fiscal (nem "pendências"/"débitos" em registros legítimos).
    textos = [conteudo.get("prosa", ""), conteudo["texto"], *conteudo.get("mensagens", [])]
    textos.extend(c for t in conteudo["tabelas"] for row in t["linhas"] for c in row)
    for texto in textos:
        valor = normalizar(texto)
        if re.search(
            r"\b(?:nao foi possivel (?:consultar|carregar|obter)|erro ao (?:carregar|consultar|obter)|consulta nao concluida)\b"
            r"|(?:^|[.!?:]\s*)(?:erro\b|falha\b|carregando\b|aguarde\b|(?:consulta|informacao)(?: temporariamente)? (?:indisponivel|pendente)\b)",
            valor,
        ):
            falha(secao, "consulta incompleta ou erro da origem")


def _lista(conteudo: dict, secao: str, colunas: dict, datas: set, adicionais: list) -> list[dict]:
    if conteudo is None:
        falha(secao, "rótulo obrigatório ausente ou duplicado")
    _validar_estado(conteudo, secao)
    obrigatorios = {normalizar(h) for h in colunas}
    tabelas = conteudo["tabelas"]
    conhecidas = [t for t in tabelas if any(normalizar(h) in obrigatorios for h in t['cabecalhos'])]
    desconhecidas = [t for t in tabelas if t not in conhecidas]
    extra = {'texto': conteudo['prosa'], 'tabelas': desconhecidas}
    if extra['texto'] or desconhecidas:
        adicionais.append({'secao': secao, **_generico(extra, secao)})
    if conteudo['ausencia'] and not conhecidas:
        return []
    if len(conhecidas) != 1 or conteudo['ausencia']:
        falha(secao, "ausência não confirmada ou conteúdo ambíguo")
    tabela = conhecidas[0]
    _tabela_valida(tabela, secao)
    headers = tabela["cabecalhos"]
    normalizados = [normalizar(h) for h in headers]
    indices = {}
    for coluna, campo in colunas.items():
        if normalizados.count(normalizar(coluna)) != 1:
            falha(secao, f"cabeçalho {coluna} ausente ou duplicado")
        indices[campo] = normalizados.index(normalizar(coluna))
    registros = []
    for row in tabela["linhas"]:
        registro = {}
        for campo, index in indices.items():
            valor = row[index]
            if campo in datas:
                valor = data_estrita(valor, secao, campo)
            elif campo == "detalhamento":
                valor = valor or None
            elif not valor.strip():
                falha(secao, f"{campo} vazio")
            registro[campo] = valor
        extras = [{"coluna": h, "valor": row[i]} for i, h in enumerate(headers) if i not in indices.values()]
        if extras:
            registro["campos_adicionais"] = extras
        registros.append(registro)
    return registros


def _situacao(texto: str, regime: str) -> dict:
    base = "optante pelo simples nacional" if regime == "Simples Nacional" else "enquadrado no simei"
    match = re.fullmatch(rf"(nao )?{base}(?: desde (.+))?", normalizar(texto))
    if not match:
        falha(regime, "situação desconhecida")
    return {
        "optante" if regime == "Simples Nacional" else "enquadrado": match[1] is None,
        "situacao": texto,
        "data_desde": data_estrita(match[2], regime, "data_desde") if match[2] is not None else None,
    }


def _generico(conteudo: dict, secao: str) -> dict:
    for tabela in conteudo["tabelas"]:
        _tabela_valida(tabela, secao)
    return {"texto": conteudo["texto"], "tabelas": [
        {"cabecalhos": t["cabecalhos"], "linhas": t["linhas"]} for t in conteudo["tabelas"]
    ]}


def transformar_snapshot(snapshot: dict, cnpj_consultado: str) -> dict:
    identificacao = _identificacao(snapshot, cnpj_consultado)
    consultado_em = _horario_consulta(snapshot)
    situacao = _painel(snapshot, SITUACAO)["conteudo"]["texto"]
    # Novos regimes aparecem depois do SIMEI no mesmo painel. Preservá-los
    # integralmente, sem interpretar seu estado como parte do SIMEI.
    adicional_situacao = None
    novo_regime = re.search(r'\s+Situação no Regime Regular (?:do IBS|da CBS):', situacao, re.I)
    if novo_regime:
        adicional_situacao = situacao[novo_regime.start():].strip()
        situacao = situacao[:novo_regime.start()].strip()
    match = re.fullmatch(r"Situação no Simples Nacional:\s*(.*?)\s*Situação no SIMEI:\s*(.*)", situacao, re.I)
    if match is None:
        falha(SITUACAO, "rótulos obrigatórios ausentes ou ambíguos")
    simples = _situacao(match[1], "Simples Nacional")
    simei = _situacao(match[2], "SIMEI")
    history = _painel(snapshot, HISTORICOS, True)
    if not history.get("limites_validos"):
        falha(HISTORICOS, "rótulos ausentes ou duplicados")
    adicionais = []
    if adicional_situacao:
        adicionais.append({'secao': SITUACAO, 'texto': adicional_situacao, 'tabelas': []})
    antes = history.get("antes_historicos")
    if antes and (antes["texto"] or antes["tabelas"]):
        _validar_estado(antes, HISTORICOS)
        adicionais.append({"secao": HISTORICOS, **_generico(antes, HISTORICOS)})
    for conteudo_adicional in history.get("adicionais_historicos", []):
        adicionais.append({"secao": HISTORICOS, **_generico(conteudo_adicional, HISTORICOS)})
    for i, (regime, dados, titulo) in enumerate((("Simples Nacional", simples, EVENTOS_SIMPLES), ("SIMEI", simei, EVENTOS_SIMEI))):
        dados["periodos_anteriores"] = _lista(history["historicos"][i], f"{HISTORICOS} ({regime})", {"Data Inicial": "data_inicial", "Data Final": "data_final", "Detalhamento": "detalhamento"}, {"data_inicial", "data_final"}, adicionais)
        dados["eventos_futuros"] = _lista(_painel(snapshot, titulo, True)["conteudo"], titulo, {"Descrição do Evento": "descricao", "Data Efeito": "data_efeito"}, {"data_efeito"}, adicionais)
    transportador = _transportador(_painel(snapshot, TRANSPORTADOR, True)["conteudo"])
    conhecidos = {normalizar(t) for t in (IDENTIFICACAO, SITUACAO, HISTORICOS, EVENTOS_SIMPLES, EVENTOS_SIMEI, TRANSPORTADOR)}
    complementares = snapshot['complementares']
    if complementares and (complementares['texto'] or complementares['tabelas']):
        adicionais.append({'secao': 'Mais informações', **_generico(complementares, 'Mais informações')})
    for p in snapshot["paineis"]:
        if normalizar(p["titulo"]) not in conhecidos:
            if not p["titulo"] or p["conteudo"] is None:
                falha("seção adicional", "limites inválidos")
            if p["conteudo"]["texto"] or p["conteudo"]["tabelas"]:
                adicionais.append({"secao": p["titulo"], **_generico(p["conteudo"], "seção adicional")})
    resultado = {
        **identificacao, "consultado_em": consultado_em,
        "simples_nacional": simples, "simei": simei,
        "mei_transportador": transportador, "alertas": snapshot["alertas"],
        "dados_adicionais": adicionais,
    }
    try:
        return OptantesResponse.model_validate(resultado).model_dump(mode="json")
    except ValidationError as exc:
        # loc contém apenas os campos do nosso modelo, não os valores externos.
        campo = ".".join(str(v) for v in exc.errors(include_input=False, include_context=False, include_url=False)[0]["loc"])
        falha("validação do resultado", f"campo {campo} inválido")


def _identificacao(snapshot: dict, cnpj_consultado: str) -> dict:
    identificacao = _painel(snapshot, IDENTIFICACAO)["conteudo"]["texto"]
    cnpj = re.search(r"\bCNPJ:\s*([0-9]{2}\.[0-9]{3}\.[0-9]{3}/[0-9]{4}-[0-9]{2}|[0-9]{14})(?=\s|$)", identificacao)
    nome = re.search(r"Nome Empresarial:\s*(.*)$", identificacao)
    if cnpj is None or nome is None or not nome[1].strip():
        falha("identificação", "CNPJ matriz ou nome empresarial inválido")
    if re.fullmatch(r'[0-9]{14}', cnpj_consultado) and re.sub(r'[^0-9]', '', cnpj[1])[:8] != cnpj_consultado[:8]:
        raise IdentidadeDivergenteError('Optantes - identidade: CNPJ matriz de outra empresa')
    nota = normalizar(identificacao[cnpj.end():nome.start()])
    notas = {
        "a opcao pelo simples nacional e/ou simei abrange todos os estabelecimentos da empresa": True,
        "a opcao pelo simples nacional e/ou simei nao abrange todos os estabelecimentos da empresa": False,
    }
    if nota not in notas:
        falha("abrangência", "nota ausente ou desconhecida")
    return {
        "cnpj_consultado": cnpj_consultado,
        "cnpj_matriz": re.sub(r"[^0-9]", "", cnpj[1]),
        "nome_empresarial": nome[1],
        "abrange_todos_estabelecimentos": notas[nota],
    }


def _horario_consulta(snapshot: dict) -> str:
    horarios = snapshot["horarios"]
    if len(horarios) != 1:
        falha("Data da consulta", "horário ausente ou duplicado")
    horario = re.fullmatch(r"Data da consulta:\s*([0-9]{2}/[0-9]{2}/[0-9]{4} [0-9]{2}:[0-9]{2}:[0-9]{2})", horarios[0], re.I)
    try:
        if horario is None:
            raise ValueError
        consultado_em = datetime.strptime(horario[1], "%d/%m/%Y %H:%M:%S").isoformat()
    except ValueError:
        falha("Data da consulta", "horário inválido")
    return consultado_em


def _transportador(conteudo: dict) -> dict:
    _validar_estado(conteudo, "MEI Transportador")
    texto = normalizar(conteudo["texto"])
    if texto == "nao existem" and not conteudo["tabelas"]:
        transportador = {"possui_periodos": False}
    else:
        if not texto or re.search(r"\bnao existem\b", texto):
            falha("MEI Transportador", "conteúdo vazio, ambíguo ou erro da origem")
        # Tabelas substantivas ou texto explícito de períodos com datas são
        # evidência de registros; não exigir nomes/semântica de colunas ainda
        # não observadas em captura real nem inferir datas inexistentes.
        datas = re.findall(r"\b[0-9]{2}/[0-9]{2}/[0-9]{4}\b", conteudo["texto"])
        linhas = [r for t in conteudo["tabelas"] for r in t["linhas"]]
        registros = bool(linhas) and all(any(c.strip() for c in r) for r in linhas)
        texto_periodos = not conteudo["tabelas"] and bool(datas) and 'periodo' in texto
        if not registros and not texto_periodos:
            falha("MEI Transportador", "registros de períodos não reconhecidos")
        for data in datas:
            data_estrita(data, "MEI Transportador", "período")
        transportador = {"possui_periodos": True, "detalhes": _generico(conteudo, "MEI Transportador")}
    return transportador
