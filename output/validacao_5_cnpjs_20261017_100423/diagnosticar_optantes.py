"""Captura somente snapshot fiscal e estrutura dos painéis, sem cookies/HTML bruto."""
import asyncio
import json
from pathlib import Path
import sys

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.browser import create_browser, fechar_browser
from app.scrapers.optantes import consultar_optantes
from app.scrapers.optantes_parser import adquirir_snapshot, transformar_snapshot

PASTA = Path(__file__).resolve().parent
CNPJ = '43996591000101'


async def main():
    async with async_playwright() as p:
        browser, context = await create_browser(p)
        try:
            page = await context.new_page()
            try:
                await consultar_optantes(page, CNPJ)
                erro = None
            except Exception as exc:
                erro = {'tipo': type(exc).__name__, 'mensagem': str(exc)}
            snapshot = await adquirir_snapshot(page)
            estrutura = await page.evaluate('''() => [...document.querySelectorAll('#conteudo .panel')]
              .filter(p => p.querySelector(':scope > .panel-heading h3'))
              .map(p => ({
                titulo: p.querySelector(':scope > .panel-heading h3').textContent.trim(),
                pai: {tag: p.parentElement.tagName, id: p.parentElement.id, classe: p.parentElement.className},
                corpos: [...p.querySelectorAll(':scope > .panel-body')].map(b => ({
                  display: getComputedStyle(b).display,
                  visibility: getComputedStyle(b).visibility,
                  hidden: b.hidden,
                  filhos: [...b.children].map(c => c.tagName)
                })),
                dentroMaisInfo: !!p.closest('#maisInfo')
              }))''')
            await page.screenshot(path=str(PASTA / 'optantes_diagnostico.png'), full_page=True)
            diagnostico = {'cnpj': CNPJ, 'erro': erro, 'estrutura': estrutura}
            for nome, valor in (('optantes_snapshot.json', snapshot), ('optantes_diagnostico.json', diagnostico)):
                (PASTA / nome).write_text(json.dumps(valor, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps(diagnostico, ensure_ascii=True, indent=2))
            try:
                transformar_snapshot(snapshot, CNPJ)
            except Exception as exc:
                print('Reproducao local do snapshot:', type(exc).__name__, str(exc))
        finally:
            await fechar_browser(browser, preservar_erro=True)


if __name__ == '__main__':
    asyncio.run(main())
