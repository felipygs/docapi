"""Recuperação local: sessões simuladas, sem acesso aos portais da Receita."""
import asyncio
from contextlib import ExitStack
from copy import deepcopy
import importlib
import unittest
from unittest.mock import AsyncMock, patch

from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from app.browser import create_browser
from app.models import DasnResponse, OptantesResponse

consultas = importlib.import_module('app.consultar')
browser_module = importlib.import_module('app.browser')


class Pagina:
    def __init__(self, sessao):
        self.sessao = sessao


class Sessao:
    def __init__(self):
        self.cookies = {}
        self.storage = {}
        self.fechada = False

    async def new_page(self):
        return Pagina(self)

    async def close(self):
        self.fechada = True


class PlaywrightLocal:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class TestConsultarRecovery(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.sessoes = []
        self.esperas = []
        self.dasn = deepcopy(DasnResponse.model_config['json_schema_extra']['examples'][0])
        self.optantes = deepcopy(OptantesResponse.model_config['json_schema_extra']['examples'][0])
        self.cn = '43996591000101'
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)

        async def criar(playwright):
            sessao = Sessao()
            self.sessoes.append(sessao)
            return sessao, sessao

        async def esperar(segundos):
            self.esperas.append(segundos)

        self.stack.enter_context(patch.object(consultas, 'create_browser', criar))
        self.stack.enter_context(patch.object(consultas.asyncio, 'sleep', esperar))

    async def executar(self, consultar, modulo='DASN', **kwargs):
        self.assertTrue(hasattr(consultas, '_consultar_com_recuperacao'),
                        'Falta executor limitado com sessão nova por tentativa')
        return await consultas._consultar_com_recuperacao(
            object(), modulo, self.cn, consultar, **kwargs)

    async def test_timeout_recupera_em_sessao_sem_cookies_ou_storage_anteriores(self):
        tentativas = 0

        async def consultar(page, cnpj):
            nonlocal tentativas
            tentativas += 1
            self.assertEqual(cnpj, self.cn)
            self.assertEqual(page.sessao.cookies, {})
            self.assertEqual(page.sessao.storage, {})
            if tentativas == 1:
                page.sessao.cookies['token'] = 'SEGREDO'
                page.sessao.storage['local'] = 'SEGREDO'
                raise PlaywrightTimeoutError('SEGREDO')
            return self.dasn

        resultado = await self.executar(consultar)
        self.assertEqual(resultado['declaracoes'][0]['ano'], 2024)
        self.assertEqual(tentativas, 2)
        self.assertEqual(self.esperas, [2])
        self.assertEqual(len(self.sessoes), 2)
        self.assertTrue(all(s.fechada for s in self.sessoes))

    async def test_timeout_persistente_termina_em_tres_tentativas_com_backoff(self):
        async def consultar(page, cnpj):
            raise TimeoutError('indisponível')

        with self.assertRaises(TimeoutError):
            await self.executar(consultar)
        self.assertEqual(len(self.sessoes), 3)
        self.assertEqual(self.esperas, [2, 5])
        self.assertTrue(all(s.fechada for s in self.sessoes))

    async def test_falha_transitoria_tipificada_pode_recuperar(self):
        from app.errors import FalhaTransitoriaError

        async def consultar(page, cnpj):
            if len(self.sessoes) == 1:
                raise FalhaTransitoriaError('Origem temporariamente indisponível')
            return self.dasn

        self.assertEqual((await self.executar(consultar))['pendentes'], [])
        self.assertEqual(len(self.sessoes), 2)

    async def test_erros_definitivos_nao_repetem_nem_esperam(self):
        from app.errors import (
            CaptchaBloqueadoError, CnpjInvalidoError, DadosIncompletosError,
            IdentidadeDivergenteError, NaoOptanteError,
        )
        for tipo in (RuntimeError, CnpjInvalidoError,
                     DadosIncompletosError, IdentidadeDivergenteError, NaoOptanteError):
            with self.subTest(tipo=tipo):
                self.sessoes.clear()
                async def consultar(page, cnpj):
                    raise tipo('resposta definitiva')

                with self.assertRaises(tipo):
                    await self.executar(consultar)
                self.assertEqual(len(self.sessoes), 1)
                self.assertTrue(self.sessoes[0].fechada)
        self.assertEqual(self.esperas, [])

    async def test_bloqueio_isolado_recupera_com_sessao_limpa(self):
        from app.errors import CaptchaBloqueadoError

        async def consultar(page, cnpj):
            self.assertEqual(page.sessao.cookies, {})
            if len(self.sessoes) == 1:
                page.sessao.cookies['bloqueio'] = 'anterior'
                raise CaptchaBloqueadoError('bloqueio da origem')
            return self.dasn

        self.assertEqual((await self.executar(consultar))['razao_social'], self.dasn['razao_social'])
        self.assertEqual(len(self.sessoes), 2)
        self.assertEqual(self.esperas, [2])
        self.assertTrue(all(s.fechada for s in self.sessoes))

    async def test_bloqueio_persistente_encerra_apos_tres_tentativas(self):
        from app.errors import CaptchaBloqueadoError

        async def consultar(page, cnpj):
            raise CaptchaBloqueadoError('consulta bloqueada')

        with self.assertRaises(CaptchaBloqueadoError):
            await self.executar(consultar)
        self.assertEqual(len(self.sessoes), 3)
        self.assertEqual(self.esperas, [2, 5])
        self.assertTrue(all(s.fechada for s in self.sessoes))

    async def test_payload_invalido_nao_e_sucesso_nem_nova_tentativa(self):
        from app.errors import DadosIncompletosError

        async def consultar(page, cnpj):
            return {'declaracoes': [{'ano': 'SEGREDO'}]}

        with self.assertRaises(DadosIncompletosError) as raised:
            await self.executar(consultar)
        self.assertNotIn('SEGREDO', str(raised.exception))
        self.assertEqual(len(self.sessoes), 1)
        self.assertTrue(self.sessoes[0].fechada)

    async def test_dasn_defaults_nao_transformam_payload_vazio_em_sucesso(self):
        from app.errors import DadosIncompletosError
        for payload in ({}, {'razao_social': 'EMPRESA', 'declaracoes': []}):
            self.sessoes.clear()
            async def consultar(page, cnpj):
                return payload
            with self.subTest(payload=payload), self.assertRaises(DadosIncompletosError):
                await self.executar(consultar)
            self.assertEqual(len(self.sessoes), 1)

    async def test_falha_cleanup_preserva_erro_captcha_original(self):
        from app.errors import CaptchaBloqueadoError
        sessao = Sessao()
        sessao.close = AsyncMock(side_effect=RuntimeError('SEGREDO cookie=TOKEN'))

        async def criar(playwright):
            return sessao, sessao

        async def consultar(page, cnpj):
            raise CaptchaBloqueadoError('Captcha bloqueado')

        with patch.object(consultas, 'create_browser', criar), \
             self.assertLogs('app.browser', level='WARNING') as captured:
            with self.assertRaises(CaptchaBloqueadoError):
                await self.executar(consultar)
        self.assertNotIn('SEGREDO', '\n'.join(captured.output))

    async def test_falha_cleanup_apos_sucesso_e_sanitizada_sem_retry(self):
        sessao = Sessao()
        sessao.close = AsyncMock(side_effect=RuntimeError('SEGREDO cookie=TOKEN'))
        criacoes = 0

        async def criar(playwright):
            nonlocal criacoes
            criacoes += 1
            return sessao, sessao

        async def consultar(page, cnpj):
            return self.dasn

        with patch.object(consultas, 'create_browser', criar), \
             self.assertLogs('app.browser', level='WARNING'):
            with self.assertRaises(RuntimeError) as raised:
                await self.executar(consultar)
        self.assertNotIn('SEGREDO', str(raised.exception))
        self.assertEqual(criacoes, 1)

    async def test_optantes_tambem_valida_payload_antes_de_sucesso(self):
        from app.errors import DadosIncompletosError

        async def consultar(page, cnpj):
            return {'cnpj_consultado': cnpj}

        with self.assertRaises(DadosIncompletosError):
            await self.executar(consultar, modulo='Optantes')
        self.assertEqual(len(self.sessoes), 1)

    async def test_prazo_global_interrompe_operacao_em_andamento_e_fecha(self):
        iniciou = asyncio.Event()

        async def consultar(page, cnpj):
            iniciou.set()
            await asyncio.Event().wait()

        with self.assertRaises(TimeoutError):
            await self.executar(consultar, prazo_total=0.02)
        self.assertTrue(iniciou.is_set())
        self.assertEqual(len(self.sessoes), 1)
        self.assertTrue(self.sessoes[0].fechada)

    async def test_prazo_global_cobre_espera_e_impede_segunda_sessao(self):
        async def consultar(page, cnpj):
            raise TimeoutError('falha')

        async def esperar(segundos):
            await asyncio.Event().wait()

        with patch.object(consultas.asyncio, 'sleep', esperar):
            with self.assertRaises(TimeoutError):
                await self.executar(consultar, prazo_total=0.02)
        self.assertEqual(len(self.sessoes), 1)
        self.assertTrue(self.sessoes[0].fechada)

    async def test_cancelamento_fecha_sessao_sem_retry(self):
        iniciou = asyncio.Event()

        async def consultar(page, cnpj):
            iniciou.set()
            await asyncio.Event().wait()

        # Se o executor ainda não existir, falhar antes de aguardar o evento.
        self.assertTrue(hasattr(consultas, '_consultar_com_recuperacao'))
        task = asyncio.create_task(self.executar(consultar))
        await iniciou.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(len(self.sessoes), 1)
        self.assertTrue(self.sessoes[0].fechada)
        self.assertEqual(self.esperas, [])

    async def test_falha_criacao_page_fecha_browser(self):
        async def criar(playwright):
            sessao = Sessao()
            sessao.new_page = AsyncMock(side_effect=RuntimeError('falha interna'))
            self.sessoes.append(sessao)
            return sessao, sessao

        with patch.object(consultas, 'create_browser', criar):
            with self.assertRaises(RuntimeError):
                await self.executar(AsyncMock())
        self.assertEqual(len(self.sessoes), 1)
        self.assertTrue(self.sessoes[0].fechada)

    async def test_cancelamento_durante_fechamento_aguarda_liberacao_do_browser(self):
        fechando = asyncio.Event()
        liberar = asyncio.Event()

        class SessaoLenta(Sessao):
            async def close(self):
                fechando.set()
                await liberar.wait()
                self.fechada = True

        sessao = SessaoLenta()

        async def criar(playwright):
            return sessao, sessao

        async def consultar(page, cnpj):
            return self.dasn

        with patch.object(consultas, 'create_browser', criar):
            task = asyncio.create_task(self.executar(consultar))
            await fechando.wait()
            task.cancel()
            liberar.set()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertTrue(sessao.fechada)

    async def test_logs_nao_expoem_cnpj_tokens_ou_excecao_bruta(self):
        async def consultar(page, cnpj):
            if len(self.sessoes) == 1:
                raise TimeoutError('SEGREDO cookie=TOKEN')
            return self.dasn

        with self.assertLogs('app.consultar', level='INFO') as captured:
            await self.executar(consultar)
        texto = '\n'.join(captured.output)
        for segredo in (self.cn, 'SEGREDO', 'TOKEN', 'cookie'):
            self.assertNotIn(segredo, texto)
        self.assertIn('DASN', texto)

    async def test_individuais_usam_recuperacao_e_preservam_contrato(self):
        for nome, scraper, payload in (
            ('consultar_apenas_dasn', 'consultar_dasn', self.dasn),
            ('consultar_apenas_optantes', 'consultar_optantes', self.optantes),
        ):
            self.sessoes.clear()
            async def consultar(page, cnpj):
                if len(self.sessoes) == 1:
                    raise TimeoutError('transitório')
                return deepcopy(payload)

            with self.subTest(nome=nome), patch.object(consultas, 'async_playwright', PlaywrightLocal), \
                 patch.object(consultas, scraper, consultar):
                resultado = await getattr(consultas, nome)(self.cn)
                self.assertEqual(resultado, payload)
                self.assertEqual(len(self.sessoes), 2)
                self.assertTrue(all(s.fechada for s in self.sessoes))

    async def test_erro_cadastral_preservado_quando_fechamento_falha(self):
        for nome in ('consultar_apenas_cnpj', 'consultar_mei'):
            self.sessoes.clear()
            erro_original = RuntimeError('falha na consulta cadastral')

            async def cadastro(page, cnpj):
                page.sessao.close = AsyncMock(side_effect=RuntimeError('SEGREDO cookie=TOKEN'))
                raise erro_original

            with self.subTest(nome=nome), \
                 patch.object(consultas, 'async_playwright', PlaywrightLocal), \
                 patch.object(consultas, 'consultar_cnpj', cadastro), \
                 self.assertLogs('app.browser', level='WARNING') as captured:
                with self.assertRaises(RuntimeError) as raised:
                    await getattr(consultas, nome)(self.cn)
                self.assertIs(raised.exception, erro_original)
                self.assertEqual(len(self.sessoes), 1)
                self.sessoes[0].close.assert_awaited_once()
                self.assertNotIn('SEGREDO', '\n'.join(captured.output))

    async def test_cancelamento_cadastral_fecha_sessao(self):
        for nome in ('consultar_apenas_cnpj', 'consultar_mei'):
            self.sessoes.clear()
            iniciou = asyncio.Event()

            async def cadastro(page, cnpj):
                iniciou.set()
                await asyncio.Event().wait()

            with self.subTest(nome=nome), \
                 patch.object(consultas, 'async_playwright', PlaywrightLocal), \
                 patch.object(consultas, 'consultar_cnpj', cadastro):
                task = asyncio.create_task(getattr(consultas, nome)(self.cn))
                try:
                    await asyncio.wait_for(iniciou.wait(), timeout=1)
                    task.cancel()
                    with self.assertRaises(asyncio.CancelledError):
                        await task
                    self.assertEqual(len(self.sessoes), 1)
                    self.assertTrue(self.sessoes[0].fechada)
                finally:
                    if not task.done():
                        task.cancel()
                    await asyncio.gather(task, return_exceptions=True)

    async def test_cadastro_tem_prazo_total_e_fecha_sessao_pendurada(self):
        iniciou = asyncio.Event()

        async def cadastro(page, cnpj):
            iniciou.set()
            await asyncio.Event().wait()

        with patch.object(consultas, 'consultar_cnpj', cadastro), \
             patch.object(consultas, '_CADASTRO_TIMEOUT_SECONDS', 0.02, create=True):
            task = asyncio.create_task(consultas._consultar_cadastro(object(), self.cn))
            try:
                done, _ = await asyncio.wait({task}, timeout=0.2)
                self.assertIn(task, done, 'Cadastro sem prazo total deixa consulta completa pendurada')
                with self.assertRaisesRegex(TimeoutError, 'CNPJ'):
                    task.result()
                self.assertTrue(iniciou.is_set())
                self.assertTrue(self.sessoes[0].fechada)
            finally:
                if not task.done():
                    task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    async def test_cadastro_registra_inicio_antes_de_aguardar_e_falha_sem_segredos(self):
        from app.errors import CaptchaBloqueadoError
        iniciou = asyncio.Event()
        liberar = asyncio.Event()

        async def cadastro(page, cnpj):
            iniciou.set()
            await liberar.wait()
            raise CaptchaBloqueadoError(f'SEGREDO cookie=TOKEN {cnpj}')

        with patch.object(consultas, 'consultar_cnpj', cadastro), \
             self.assertLogs('app.consultar', level='INFO') as captured:
            task = asyncio.create_task(consultas._consultar_cadastro(object(), self.cn))
            try:
                await asyncio.wait_for(iniciou.wait(), timeout=1)
                self.assertTrue(any('modulo=CNPJ' in msg and 'evento=inicio' in msg
                                    for msg in captured.output))
            finally:
                liberar.set()
                with self.assertRaises(CaptchaBloqueadoError):
                    await task
        texto = '\n'.join(captured.output)
        self.assertIn('codigo=captcha_bloqueado', texto)
        for segredo in (self.cn, 'SEGREDO', 'TOKEN', 'cookie'):
            self.assertNotIn(segredo, texto)

    async def test_agregado_recupera_optantes_sem_repetir_cadastro_e_dasn(self):
        chamadas = {'cadastro': 0, 'dasn': 0, 'optantes': 0}

        async def cadastro(page, cnpj):
            chamadas['cadastro'] += 1
            return {'nome_empresarial': 'EMPRESA EXEMPLO'}

        async def dasn(page, cnpj):
            chamadas['dasn'] += 1
            return deepcopy(self.dasn)

        async def optantes(page, cnpj):
            chamadas['optantes'] += 1
            if chamadas['optantes'] == 1:
                raise TimeoutError('transitório')
            return deepcopy(self.optantes)

        with patch.object(consultas, 'async_playwright', PlaywrightLocal), \
             patch.object(consultas, 'consultar_cnpj', cadastro), \
             patch.object(consultas, 'consultar_dasn', dasn), \
             patch.object(consultas, 'consultar_optantes', optantes):
            resultado = await consultas.consultar_mei(self.cn)
        self.assertEqual(resultado['optantes'], self.optantes)
        self.assertEqual(resultado['dasn'], self.dasn)
        self.assertEqual(chamadas, {'cadastro': 1, 'dasn': 1, 'optantes': 2})
        self.assertEqual(len(self.sessoes), 4)
        self.assertTrue(all(s.fechada for s in self.sessoes))


class TestBrowserCleanup(unittest.IsolatedAsyncioTestCase):
    async def test_fechamento_pendurado_tem_prazo_e_nao_deixa_task_orfa(self):
        liberar = asyncio.Event()
        terminou = asyncio.Event()

        class Navegador:
            async def close(self):
                try:
                    await liberar.wait()
                finally:
                    terminou.set()

        with patch.object(browser_module, '_CLEANUP_TIMEOUT_SECONDS', 0.02), \
             self.assertLogs('app.browser', level='WARNING'):
            task = asyncio.create_task(browser_module.fechar_browser(Navegador()))
            try:
                done, _ = await asyncio.wait({task}, timeout=0.1)
                self.assertIn(task, done, 'Cleanup ignorou seu prazo máximo')
                with self.assertRaises(RuntimeError):
                    task.result()
                self.assertTrue(terminou.is_set(), 'Task de close não foi cancelada')
            finally:
                liberar.set()
                if not task.done():
                    task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    async def test_cancelamento_com_close_pendurado_preserva_cancel_e_limita_cleanup(self):
        liberar = asyncio.Event()
        iniciou = asyncio.Event()
        terminou = asyncio.Event()

        class Navegador:
            async def close(self):
                iniciou.set()
                try:
                    await liberar.wait()
                finally:
                    terminou.set()

        with patch.object(browser_module, '_CLEANUP_TIMEOUT_SECONDS', 0.02), \
             self.assertLogs('app.browser', level='WARNING'):
            task = asyncio.create_task(browser_module.fechar_browser(Navegador()))
            try:
                await asyncio.wait_for(iniciou.wait(), timeout=1)
                task.cancel()
                done, _ = await asyncio.wait({task}, timeout=0.1)
                self.assertIn(task, done, 'Cancelamento deixou cleanup ilimitado')
                with self.assertRaises(asyncio.CancelledError):
                    task.result()
                self.assertTrue(terminou.is_set())
            finally:
                liberar.set()
                if not task.done():
                    task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    async def test_new_context_falha_fecha_browser(self):
        class Navegador:
            fechado = False

            async def new_context(self, **kwargs):
                raise RuntimeError('não foi possível abrir contexto')

            async def close(self):
                self.fechado = True

        browser = Navegador()
        playwright = type('P', (), {'chromium': type('C', (), {
            'launch': AsyncMock(return_value=browser)})()})()
        with self.assertRaises(RuntimeError):
            await create_browser(playwright)
        self.assertTrue(browser.fechado)
