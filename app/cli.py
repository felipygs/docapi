import sys
import asyncio
import json
from .cli_output import imprimir_resultado


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

    imprimir_resultado(r)

    if "--json" in sys.argv:
        print(f"\n{json.dumps(r, ensure_ascii=False, indent=2)}")
