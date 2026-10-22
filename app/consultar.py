"""Fachada compativel das quatro operacoes publicas de consulta."""
from .consulta_service import (
    consultar_mei, consultar_apenas_cnpj, consultar_apenas_dasn,
    consultar_apenas_optantes, _limpar_cnpj,
)

__all__ = ['consultar_mei', 'consultar_apenas_cnpj', 'consultar_apenas_dasn', 'consultar_apenas_optantes']
