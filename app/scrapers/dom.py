"""Primitiva DOM compartilhada; nao interpreta conteudo fiscal."""
_JS_VISIBLE = """    const visible = el => {
        for (let p = el; p; p = p.parentElement) {
            const s = getComputedStyle(p);
            if (p.hidden || s.display === 'none' || s.visibility === 'hidden') return false;
        }
        return true;
    };"""


def com_visibilidade(script: str) -> str:
    return script.replace('/* visibilidade herdada */', _JS_VISIBLE)
