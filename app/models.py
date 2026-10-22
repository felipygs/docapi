"""Fachada compatível dos contratos de entrada e saída."""
from .contracts.request import ConsultaRequest
from .contracts.cadastro import (
    CadastroResponse, Cnae, Contato, Endereco, NaturezaJuridica,
    SituacaoCadastral, Socio, Telefone,
)
from .contracts.dasn import Declaracao, DasnResponse, DasnNaoOptanteResponse, DasnResultado
from .contracts.optantes import (
    CampoAdicional, ConteudoSecao, DadoAdicional, EventoFuturo,
    MeiTransportador, OptantesResponse, Periodo, SimeiInfo, SimplesInfo, Tabela,
)
from .contracts.consulta import ConsultaResponse

__all__ = [
    'ConsultaRequest', 'CadastroResponse', 'Cnae', 'Contato', 'Endereco',
    'NaturezaJuridica', 'SituacaoCadastral', 'Socio', 'Telefone',
    'Declaracao', 'DasnResponse', 'DasnNaoOptanteResponse', 'DasnResultado',
    'CampoAdicional', 'ConteudoSecao', 'DadoAdicional', 'EventoFuturo',
    'MeiTransportador', 'OptantesResponse', 'Periodo', 'SimeiInfo', 'SimplesInfo',
    'Tabela', 'ConsultaResponse',
]
