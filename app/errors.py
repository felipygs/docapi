"""Falhas de consulta classificadas sem depender do texto público do erro."""


class FalhaTransitoriaError(RuntimeError):
    codigo = 'falha_transitoria'


class CaptchaBloqueadoError(RuntimeError):
    codigo = 'captcha_bloqueado'


class DadosIncompletosError(RuntimeError):
    codigo = 'dados_incompletos'


class IdentidadeDivergenteError(DadosIncompletosError):
    codigo = 'identidade_divergente'


class CnpjInvalidoError(ValueError):
    codigo = 'cnpj_invalido'


class NaoOptanteError(RuntimeError):
    codigo = 'nao_optante'
