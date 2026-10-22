"""A transformação DASN deve funcionar com dados brutos, sem navegador."""
from copy import deepcopy
import unittest

from app.errors import DadosIncompletosError, IdentidadeDivergenteError
from app.scrapers import dasn


class DasnParserTests(unittest.TestCase):
    def snapshot(self):
        return {'cnpj_origem': '43.996.591/0001-01', 'razao_social': 'EMPRESA', 'declaracoes': [
            {'ano': '2025', 'tipo_declaracao': 'Retificadora', 'situacao_especial': 'Extinção',
             'data_baixa': '26/08/2025', 'status': 'não apresentada', 'pendente': True, 'baixada': True},
        ]}

    def test_transformacao_pura_preserva_baixa_pendencias_e_ordem(self):
        raw = self.snapshot()
        original = deepcopy(raw)
        result = dasn.transformar_snapshot_dasn(raw, '43996591000101')
        self.assertEqual(result['pendentes'], [2025])
        self.assertTrue(result['mei_baixada'])
        self.assertEqual(result['data_baixa'], '2025-08-26')
        self.assertTrue(result['declaracoes'][0]['retificadora'])
        self.assertEqual(result['declaracoes'][0]['status'], 'não apresentada')
        self.assertEqual(raw, original)

    def test_identidade_ausente_continua_aceita_e_divergente_rejeitada(self):
        raw = self.snapshot()
        raw['cnpj_origem'] = None
        self.assertEqual(dasn.transformar_snapshot_dasn(raw, '43996591000101')['razao_social'], 'EMPRESA')
        raw['cnpj_origem'] = '00000000000191'
        with self.assertRaises(IdentidadeDivergenteError):
            dasn.transformar_snapshot_dasn(raw, '43996591000101')

    def test_dados_incompletos_continuam_erro(self):
        raw = self.snapshot()
        raw['declaracoes'] = []
        with self.assertRaises(DadosIncompletosError):
            dasn.transformar_snapshot_dasn(raw, '43996591000101')
