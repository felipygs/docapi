import json
import unittest
from pathlib import Path
from unittest.mock import patch

from playwright.async_api import async_playwright

from app.scrapers.cnpj import consultar_cnpj

URL = 'https://cnpj.test/'
API = URL + 'api/v1/consultapublica/'
CNPJ = '37482317000111'
HTML = '''<div id="alert-cnpj"><input></div><button disabled>Consultar</button>
<script>
let token = null;
window.hcaptcha = {render: (el, options) => {window.opts = options; return 'widget'}, reset: () => {}};
hcaptcha.render(null, {sitekey: 'sitekey-teste', callback: t => {token=t;document.querySelector('button').disabled=false}});
document.querySelector('button').onclick = async () => {
 const res = await fetch('/api/v1/consultapublica/validar-captcha', {method:'POST',body:JSON.stringify({captchaToken:token,cnpj:document.querySelector('input').value})});
 if (!(await res.json()).valido) return;
 await fetch('/api/v1/consultapublica/cnpj/37482317000111');
 history.pushState({},'', '/comprovante');
 document.body.innerHTML = '<div id="principal">Comprovante</div><button name="qsa">Consultar QSA</button>';
 document.querySelector('button').onclick=async()=>{
  await fetch('/api/v1/consultapublica/qsa/37482317000111');
  history.pushState({},'', '/qsa');
  document.body.innerHTML='<div id="capital">Capital social</div>';
 };
};
</script>'''


class CnpjAcquisitionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.p = await async_playwright().start()
        self.addAsyncCleanup(self.p.stop)
        self.browser = await self.p.chromium.launch(channel='chrome', headless=True)
        self.addAsyncCleanup(self.browser.close)
        self.page = await self.browser.new_page()
        self.page.set_default_timeout(1000)
        self.captcha_valido = True
        self.qsa_status = 200
        self.enviado = None
        self.validacoes = 0
        self.rejeitar_primeiro = False
        self.cadastro = json.loads((Path(__file__).parent/'fixtures/cnpj/cadastro.json').read_text(encoding='utf8'))
        await self.page.route('**/*', self.route)

    async def route(self, route):
        url = route.request.url
        if url.rstrip('/') == URL.rstrip('/'):
            return await route.fulfill(content_type='text/html', body=HTML)
        if url == API+'validar-captcha':
            self.enviado = route.request.post_data_json
            self.validacoes += 1
            valido = self.captcha_valido and not (self.rejeitar_primeiro and self.validacoes == 1)
            return await route.fulfill(json={'valido': valido})
        if url == API+'cnpj/'+CNPJ:
            return await route.fulfill(json=self.cadastro)
        if url == API+'qsa/'+CNPJ:
            return await route.fulfill(status=self.qsa_status,json={'socios': []})
        await route.abort()

    async def consultar(self, max_retries=1):
        with patch('app.scrapers.cnpj.CNPJ_URL', URL), patch('app.scrapers.cnpj.NONECAP_API_KEY', 'CHAVE_TESTE', create=True), patch('app.scrapers.cnpj.resolver_hcaptcha_nonecap', return_value={'token':'TOKEN_TESTE', 'user_agent':'UA_TESTE'}, create=True):
            return await consultar_cnpj(self.page, CNPJ, max_retries=max_retries)

    async def test_captcha_rejeitado_recupera_na_mesma_pagina_e_obtem_qsa(self):
        self.rejeitar_primeiro = True
        resultado = await self.consultar(max_retries=2)
        self.assertEqual(self.validacoes, 2)
        self.assertEqual(resultado['socios'], [])
        self.assertTrue(self.page.url.endswith('/qsa'))

    async def test_tentativas_invalidas_rejeitadas_antes_de_navegar(self):
        for quantidade in (0, 4):
            with self.subTest(quantidade=quantidade), self.assertRaises(ValueError):
                await self.consultar(max_retries=quantidade)
        self.assertEqual(self.page.url, 'about:blank')

    async def test_fluxo_atual_preenche_cnpj_callback_consulta_e_qsa(self):
        r = await self.consultar()
        self.assertEqual(self.enviado, {'captchaToken':'TOKEN_TESTE','cnpj':CNPJ})
        self.assertEqual(r['nome_empresarial'], 'THIARLLES BARBOSA DE SOUSA')
        self.assertTrue(self.page.url.endswith('/qsa'))

    async def test_captcha_rejeitado_falha_sem_falso_sucesso(self):
        self.captcha_valido = False
        with self.assertRaisesRegex(RuntimeError, '[Cc]aptcha'):
            await self.consultar()

    async def test_qsa_503_nao_vira_socios_vazios(self):
        self.qsa_status = 503
        with self.assertRaisesRegex(RuntimeError, 'QSA'):
            await self.consultar()


if __name__ == '__main__':
    unittest.main()
