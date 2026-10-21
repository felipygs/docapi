"""Contrato cadastral exercitado com respostas reais e variantes sintéticas."""
import copy
import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app import captcha
from app.models import CadastroResponse
from app.scrapers import cnpj

FIXTURE = Path(__file__).parent / 'fixtures' / 'cnpj' / 'cadastro.json'


class CadastroParserTests(unittest.TestCase):
    def setUp(self):
        self.dados = json.loads(FIXTURE.read_text(encoding='utf8'))

    def parse(self, dados=None, qsa=None):
        return cnpj.parse_cadastro(dados or self.dados, qsa or {'socios': []}, '37482317000111')

    def test_resposta_real_preserva_contrato_e_capital_em_centavos(self):
        r = CadastroResponse.model_validate(self.parse()).model_dump()
        self.assertEqual(r['nome_empresarial'], 'THIARLLES BARBOSA DE SOUSA')
        self.assertEqual(r['data_abertura'], '2020-06-22')
        self.assertEqual(r['capital_social'], 400000)
        self.assertEqual(r['atividade_principal']['codigo'], '49.30-2-01')
        self.assertEqual(len(r['atividades_secundarias']), 1)
        self.assertEqual(r['endereco']['cep'], '65918384')
        self.assertEqual(r['contato']['telefone'], {'ddd': '99', 'numero': '84559174'})
        self.assertTrue(r['situacao_cadastral']['ativa'])
        self.assertIsNone(r['nome_fantasia'])
        self.assertIsNone(r['ente_federativo'])
        self.assertEqual(r['socios'], [])

    def test_socios_qualificacao_filial_e_todos_cnaes(self):
        dados = copy.deepcopy(self.dados)
        dados['tipoEstabelecimento'] = 'FILIAL'
        dados['indicadorMatriz'] = '2'
        dados['cnaesSecundarias'] *= 25
        r = self.parse(dados, {'socios': [{'nome': 'SOCIO EXEMPLO', 'qualificacao': '49', 'qualificacaoExtenso': 'Sócio-Administrador'}]})
        self.assertFalse(r['matriz'])
        self.assertEqual(len(r['atividades_secundarias']), 25)
        self.assertEqual(r['socios'], [{'nome': 'SOCIO EXEMPLO', 'qualificacao': '49-Sócio-Administrador'}])

    def test_identidade_incompleta_situacao_desconhecida_e_datas_invalidas_falham(self):
        for campo, valor in [('cnpj', '00000000000191'), ('nomeEmpresarial', ''), ('dataAbertura', '31/02/2020'), ('descricaoSituacaoCadastral', ''), ('cnaesSecundarias', None)]:
            with self.subTest(campo=campo):
                dados = copy.deepcopy(self.dados)
                dados[campo] = valor
                with self.assertRaises(RuntimeError):
                    self.parse(dados)

    def test_qsa_incompleto_nao_se_converte_em_lista_vazia(self):
        with self.assertRaises(RuntimeError):
            cnpj.parse_cadastro(self.dados, {}, '37482317000111')


class NonecapTests(unittest.TestCase):
    def response(self, status, payload):
        return Mock(status_code=status, json=Mock(return_value=payload))

    def test_submit_poll_e_user_agent(self):
        pending = self.response(202, {'id': 'solve_teste', 'status': 'solving'})
        solved = self.response(200, {'id': 'solve_teste', 'status': 'solved', 'token': 'TOKEN_TESTE', 'user_agent': 'UA_TESTE'})
        with patch.object(captcha, 'NONECAP_API_KEY', 'CHAVE_TESTE', create=True), patch.object(captcha.requests, 'post', return_value=pending) as post, patch.object(captcha.requests, 'get', return_value=solved):
            r = captcha.resolver_hcaptcha_nonecap('https://portal.test/', 'sitekey', user_agent='UA_TESTE')
        self.assertEqual(r['token'], 'TOKEN_TESTE')
        self.assertEqual(post.call_args.kwargs['headers']['Authorization'], 'Bearer CHAVE_TESTE')
        self.assertEqual(post.call_args.kwargs['json']['user_agent'], 'UA_TESTE')

    def test_erro_sem_creditos_nao_expoe_mensagem_ou_chave(self):
        response = self.response(402, {'error': {'code': 'insufficient_credits', 'message': 'SEGREDO CHAVE_TESTE'}})
        with patch.object(captcha, 'NONECAP_API_KEY', 'CHAVE_TESTE', create=True), patch.object(captcha.requests, 'post', return_value=response):
            with self.assertRaisesRegex(RuntimeError, 'insufficient_credits') as raised:
                captcha.resolver_hcaptcha_nonecap('https://portal.test/', 'sitekey')
        self.assertNotIn('SEGREDO', str(raised.exception))
        self.assertNotIn('CHAVE_TESTE', str(raised.exception))


if __name__ == '__main__':
    unittest.main()
