import unittest
from copy import deepcopy
from unittest.mock import AsyncMock, patch

from app import consulta_service as consultas
from app.errors import NaoOptanteError
from app.models import OptantesResponse
from support.sessions import PlaywrightLocal, Sessao


class TestDasnOutcome(unittest.IsolatedAsyncioTestCase):
    async def test_agregado_reutiliza_evidencia_optantes_da_conferencia(self):
        opt = deepcopy(OptantesResponse.model_config['json_schema_extra']['examples'][0])
        sessao = Sessao()
        recovery = AsyncMock(side_effect=[NaoOptanteError('33001'), opt])
        with patch.object(consultas, 'async_playwright', PlaywrightLocal), \
             patch.object(consultas, 'create_browser', AsyncMock(return_value=(sessao, sessao))), \
             patch.object(consultas, 'consultar_cnpj', AsyncMock(return_value={'nome_empresarial':'EXEMPLO'})), \
             patch.object(consultas, '_consultar_com_recuperacao', recovery):
            result = await consultas.consultar_mei('43996591000101')
        self.assertEqual(recovery.await_count, 2)
        self.assertEqual(result['optantes'], opt)
        self.assertIsNone(result['dasn']['pendentes'])

    async def test_33001_cruza_optantes_sem_inventar_declaracoes(self):
        opt = deepcopy(OptantesResponse.model_config['json_schema_extra']['examples'][0])
        recovery = AsyncMock(side_effect=[NaoOptanteError('33001'), opt])
        with patch.object(consultas, '_consultar_com_recuperacao', recovery):
            result, evidence = await consultas._consultar_dasn_com_situacao(object(), '43996591000101')
        self.assertEqual(result['status'], 'nao_optante_simei_confirmado_por_optantes')
        self.assertEqual(result['codigo_origem'], '33001')
        self.assertIsNone(result['declaracoes'])
        self.assertIsNone(result['pendentes'])
        self.assertIsNone(result['mei_baixada'])
        self.assertEqual(result['situacao_declaracoes'], 'nao_consultadas')
        self.assertEqual(evidence, opt)

    async def test_historico_simei_ou_enquadramento_atual_impede_confirmacao(self):
        for current in (True, False):
            opt = deepcopy(OptantesResponse.model_config['json_schema_extra']['examples'][0])
            opt['simei']['enquadrado'] = current
            if not current:
                opt['simei']['periodos_anteriores'] = [{'data_inicial': '2020-01-01', 'data_final': '2021-01-01', 'detalhamento': None}]
            with patch.object(consultas, '_consultar_com_recuperacao', AsyncMock(side_effect=[NaoOptanteError('33001'), opt])):
                with self.assertRaisesRegex(RuntimeError, 'divergencia'):
                    await consultas._consultar_dasn_com_situacao(object(), '43996591000101')

    async def test_falha_optantes_nao_vira_confirmacao(self):
        with patch.object(consultas, '_consultar_com_recuperacao', AsyncMock(side_effect=[NaoOptanteError('33001'), TimeoutError('origem')])):
            with self.assertRaises(TimeoutError):
                await consultas._consultar_dasn_com_situacao(object(), '43996591000101')

    async def test_declaracoes_obtidas_preservam_contrato_sem_consulta_extra(self):
        payload = {'razao_social': 'EXEMPLO', 'declaracoes': [{'ano': 2025}]}
        recovery = AsyncMock(return_value=payload)
        with patch.object(consultas, '_consultar_com_recuperacao', recovery):
            result, evidence = await consultas._consultar_dasn_com_situacao(object(), '43996591000101')
        self.assertEqual(result, payload)
        self.assertIsNone(evidence)
        self.assertEqual(recovery.await_count, 1)
