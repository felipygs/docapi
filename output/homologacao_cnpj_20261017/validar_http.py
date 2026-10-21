"""Homologacao HTTP real: sem substituir navegador, scraper ou solver."""
import json
import socket
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import requests
import uvicorn

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from app.api import app
from app.models import CadastroResponse

OUT = Path(__file__).parent
sock = socket.socket()
sock.bind(('127.0.0.1', 0))
sock.listen(128)
server = uvicorn.Server(uvicorn.Config(app, log_level='error', lifespan='off'))
thread = threading.Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True)
thread.start()
base = f'http://127.0.0.1:{sock.getsockname()[1]}'
relatorio = {'executado_em': datetime.now().astimezone().isoformat(), 'endpoint': 'POST /consultar/cnpj', 'resultados': []}
arquivo_relatorio = OUT / ('relatorio_http_' + datetime.now().strftime('%H%M%S') + '.json')
try:
    requests.get(base+'/health', timeout=10).raise_for_status()
    for cnpj in (sys.argv[1:] or ('37.482.317/0001-11', '00000000000191')):
        inicio = time.monotonic()
        r = requests.post(base+'/consultar/cnpj', json={'cnpj': cnpj}, timeout=600)
        payload = r.json()
        cn = ''.join(c for c in cnpj if c.isdigit())
        (OUT/f'http_{cn}.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf8')
        item = {'cnpj': cnpj, 'http_status': r.status_code, 'duracao_s': round(time.monotonic()-inicio, 2)}
        if r.status_code == 200:
            CadastroResponse.model_validate(payload)
            assert payload['nome_empresarial'] and payload['data_abertura']
            assert sum(payload['situacao_cadastral'][k] for k in ('ativa','baixada','suspensa','inapta','nula')) == 1
            item.update(nome=payload['nome_empresarial'], capital_social_centavos=payload['capital_social'], quantidade_socios=len(payload['socios']), contrato_validado=True)
        else:
            item['erro'] = payload
        relatorio['resultados'].append(item)
        arquivo_relatorio.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding='utf8')
        (OUT/'relatorio_http.json').write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding='utf8')
        print(json.dumps(item,ensure_ascii=True),flush=True)
finally:
    server.should_exit = True
    thread.join(timeout=10)
    sock.close()
assert all(r['http_status'] == 200 for r in relatorio['resultados'])
