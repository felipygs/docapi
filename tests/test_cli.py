"""Saida da CLI com o contrato atual; apenas a consulta externa e simulada."""
from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
import json
import unittest
from unittest.mock import AsyncMock, patch

import main
from app.models import CadastroResponse, DasnResponse
from test_optantes_models import eliane


class TestCLI(unittest.TestCase):
    def resultado(self):
        return {
            'cnpj': '43.996.591/0001-01',
            'cadastro': deepcopy(CadastroResponse.model_config['json_schema_extra']['examples'][0]),
            'dasn': deepcopy(DasnResponse.model_config['json_schema_extra']['examples'][0]),
            'optantes': eliane(),
        }

    def executar(self, resultado, *opcoes):
        saida = StringIO()
        with patch('sys.argv', ['main.py', resultado['cnpj'], *opcoes]), patch(
            'app.consultar.consultar_mei', AsyncMock(return_value=resultado),
        ), redirect_stdout(saida):
            try:
                main.run_cli()
            except KeyError as exc:
                self.fail(f'A CLI ainda depende de um campo legado: {exc}')
        return saida.getvalue()

    def test_exibe_endereco_contato_historicos_e_pendencias_do_contrato_atual(self):
        resultado = self.resultado()
        resultado['dasn']['pendentes'] = [2023]
        resultado['dasn']['declaracoes'][1].update(status='nao apresentada', pendente=True)
        saida = self.executar(resultado)
        for trecho in (
            'R EXEMPLO, 123', 'SAO PAULO/SP', 'contato@exemplo.com',
            '912345678', 'Optante pelo Simples Nacional desde 01/01/2026',
            '2025-01-01', '2025-12-31', 'Declaracoes PENDENTES: 2023',
        ):
            self.assertIn(trecho, saida)

    def test_dasn_nao_consultada_nao_afirma_ausencia_de_pendencias(self):
        resultado = self.resultado()
        resultado['dasn'] = {
            'status': 'nao_optante_simei_confirmado_por_optantes',
            'codigo_origem': '33001', 'cnpj': '43996591000101',
            'razao_social': 'EMPRESA EXEMPLO', 'situacao_declaracoes': 'nao_consultadas',
            'declaracoes': None, 'pendentes': None, 'mei_baixada': None,
            'data_baixa': None, 'optantes_consultado_em': '2026-10-17T00:42:08',
            'mensagem': 'Declaracoes e pendencias DASN nao verificadas.',
        }
        saida = self.executar(resultado)
        self.assertIn('Declaracoes e pendencias DASN nao verificadas.', saida)
        self.assertNotIn('Nenhuma declaracao pendente', saida)
        self.assertNotIn('MEI BAIXADA', saida)

    def test_json_preserva_resposta_completa_e_campos_opcionais_vazios(self):
        resultado = self.resultado()
        resultado['cadastro']['nome_empresarial'] = None
        resultado['cadastro']['nome_fantasia'] = None
        resultado['cadastro']['contato'] = {'email': None, 'telefone': {'ddd': None, 'numero': None}}
        resultado['cadastro']['endereco']['complemento'] = None
        saida = self.executar(resultado, '--json')
        inicio = saida.index('\n{') + 1
        self.assertEqual(json.loads(saida[inicio:]), resultado)
        self.assertIn('Razao Social: EMPRESA EXEMPLO LTDA', saida)


if __name__ == '__main__':
    unittest.main()
