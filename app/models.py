from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import (
    BaseModel, BeforeValidator, Field, NaiveDatetime, StrictBool, StringConstraints,
    field_validator, model_validator,
)


class ConsultaRequest(BaseModel):
    cnpj: str = Field(
        ...,
        description="CNPJ da empresa, com ou sem mascara",
        examples=["45.726.608/0001-36", "45726608000136"],
    )

    @field_validator("cnpj")
    @classmethod
    def validar_cnpj(cls, v: str) -> str:
        limpo = v.replace(".", "").replace("/", "").replace("-", "")
        if len(limpo) != 14 or not limpo.isdigit():
            raise ValueError("CNPJ invalido")
        return v


# --- CNPJ ---

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


# --- DASN ---

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


# --- Optantes ---

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

_OptantesTexto = Annotated[str, StringConstraints(pattern=r"\S")]
_OptantesCnpj = Annotated[str, StringConstraints(pattern=r"^[0-9]{14}$")]


def _validar_data_optantes(valor):
    # Nao aceitar timestamps/coercao numerica nem apagar datas invalidas.
    if isinstance(valor, str):
        if len(valor) != 10 or valor[4] != "-" or valor[7] != "-":
            raise ValueError("Data de Optantes deve estar em YYYY-MM-DD")
        return date.fromisoformat(valor)
    if valor is not None and type(valor) is not date:
        raise ValueError("Data de Optantes deve ser data civil ISO ou null")
    return valor


def _validar_horario_optantes(valor):
    if isinstance(valor, str):
        if len(valor) < 16 or valor[10] not in ("T", " "):
            raise ValueError("Horario de Optantes exige data e hora locais")
        return datetime.fromisoformat(valor)
    if not isinstance(valor, datetime):
        raise ValueError("Horario de Optantes deve ser datetime local sem fuso")
    return valor


_OptantesData = Annotated[date | None, BeforeValidator(_validar_data_optantes)]
_OptantesHorario = Annotated[NaiveDatetime, BeforeValidator(_validar_horario_optantes)]


class CampoAdicional(BaseModel):
    """Coluna nao normalizada; lista preserva ordem e cabecalhos repetidos."""

    coluna: str = Field(..., description="Cabecalho original da coluna adicional")
    valor: str = Field(..., description="Valor integral da celula, inclusive vazio")


class Tabela(BaseModel):
    """Tabela generica sem inferir o significado de colunas desconhecidas."""

    cabecalhos: list[str] = Field(..., description="Cabecalhos na ordem original, inclusive repetidos")
    linhas: list[list[str]] = Field(..., description="Todas as linhas e celulas na ordem original")


class ConteudoSecao(BaseModel):
    """Conteudo integral de uma secao fiscal ainda nao normalizada."""

    texto: str = Field(..., description="Texto integral da secao fiscal")
    tabelas: list[Tabela] = Field(..., description="Todas as tabelas da secao, na ordem original")

    def tem_conteudo(self) -> bool:
        return bool(self.texto.strip() or any(tabela.linhas for tabela in self.tabelas))


class DadoAdicional(ConteudoSecao):
    """Secao fiscal desconhecida preservada sem repetir dados ja normalizados."""

    secao: _OptantesTexto = Field(..., description="Titulo original da secao fiscal adicional")


class Periodo(BaseModel):
    """Periodo anterior do respectivo regime; null indica celula explicitamente vazia."""

    data_inicial: _OptantesData = Field(..., description="Data inicial civil ISO; null para celula vazia", examples=["2025-01-01", None])
    data_final: _OptantesData = Field(..., description="Data final civil ISO; null para celula vazia", examples=["2025-12-31", None])
    detalhamento: str | None = Field(..., description="Motivo integral do periodo; null para celula vazia")
    campos_adicionais: list[CampoAdicional] | None = Field(default_factory=list, exclude_if=lambda valor: not valor, description="Colunas adicionais ordenadas; omitido quando vazio")

    @field_validator("detalhamento")
    @classmethod
    def normalizar_detalhamento(cls, valor: str | None) -> str | None:
        return valor if valor is None or valor.strip() else None


class EventoFuturo(BaseModel):
    """Evento futuro independente da situacao atual do regime."""

    descricao: _OptantesTexto = Field(..., description="Descricao integral do evento futuro", examples=["Exclusão de Ofício - Débitos"])
    data_efeito: _OptantesData = Field(..., description="Data civil ISO de efeito; null para celula explicitamente vazia", examples=["2027-01-01", None])
    campos_adicionais: list[CampoAdicional] | None = Field(default_factory=list, exclude_if=lambda valor: not valor, description="Colunas adicionais ordenadas; omitido quando vazio")


class SimplesInfo(BaseModel):
    """Situacao atual, historicos e eventos exclusivos do Simples Nacional."""

    optante: StrictBool = Field(..., description="Opcao atual explicitamente reconhecida; evento futuro nao altera este fato")
    situacao: _OptantesTexto = Field(..., description="Redacao integral da situacao atual na origem")
    data_desde: _OptantesData = Field(..., description="Optante desde, em data civil ISO; null quando explicitamente ausente")
    periodos_anteriores: list[Periodo] = Field(..., description="Historico exclusivo do Simples; [] somente para ausencia confirmada")
    eventos_futuros: list[EventoFuturo] = Field(..., description="Eventos exclusivos do Simples, na ordem original; [] para ausencia confirmada, nunca texto/null")


class SimeiInfo(BaseModel):
    """Situacao atual, historicos e eventos exclusivos do SIMEI."""

    enquadrado: StrictBool = Field(..., description="Enquadramento atual explicitamente reconhecido")
    situacao: _OptantesTexto = Field(..., description="Redacao integral da situacao atual na origem")
    data_desde: _OptantesData = Field(..., description="Enquadrado desde, em data civil ISO; null quando explicitamente ausente")
    periodos_anteriores: list[Periodo] = Field(..., description="Historico exclusivo do SIMEI; [] somente para ausencia confirmada")
    eventos_futuros: list[EventoFuturo] = Field(..., description="Eventos exclusivos do SIMEI, na ordem original; [] para ausencia confirmada, nunca texto/null")


class MeiTransportador(BaseModel):
    """Ausencia confirmada ou conteudo preservado sem esquema ficticio de periodos."""

    possui_periodos: StrictBool = Field(..., description="False somente para ausencia explicita de periodos de MEI Transportador")
    detalhes: ConteudoSecao | None = Field(None, exclude_if=lambda valor: valor is None or not valor.tem_conteudo(), description="Conteudo integral obrigatorio quando possui_periodos=true; omitido se vazio")

    @model_validator(mode="after")
    def validar_coerencia(self):
        preenchido = self.detalhes is not None and self.detalhes.tem_conteudo()
        if self.possui_periodos != preenchido:
            raise ValueError("MEI Transportador: possui_periodos deve corresponder a detalhes preenchidos")
        return self


class OptantesResponse(BaseModel):
    """Consulta integra de Optantes; listas vazias representam ausencia confirmada."""

    cnpj_consultado: _OptantesCnpj = Field(..., description="CNPJ consultado normalizado, com 14 digitos ASCII")
    cnpj_matriz: _OptantesCnpj = Field(..., description="CNPJ da matriz informado pela origem, podendo diferir do consultado")
    nome_empresarial: _OptantesTexto = Field(..., description="Nome empresarial integral informado pela origem")
    consultado_em: _OptantesHorario = Field(..., description="Data/hora local da consulta na origem, sem fuso presumido")
    abrange_todos_estabelecimentos: StrictBool = Field(..., description="Abrangencia explicitamente reconhecida na nota da origem")
    simples_nacional: SimplesInfo = Field(..., description="Situacao, historicos e eventos exclusivos do Simples Nacional")
    simei: SimeiInfo = Field(..., description="Situacao, historicos e eventos exclusivos do SIMEI")
    mei_transportador: MeiTransportador = Field(..., description="Periodos de MEI Transportador, sem inferir colunas desconhecidas")
    alertas: list[str] = Field(..., description="Mensagens visiveis distintas; [] quando nao ha alertas")
    dados_adicionais: list[DadoAdicional] | None = Field(default_factory=list, exclude_if=lambda valor: not valor, description="Secoes fiscais desconhecidas; omitido quando vazio")

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "cnpj_consultado": "43996591000101",
                "cnpj_matriz": "43996591000101",
                "nome_empresarial": "ELIANE S MURTA CONSULTORIO ODONTOLOGICO",
                "consultado_em": "2026-10-15T18:08:45",
                "abrange_todos_estabelecimentos": True,
                "simples_nacional": {
                    "optante": True,
                    "situacao": "Optante pelo Simples Nacional desde 01/01/2026",
                    "data_desde": "2026-01-01",
                    "periodos_anteriores": [
                        {
                            "data_inicial": "2025-01-01",
                            "data_final": "2025-12-31",
                            "detalhamento": "Excluída por Ato Administrativo praticado pela Receita Federal do Brasil",
                        },
                        {
                            "data_inicial": "2024-01-01",
                            "data_final": "2024-12-31",
                            "detalhamento": "Excluída por Ato Administrativo praticado pela Receita Federal do Brasil",
                        },
                        {
                            "data_inicial": "2021-10-25",
                            "data_final": "2023-12-31",
                            "detalhamento": "Excluída por Ato Administrativo praticado pela Receita Federal do Brasil",
                        },
                    ],
                    "eventos_futuros": [{
                        "descricao": "Exclusão de Ofício - Débitos",
                        "data_efeito": "2027-01-01",
                    }],
                },
                "simei": {
                    "enquadrado": False,
                    "situacao": "NÃO enquadrado no SIMEI",
                    "data_desde": None,
                    "periodos_anteriores": [],
                    "eventos_futuros": [],
                },
                "mei_transportador": {"possui_periodos": False},
                "alertas": [],
            }],
        },
    }


class ConsultaResponse(BaseModel):
    """Resposta completa com cadastro, DASN e situacao no Simples/SIMEI."""

    cnpj: str = Field(..., description="CNPJ consultado", examples=["45.726.608/0001-36"])
    cadastro: CadastroResponse = Field(..., description="Dados cadastrais do CNPJ")
    dasn: DasnResultado = Field(..., description="Declaracoes ou resposta 33001 corroborada; null nao confirma ausencia de pendencias")
    optantes: OptantesResponse = Field(..., description="Situacao no Simples Nacional e SIMEI")
