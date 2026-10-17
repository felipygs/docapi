"""Snapshot DOM local de Optantes e transformação pura, sem acesso à rede.

Títulos delimitam painéis; os rótulos delimitam intervalos no painel histórico.
Nenhum índice global de tabelas ou ID de evento identifica um regime.
"""
import re
import unicodedata
from datetime import datetime

from pydantic import ValidationError

from ..models import OptantesResponse
from .utils import ALERT_SELECTORS

IDENTIFICACAO = "Identificação do Contribuinte - CNPJ Matriz"
SITUACAO = "Situação Atual"
HISTORICOS = "Períodos Anteriores"
EVENTOS_SIMPLES = "Eventos Futuros (Simples Nacional)"
EVENTOS_SIMEI = "Eventos Futuros (SIMEI)"
TRANSPORTADOR = "Informações de Períodos como MEI Transportador Autônomo de Cargas"
ROTULOS = (
    "Opções pelo Simples Nacional em Períodos Anteriores:",
    "Enquadramentos no SIMEI em Períodos Anteriores:",
)

_JS_SNAPSHOT = r"""({rotulos, alertSelectors}) => {
    const norm = s => s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/\s+/g, ' ').trim().toLowerCase();
    const space = s => s.replace(/\s+/g, ' ').trim();
    const visible = el => {
        for (let p = el; p; p = p.parentElement) {
            const s = getComputedStyle(p);
            if (p.hidden || s.display === 'none' || s.visibility === 'hidden') return false;
        }
        return true;
    };
    const clean = node => {
        const clone = node.cloneNode(true);
        if (node.nodeType === Node.ELEMENT_NODE && !visible(node)) return document.createDocumentFragment();
        if (node.nodeType === Node.ELEMENT_NODE) {
            const original = [...node.querySelectorAll('*')];
            const copies = [...clone.querySelectorAll('*')];
            original.forEach((el, i) => { if (!visible(el)) copies[i].remove(); });
        }
        clone.querySelectorAll('script, style, button, input, select, textarea, a.btn, [role="button"], .modal, template, noscript').forEach(el => el.remove());
        const comments = document.createTreeWalker(clone, NodeFilter.SHOW_COMMENT);
        const remove = []; while (comments.nextNode()) remove.push(comments.currentNode);
        remove.forEach(n => n.remove());
        return clone;
    };
    const text = node => {
        const clone = node.cloneNode(true);
        clone.querySelectorAll('br').forEach(el => el.replaceWith('\n'));
        clone.querySelectorAll('table,td,th,p,div,tr,li,caption').forEach(el => {
            el.prepend(document.createTextNode(' '));
            el.appendChild(document.createTextNode(' '));
        });
        return space(clone.textContent);
    };
    const content = node => {
        // Todos os nós daqui em diante vêm da cópia já saneada NO contexto
        // original. Não recalcular CSS de fragmentos desconectados.
        const clone = node.cloneNode(true);
        const prosa = clone.cloneNode(true);
        // Caption não possui campo próprio no contrato: preservá-la como
        // prosa, inclusive quando a tabela será normalizada separadamente.
        prosa.querySelectorAll('table').forEach(t => t.replaceWith(...t.querySelectorAll(':scope > caption')));
        let ausencia = false;
        const walker = document.createTreeWalker(prosa, NodeFilter.SHOW_TEXT);
        while (walker.nextNode()) {
            const node = walker.currentNode;
            // O nó isolado não basta: "Não Existem <span>...?</span>"
            // ainda é prosa ambígua, não uma confirmação de ausência.
            const contexto = node.parentElement || node;
            // Caption é metadado preservado, não declaração do estado do painel.
            if (node.parentElement?.closest('caption')) continue;
            if (norm(node.textContent) === 'nao existem' && norm(contexto.textContent) === 'nao existem') {
                ausencia = true;
                node.textContent = '';
            }
        }
        return {
            texto: text(clone),
            prosa: text(prosa), ausencia,
            // Manter limites locais de mensagens: concatenar toda a prosa
            // esconderia um "Carregando" após uma nota fiscal legítima.
            mensagens: [...prosa.querySelectorAll('p,li,div,span,caption')].map(text),
            tabelas: [...clone.querySelectorAll('table')].map(t => ({
                cabecalhos: [...t.querySelectorAll(':scope > thead > tr > th')].map(text),
                linhas: [...t.querySelectorAll(':scope > tbody > tr')].map(tr => [...tr.children].map(text)),
                // Não descartar tfoot ou outro segmento não representado.
                // Formatos estruturados inesperados falham em vez de truncar.
                invalida: !!t.querySelector('table, tfoot, [colspan]:not([colspan="1"]), [rowspan]:not([rowspan="1"])')
                    || t.querySelectorAll(':scope > thead').length !== 1
                    || t.querySelectorAll(':scope > thead > tr').length !== 1
                    || !t.querySelector(':scope > tbody')
                    || [...t.children].some(el => !['CAPTION', 'COLGROUP', 'THEAD', 'TBODY'].includes(el.tagName))
                    || [...t.querySelectorAll(':scope > thead > tr')].some(tr => [...tr.children].some(th => th.tagName !== 'TH'))
                    || [...t.querySelectorAll(':scope > thead, :scope > tbody')].some(group => [...group.children].some(el => el.tagName !== 'TR'))
                    || [...t.querySelectorAll(':scope > tbody > tr')].some(tr => [...tr.children].some(td => td.tagName !== 'TD')),
            })),
        };
    };
    const originalRoot = document.querySelector('#conteudo');
    if (!originalRoot) return {paineis: [], horarios: [], alertas: [], complementares: null};
    // getComputedStyle é consultado antes de clonar/cortar qualquer Range:
    // preserva hidden, estilos herdados e seletores CSS que dependem de #maisInfo.
    const root = clean(originalRoot);
    const paineis = [];
    for (const panel of root.querySelectorAll('.panel')) {
        const titles = panel.querySelectorAll(':scope > .panel-heading h3');
        if (!titles.length) continue;
        const bodies = panel.querySelectorAll(':scope > .panel-body');
        const body = bodies.length === 1 ? bodies[0] : null;
        const snap = {
            titulo: titles.length === 1 ? space(titles[0].textContent) : '',
            complementar: panel.parentElement?.id === 'maisInfo',
            conteudo: body ? content(body) : null,
        };
        if (body && norm(snap.titulo) === norm('Períodos Anteriores')) {
            // Ranges de texto dentro DESTE corpo. Incluem filhos do rótulo
            // (Não Existem) e irmãos seguintes até o próximo rótulo fiscal.
            const walker = document.createTreeWalker(body, NodeFilter.SHOW_TEXT);
            const starts = [];
            while (walker.nextNode()) {
                const n = walker.currentNode;
                if (n.parentElement.closest('table,script,style,button')) continue;
                rotulos.forEach((label, index) => {
                    const value = norm(n.textContent);
                    if (value.startsWith(norm(label))) {
                        const colon = n.textContent.indexOf(':');
                        starts.push({node: n, offset: colon + 1, index});
                    }
                });
            }
            snap.historicos = rotulos.map((_, index) => {
                const matches = starts.filter(s => s.index === index);
                if (matches.length !== 1) return null;
                const start = matches[0];
                const next = starts[starts.indexOf(start) + 1];
                const range = document.createRange();
                range.setStart(start.node, start.offset);
                if (next) range.setEnd(next.node, 0); else range.setEnd(body, body.childNodes.length);
                return content(range.cloneContents());
            });
            snap.limites_validos = starts.length === rotulos.length && new Set(starts.map(s => s.index)).size === rotulos.length;
            if (snap.limites_validos) {
                const prefix = document.createRange();
                prefix.setStart(body, 0);
                prefix.setEnd(starts[0].node, 0);
                snap.antes_historicos = content(prefix.cloneContents());
            }
        }
        paineis.push(snap);
    }
    const horarios = [...root.querySelectorAll('h5')].filter(h => norm(h.textContent).startsWith('data da consulta:')).map(text);
    const maisInfo = root.querySelector('#maisInfo')?.cloneNode(true);
    // Conteúdo fiscal avulso não pode desaparecer só por não vir em .panel.
    // Painéis titulados já foram processados; controles foram saneados antes.
    if (maisInfo) maisInfo.querySelectorAll('.panel').forEach(panel => {
        if (panel.querySelector(':scope > .panel-heading h3')) panel.remove();
    });
    const complementares = maisInfo ? content(maisInfo) : null;
    const alertas = [];
    for (const sel of alertSelectors) for (const el of document.querySelectorAll(sel)) {
        if (!visible(el)) continue;
        const value = text(clean(el));
        if (value && !alertas.includes(value)) alertas.push(value);
    }
    return {paineis, horarios, alertas, complementares};
}"""


def normalizar(texto: str) -> str:
    return " ".join("".join(c for c in unicodedata.normalize("NFD", texto) if not unicodedata.combining(c)).lower().split())


def falha(secao: str, campo: str) -> None:
    # Somente nomes de campos controlados pelo parser; nunca ecoar HTML, URL,
    # mensagens Ajax, cookies, tokens ou inputs rejeitados pelo Pydantic.
    raise RuntimeError(f"Optantes - {secao}: {campo}")


async def adquirir_snapshot(page) -> dict:
    return await page.evaluate(_JS_SNAPSHOT, {"rotulos": ROTULOS, "alertSelectors": ALERT_SELECTORS})


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
    identificacao = _painel(snapshot, IDENTIFICACAO)["conteudo"]["texto"]
    cnpj = re.search(r"\bCNPJ:\s*([0-9]{2}\.[0-9]{3}\.[0-9]{3}/[0-9]{4}-[0-9]{2}|[0-9]{14})(?=\s|$)", identificacao)
    nome = re.search(r"Nome Empresarial:\s*(.*)$", identificacao)
    if cnpj is None or nome is None or not nome[1].strip():
        falha("identificação", "CNPJ matriz ou nome empresarial inválido")
    nota = normalizar(identificacao[cnpj.end():nome.start()])
    notas = {
        "a opcao pelo simples nacional e/ou simei abrange todos os estabelecimentos da empresa": True,
        "a opcao pelo simples nacional e/ou simei nao abrange todos os estabelecimentos da empresa": False,
    }
    if nota not in notas:
        falha("abrangência", "nota ausente ou desconhecida")
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
    situacao = _painel(snapshot, SITUACAO)["conteudo"]["texto"]
    match = re.fullmatch(r"Situação no Simples Nacional:\s*(.*?)\s*Situação no SIMEI:\s*(.*)", situacao, re.I)
    if match is None:
        falha(SITUACAO, "rótulos obrigatórios ausentes ou ambíguos")
    simples = _situacao(match[1], "Simples Nacional")
    simei = _situacao(match[2], "SIMEI")
    history = _painel(snapshot, HISTORICOS, True)
    if not history.get("limites_validos"):
        falha(HISTORICOS, "rótulos ausentes ou duplicados")
    adicionais = []
    antes = history.get("antes_historicos")
    if antes and (antes["texto"] or antes["tabelas"]):
        _validar_estado(antes, HISTORICOS)
        adicionais.append({"secao": HISTORICOS, **_generico(antes, HISTORICOS)})
    for i, (regime, dados, titulo) in enumerate((("Simples Nacional", simples, EVENTOS_SIMPLES), ("SIMEI", simei, EVENTOS_SIMEI))):
        dados["periodos_anteriores"] = _lista(history["historicos"][i], f"{HISTORICOS} ({regime})", {"Data Inicial": "data_inicial", "Data Final": "data_final", "Detalhamento": "detalhamento"}, {"data_inicial", "data_final"}, adicionais)
        dados["eventos_futuros"] = _lista(_painel(snapshot, titulo, True)["conteudo"], titulo, {"Descrição do Evento": "descricao", "Data Efeito": "data_efeito"}, {"data_efeito"}, adicionais)
    conteudo = _painel(snapshot, TRANSPORTADOR, True)["conteudo"]
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
        "cnpj_consultado": cnpj_consultado,
        "cnpj_matriz": re.sub(r"[^0-9]", "", cnpj[1]),
        "nome_empresarial": nome[1], "consultado_em": consultado_em,
        "abrange_todos_estabelecimentos": notas[nota],
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
