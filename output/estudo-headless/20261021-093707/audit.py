"""Auditoria das evidências sem imprimir valores de credenciais."""
import json
from pathlib import Path
import os
import sys
from dotenv import dotenv_values

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]

def main():
    secrets = {v for k,v in {**dotenv_values(ROOT/'.env'),**os.environ}.items()
               if k in ('NONECAP_API_KEY','NOPECHA_API_KEY') and v}
    hits = []
    files = [p for p in OUT.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    report = ROOT/'docs'/'estudo-headless-2026-10-21.md'
    if report.exists():
        files.append(report)
    for p in files:
        raw = p.read_bytes()
        if any(s.encode(enc) in raw for s in secrets for enc in ('utf8','utf-16-le')):
            hits.append(str(p.relative_to(ROOT)))
    before = json.loads((OUT/'before.json').read_text(encoding='utf8'))
    after = json.loads((OUT/'after.json').read_text(encoding='utf8'))
    differences = sorted(k for k in before['hashes'].keys()|after['hashes'].keys()
                         if before['hashes'].get(k)!=after['hashes'].get(k))
    results = [json.loads(p.read_text(encoding='utf8')) for p in sorted(OUT.glob('*/result.json'))]
    real_results = [r for r in results if not r['case'].startswith('smoke')]
    pairs = []
    for group in ('cnpj','dasn','optantes','complete'):
        pairs.extend(json.loads((OUT/f'pairs-{group}.json').read_text(encoding='utf8')))
    assert len(pairs)==13 and len({(p['route'],p['cnpj']) for p in pairs})==13
    assert len(real_results)==sum(len(p['rounds'])*2 for p in pairs)
    assert all(len(p['rounds'])==(2 if p['rounds'][0]['reasons'] else 1) for p in pairs)
    ordered = sorted(real_results,key=lambda r:r['started'])
    assert all(a['ended']<=b['started'] for a,b in zip(ordered,ordered[1:])), 'Chamadas se sobrepuseram'
    assert all('data' not in r for r in real_results if r.get('http_status')!=200), 'Falha contém dados parciais'
    for result in real_results:
        if result['route']=='/consultar':
            starts = [s for s in result['module_logs'] if 'evento=inicio' in s]
            assert sum(s.startswith('modulo=CNPJ ') for s in starts)==1
            if result.get('http_status')==200:
                assert all(k in result['data'] for k in ('cadastro','dasn','optantes'))
    remaining = [r['case'] for r in results if r['windows']['remaining_after_intervention']]
    cleanup = [r['case'] for r in results if r['cleanup_failure']]
    observation = [r['case'] for r in results if r['windows']['errors']]
    headless_windows = [r['case'] for r in results if r['mode']=='headless' and
                        (r['windows']['visible_events'] or r['windows']['foreground_events'])]
    inventory_hits = []
    inventory_foreground = []
    from windows_observer import identity
    live_experimental = set()
    for result in results:
        window_observation = json.loads((OUT/result['case']/'windows.json').read_text(encoding='utf8'))
        for process in window_observation['processes']:
            stamp = identity(process['pid'])
            if stamp and stamp['alive'] and stamp['created']==process['created']:
                live_experimental.add(process['pid'])
    for result in results:
        if result['mode'] != 'headless':
            continue
        window_observation = json.loads((OUT/result['case']/'windows.json').read_text(encoding='utf8'))
        if any(w['visible'] for inventory in window_observation['inventories'] for w in inventory['windows']):
            inventory_hits.append(result['case'])
        if any(inventory['foreground_owned'] for inventory in window_observation['inventories']):
            inventory_foreground.append(result['case'])
    audit = dict(files_scanned=len(files),credential_hits=hits,hash_differences=differences,
                 hash_count=len(before['hashes']),listeners_before=before['listeners'],listeners_after=after['listeners'],
                 result_count=len(results),real_call_count=len(real_results),pair_count=len(pairs),
                 repeated_pair_count=sum(len(p['rounds'])==2 for p in pairs),sequential_calls_verified=True,
                 remaining_process_cases=remaining,cleanup_failure_cases=cleanup,
                 live_experimental_pids=sorted(live_experimental),
                 observer_error_cases=observation,headless_window_or_focus_cases=headless_windows,
                 headless_visible_inventory_cases=inventory_hits,
                 headless_foreground_inventory_cases=inventory_foreground)
    (OUT/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(audit,ensure_ascii=False))
    assert not hits and not differences and not remaining and not live_experimental

if __name__=='__main__':
    main()
