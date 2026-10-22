"""Regra pura: corroborar o desfecho DASN 33001 com evidencia Optantes."""
from .errors import DadosIncompletosError
from .models import DasnNaoOptanteResponse, OptantesResponse


def confirmar_nao_optante(cnpj: str, optantes: dict) -> dict:
    evidencia = OptantesResponse.model_validate(optantes)
    if evidencia.cnpj_consultado != cnpj or evidencia.cnpj_matriz[:8] != cnpj[:8]:
        raise DadosIncompletosError('DASN - divergencia de identidade na conferencia Optantes') from None
    if evidencia.simei.enquadrado or evidencia.simei.periodos_anteriores or evidencia.simei.eventos_futuros:
        raise DadosIncompletosError('DASN - divergencia entre resposta 33001 e situacao ou historico SIMEI; conferir') from None
    resultado = DasnNaoOptanteResponse(
        status='nao_optante_simei_confirmado_por_optantes', codigo_origem='33001',
        cnpj=cnpj, razao_social=evidencia.nome_empresarial,
        situacao_declaracoes='nao_consultadas', declaracoes=None, pendentes=None,
        mei_baixada=None, data_baixa=None, optantes_consultado_em=evidencia.consultado_em,
        mensagem='Receita informou nao optante pelo SIMEI (33001); Optantes confirmou ausencia de enquadramento atual e periodos anteriores. Declaracoes e pendencias DASN nao verificadas.',
    )
    return resultado.model_dump(mode='json')
