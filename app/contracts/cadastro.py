from pydantic import BaseModel, Field


class Cnae(BaseModel):
    codigo: str | None = Field(None, description="Codigo CNAE formatado", examples=["47.81-4-00"])
    descricao: str | None = Field(None, description="Descricao da atividade economica", examples=["Comercio varejista de artigos do vestuario e acessorios"])


class NaturezaJuridica(BaseModel):
    codigo: str | None = Field(None, description="Codigo da natureza juridica", examples=["213-5"])
    descricao: str | None = Field(None, description="Descricao da natureza juridica", examples=["Empresario (Individual)"])


class Telefone(BaseModel):
    ddd: str | None = Field(None, description="DDD do telefone", examples=["11"])
    numero: str | None = Field(None, description="Numero do telefone sem DDD", examples=["912345678"])


class Endereco(BaseModel):
    logradouro: str | None = Field(None, description="Logradouro (rua, avenida, etc.)", examples=["R EXEMPLO"])
    numero: str | None = Field(None, description="Numero do endereco", examples=["123"])
    complemento: str | None = Field(None, description="Complemento do endereco")
    bairro: str | None = Field(None, description="Bairro", examples=["CENTRO"])
    municipio: str | None = Field(None, description="Municipio", examples=["SAO PAULO"])
    uf: str | None = Field(None, description="Unidade federativa (sigla)", examples=["SP"])
    cep: str | None = Field(None, description="CEP (somente digitos)", examples=["01001000"])


class Contato(BaseModel):
    email: str | None = Field(None, description="Email de contato da empresa")
    telefone: Telefone = Field(default_factory=Telefone, description="Telefone de contato")


class SituacaoCadastral(BaseModel):
    ativa: bool = Field(False, description="Empresa com situacao ATIVA")
    baixada: bool = Field(False, description="Empresa com situacao BAIXADA")
    suspensa: bool = Field(False, description="Empresa com situacao SUSPENSA")
    inapta: bool = Field(False, description="Empresa com situacao INAPTA")
    nula: bool = Field(False, description="Empresa com situacao NULA")
    data: str | None = Field(None, description="Data da situacao cadastral (ISO 8601)", examples=["2022-03-21"])
    motivo: str | None = Field(None, description="Motivo da situacao cadastral")


class Socio(BaseModel):
    nome: str = Field(..., description="Nome do socio ou administrador")
    qualificacao: str | None = Field(None, description="Qualificacao do socio (ex: Socio-Administrador)")


class CadastroResponse(BaseModel):
    """Dados cadastrais do CNPJ extraidos da Receita Federal."""

    nome_empresarial: str | None = Field(None, description="Razao social da empresa")
    nome_fantasia: str | None = Field(None, description="Nome fantasia")
    matriz: bool = Field(True, description="True se for matriz, False se filial")
    data_abertura: str | None = Field(None, description="Data de abertura (ISO 8601)", examples=["2022-03-21"])
    porte: str | None = Field(None, description="Porte da empresa", examples=["ME", "EPP", "DEMAIS"])
    atividade_principal: Cnae | None = Field(None, description="CNAE da atividade economica principal")
    atividades_secundarias: list[Cnae] = Field([], description="Lista de CNAEs secundarios")
    natureza_juridica: NaturezaJuridica | None = Field(None, description="Natureza juridica da empresa")
    ente_federativo: str | None = Field(None, description="Ente federativo responsavel (quando aplicavel)")
    endereco: Endereco = Field(..., description="Endereco completo da empresa")
    contato: Contato = Field(..., description="Dados de contato (email e telefone)")
    situacao_cadastral: SituacaoCadastral = Field(default_factory=SituacaoCadastral, description="Situacao cadastral atual")
    situacao_especial: str | None = Field(None, description="Situacao especial (se houver)")
    data_situacao_especial: str | None = Field(None, description="Data da situacao especial (ISO 8601)")
    capital_social: int | None = Field(None, description="Capital social em centavos (R$5.000,00 = 500000)", examples=[500000])
    socios: list[Socio] = Field([], description="Quadro de socios e administradores")
    alertas: list[str] = Field([], description="Alertas ou avisos capturados da pagina")

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "nome_empresarial": "EMPRESA EXEMPLO LTDA",
                "nome_fantasia": "EXEMPLO",
                "matriz": True,
                "data_abertura": "2022-03-21",
                "porte": "ME",
                "atividade_principal": {"codigo": "47.81-4-00", "descricao": "Comercio varejista de artigos do vestuario"},
                "atividades_secundarias": [],
                "natureza_juridica": {"codigo": "213-5", "descricao": "Empresario (Individual)"},
                "ente_federativo": None,
                "endereco": {"logradouro": "R EXEMPLO", "numero": "123", "complemento": None, "bairro": "CENTRO", "municipio": "SAO PAULO", "uf": "SP", "cep": "01001000"},
                "contato": {"email": "contato@exemplo.com", "telefone": {"ddd": "11", "numero": "912345678"}},
                "situacao_cadastral": {"ativa": True, "baixada": False, "suspensa": False, "inapta": False, "nula": False, "data": "2022-03-21", "motivo": None},
                "situacao_especial": None,
                "data_situacao_especial": None,
                "capital_social": 500000,
                "socios": [],
                "alertas": [],
            }],
        },
    }
