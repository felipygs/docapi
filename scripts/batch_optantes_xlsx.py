"""Consulta Optantes em lote e gera planilha XLSX."""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CNPJS = """
11365521000169
12309631000176
29371597000162
36806752000191
36928735000127
37482317000111
46860504000182
57282645000181
57446879000117
60015464000101
63722519000101
65110849000163
67948319000114
51476314000104
49044302000150
26461528000151
39521518000106
62759228000117
48390941000105
36785023000104
16014960400177
53178144000107
67507778000162
34555461000142
48743464000114
61180301000139
47724108000190
44458587000152
58741540000106
30288513000100
54860374000106
46787246000156
52847783000147
66109261000152
03382803000146
54790003000103
58360581000152
07517468000105
36181093000145
65485076000108
32918995000160
68164043000146
49173066000172
67080983000194
56419239000155
51867294000194
53479308000128
44223079000195
30699240000197
35340137000170
52164912000100
34606066000141
26114962000165
52414008000106
59619746000120
50029654000116
52645932000195
33552154000145
68375946000176
43996591000101
33618781000131
41646909000107
50824718000170
42115775000152
60112305000117
38139407000177
58816581000114
53648206000199
40779544000118
48123272000105
35948057000100
37633558000114
35805623000116
49542636000154
64421653000127
36808587000107
62396283000190
63638227000187
55419982000142
35636409000183
49858909000174
22932054000128
29754242000152
58883287000125
58189115000156
60664100000144
40770892000124
47144728000150
55591938000115
45726608000136
51897234000114
47693349000110
50115777000170
68796263000192
31785334000141
38139563000138
30664867000102
32800353000162
40038968000121
48679135000151
54292367000155
39272095000138
48262850000194
64951942000138
42789088000112
60279633000102
66145097000139
41883628000160
43119495000185
40713508000151
66055256000104
48956712000105
59066960000105
60279473000100
49998679000149
62978773000102
53135198000187
50858824000175
41884059000177
53446534000102
05463274000130
48214442000167
61330845000130
36587276000165
43473712000130
47218354000170
67134198000177
54542237000123
69428563000181
65861582000146
57599840000130
58921767000133
64705913000196
53618848000145
68757653000153
50833697000150
57515509000194
44769491000377
56022039000164
43054625000149
36860733000143
33145114000189
66146429000108
55633244000101
46951978000130
34606131000139
60920523000188
39296754000176
50484004000160
50855984000160
55975756000148
65695832000115
44520539000147
34194865000158
46635290000140
63121519000148
35996548000118
61876019000190
63031274000168
50442256000127
40805485000105
53704399000158
36453418000100
40255637000143
47442982000135
67747481000174
""".strip().split()


def _fmt_eventos(eventos: list[dict]) -> str:
    if not eventos:
        return ""
    partes = []
    for ev in eventos:
        data = ev.get("data_efeito") or "sem data"
        partes.append(f"{ev.get('descricao', '')} ({data})")
    return " | ".join(partes)


def _row_from_result(cnpj: str, data: dict | None, erro: str | None) -> dict:
    if erro or not data:
        return {
            "cnpj": cnpj,
            "nome_empresarial": "",
            "optante_simples": "",
            "situacao_simples": "",
            "desde_simples": "",
            "enquadrado_mei": "",
            "situacao_simei": "",
            "desde_simei": "",
            "eventos_futuros_simples": "",
            "eventos_futuros_simei": "",
            "consultado_em": "",
            "erro": erro or "desconhecido",
        }
    sn = data["simples_nacional"]
    sm = data["simei"]
    return {
        "cnpj": data.get("cnpj_consultado", cnpj),
        "nome_empresarial": data.get("nome_empresarial", ""),
        "optante_simples": "Sim" if sn["optante"] else "Não",
        "situacao_simples": sn.get("situacao", ""),
        "desde_simples": sn.get("data_desde") or "",
        "enquadrado_mei": "Sim" if sm["enquadrado"] else "Não",
        "situacao_simei": sm.get("situacao", ""),
        "desde_simei": sm.get("data_desde") or "",
        "eventos_futuros_simples": _fmt_eventos(sn.get("eventos_futuros", [])),
        "eventos_futuros_simei": _fmt_eventos(sm.get("eventos_futuros", [])),
        "consultado_em": str(data.get("consultado_em", "")),
        "erro": "",
    }


def _write_xlsx(rows: list[dict], path: Path) -> None:
    from openpyxl import Workbook
    from openpyxl.utils import get_column_letter

    headers = [
        ("cnpj", "CNPJ"),
        ("nome_empresarial", "Razão Social"),
        ("optante_simples", "Optante Simples"),
        ("situacao_simples", "Situação Simples"),
        ("desde_simples", "Desde Simples"),
        ("enquadrado_mei", "MEI (SIMEI)"),
        ("situacao_simei", "Situação SIMEI"),
        ("desde_simei", "Desde SIMEI"),
        ("eventos_futuros_simples", "Eventos Futuros Simples"),
        ("eventos_futuros_simei", "Eventos Futuros SIMEI"),
        ("consultado_em", "Consultado em"),
        ("erro", "Erro"),
    ]

    def sheet_rows(wb: Workbook, title: str, subset: list[dict]) -> None:
        ws = wb.create_sheet(title)
        ws.append([h[1] for h in headers])
        for r in subset:
            ws.append([r[k] for k, _ in headers])
        for i, (_, label) in enumerate(headers, 1):
            width = max(len(label), *(len(str(r[headers[i - 1][0]] or "")) for r in subset) if subset else [0])
            ws.column_dimensions[get_column_letter(i)].width = min(max(width + 2, 12), 60)

    ok = [r for r in rows if not r["erro"]]
    wb = Workbook()
    wb.remove(wb.active)
    sheet_rows(wb, "Todas", rows)
    sheet_rows(wb, "Optantes Simples", [r for r in ok if r["optante_simples"] == "Sim"])
    sheet_rows(wb, "MEI", [r for r in ok if r["enquadrado_mei"] == "Sim"])
    sheet_rows(
        wb,
        "Eventos Futuros",
        [
            r
            for r in ok
            if r["eventos_futuros_simples"] or r["eventos_futuros_simei"]
        ],
    )
    sheet_rows(wb, "Erros", [r for r in rows if r["erro"]])
    wb.save(path)


async def main() -> None:
    from app.consultar import consultar_apenas_optantes

    out_dir = ROOT / "output"
    out_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    cache_path = out_dir / f"optantes_batch_{stamp}.json"
    xlsx_path = out_dir / f"consultas_optantes_{stamp}.xlsx"

    # Reutilizar cache do mesmo dia se existir (retomada)
    caches = sorted(out_dir.glob("optantes_batch_*.json"), reverse=True)
    results: dict[str, dict] = {}
    if caches:
        try:
            loaded = json.loads(caches[0].read_text(encoding="utf-8"))
            if isinstance(loaded.get("results"), dict):
                results = loaded["results"]
                cache_path = caches[0]
                print(f"Retomando cache: {cache_path.name} ({len(results)} já consultados)")
        except (json.JSONDecodeError, OSError):
            pass

    total = len(CNPJS)
    for i, cnpj in enumerate(CNPJS, 1):
        cnpj = cnpj.strip().zfill(14)
        if cnpj in results and "data" in results[cnpj] and not results[cnpj].get("erro"):
            continue
        print(f"[{i}/{total}] {cnpj}...", flush=True)
        try:
            data = await consultar_apenas_optantes(cnpj)
            results[cnpj] = {"data": data, "erro": None}
        except Exception as exc:
            results[cnpj] = {"data": None, "erro": str(exc)}
            print(f"  ERRO: {exc}", flush=True)

        cache_path.write_text(
            json.dumps({"updated": datetime.now().isoformat(), "results": results}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        rows = [_row_from_result(c, v.get("data"), v.get("erro")) for c, v in sorted(results.items())]
        _write_xlsx(rows, xlsx_path)

    rows = [_row_from_result(c, v.get("data"), v.get("erro")) for c, v in sorted(results.items())]
    _write_xlsx(rows, xlsx_path)
    ok = sum(1 for r in rows if not r["erro"])
    print(f"\nConcluído: {ok}/{total} OK")
    print(f"Planilha: {xlsx_path}")
    print(f"Cache JSON: {cache_path}")


if __name__ == "__main__":
    asyncio.run(main())
