import sys
import asyncio
import json
from copy import deepcopy
import uvicorn

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")


def run_cli():
    from app.consultar import consultar_mei

    if len(sys.argv) < 2:
        print("Uso: python main.py <CNPJ>")
        print("  ou: python main.py --server [--port 8000]")
        sys.exit(1)

    cnpj = sys.argv[1]
    print(f"Consultando MEI para CNPJ: {cnpj}\n")

    try:
        r = asyncio.run(consultar_mei(cnpj))
    except Exception as e:
        print(f"ERRO: {e}")
        sys.exit(1)

    cad = r["cadastro"]
    print(f"CNPJ: {r['cnpj']}")
    print(f"Razao Social: {cad['nome_empresarial'] or r['razao_social']}")
    if cad["nome_fantasia"] and cad["nome_fantasia"] != "********":
        print(f"Nome Fantasia: {cad['nome_fantasia']}")
    print(f"Abertura: {cad['data_abertura']}  |  Porte: {cad['porte']}")
    print(f"Natureza Juridica: {cad['natureza_juridica']}")
    print(f"CNAE Principal: {cad['atividade_principal']}")
    if cad["atividades_secundarias"]:
        print(f"CNAE Secundario: {cad['atividades_secundarias']}")
    end = f"{cad['logradouro']}, {cad['numero']}"
    if cad["complemento"] and cad["complemento"] != "********":
        end += f" - {cad['complemento']}"
    end += f" - {cad['bairro']}, {cad['municipio']}/{cad['uf']} - CEP {cad['cep']}"
    print(f"Endereco: {end}")
    if cad["email"] and cad["email"] != "********":
        print(f"Email: {cad['email']}  |  Tel: {cad['telefone']}")
    print(f"Situacao Cadastral: {cad['situacao_cadastral']} desde {cad['data_situacao_cadastral']}")
    if r["mei_baixada"]:
        print("*** MEI BAIXADA ***" + (f" em {r['data_baixa']}" if r["data_baixa"] else ""))
    print()

    opt = r["optantes"]
    print("--- Situacao Atual ---")
    print(f"  Simples Nacional: {opt['situacao_simples']}")
    print(f"  SIMEI: {opt['situacao_simei']}")
    print()

    if opt["periodos_simei_anteriores"]:
        print("--- Periodos SIMEI Anteriores ---")
        print(f"  {'DE':<12} {'ATE':<12} {'DETALHAMENTO'}")
        for p in opt["periodos_simei_anteriores"]:
            print(f"  {p['data_inicial']:<12} {p['data_final']:<12} {p['detalhamento']}")
        print()

    if opt["periodos_simples_anteriores"]:
        print("--- Periodos Simples Nacional Anteriores ---")
        print(f"  {'DE':<12} {'ATE':<12} {'DETALHAMENTO'}")
        for p in opt["periodos_simples_anteriores"]:
            print(f"  {p['data_inicial']:<12} {p['data_final']:<12} {p['detalhamento']}")
        print()

    print("--- Declaracoes DASN-SIMEI ---")
    print("=" * 70)
    print(f"{'ANO':<6} {'STATUS':<20} {'ACAO':<15} {'SIT.ESPECIAL':<15} {'PENDENTE'}")
    print("=" * 70)

    for d in r["declaracoes"]:
        if d["pendente"]:
            flag = ">>> SIM <<<"
        elif d["baixada"]:
            flag = "BAIXADA"
        else:
            flag = "Nao"
        sit = d["situacao_especial"] if d["situacao_especial"] != "-" else ""
        if d["data_baixa"] != "-":
            sit = f"{sit} {d['data_baixa']}".strip()
        print(f"{d['ano']:<6} {d['status']:<20} {d['acao']:<15} {sit:<15} {flag}")

    print("=" * 70)

    pendentes = r["pendentes"]
    if pendentes:
        anos = ", ".join(d["ano"] for d in pendentes)
        print(f"\n[!] Declaracoes PENDENTES: {anos}")
    else:
        print("\n[OK] Nenhuma declaracao pendente.")

    if "--json" in sys.argv:
        print(f"\n{json.dumps(r, ensure_ascii=False, indent=2)}")


def run_server():
    port = 8000
    if "--port" in sys.argv:
        idx = sys.argv.index("--port")
        if idx + 1 < len(sys.argv):
            port = int(sys.argv[idx + 1])

    log_config = deepcopy(uvicorn.config.LOGGING_CONFIG)
    log_config['formatters']['default']['fmt'] = '%(asctime)s %(levelprefix)s %(name)s %(message)s'
    log_config['loggers']['app'] = {
        'handlers': ['default'], 'level': 'INFO', 'propagate': False,
    }

    uvicorn.run(
        "app.api:app",
        host="0.0.0.0",
        port=port,
        proxy_headers=True,
        forwarded_allow_ips="*",
        log_config=log_config,
    )


if __name__ == "__main__":
    if "--server" in sys.argv:
        run_server()
    else:
        run_cli()
