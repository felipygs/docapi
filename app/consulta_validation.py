"""Condições de sucesso operacional, sem modificar os dicionários retornados."""
from pydantic import ValidationError

from .errors import DadosIncompletosError
from .models import DasnResponse, OptantesResponse


def _validar_modelo(resultado: dict, modelo, modulo: str):
    try:
        return modelo.model_validate(resultado)
    except ValidationError:
        raise DadosIncompletosError(f'{modulo} - resposta incompatível com o contrato') from None


def validar_dasn(resultado: dict) -> None:
    validado = _validar_modelo(resultado, DasnResponse, 'DASN')
    if not validado.razao_social or not validado.razao_social.strip() or not validado.declaracoes:
        raise DadosIncompletosError('DASN - resposta incompleta')


def validar_optantes(resultado: dict) -> None:
    _validar_modelo(resultado, OptantesResponse, 'Optantes')
