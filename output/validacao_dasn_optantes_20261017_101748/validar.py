"""Smoke HTTP DASN e Optantes com cinco CNPJs reais, sem mocks."""
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
import socket
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import uvicorn
from pydantic import TypeAdapter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.api import app
from app.models import ConsultaResponse, DasnNaoOptanteResponse, DasnResultado, OptantesResponse

PASTA = Path(__file__).resolve().parent
FUSO = timezone(timedelta(hours=-3))
CNPJS = [
    '43996591000101',
    '45726608000136',
    '53987789000182',
    '57435953000108',
    '12309631000176',
]
MODELOS = {
    'completa': TypeAdapter(ConsultaResponse),
    'dasn': TypeAdapter(DasnResultado),
    'optantes': TypeAdapter(OptantesResponse),
}


def agora():
    return datetime.now(FUSO).isoformat(timespec='seconds')


def post(base_url, rota, cnpj):
    request = Request(
        base_url + rota,
        data=json.dumps({'cnpj': cnpj}).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urlopen(request, timeout=800) as response:
            return response.status, json.load(response)
    except HTTPError as exc:
        return exc.code, json.loads(exc.read())


def validar_optantes(dados, cnpj):
    assert dados.cnpj_consultado == cnpj, 'CNPJ consultado divergente'
    assert dados.cnpj_matriz[:8] == cnpj[:8], 'Raiz da matriz divergente'


def validar_dasn(dados):
    if isinstance(dados, DasnNaoOptanteResponse):
        assert dados.declaracoes is None and dados.pendentes is None
        return
    assert dados.razao_social and dados.razao_social.strip(), 'Razao social ausente'
    assert dados.declaracoes, 'Declaracoes ausentes'
    assert dados.pendentes == [d.ano for d in dados.declaracoes if d.pendente]
    assert dados.mei_baixada == any(d.baixada for d in dados.declaracoes)


def validar_resposta(tipo, payload, cnpj):
    dados = MODELOS[tipo].validate_python(payload)
    if tipo == 'completa':
        assert dados.cnpj == cnpj, 'CNPJ agregado divergente'
        validar_optantes(dados.optantes, cnpj)
        validar_dasn(dados.dasn)
    elif tipo == 'optantes':
        validar_optantes(dados, cnpj)
    else:
        validar_dasn(dados)


async def main():
    logging.basicConfig(
        filename=PASTA / 'recuperacao.log',
        level=logging.INFO,
        format='%(asctime)s %(name)s %(levelname)s %(message)s',
        encoding='utf-8',
    )
    relatorio = {'inicio': agora(), 'cnpjs': CNPJS, 'consultas': []}

    def salvar():
        (PASTA / 'relatorio.json').write_text(
            json.dumps(relatorio, ensure_ascii=False, indent=2), encoding='utf-8',
        )

    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    base_url = f'http://127.0.0.1:{sock.getsockname()[1]}'
    server = uvicorn.Server(uvicorn.Config(
        app, host='127.0.0.1', port=sock.getsockname()[1],
        log_config=None, access_log=False,
    ))
    servidor = asyncio.create_task(server.serve(sockets=[sock]))
    try:
        while not server.started:
            if servidor.done():
                await servidor
                raise RuntimeError('Servidor nao iniciou')
            await asyncio.sleep(0.05)
        print(f'INICIO {agora()} servidor={base_url}', flush=True)
        salvar()
        for cnpj in CNPJS:
            for tipo, rota in (
                ('dasn', '/consultar/dasn'),
                ('optantes', '/consultar/optantes'),
            ):
                inicio = time.monotonic()
                print(f'CONSULTANDO {cnpj} {tipo}', flush=True)
                registro = {'cnpj': cnpj, 'tipo': tipo, 'rota': rota, 'inicio': agora()}
                try:
                    status, payload = await asyncio.to_thread(post, base_url, rota, cnpj)
                    registro.update(http=status, resposta=payload)
                    if status == 200:
                        try:
                            validar_resposta(tipo, payload, cnpj)
                            registro['validacao'] = 'aprovada'
                        except Exception as exc:
                            registro['validacao'] = 'falhou'
                            registro['erro_validacao'] = type(exc).__name__
                    else:
                        registro['validacao'] = 'origem_nao_concluiu'
                except Exception as exc:
                    registro.update(http=None, validacao='falha_transporte', erro=type(exc).__name__)
                registro['duracao_segundos'] = round(time.monotonic() - inicio, 2)
                relatorio['consultas'].append(registro)
                salvar()
                print(
                    f"RESULTADO {cnpj} {tipo} HTTP={registro['http']} "
                    f"validacao={registro['validacao']} duracao={registro['duracao_segundos']}s",
                    flush=True,
                )
                if tipo == 'completa' and registro.get('validacao') == 'aprovada':
                    break
        relatorio['fim'] = agora()
        salvar()
        print(f'FIM {agora()} relatorio={PASTA / "relatorio.json"}', flush=True)
    finally:
        server.should_exit = True
        await servidor
        sock.close()


if __name__ == '__main__':
    asyncio.run(main())
