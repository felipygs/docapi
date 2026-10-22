"""Contrato HTTP real em loopback; os serviços externos são simulados, não as rotas."""
import asyncio
import json
import socket
import threading
import unittest
from copy import deepcopy
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import AsyncMock, MagicMock, patch

import uvicorn
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from app.api import app
from app.models import CadastroResponse, DasnResponse
from test_optantes_models import eliane, conteudo


class TestOptantesHTTP(unittest.TestCase):
    def test_http_dasn_33001_preserva_null_e_status(self):
        payload = {
            'status': 'nao_optante_simei_confirmado_por_optantes',
            'codigo_origem': '33001', 'cnpj': '43996591000101',
            'razao_social': 'EMPRESA EXEMPLO', 'situacao_declaracoes': 'nao_consultadas',
            'declaracoes': None, 'pendentes': None, 'mei_baixada': None,
            'data_baixa': None, 'optantes_consultado_em': '2026-10-17T00:42:08',
            'mensagem': 'Declaracoes e pendencias nao verificadas.',
        }
        with patch('app.api.consultar_apenas_dasn', AsyncMock(return_value=payload)):
            status, body = self.post('/consultar/dasn')
        self.assertEqual(status, 200)
        self.assertEqual(body, payload)
        with patch('app.api.consultar_mei', AsyncMock(return_value={**self.agregado(eliane()), 'dasn': payload})):
            status, body = self.post('/consultar')
        self.assertEqual(status, 200)
        self.assertEqual(body['dasn'], payload)

    @classmethod
    def setUpClass(cls):
        cls.socket = socket.socket()
        cls.socket.bind(('127.0.0.1', 0))
        cls.socket.listen(128)
        cls.server = uvicorn.Server(uvicorn.Config(app, log_level='error', lifespan='off'))
        cls.thread = threading.Thread(target=cls.server.run, kwargs={'sockets': [cls.socket]}, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.socket.getsockname()[1]}'
        # Uma requisição HTTP de prontidão é suficiente: o socket já está escutando.
        try:
            with urlopen(cls.base + '/health', timeout=10) as r:
                assert r.status == 200
        except Exception:
            cls.server.should_exit = True
            cls.thread.join(timeout=10)
            cls.socket.close()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.server.should_exit = True
        cls.thread.join(timeout=10)
        cls.socket.close()
        if cls.thread.is_alive():
            raise AssertionError('Servidor HTTP de teste não encerrou')

    def post(self, path, body=None):
        request = Request(self.base + path, data=json.dumps(body or {'cnpj': '43.996.591/0001-01'}).encode(), headers={'Content-Type': 'application/json'}, method='POST')
        try:
            response = urlopen(request, timeout=10)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response)

    @staticmethod
    def agregado(payload):
        return {'cnpj': '43.996.591/0001-01', 'cadastro': CadastroResponse.model_config['json_schema_extra']['examples'][0], 'dasn': DasnResponse.model_config['json_schema_extra']['examples'][0], 'optantes': payload}

    def test_openapi_2000_migracao_e_integridade_documentadas(self):
        with urlopen(self.base + '/openapi.json', timeout=10) as r:
            schema = json.load(r)
        self.assertEqual(schema['info']['version'], '2.0.0')
        description = schema['info']['description'].lower()
        for trecho in ('eventos_futuros', 'texto', 'null', 'lista', '502', '504', 'sem fuso', 'parcial'):
            self.assertIn(trecho, description)
        components = schema['components']['schemas']
        # Pydantic pode separar nomes de entrada e saída com omissão condicional.
        opt_key = schema['paths']['/consultar/optantes']['post']['responses']['200']['content']['application/json']['schema']['$ref'].split('/')[-1]
        opt = components[opt_key]
        self.assertIn('cnpj_matriz', opt['required'])
        self.assertIn('mei_transportador', opt['properties'])
        simples_key = opt['properties']['simples_nacional']['$ref'].split('/')[-1]
        eventos = components[simples_key]['properties']['eventos_futuros']
        self.assertEqual(eventos['type'], 'array')
        event = components[eventos['items']['$ref'].split('/')[-1]]
        self.assertIn('descricao', event['properties'])
        self.assertIn('data_efeito', event['properties'])
        example = opt['examples'][0]
        self.assertEqual(example['simei']['periodos_anteriores'], [])
        self.assertEqual(example['simples_nacional']['eventos_futuros'][0]['data_efeito'], '2027-01-01')
        complete_key = schema['paths']['/consultar']['post']['responses']['200']['content']['application/json']['schema']['$ref'].split('/')[-1]
        self.assertEqual(components[complete_key]['properties']['optantes']['$ref'].split('/')[-1], opt_key)

    def test_http_individual_e_agregado_preservam_contrato_e_nulos(self):
        expected = eliane()
        payload = deepcopy(expected)
        payload['dados_adicionais'] = []
        payload['mei_transportador']['detalhes'] = None
        payload['simples_nacional']['periodos_anteriores'][0]['campos_adicionais'] = []
        payload['simples_nacional']['eventos_futuros'][0]['campos_adicionais'] = None
        individual = AsyncMock(return_value=deepcopy(payload))
        completo = AsyncMock(return_value=self.agregado(deepcopy(payload)))
        with patch('app.api.consultar_apenas_optantes', individual), patch('app.api.consultar_mei', completo):
            status, result = self.post('/consultar/optantes')
            aggregate_status, aggregate = self.post('/consultar')
        self.assertEqual(status, 200)
        self.assertEqual(aggregate_status, 200)
        self.assertEqual(result, expected)
        self.assertEqual(aggregate['optantes'], result)
        self.assertIsNone(result['simei']['data_desde'])
        self.assertNotIn('dados_adicionais', result)
        self.assertNotIn('detalhes', result['mei_transportador'])
        individual.assert_awaited_once_with('43.996.591/0001-01')
        completo.assert_awaited_once_with('43.996.591/0001-01')

    def test_http_extensoes_preenchidas_nao_sao_filtradas(self):
        payload = eliane()
        payload['simples_nacional']['eventos_futuros'][0]['data_efeito'] = None
        payload['simples_nacional']['eventos_futuros'][0]['campos_adicionais'] = [{'coluna': 'Nota', 'valor': 'A'}, {'coluna': 'Nota', 'valor': ''}]
        payload['mei_transportador'] = {'possui_periodos': True, 'detalhes': conteudo()}
        payload['dados_adicionais'] = [{'secao': 'Seção sintética', **conteudo()}]
        expected = deepcopy(payload)  # Oráculo independente do serializer sob teste.
        with patch('app.api.consultar_apenas_optantes', AsyncMock(return_value=payload)), patch('app.api.consultar_mei', AsyncMock(return_value=self.agregado(payload))):
            status, result = self.post('/consultar/optantes')
            agg_status, aggregate = self.post('/consultar')
        self.assertEqual((status, agg_status), (200, 200))
        self.assertEqual(result, expected)
        self.assertEqual(aggregate['optantes'], expected)

    def test_http_502_504_sem_payload_parcial_em_ambas_rotas(self):
        for path, target in (('/consultar/optantes', 'app.api.consultar_apenas_optantes'), ('/consultar', 'app.api.consultar_mei')):
            for exception, expected in ((RuntimeError('Optantes - Eventos Futuros (SIMEI): painel obrigatório ausente'), 502), (PlaywrightTimeoutError('Optantes - timeout no carregamento complementar'), 504)):
                with self.subTest(path=path, status=expected), patch(target, AsyncMock(side_effect=exception)):
                    status, body = self.post(path)
                    self.assertEqual(status, expected)
                    self.assertEqual(set(body), {'detail'})
                    self.assertIn('Optantes', body['detail'])
                    self.assertNotIn('simples_nacional', body)

    def test_agregado_real_propaga_falha_optantes_e_fecha_browser(self):
        # Não mocka app.api.consultar_mei: executa a orquestração real.
        # Somente browser e consultas externas são substituídos.
        # Falha definitiva não usa backoff; preservar asyncio.sleep do Uvicorn.
        browser = MagicMock()
        browser.close = AsyncMock()
        context = MagicMock()
        context.new_page = AsyncMock(return_value=MagicMock())
        playwright_context = MagicMock()
        playwright_context.__aenter__ = AsyncMock(return_value=MagicMock())
        playwright_context.__aexit__ = AsyncMock(return_value=False)
        cadastro = deepcopy(CadastroResponse.model_config['json_schema_extra']['examples'][0])
        dasn = deepcopy(DasnResponse.model_config['json_schema_extra']['examples'][0])
        with patch('app.consultar.async_playwright', return_value=playwright_context), \
             patch('app.consultar.create_browser', AsyncMock(return_value=(browser, context))), \
             patch('app.consultar.consultar_cnpj', AsyncMock(return_value=cadastro)), \
             patch('app.consultar.consultar_dasn', AsyncMock(return_value=dasn)), \
             patch('app.consultar.consultar_optantes', AsyncMock(side_effect=RuntimeError('Optantes - SIMEI: painel ausente'))):
            status, body = self.post('/consultar')
        self.assertEqual(status, 502)
        self.assertEqual(body, {'detail': 'Optantes - SIMEI: painel ausente'})
        # Cadastro, DASN e Optantes agora têm sessões independentes.
        self.assertEqual(browser.close.await_count, 3)
        playwright_context.__aexit__.assert_awaited_once()

    def test_agregado_cadastro_pendurado_retorna_504_e_libera_sessao(self):
        from test_consultar_recovery import PlaywrightLocal, Sessao

        sessao = Sessao()
        seguintes = []

        async def cadastro(page, cnpj):
            await asyncio.Event().wait()

        async def indevido(*args, **kwargs):
            seguintes.append(True)
            raise AssertionError('Executou modulo apos expirar o cadastro')

        with patch('app.consultar.async_playwright', PlaywrightLocal), \
             patch('app.consultar.create_browser', AsyncMock(return_value=(sessao, sessao))), \
             patch('app.consultar.consultar_cnpj', cadastro), \
             patch('app.consultar.consultar_dasn', indevido), \
             patch('app.consultar.consultar_optantes', indevido), \
             patch('app.consultar._CADASTRO_TIMEOUT_SECONDS', 0.02):
            status, body = self.post('/consultar')
        self.assertEqual(status, 504)
        self.assertIn('CNPJ', body['detail'])
        self.assertNotIn('cadastro', body)
        self.assertTrue(sessao.fechada)
        self.assertEqual(seguintes, [])

    def test_http_cnpj_e_dasn_continuam_serializando_como_antes(self):
        for path, target, model in (('/consultar/cnpj', 'app.api.consultar_apenas_cnpj', CadastroResponse), ('/consultar/dasn', 'app.api.consultar_apenas_dasn', DasnResponse)):
            payload = deepcopy(model.model_config['json_schema_extra']['examples'][0])
            with self.subTest(path=path), patch(target, AsyncMock(return_value=payload)):
                status, body = self.post(path)
                self.assertEqual(status, 200)
                self.assertEqual(body, model.model_validate(payload).model_dump(mode='json'))


if __name__ == '__main__':
    unittest.main()
