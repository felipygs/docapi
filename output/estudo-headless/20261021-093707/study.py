"""Instrumento descartável. Executar da raiz; nenhum arquivo de runtime é editado."""
import argparse
import asyncio
import copy
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
sys.path.insert(0,str(ROOT))

def write(path,data):
    Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')

def normalize(route, data):
    data = copy.deepcopy(data)
    if route == '/consultar/optantes':
        data.pop('consultado_em',None)
    elif route == '/consultar/dasn':
        data.pop('optantes_consultado_em',None)
    elif route == '/consultar':
        data.get('optantes',{}).pop('consultado_em',None)
        data.get('dasn',{}).pop('optantes_consultado_em',None)
    return data

def safe_failure(status, data):
    # Never copy exception text or external detail into study artifacts.
    return dict(http_status=status,error={502:'external_failure',504:'timeout',500:'internal_failure'}.get(status,'request_failure'))

def launch_options(mode, options):
    options = copy.deepcopy(options)
    if mode == 'headless':
        options['headless'] = True
        options['args'] = [a for a in options.get('args',[]) if not a.startswith(('--window-position=','--window-size='))]
    return options

def worker(mode,port,folder):
    import uvicorn
    from fastapi import BackgroundTasks
    from playwright.async_api import BrowserType,async_playwright
    from app.api import app,_safe_call
    from app.browser import create_browser,fechar_browser
    folder = Path(folder)
    events_file = folder/'worker-events.jsonl'
    def record(data):
        with events_file.open('a',encoding='utf8') as f:
            f.write(json.dumps(dict(t=time.time(),**data),ensure_ascii=False)+'\n')

    class SafeHandler(logging.Handler):
        def emit(self,rec):
            msg = rec.getMessage()
            # Only the existing local diagnostic vocabulary, never tracebacks.
            if re.fullmatch(r'(?:modulo=(?:CNPJ|DASN|Optantes) tentativa=\d+ (?:evento=inicio|duracao=\d+\.\d+ codigo=[a-z_]+)|codigo=cleanup_[a-z_]+)',msg):
                record(dict(kind='app_log',message=msg))
    logger = logging.getLogger('app')
    logger.handlers[:] = [SafeHandler()]
    logger.setLevel(logging.INFO)
    logger.propagate = False
    original = BrowserType.launch
    async def launch(self,*args,**kwargs):
        effective = launch_options(mode,kwargs)
        record(dict(kind='launch',options={k:effective[k] for k in ('channel','headless','args') if k in effective}))
        return await original(self,*args,**effective)
    BrowserType.launch = launch

    @app.get('/_study/smoke')
    async def smoke():
        async with async_playwright() as p:
            browser,context = await create_browser(p)
            try:
                page = await context.new_page()
                await page.set_content('<html><body><input id="x"><button onclick="document.body.dataset.ok=document.querySelector(\'#x\').value">Test</button></body></html>')
                await page.locator('#x').fill('local-ok')
                await page.locator('button').click()
                await asyncio.sleep(.3)
                return await page.evaluate('({value:document.body.dataset.ok,width:innerWidth,height:innerHeight,locale:navigator.language})')
            finally:
                await fechar_browser(browser)

    @app.get('/_study/error')
    async def error():
        async def fail():
            raise RuntimeError('cookie=TOKEN API_KEY=SEGREDO')
        return await _safe_call(fail)

    server = uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,log_config=None,
                                          log_level='critical',access_log=False))
    @app.post('/_study/stop')
    async def stop():
        server.should_exit = True
        return {'stopping':True}
    record(dict(kind='worker_start',pid=os.getpid(),mode=mode,port=port))
    server.run()
    record(dict(kind='worker_end'))

def validate(route,data,cnpj):
    from pydantic import TypeAdapter
    from app.models import CadastroResponse,DasnResultado,OptantesResponse,ConsultaResponse
    models = {'/consultar/cnpj':CadastroResponse,'/consultar/dasn':DasnResultado,
              '/consultar/optantes':OptantesResponse,'/consultar':ConsultaResponse}
    value = TypeAdapter(models[route]).validate_python(data).model_dump(mode='json')
    opt = value if route=='/consultar/optantes' else value.get('optantes')
    if opt is not None:
        assert opt['cnpj_consultado']==cnpj and opt['cnpj_matriz'][:8]==cnpj[:8]
    if route=='/consultar':
        assert value['cnpj']==cnpj
    dasn = value if route=='/consultar/dasn' else value.get('dasn')
    if dasn is not None:
        if dasn.get('codigo_origem')=='33001':
            assert dasn['cnpj']==cnpj
            assert all(dasn[k] is None for k in ('declaracoes','pendentes','mei_baixada','data_baixa'))
        else:
            assert dasn.get('razao_social') and dasn.get('declaracoes')
    cad = value if route=='/consultar/cnpj' else value.get('cadastro')
    if cad is not None:
        assert cad.get('nome_empresarial') and 'socios' in cad
        assert cad['capital_social'] is None or type(cad['capital_social']) is int
    return value

def run_case(mode,route,cnpj,round_no,smoke=False):
    import requests
    from windows_observer import Observer,identity,terminate_owned
    name = ('smoke' if smoke else route.strip('/').replace('/','_')+'_'+cnpj)+f'_r{round_no}_{mode}'
    folder = OUT/name
    folder.mkdir(exist_ok=False)
    with socket.socket() as listener:
        listener.bind(('127.0.0.1',0))
        port = listener.getsockname()[1]
    base = f'http://127.0.0.1:{port}'
    observer = Observer().start()
    proc = None
    result = dict(case=name,mode=mode,route=route,cnpj=cnpj,round=round_no,
                  started=datetime.now().astimezone().isoformat())
    try:
        proc = subprocess.Popen([sys.executable,str(__file__),'worker','--mode',mode,'--port',str(port),'--folder',str(folder)],
                                cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        deadline = time.monotonic()+25
        while True:
            if proc.poll() is not None:
                raise RuntimeError('worker_exited')
            try:
                if requests.get(base+'/health',timeout=1).status_code==200:
                    break
            except requests.RequestException:
                pass
            if time.monotonic()>deadline:
                raise TimeoutError('worker_start_timeout')
            time.sleep(.1)
        started = time.monotonic()
        response = requests.get(base+'/_study/smoke',timeout=30) if smoke else requests.post(base+route,json={'cnpj':cnpj},timeout=800)
        result['duration_seconds'] = round(time.monotonic()-started,3)
        result['http_status'] = response.status_code
        if response.status_code==200:
            data = response.json()
            result['data'] = data if smoke else validate(route,data,cnpj)
            result['contract_valid'] = True
        else:
            result.update(safe_failure(response.status_code,None))
        if smoke:
            bad = requests.get(base+'/_study/error',timeout=5)
            result['safe_failure_probe'] = safe_failure(bad.status_code,bad.json())
    except Exception as exc:
        result.update(error=type(exc).__name__,contract_valid=False)
    finally:
        if proc:
            try:
                requests.post(base+'/_study/stop',timeout=2)
            except requests.RequestException:
                pass
            try:
                proc.wait(15)
            except subprocess.TimeoutExpired:
                result['forced_worker_stop'] = True
                proc.terminate()
                proc.wait(10)
            result['worker_exit'] = proc.returncode
        time.sleep(.4)
        observations = observer.finish()
        interventions = []
        for info in reversed(observations['alive_after']):
            if terminate_owned(info['pid'],info['created']):
                interventions.append(info['pid'])
        observations['forced_cleanup'] = interventions
        observations['remaining_after_intervention'] = [p['pid'] for p in observations['alive_after']
            if (stamp:=identity(p['pid'])) and stamp['alive'] and stamp['created']==p['created']]
        write(folder/'windows.json',observations)
        result['windows'] = {k:observations[k] for k in ('errors','visible_events','foreground_events','alive_after','forced_cleanup','remaining_after_intervention','max_inventory_gap_seconds')}
        events = [json.loads(line) for line in (folder/'worker-events.jsonl').read_text(encoding='utf8').splitlines()] if (folder/'worker-events.jsonl').exists() else []
        result['launches'] = [e['options'] for e in events if e['kind']=='launch']
        result['module_logs'] = [e['message'] for e in events if e['kind']=='app_log']
        result['attempts'] = sum('evento=inicio' in m for m in result['module_logs'])
        result['captcha_blocks'] = sum('codigo=captcha_bloqueado' in m for m in result['module_logs'])
        result['cleanup_failure'] = bool(observations['alive_after'] or interventions or result.get('forced_worker_stop') or any('cleanup_' in m for m in result['module_logs']))
        result['ended'] = datetime.now().astimezone().isoformat()
        write(folder/'result.json',result)
    print(json.dumps({k:result.get(k) for k in ('case','http_status','error','duration_seconds','attempts','captcha_blocks','cleanup_failure')},ensure_ascii=False),flush=True)
    return result

def reasons(a,b):
    flags = []
    if a.get('http_status')!=200 or b.get('http_status')!=200 or not a.get('contract_valid') or not b.get('contract_valid'):
        flags.append('http_or_contract')
    elif normalize(a['route'],a['data']) != normalize(b['route'],b['data']):
        flags.append('data_difference')
    if b['attempts']>a['attempts'] or b['captcha_blocks']>a['captcha_blocks']:
        flags.append('more_attempts_or_blocks')
    if a['cleanup_failure'] or b['cleanup_failure']:
        flags.append('cleanup_failure')
    if b['windows']['visible_events'] or b['windows']['foreground_events']:
        flags.append('visible_or_foreground')
    if a['windows']['errors'] or b['windows']['errors']:
        flags.append('observer_error')
    return flags

CASES = [('/consultar/cnpj',c) for c in ('37482317000111','00000000000191')]
CN = ('43996591000101','45726608000136','53987789000182','57435953000108','12309631000176')
CASES += [(r,c) for r in ('/consultar/dasn','/consultar/optantes') for c in CN]
CASES += [('/consultar','45726608000136')]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action',choices=['worker','smoke','real'])
    parser.add_argument('--mode',choices=['control','headless'])
    parser.add_argument('--port',type=int)
    parser.add_argument('--folder')
    parser.add_argument('--group',choices=['cnpj','dasn','optantes','complete','all'],default='all')
    args = parser.parse_args()
    if args.action=='worker':
        worker(args.mode,args.port,args.folder)
    elif args.action=='smoke':
        a = run_case('control','/_study/smoke','',1,True)
        b = run_case('headless','/_study/smoke','',1,True)
        expected = dict(value='local-ok',width=1280,height=720,locale='pt-BR')
        assert a.get('data')==b.get('data')==expected,(a.get('data'),b.get('data'))
        assert a['launches']==[dict(channel='chrome',headless=False,args=['--disable-blink-features=AutomationControlled','--no-sandbox','--disable-dev-shm-usage','--window-position=-32000,-32000','--window-size=1,1'])]
        assert b['launches']==[launch_options('headless',a['launches'][0])]
        assert a['windows']['visible_events']>0,'Observador não detectou janela do controle'
        assert not b['windows']['visible_events'] and not b['windows']['foreground_events']
        assert not a['windows']['errors'] and not b['windows']['errors']
        assert not a['cleanup_failure'] and not b['cleanup_failure']
        assert a['safe_failure_probe']==b['safe_failure_probe']==dict(http_status=502,error='external_failure')
        write(OUT/'smoke-summary.json',dict(passed=True,control=a['windows'],headless=b['windows']))
        print('SMOKE PASSED',flush=True)
    else:
        assert json.loads((OUT/'smoke-summary.json').read_text())['passed']
        assert json.loads((OUT/'suite-result.json').read_text(encoding='utf-8-sig'))['exit_code']==0
        pairs = []
        for route,cnpj in CASES:
            group = 'complete' if route=='/consultar' else route.split('/')[-1]
            if args.group not in ('all',group):
                continue
            rounds = []
            for round_no in (1,2):
                a = run_case('control',route,cnpj,round_no)
                b = run_case('headless',route,cnpj,round_no)
                flags = reasons(a,b)
                rounds.append(dict(round=round_no,control=a['case'],headless=b['case'],reasons=flags))
                if not flags:
                    break
            pairs.append(dict(route=route,cnpj=cnpj,rounds=rounds))
            write(OUT/f'pairs-{args.group}.json',pairs)

if __name__ == '__main__':
    main()
