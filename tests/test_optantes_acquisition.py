"""AjaxMaisInfo simulado por route.fulfill: nenhuma conexão com Receita.

Somente goto é substituído; clique, fetch, loader e conteúdo usam DOM real.
Os únicos requests permitidos são explicitamente interceptados no host .test.
"""
import asyncio
from functools import partial
from unittest.mock import patch

from fastapi import HTTPException
from playwright.async_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError

from app.api import _safe_call
from app.scrapers.optantes import consultar_optantes
from test_optantes_parser import BrowserOffline, PaginaOffline, fixture

AJAX = "https://optantes.test/consultaoptantes/Home/AjaxMaisInfo?cnpjHdn=43996591000101"


class TestOptantesAcquisition(BrowserOffline):
    async def asyncTearDown(self):
        self.assertEqual(self.bloqueadas, [])
        self.assertTrue(all(url == AJAX for url in self.requests), self.requests)

    async def inicial(self, *, conteudo=None, erro=False, status=200, stuck=False, iniciar=True):
        await self.page.set_content(fixture("eliane_sintetica.html"))
        complemento = await self.page.locator('#maisInfo').inner_html()
        await self.page.locator('#maisInfo').evaluate('(el) => el.innerHTML = ""')
        await self.page.locator('#btnMaisInfo').evaluate('(el) => el.disabled = false')
        html = await self.page.content()
        if conteudo is None:
            conteudo = complemento
        async def responder(route):
            await asyncio.sleep(0.03)
            await route.fulfill(status=status, content_type='text/html', body=conteudo,
                                headers={'Access-Control-Allow-Origin': '*'})
        await self.context.route(AJAX, responder)
        # Script controlado de teste, equivalente ao beforeSend/success/error/
        # complete observado no HTML real, com uma fase DOM após a resposta.
        script = """<script>
        document.querySelector('#btnMaisInfo').onclick = async () => {
            document.querySelector('#btnMaisInfo').disabled = true;
            document.querySelector('.loader').style.display = 'block';
            if (!INICIAR) return;
            try {
                const response = await fetch('URL_AJAX');
                const html = await response.text();
                await new Promise(r => setTimeout(r, 50));
                if (ERRO || !response.ok) throw new Error('SEGREDO cookie=TOKEN');
                document.querySelector('#maisInfo').innerHTML = html;
            } catch (error) {
                document.querySelector('#spnMsgErro').style.display = 'inline';
                document.querySelector('#spnMsgErro').textContent = 'Erro complementar SEGREDO cookie=TOKEN';
            } finally {
                if (!STUCK) document.querySelector('.loader').style.display = 'none';
            }
        };
        </script>""".replace('URL_AJAX', AJAX).replace('ERRO', str(erro).lower()).replace('STUCK', str(stuck).lower()).replace('INICIAR', str(iniciar).lower())
        return html.replace('</body>', script + '</body>')

    async def executar(self, html):
        offline = PaginaOffline(self.page, html)
        async def esperar_curto(selector, **kwargs):
            kwargs['timeout'] = 1500
            return await self.page.wait_for_selector(selector, **kwargs)
        try:
            # Somente prazo de teste: exercita Playwright TimeoutError real sem
            # demorar 10s por cenário. Nenhum locator/evaluate é simulado.
            with patch.object(offline, 'wait_for_selector', esperar_curto), patch('app.scrapers.optantes._LOAD_TIMEOUT_MS', 1000), patch('app.scrapers.optantes.OPTANTES_URL', 'https://optantes.test/consultaoptantes/'):
                return await _safe_call(partial(consultar_optantes, offline, '43996591000101', max_retries=3))
        finally:
            self.assertEqual(len(offline.navegacoes), 1, 'Sem retry de captcha/origem')

    async def test_ajax_sucesso_aguarda_loader_e_conteudo_completo(self):
        r = await self.executar(await self.inicial())
        self.assertEqual(len(r['simples_nacional']['periodos_anteriores']), 3)
        self.assertEqual(r['simei']['periodos_anteriores'], [])
        self.assertFalse(await self.page.locator('.loader').is_visible())
        self.assertEqual(self.requests, [AJAX])

    async def test_ajax_erro_explicito_e_http_falha_502_sem_segredos(self):
        for erro, status in ((True, 200), (False, 503)):
            with self.subTest(erro=erro, status=status):
                with self.assertRaises(HTTPException) as raised:
                    await self.executar(await self.inicial(erro=erro, status=status))
                self.assertEqual(raised.exception.status_code, 502)
                self.assertIn('complementar', raised.exception.detail)
                self.assertNotIn('SEGREDO', raised.exception.detail)
                self.assertNotIn('TOKEN', raised.exception.detail)

    async def test_ajax_falha_transporte_com_erro_ui_e_502_nao_timeout(self):
        html = await self.inicial()
        async def abortar(route):
            await route.abort('failed')
        await self.context.route(AJAX, abortar)
        with self.assertRaises(HTTPException) as raised:
            await self.executar(html)
        self.assertEqual(raised.exception.status_code, 502)
        self.assertIn('complementar', raised.exception.detail)
        self.assertNotIn('SEGREDO', raised.exception.detail)

    async def test_ajax_timeout_antes_response_e_loader_preserva_504(self):
        for kwargs in ({'iniciar': False}, {'stuck': True}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(HTTPException) as raised:
                    await self.executar(await self.inicial(**kwargs))
                self.assertEqual(raised.exception.status_code, 504)
                self.assertIn('Optantes', raised.exception.detail)
                self.assertNotIn('cnpjHdn', raised.exception.detail)

    async def test_ajax_conteudo_vazio_ou_parcial_502(self):
        for conteudo in ('', '<div class="panel"><div class="panel-heading"><h3>Períodos Anteriores</h3></div><div class="panel-body"></div></div>'):
            with self.subTest(conteudo=conteudo):
                with self.assertRaises(HTTPException) as raised:
                    await self.executar(await self.inicial(conteudo=conteudo))
                self.assertEqual(raised.exception.status_code, 502)

    async def test_disabled_expandido_valido_e_sem_conteudo_falha(self):
        r = await self.executar(fixture('eliane_sintetica.html'))
        self.assertEqual(r['cnpj_matriz'], '43996591000101')
        self.assertEqual(self.requests, [])
        await self.page.set_content(fixture('eliane_sintetica.html'))
        await self.page.locator('#maisInfo').evaluate('(el) => el.innerHTML = ""')
        with self.assertRaises(HTTPException) as raised:
            await self.executar(await self.page.content())
        self.assertEqual(raised.exception.status_code, 502)

    async def test_erro_visivel_preexistente_nao_sucesso_parcial(self):
        html = fixture('eliane_sintetica.html').replace('<span id="spnMsgErro" style="display: none;"></span>', '<span id="spnMsgErro">SEGREDO erro complementar</span>')
        with self.assertRaises(HTTPException) as raised:
            await self.executar(html)
        self.assertEqual(raised.exception.status_code, 502)
        self.assertNotIn('SEGREDO', raised.exception.detail)

    async def test_loader_ausente_nao_permite_sucesso_presumido(self):
        html = fixture('eliane_sintetica.html').replace('<div class="loader" style="display: none;"></div>', '')
        with self.assertRaises(HTTPException) as raised:
            await self.executar(html)
        self.assertEqual(raised.exception.status_code, 502)
        self.assertIn('loader', raised.exception.detail)

    async def test_falha_navegacao_nao_timeout_e_502_seguro(self):
        offline = PaginaOffline(self.page, fixture('eliane_sintetica.html'))
        async def falhar(*args, **kwargs):
            raise PlaywrightError('net::ERR_FAILED SEGREDO https://portal/?token=TOKEN')
        with patch.object(offline, 'goto', falhar):
            with self.assertRaises(HTTPException) as raised:
                await _safe_call(partial(consultar_optantes, offline, '43996591000101'))
        self.assertEqual(raised.exception.status_code, 502)
        self.assertIn('Optantes', raised.exception.detail)
        self.assertNotIn('SEGREDO', raised.exception.detail)
        self.assertNotIn('TOKEN', raised.exception.detail)

    async def test_timeouts_navegacao_seguro_e_sem_retry(self):
        offline = PaginaOffline(self.page, fixture('eliane_sintetica.html'))
        async def timeout(*args, **kwargs):
            raise PlaywrightTimeoutError('SEGREDO https://portal/?token=TOKEN')
        with patch.object(offline, 'goto', timeout):
            with self.assertRaises(HTTPException) as raised:
                await _safe_call(partial(consultar_optantes, offline, '43996591000101'))
        self.assertEqual(raised.exception.status_code, 504)
        self.assertNotIn('SEGREDO', raised.exception.detail)
        self.assertNotIn('TOKEN', raised.exception.detail)
