from typing import Literal
from pydantic import BaseModel, Field, NaiveDatetime


class Declaracao(BaseModel):
    """Declaracao anual DASN-SIMEI."""

    ano: int = Field(..., description="Ano-calendario da declaracao", examples=[2024])
    retificadora: bool = Field(False, description="True se for declaracao retificadora")
    status: str | None = Field(None, description="Status da declaracao", examples=["apresentada", "nao apresentada"])
    data_apresentacao: str | None = Field(None, description="Data de apresentacao (ISO 8601)", examples=["2025-01-15"])
    pendente: bool = Field(False, description="True se a declaracao esta pendente de entrega")
    baixada: bool = Field(False, description="True se relacionada a baixa do MEI")
    situacao_especial: str | None = Field(None, description="Tipo de situacao especial (ex: Extincao)")
    data_baixa: str | None = Field(None, description="Data da baixa (ISO 8601)")


class DasnResponse(BaseModel):
    """Declaracoes DASN-SIMEI do contribuinte."""

    razao_social: str | None = Field(None, description="Razao social do contribuinte")
    mei_baixada: bool = Field(False, description="True se o MEI esta baixado")
    data_baixa: str | None = Field(None, description="Data da baixa do MEI (ISO 8601)")
    declaracoes: list[Declaracao] = Field([], description="Lista de declaracoes DASN-SIMEI")
    pendentes: list[int] = Field([], description="Anos com declaracoes pendentes", examples=[[2023, 2024]])
    alertas: list[str] = Field([], description="Alertas ou avisos capturados da pagina")

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "razao_social": "EMPRESA EXEMPLO LTDA",
                "mei_baixada": False,
                "data_baixa": None,
                "declaracoes": [
                    {"ano": 2024, "retificadora": False, "status": "apresentada", "data_apresentacao": "2025-01-15", "pendente": False, "baixada": False, "situacao_especial": None, "data_baixa": None},
                    {"ano": 2023, "retificadora": False, "status": "apresentada", "data_apresentacao": "2024-02-10", "pendente": False, "baixada": False, "situacao_especial": None, "data_baixa": None},
                ],
                "pendentes": [],
                "alertas": [],
            }],
        },
    }


class DasnNaoOptanteResponse(BaseModel):
    """Resposta 33001 corroborada por Optantes; obrigações não consultadas."""

    status: Literal['nao_optante_simei_confirmado_por_optantes']
    codigo_origem: Literal['33001']
    cnpj: str
    razao_social: str
    situacao_declaracoes: Literal['nao_consultadas']
    declaracoes: None
    pendentes: None
    mei_baixada: None
    data_baixa: None
    optantes_consultado_em: NaiveDatetime
    mensagem: str


DasnResultado = DasnNaoOptanteResponse | DasnResponse
