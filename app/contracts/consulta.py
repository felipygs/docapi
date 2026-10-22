from pydantic import BaseModel, Field
from .cadastro import CadastroResponse
from .dasn import DasnResultado
from .optantes import OptantesResponse


class ConsultaResponse(BaseModel):
    """Resposta completa com cadastro, DASN e situacao no Simples/SIMEI."""

    cnpj: str = Field(..., description="CNPJ consultado", examples=["45.726.608/0001-36"])
    cadastro: CadastroResponse = Field(..., description="Dados cadastrais do CNPJ")
    dasn: DasnResultado = Field(..., description="Declaracoes ou resposta 33001 corroborada; null nao confirma ausencia de pendencias")
    optantes: OptantesResponse = Field(..., description="Situacao no Simples Nacional e SIMEI")
