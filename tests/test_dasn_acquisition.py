"""Fluxo DASN com HTML controlado e navegador real, sem acesso à Receita."""
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from playwright.async_api import async_playwright, Error as PlaywrightError

from app.api import _safe_call
from app.models import DasnResponse
from app.scrapers.dasn import consultar_dasn

URL = 'https://dasn.test/dasnsimei.app'
IDENTIFICACAO = '''<!doctype html><html><body>
<input id="identificacao-cnpj"><button id="identificacao-continuar"
onclick="location.href='/dasnsimei.app/'">Continuar</button></body></html>'''


def resultado(tipo='Extinção', data='26/08/2025', status='não apresentada', acao='Declarar', disabled=''):
    # Estrutura observada na execução real; identificação substituída por exemplo.
    return f'''<!doctype html><html><body>
    <p><strong>Razão Social:</strong></p><p>EMPRESA EXEMPLO</p>
    <div id="iniciar-ano-calendario"><div class="br-radio">
    <input type="radio" value="2025" data-tipo-declaracao="Original"
    data-situacao-especial-tipo="{tipo}" data-situacao-especial-eventobaixa="{data}" {disabled}>
    <span>{status}</span><span class="br-tag">{acao}</span>
    </div></div></body></html>'''


class TestDasnAcquisition(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.p = await async_playwright().start()
        self.addAsyncCleanup(self.p.stop)
        self.browser = await self.p.chromium.launch(channel='chrome', headless=True)
        self.addAsyncCleanup(self.browser.close)
        self.context = await self.browser.new_context(offline=True, service_workers='block')
        self.addAsyncCleanup(self.context.close)
        self.unexpected = []
        self.result_html = resultado()
        self.ident_html = IDENTIFICACAO

        async def route(request):
            if request.request.url == URL + '/Identificacao':
                html = self.ident_html
            elif request.request.url == URL + '/':
                html = self.result_html
            else:
                self.unexpected.append(request.request.url)
                await request.abort()
                return
            await request.fulfill(status=200, content_type='text/html; charset=utf-8', body=html)

        await self.context.route('**/*', route)
        self.page = await self.context.new_page()

    async def asyncTearDown(self):
        self.assertEqual(self.unexpected, [])

    async def consultar(self):
        with patch('app.scrapers.dasn.DASN_URL', URL):
            return await consultar_dasn(self.page, '57435953000108')

    async def test_extincao_com_declaracao_pendente_indica_mei_baixada(self):
        dados = DasnResponse.model_validate(await self.consultar()).model_dump()
        self.assertTrue(dados['mei_baixada'])
        self.assertEqual(dados['data_baixa'], '2025-08-26')
        self.assertTrue(dados['declaracoes'][0]['baixada'])
        self.assertTrue(dados['declaracoes'][0]['pendente'])
        self.assertEqual(dados['pendentes'], [2025])

    async def test_extincao_apresentada_continua_indicando_baixa(self):
        self.result_html = resultado(status='apresentada em 01/09/2025', acao='Retificar')
        dados = await self.consultar()
        self.assertTrue(dados['mei_baixada'])
        self.assertTrue(dados['declaracoes'][0]['baixada'])
        self.assertEqual(dados['declaracoes'][0]['data_apresentacao'], '2025-09-01')
        self.assertEqual(dados['pendentes'], [])

    async def test_extincao_normalizada_preserva_data_de_baixa(self):
        self.result_html = resultado(tipo='extinção')
        dados = await self.consultar()
        self.assertTrue(dados['mei_baixada'])
        self.assertEqual(dados['data_baixa'], '2025-08-26')

    async def test_declaracao_normal_nao_indica_baixa(self):
        self.result_html = resultado(tipo='-', data='-')
        dados = await self.consultar()
        self.assertFalse(dados['mei_baixada'])
        self.assertIsNone(dados['data_baixa'])
        self.assertFalse(dados['declaracoes'][0]['baixada'])
        self.assertEqual(dados['pendentes'], [2025])

    async def test_erro_explicito_da_receita_nao_vira_timeout_generico(self):
        self.result_html = '''<html><body><div class="template-erro">
        <p>33001 - Contribuinte não optante pelo Simei.</p></div></body></html>'''
        # Reduz só o prazo do teste, usando TimeoutError real se a mensagem
        # explícita não for reconhecida. Não simula evaluate/locators.
        original = self.page.wait_for_selector

        async def curto(selector, **kwargs):
            kwargs['timeout'] = 800
            return await original(selector, **kwargs)

        with patch.object(self.page, 'wait_for_selector', curto):
            with self.assertRaises(HTTPException) as raised:
                await _safe_call(self.consultar)
        self.assertEqual(raised.exception.status_code, 502)
        self.assertIn('33001', raised.exception.detail)

    async def test_bloqueio_captcha_expresso_e_reportado_sem_esperar_timeout(self):
        self.result_html = '''<html><body><div id="identificacao-warning" class="feedback warning">
        13896 - Impedido por proteção Captcha. Comportamento de Robô.</div></body></html>'''
        original = self.page.wait_for_selector

        async def curto(selector, **kwargs):
            kwargs['timeout'] = 800
            return await original(selector, **kwargs)

        with patch.object(self.page, 'wait_for_selector', curto):
            with self.assertRaises(HTTPException) as raised:
                await _safe_call(self.consultar)
        self.assertEqual(raised.exception.status_code, 502)
        self.assertIn('13896', raised.exception.detail)

    async def test_ausencia_de_resposta_preserva_timeout_504(self):
        self.result_html = '<html><body>Carregando</body></html>'
        original = self.page.wait_for_selector

        async def curto(selector, **kwargs):
            kwargs['timeout'] = 800
            return await original(selector, **kwargs)

        with patch.object(self.page, 'wait_for_selector', curto):
            with self.assertRaises(HTTPException) as raised:
                await _safe_call(self.consultar)
        self.assertEqual(raised.exception.status_code, 504)

    async def test_warning_oculto_nao_impede_resultado_valido(self):
        self.result_html = self.result_html.replace('<body>', '<body><div id="identificacao-warning" style="display:none"></div>')
        original = self.page.wait_for_selector

        async def curto(selector, **kwargs):
            kwargs['timeout'] = 800
            return await original(selector, **kwargs)

        with patch.object(self.page, 'wait_for_selector', curto):
            dados = await self.consultar()
        self.assertEqual(dados['razao_social'], 'EMPRESA EXEMPLO')

    async def test_bloqueio_exibido_sem_navegacao_tambem_e_reconhecido(self):
        self.ident_html = '''<html><body><input id="identificacao-cnpj">
        <div id="identificacao-warning" style="display:none"></div>
        <button id="identificacao-continuar" onclick="setTimeout(() => {
          const w = document.querySelector('#identificacao-warning');
          w.textContent = '13896 - Impedido por proteção Captcha. Comportamento de Robô.';
          w.style.display = 'block';
        }, 30)">Continuar</button></body></html>'''
        with self.assertRaises(HTTPException) as raised:
            await _safe_call(self.consultar)
        self.assertEqual(raised.exception.status_code, 502)
        self.assertIn('13896', raised.exception.detail)

    async def test_falha_do_navegador_na_espera_e_502_sanitizado(self):
        original = self.page.wait_for_selector

        async def falhar_resultado(selector, **kwargs):
            if '#iniciar-ano-calendario' in selector:
                raise PlaywrightError('net::ERR_CONNECTION_RESET SEGREDO=TOKEN')
            return await original(selector, **kwargs)

        with patch.object(self.page, 'wait_for_selector', falhar_resultado):
            with self.assertRaises(HTTPException) as raised:
                await _safe_call(self.consultar)
        self.assertEqual(raised.exception.status_code, 502)
        self.assertNotIn('SEGREDO', raised.exception.detail)

    async def test_extracao_incompleta_ou_invalida_nao_e_sucesso(self):
        casos = [
            '<div id="iniciar-ano-calendario" style="min-height:40px">Ano calendário:</div>',
            resultado().replace('EMPRESA EXEMPLO', ''),
            resultado(data='31/02/2025'),
            resultado(status='apresentada em 31/02/2025'),
            resultado().replace('value="2025"', 'value="SEGREDO"'),
            resultado(status='Processando SEGREDO'),
            resultado(tipo='Extinção', data='-'),
        ]
        for index, html in enumerate(casos):
            with self.subTest(caso=index):
                self.result_html = html
                with self.assertRaises(HTTPException) as raised:
                    await _safe_call(self.consultar)
                self.assertEqual(raised.exception.status_code, 502)
                self.assertNotIn('SEGREDO', raised.exception.detail)

    async def test_identidade_cnpj_divergente_rejeita_dados(self):
        self.result_html = resultado().replace('<p><strong>Razão', '<p><strong>CNPJ:</strong></p><p>43.996.591/0001-01</p><p><strong>Razão')
        with self.assertRaises(HTTPException) as raised:
            await _safe_call(self.consultar)
        self.assertEqual(raised.exception.status_code, 502)
        self.assertIn('identidade', raised.exception.detail)

    async def test_cnpj_rejeitado_pela_origem_e_400(self):
        self.result_html = '<div class="template-erro"><p>CNPJ invalido!</p></div>'
        with self.assertRaises(HTTPException) as raised:
            await _safe_call(self.consultar)
        self.assertEqual(raised.exception.status_code, 400)



if __name__ == '__main__':
    unittest.main()
