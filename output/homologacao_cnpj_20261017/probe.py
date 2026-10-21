"""Sondagem descartavel do portal atual; nao registra tokens ou credenciais."""
import asyncio
import json
import re
import sys
import time
from pathlib import Path

import requests
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from app.browser import create_browser, fechar_browser

OUT = Path(__file__).parent
URL = 'https://solucoes.receita.fazenda.gov.br/Servicos/cnpjreva/'
CAPTURE = """(() => {
 let api;
 Object.defineProperty(window, 'hcaptcha', {
  configurable: true,
  get: () => api,
  set: value => {
   api = value;
   const render = value.render;
   value.render = function(element, options) {
    window.__captchaOptions = options;
    return render.call(this, element, options);
   };
  }
 });
})()"""

def solve(sitekey, user_agent):
 key = next(line.split('=', 1)[1].strip() for line in (ROOT/'.env').read_text().splitlines() if line.startswith('NONECAP_API_KEY='))
 headers = {'Authorization': f'Bearer {key}'}
 r = requests.get('https://api.nonecap.com/v1/me', headers=headers, timeout=20)
 d = r.json()
 print('nonecap conta HTTP', r.status_code, 'campos', list(d), flush=True)
 r = requests.post('https://api.nonecap.com/v1/solves', params={'wait':30}, headers=headers,
  json={'type':'hcaptcha', 'url':URL, 'sitekey':sitekey, 'user_agent':user_agent}, timeout=40)
 d = r.json()
 end = time.monotonic()+180
 while True:
  print('nonecap HTTP', r.status_code, 'status', d.get('status'), 'error', (d.get('error') or {}).get('code'), flush=True)
  if d.get('status') == 'solved': return d
  if r.status_code >= 400 or d.get('status') in ('failed','expired','cancelled'):
   raise RuntimeError('Nonecap: '+str(d.get('error')))
  if time.monotonic() >= end: raise TimeoutError('NoneCap')
  r = requests.get('https://api.nonecap.com/v1/solves/'+d['id'], params={'wait':30}, headers=headers, timeout=40)
  d = r.json()

async def main():
 async with async_playwright() as p:
  browser, context = await create_browser(p)
  await context.add_init_script(CAPTURE)
  page = await context.new_page()
  async def capture(response):
   if '/api/v1/' not in response.url: return
   name = response.url.split('/api/v1/')[-1].replace('/','_')
   print('portal', name, response.status, flush=True)
   try:
    d = await response.json()
    (OUT/(name+'.json')).write_text(json.dumps(d,ensure_ascii=False,indent=2), encoding='utf8')
   except Exception: pass
  page.on('response', capture)
  try:
   await page.goto(URL)
   await page.wait_for_function('window.__captchaOptions?.sitekey')
   print('callback capturado', flush=True)
   await page.locator('#alert-cnpj input').fill('37482317000111')
   print('input',await page.locator('#alert-cnpj input').input_value(),flush=True)
   sitekey = await page.evaluate('window.__captchaOptions.sitekey')
   ua = await page.evaluate('navigator.userAgent')
   solution = await asyncio.to_thread(solve, sitekey, ua)
   if solution.get('user_agent'): await context.set_extra_http_headers({'User-Agent':solution['user_agent']})
   await page.evaluate('(token) => window.__captchaOptions.callback(token)',solution['token'])
   await page.get_by_role('button', name=re.compile('CONSULTAR', re.I)).click()
   try: await page.wait_for_url('**/comprovante', timeout=35000)
   except Exception:
    print('pagina', (await page.locator('body').inner_text())[:1800],flush=True)
    raise
   (OUT/'comprovante.html').write_text(await page.content(),encoding='utf8')
   await page.screenshot(path=str(OUT/'comprovante.png'),full_page=True)
   print((await page.locator('#principal').inner_text())[:6000],flush=True)
   btn=page.get_by_role('button', name=re.compile('Consultar QSA'))
   if await btn.count():
    await btn.click()
    await page.wait_for_url('**/qsa')
    (OUT/'qsa.html').write_text(await page.content(),encoding='utf8')
    await page.screenshot(path=str(OUT/'qsa.png'),full_page=True)
    print((await page.locator('body').inner_text())[-5000:],flush=True)
  finally: await fechar_browser(browser,preservar_erro=True)

asyncio.run(main())
