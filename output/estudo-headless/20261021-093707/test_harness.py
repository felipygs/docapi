"""Verificações do instrumento descartável, sem consultas externas."""
import copy
import unittest
from study import normalize, safe_failure, launch_options

class HarnessTests(unittest.TestCase):
    def test_horarios_ignorados_somente_nos_locais_previstos(self):
        a = {'optantes': {'consultado_em':'a', 'dados_adicionais':[{'consultado_em':'fato'}]},
             'dasn': {'optantes_consultado_em':'a'}, 'cadastro': {'capital_social':100}}
        b = copy.deepcopy(a)
        b['optantes']['consultado_em'] = 'b'
        b['dasn']['optantes_consultado_em'] = 'b'
        self.assertEqual(normalize('/consultar',a),normalize('/consultar',b))
        b['optantes']['dados_adicionais'][0]['consultado_em'] = 'outro fato'
        self.assertNotEqual(normalize('/consultar',a),normalize('/consultar',b))

    def test_divergencia_fiscal_nao_desaparece(self):
        self.assertNotEqual(normalize('/consultar/cnpj',{'capital_social':100}),
                            normalize('/consultar/cnpj',{'capital_social':101}))

    def test_falha_nao_copia_detail_externo(self):
        self.assertEqual(safe_failure(502, {'detail':'cookie=TOKEN API_KEY=SEGREDO'}),
                         {'http_status':502,'error':'external_failure'})

    def test_opcoes_controle_e_invisivel(self):
        original = dict(channel='chrome',headless=False,args=['--no-sandbox','--window-position=-32000,-32000','--window-size=1,1'])
        self.assertEqual(launch_options('control',original),original)
        self.assertEqual(launch_options('headless',original),dict(channel='chrome',headless=True,args=['--no-sandbox']))
        self.assertFalse(original['headless'])

if __name__ == '__main__':
    unittest.main()
