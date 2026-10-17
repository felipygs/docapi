import unittest

from app.scrapers.dasn import _validar_declaracoes


def declaracao(**changes):
    row = dict(ano='2025', tipo_declaracao='Original', situacao_especial='-',
               data_baixa='-', status='não apresentada', pendente=True, baixada=False)
    row.update(changes)
    return row


class TestDasnIntegrity(unittest.TestCase):
    def test_rejeita_extracao_incompleta_e_dados_invalidos(self):
        for rows in ([], [declaracao(ano='SEGREDO')], [declaracao(data_baixa='31/02/2025')],
                     [declaracao(status='apresentada em 31/02/2025')],
                     [declaracao(status='Processando SEGREDO')],
                     [declaracao(situacao_especial='Extinção')]):
            with self.subTest(rows=rows), self.assertRaises(RuntimeError) as raised:
                _validar_declaracoes('EMPRESA EXEMPLO', rows)
            self.assertNotIn('SEGREDO', str(raised.exception))

    def test_rejeita_nome_ausente(self):
        with self.assertRaises(RuntimeError):
            _validar_declaracoes('', [declaracao()])

    def test_preserva_status_reconhecidos_e_data_valida(self):
        for row in (declaracao(), declaracao(status='Não Optante', pendente=False),
                    declaracao(status='Baixada', pendente=False, baixada=True),
                    declaracao(status='apresentada em 01/09/2025', pendente=False),
                    declaracao(situacao_especial='Extinção', data_baixa='26/08/2025', baixada=True)):
            _validar_declaracoes('EMPRESA EXEMPLO', [row])
