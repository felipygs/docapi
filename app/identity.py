"""Formato CNPJ compartilhado; conserva a aceitação histórica de dígitos."""


def normalizar_cnpj(cnpj: str) -> str:
    limpo = cnpj.replace(".", "").replace("/", "").replace("-", "")
    if len(limpo) != 14 or not limpo.isdigit():
        raise ValueError("CNPJ invalido")
    return limpo
