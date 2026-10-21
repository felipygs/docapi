from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from .models import (
    ConsultaRequest, ConsultaResponse,
    CadastroResponse, DasnResponse, DasnResultado, OptantesResponse,
)
from .consultar import (
    consultar_mei,
    consultar_apenas_cnpj,
    consultar_apenas_dasn,
    consultar_apenas_optantes,
)

app = FastAPI(
    title="Simplix DocAPI",
    version="2.0.0",
    description="""
## API de Consulta CNPJ / MEI

Consulta automatizada de dados cadastrais, declaracoes DASN-SIMEI e situacao
no Simples Nacional direto dos portais da **Receita Federal do Brasil**.

### Endpoints disponiveis

| Endpoint | Descricao |
|---|---|
| `POST /consultar` | Consulta completa (cadastro + DASN + optantes) |
| `POST /consultar/cnpj` | Apenas dados cadastrais do CNPJ |
| `POST /consultar/dasn` | Apenas declaracoes DASN-SIMEI |
| `POST /consultar/optantes` | Apenas situacao no Simples/SIMEI |

### Formato do CNPJ
Aceita com ou sem mascara: `45.726.608/0001-36` ou `45726608000136`

### Tempo de resposta
As consultas acessam portais externos da Receita Federal em tempo real.
DASN e Optantes permitem ate **3 tentativas**, com sessao nova e prazo de
**180 segundos por modulo**, mais um prazo curto de liberacao do navegador.
Falhas transitorias e mensagens de bloqueio Captcha permitem novas submissoes
normais dentro desses limites, sem resolver desafios automaticamente. CNPJ
invalido e dados inconsistentes encerram a consulta. Falha nao significa
ausencia de pendencias. A consulta completa executa os modulos sequencialmente,
sem repetir os anteriores que ja terminaram. Cadastro CNPJ tem fluxo proprio,
com prazo total de **180 segundos**, incluindo abertura e tentativas de captcha,
mais ate cinco segundos para liberar o navegador. A consulta completa soma
os tempos dos modulos; nao ha um limite unico de 180 segundos para os tres.

### Migracao do contrato de Optantes — 2.0.0 (quebra de compatibilidade)
O novo contrato substitui a resposta anterior em `POST /consultar/optantes` e no
bloco `optantes` de `POST /consultar`, sem alterar as rotas ou a entrada `cnpj`.
`eventos_futuros` deixa de ser texto tabulado ou `null` e passa a ser uma lista de
objetos com `descricao` integral e `data_efeito` em `YYYY-MM-DD`.
Historicos e eventos sao independentes para Simples Nacional e SIMEI; uma exclusao
futura nao altera o booleano da situacao atual.

A resposta inclui CNPJ consultado e matriz, nome empresarial, abrangencia e
`consultado_em`: horario local exibido pela Receita, sem fuso presumido.
`mei_transportador.possui_periodos` informa ausencia confirmada ou existencia de
conteudo, preservado em `detalhes` quando preenchido. Colunas e secoes adicionais
sao preservadas em campos condicionais, omitidos quando vazios.

Uma lista `[]` significa ausencia explicitamente confirmada; nao significa erro
ou secao nao coletada. Datas opcionais explicitamente vazias permanecem `null`.
Nao ha resposta HTTP 200 parcial de Optantes: falha ou ambiguidade de extracao
retorna **502**, e timeout externo retorna **504**. Os contratos cadastral e DASN
permanecem inalterados.

### Codigos de erro
| Codigo | Significado |
|---|---|
| 400 | CNPJ invalido |
| 502 | Falha no portal da Receita (captcha, indisponibilidade) |
| 504 | Timeout no portal externo |
| 500 | Erro interno inesperado |
""",
    openapi_tags=[
        {
            "name": "Consulta Completa",
            "description": "Retorna cadastro, DASN e situacao no Simples/SIMEI em uma unica chamada.",
        },
        {
            "name": "Consulta Individual",
            "description": "Consulta cada modulo separadamente para maior flexibilidade e menor tempo de resposta.",
        },
        {
            "name": "Sistema",
            "description": "Endpoints de monitoramento e saude da aplicacao.",
        },
    ],
)


class ErrorResponse(BaseModel):
    """Resposta padrao de erro."""
    detail: str


_ERROR_RESPONSES = {
    400: {
        "model": ErrorResponse,
        "description": "CNPJ invalido",
        "content": {"application/json": {"example": {"detail": "CNPJ invalido"}}},
    },
    500: {
        "model": ErrorResponse,
        "description": "Erro interno",
        "content": {"application/json": {"example": {"detail": "Erro inesperado no processamento"}}},
    },
    502: {
        "model": ErrorResponse,
        "description": "Falha no servico externo (Receita Federal)",
        "content": {"application/json": {"example": {"detail": "CNPJ - captcha rejeitado pela Receita"}}},
    },
    504: {
        "model": ErrorResponse,
        "description": "Timeout no servico externo",
        "content": {"application/json": {"example": {"detail": "Timeout no servico externo: page.wait_for_url: Timeout 30000ms exceeded."}}},
    },
}


async def _safe_call(fn, *args):
    try:
        return await fn(*args)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PlaywrightTimeoutError as e:
        raise HTTPException(status_code=504, detail=f"Timeout no servico externo: {e}")
    except TimeoutError as e:
        raise HTTPException(status_code=504, detail=f"Timeout no servico externo: {e}")
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/consultar",
    response_model=ConsultaResponse,
    responses=_ERROR_RESPONSES,
    tags=["Consulta Completa"],
    summary="Consulta completa MEI/CNPJ",
    description="Retorna dados cadastrais, declaracoes DASN-SIMEI e situacao no Simples Nacional/SIMEI "
                "em uma unica chamada. Executa os 3 modulos sequencialmente.",
    response_description="Dados completos do CNPJ consultado",
)
async def consultar(req: ConsultaRequest):
    return await _safe_call(consultar_mei, req.cnpj)


@app.post(
    "/consultar/cnpj",
    response_model=CadastroResponse,
    responses=_ERROR_RESPONSES,
    tags=["Consulta Individual"],
    summary="Consultar dados cadastrais",
    description="Retorna dados cadastrais extraidos do Comprovante de Inscricao e Situacao Cadastral "
                "da Receita Federal, incluindo razao social, endereco, CNAEs, situacao cadastral, "
                "capital social e quadro de socios.",
    response_description="Dados cadastrais do CNPJ",
)
async def consultar_cnpj(req: ConsultaRequest):
    return await _safe_call(consultar_apenas_cnpj, req.cnpj)


@app.post(
    "/consultar/dasn",
    response_model=DasnResultado,
    responses=_ERROR_RESPONSES,
    tags=["Consulta Individual"],
    summary="Consultar declaracoes DASN-SIMEI",
    description="Retorna a lista de declaracoes anuais DASN-SIMEI do contribuinte, "
                "incluindo status (apresentada, pendente), ano-calendario, "
                "data de apresentacao e situacao de baixa. Quando a origem responde 33001, "
                "cruza Optantes: ausencia de enquadramento e historico SIMEI retorna status "
                "nao_optante_simei_confirmado_por_optantes, com declaracoes e pendentes null "
                "(nao consultadas). Divergencia ou falha da conferencia gera erro, nunca ausencia de pendencias.",
    response_description="Declaracoes DASN-SIMEI do contribuinte",
)
async def consultar_dasn(req: ConsultaRequest):
    return await _safe_call(consultar_apenas_dasn, req.cnpj)


@app.post(
    "/consultar/optantes",
    response_model=OptantesResponse,
    responses=_ERROR_RESPONSES,
    tags=["Consulta Individual"],
    summary="Consultar situacao Simples Nacional / SIMEI",
    description="Contrato 2.0.0: identificacao, horario local da origem sem fuso, "
                "situacoes atuais, historicos independentes e eventos futuros em listas "
                "de descricao/data_efeito, alem de MEI Transportador. Substitui eventos "
                "em texto/null; [] confirma ausencia. Nao retorna sucesso parcial: "
                "secoes incompletas ou ambiguas geram 502 e timeout gera 504.",
    response_description="Situacao no Simples Nacional e SIMEI",
)
async def consultar_optantes(req: ConsultaRequest):
    return await _safe_call(consultar_apenas_optantes, req.cnpj)


@app.get(
    "/health",
    tags=["Sistema"],
    summary="Health check",
    description="Verifica se a aplicacao esta rodando e respondendo.",
    response_description="Status da aplicacao",
)
async def health():
    return {"status": "ok"}
