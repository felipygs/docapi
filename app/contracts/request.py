from pydantic import BaseModel, Field, field_validator
from ..identity import normalizar_cnpj


class ConsultaRequest(BaseModel):
    cnpj: str = Field(
        ...,
        description="CNPJ da empresa, com ou sem mascara",
        examples=["45.726.608/0001-36", "45726608000136"],
    )

    @field_validator("cnpj")
    @classmethod
    def validar_cnpj(cls, v: str) -> str:
        normalizar_cnpj(v)
        return v
