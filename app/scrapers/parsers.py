import re
from datetime import datetime


def data_br_para_iso(s: str | None) -> str | None:
    if not s:
        return None
    s = s.strip()
    try:
        return datetime.strptime(s, "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return None


def parse_cnae(s: str | None) -> dict | None:
    if not s:
        return None
    s = s.strip()
    # "10.31-7-00 - Fabricação de conservas de frutas"
    m = re.match(r'^([\d.]+[-/][\d.-]+)\s*-\s*(.+)$', s)
    if m:
        return {"codigo": m.group(1).strip(), "descricao": m.group(2).strip()}
    return {"codigo": None, "descricao": s}


def parse_telefone(s: str | None) -> dict:
    if not s:
        return {"ddd": None, "numero": None}
    m = re.match(r'\((\d{2})\)\s*([\d\s-]+)', s.strip())
    if m:
        ddd = m.group(1)
        numero = re.sub(r'[\s-]', '', m.group(2))
        return {"ddd": ddd, "numero": numero if numero else None}
    digits = re.sub(r'\D', '', s)
    return {"ddd": None, "numero": digits if digits else None}


def parse_cep(s: str | None) -> str | None:
    if not s:
        return None
    digits = re.sub(r'\D', '', s)
    return digits if len(digits) == 8 else None


def parse_nome_empresarial(s: str | None) -> str | None:
    if not s:
        return None
    # Remove prefixo CNPJ que o site coloca: "64.184.902 NOME" -> "NOME"
    cleaned = re.sub(r'^\d{2}\.\d{3}\.\d{3}\s+', '', s.strip())
    return cleaned.strip() or None


def parse_status_declaracao(status: str | None) -> tuple[str | None, str | None]:
    """
    Separa status de data_apresentacao.
    "apresentada em 09/01/2026" -> ("apresentada", "2026-01-09")
    "não apresentada" -> ("não apresentada", None)
    "Não Optante" -> ("não optante", None)
    """
    if not status:
        return None, None
    s = status.strip()
    m = re.search(r'\bem\s+(\d{2}/\d{2}/\d{4})', s, re.IGNORECASE)
    if m:
        data_iso = data_br_para_iso(m.group(1))
        texto = s[:m.start()].strip()
        return texto.lower() or None, data_iso
    return s.lower(), None
