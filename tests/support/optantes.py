import unittest
from pathlib import Path
from playwright.async_api import async_playwright
from app.scrapers.optantes import consultar_optantes


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "optantes"
DETALHAMENTO = "Excluída por Ato Administrativo praticado pela Receita Federal do Brasil"
SIMEI_DETALHAMENTO = "Desenquadrada por Comunicação Obrigatória do Contribuinte"
TITULOS = [
    "Identificação do Contribuinte - CNPJ Matriz",
    "Situação Atual",
    "Períodos Anteriores",
    "Eventos Futuros (Simples Nacional)",
    "Eventos Futuros (SIMEI)",
    "Informações de Períodos como MEI Transportador Autônomo de Cargas",
]
ELIANE_PERIODOS = [
    {"data_inicial": "2025-01-01", "data_final": "2025-12-31", "detalhamento": DETALHAMENTO},
    {"data_inicial": "2024-01-01", "data_final": "2024-12-31", "detalhamento": DETALHAMENTO},
    {"data_inicial": "2021-10-25", "data_final": "2023-12-31", "detalhamento": DETALHAMENTO},
]
ELIANE_EVENTOS = [{"descricao": "Exclusão de Ofício - Débitos", "data_efeito": "2027-01-01"}]


def fixture(nome):
    return (FIXTURES / nome).read_text(encoding="utf-8")


class PaginaOffline:
    """Única substituição: goto carrega fixture, todo o restante usa DOM real."""

    def __init__(self, page, html):
        self.page = page
        self.html = html
        self.navegacoes = []

    async def goto(self, url, **kwargs):
        self.navegacoes.append((url, kwargs))
        controles = (
            '<section data-test-controls="offline">'
            '<label for="Cnpj">CNPJ de teste</label><input id="Cnpj">'
            '<button type="button">Consultar</button></section>'
        )
        await self.page.set_content(
            self.html.replace("<body>", "<body>" + controles, 1),
            wait_until="load",
        )
        return None

    def __getattr__(self, name):
        return getattr(self.page, name)


class BrowserOffline(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.playwright = await async_playwright().start()
        self.addAsyncCleanup(self.playwright.stop)
        # Reutiliza Chrome instalado; nenhuma instalação ou sessão de produção.
        self.browser = await self.playwright.chromium.launch(channel="chrome", headless=True)
        self.addAsyncCleanup(self.browser.close)
        self.context = await self.browser.new_context(
            offline=True, service_workers="block", accept_downloads=False,
        )
        self.addAsyncCleanup(self.context.close)
        self.requests = []
        self.bloqueadas = []
        self.context.on("request", lambda request: self.requests.append(request.url))
        await self.context.route("**/*", self.bloquear_request)
        self.page = await self.context.new_page()
        self.page.set_default_timeout(3000)

    async def bloquear_request(self, route):
        self.bloqueadas.append(route.request.url)
        await route.abort()

    async def asyncTearDown(self):
        # Contamos tentativas, não apenas requests que tiveram sucesso.
        self.assertEqual(self.requests, [], "Fixture/parser tentou acessar a rede")
        self.assertEqual(self.bloqueadas, [], "Houve tentativa de request bloqueada")

    async def consultar(self, html, cnpj="43996591000101"):
        offline = PaginaOffline(self.page, html)
        resultado = await consultar_optantes(offline, cnpj, max_retries=1)
        self.assertEqual(len(offline.navegacoes), 1)
        self.assertEqual(await self.page.locator("#Cnpj").input_value(), cnpj)
        self.assertTrue(await self.page.locator("#btnMaisInfo").is_disabled())
        self.assertEqual(self.requests, [])
        return resultado
