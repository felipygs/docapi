from .dom import com_visibilidade
"""Leitura DOM de Optantes; conserva os limites e a ordem da origem."""
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

_JS_SNAPSHOT = com_visibilidade(r"""({rotulos, alertSelectors}) => {
    const norm = s => s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/\s+/g, ' ').trim().toLowerCase();
    const space = s => s.replace(/\s+/g, ' ').trim();
    /* visibilidade herdada */
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
            complementar: panel.closest('#maisInfo') !== null,
            conteudo: body ? content(body) : null,
        };
        if (body && norm(snap.titulo) === norm('Períodos Anteriores')) {
            // Ranges de texto dentro DESTE corpo. Incluem filhos do rótulo
            // (Não Existem) e irmãos seguintes até o próximo rótulo fiscal.
            // IBS/CBS delimita uma seção adicional, sem virar histórico SIMEI.
            const labels = [...rotulos, 'Opções pelo Regime Regular IBS/CBS em Períodos Anteriores:'];
            const walker = document.createTreeWalker(body, NodeFilter.SHOW_TEXT);
            const starts = [];
            while (walker.nextNode()) {
                const n = walker.currentNode;
                if (n.parentElement.closest('table,script,style,button')) continue;
                labels.forEach((label, index) => {
                    const value = norm(n.textContent);
                    if (value.startsWith(norm(label))) {
                        const colon = n.textContent.indexOf(':');
                        starts.push({node: n, offset: colon + 1, index});
                    }
                });
            }
            const intervalContent = (start, offset) => {
                const next = starts[starts.indexOf(start) + 1];
                const range = document.createRange();
                range.setStart(start.node, offset);
                if (next) range.setEnd(next.node, 0); else range.setEnd(body, body.childNodes.length);
                return content(range.cloneContents());
            };
            snap.historicos = rotulos.map((_, index) => {
                const matches = starts.filter(s => s.index === index);
                if (matches.length !== 1) return null;
                return intervalContent(matches[0], matches[0].offset);
            });
            snap.adicionais_historicos = starts.filter(s => s.index >= rotulos.length)
                .map(start => intervalContent(start, 0));
            const required = starts.filter(s => s.index < rotulos.length);
            snap.limites_validos = required.length === rotulos.length && new Set(required.map(s => s.index)).size === rotulos.length;
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
}""")


async def adquirir_snapshot(page) -> dict:
    return await page.evaluate(_JS_SNAPSHOT, {"rotulos": ROTULOS, "alertSelectors": ALERT_SELECTORS})
