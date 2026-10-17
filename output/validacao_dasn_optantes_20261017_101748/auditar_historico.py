"""Comparação isolada entre HEAD e código atual, sem sobrescrever a aplicação."""
import asyncio
import json
from pathlib import Path
import subprocess
import sys
import time
import types

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.browser import create_browser, fechar_browser
from app.scrapers.dasn import consultar_dasn
from app.scrapers.optantes import consultar_optantes

PASTA = Path(__file__).resolve().parent


def carregar_head(caminho, nome, pacote):
    source = subprocess.check_output(['git', 'show', f'HEAD:{caminho}'], cwd=ROOT).decode('utf-8')
    modulo = types.ModuleType(nome)
    modulo.__package__ = pacote
    exec(compile(source, f'HEAD:{caminho}', 'exec'), modulo.__dict__)
    return modulo


class PaginaAuditada:
    def __init__(self, page, registro):
        self.page = page
        self.registro = registro

    def __getattr__(self, nome):
        metodo = getattr(self.page, nome)
        if nome not in ('goto', 'wait_for_selector', 'wait_for_url', 'fill', 'click', 'evaluate'):
            return metodo

        async def executar(*args, **kwargs):
            self.registro['ultima_etapa'] = nome
            if nome in ('wait_for_selector', 'click', 'wait_for_url'):
                self.registro['ultimo_seletor'] = args[0]
            print(self.registro['versao'], self.registro['modulo'], 'etapa=', nome, flush=True)
            return await metodo(*args, **kwargs)
        return executar


async def main():
    anterior_browser = carregar_head('app/browser.py', 'app._browser_head', 'app')
    anterior_dasn = carregar_head('app/scrapers/dasn.py', 'app.scrapers._dasn_head', 'app.scrapers')
    anterior_parser = carregar_head('app/scrapers/optantes_parser.py', 'app.scrapers._parser_head', 'app.scrapers')
    anterior_optantes = carregar_head('app/scrapers/optantes.py', 'app.scrapers._optantes_head', 'app.scrapers')
    anterior_optantes.adquirir_snapshot = anterior_parser.adquirir_snapshot
    anterior_optantes.transformar_snapshot = anterior_parser.transformar_snapshot
    anterior_optantes.falha = anterior_parser.falha
    relatorio = []
    for versao, modulo, criar, consultar, cnpj in (
        ('HEAD', 'DASN', anterior_browser.create_browser, anterior_dasn.consultar_dasn, '45726608000136'),
        ('atual', 'DASN', create_browser, consultar_dasn, '45726608000136'),
        ('HEAD', 'Optantes', anterior_browser.create_browser, anterior_optantes.consultar_optantes, '43996591000101'),
        ('atual', 'Optantes', create_browser, consultar_optantes, '43996591000101'),
    ):
        inicio = time.monotonic()
        registro = {'versao': versao, 'modulo': modulo, 'cnpj': cnpj}
        print('INICIO', versao, modulo, flush=True)
        async with async_playwright() as p:
            browser = None
            try:
                async with asyncio.timeout(70):
                    browser, context = await criar(p)
                    page = await context.new_page()
                    resultado = await consultar(PaginaAuditada(page, registro), cnpj)
                    registro['resultado'] = 'sucesso'
                    registro['resposta'] = resultado
            except Exception as exc:
                registro['resultado'] = 'falha'
                registro['erro'] = type(exc).__name__
                if isinstance(exc, RuntimeError):
                    registro['detalhe'] = str(exc)
            finally:
                if browser is not None:
                    await fechar_browser(browser, preservar_erro=True)
        registro['duracao_segundos'] = round(time.monotonic() - inicio, 2)
        relatorio.append(registro)
        (PASTA / 'auditoria_historico.json').write_text(
            json.dumps(relatorio, ensure_ascii=False, indent=2), encoding='utf-8',
        )
        print('RESULTADO', versao, modulo, registro['resultado'], registro.get('detalhe', registro.get('erro', '')), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
