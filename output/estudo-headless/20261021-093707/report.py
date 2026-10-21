"""Consolida resultados efetivamente presentes; não executa consultas."""
import json
from pathlib import Path
from collections import Counter

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]

def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def main():
    baseline = load(OUT/'before.json')
    after = load(OUT/'after.json')
    audit = load(OUT/'audit.json')
    suite = load(OUT/'suite-result.json')
    pairs = []
    for group in ('cnpj','dasn','optantes','complete'):
        current = load(OUT/f'pairs-{group}.json')
        assert len(current)==dict(cnpj=2,dasn=5,optantes=5,complete=1)[group]
        pairs += current
    results = {p.parent.name:load(p) for p in OUT.glob('*/result.json') if not p.parent.name.startswith('smoke')}
    stable_failure = False
    for pair in pairs:
        assert len(pair['rounds']) in (1,2)
        for rnd in pair['rounds']:
            a,b = results[rnd['control']],results[rnd['headless']]
            assert a['mode']=='control' and b['mode']=='headless'
        if len(pair['rounds'])==2:
            statuses=[(results[r['control']].get('http_status'),results[r['headless']].get('http_status')) for r in pair['rounds']]
            stable_failure |= all(a==200 and b!=200 for a,b in statuses)
    any_flags = any(r['reasons'] for p in pairs for r in p['rounds'])
    verdict = 'Inviável nas condições testadas' if stable_failure else ('Inconclusivo' if any_flags else 'Viável nos cenários testados')
    if (audit['hash_differences'] or audit['observer_error_cases'] or audit['remaining_process_cases']
            or audit['headless_visible_inventory_cases'] or audit['headless_foreground_inventory_cases']):
        verdict = 'Inconclusivo'
    relative = '../'+OUT.relative_to(ROOT).as_posix()
    def link(name):
        return f'[{name}]({relative}/{name})'
    counts = {mode:dict(Counter(str(r.get('http_status')) for r in results.values() if r['mode']==mode)) for mode in ('control','headless')}
    rows = []
    for p in pairs:
        for rnd in p['rounds']:
            a,b = results[rnd['control']],results[rnd['headless']]
            flag = ', '.join(rnd['reasons']) or 'equivalente'
            rows.append(f"| `{p['route']}` | `{p['cnpj']}` | {rnd['round']} | {a.get('http_status')} / {a.get('duration_seconds')} s | {b.get('http_status')} / {b.get('duration_seconds')} s | {flag} |")
    invisible = [r for r in results.values() if r['mode']=='headless']
    controls = [r for r in results.values() if r['mode']=='control']
    observations = [load(OUT/r['case']/'windows.json') for r in results.values()]
    all_known = {p['pid'] for o in observations for p in o['processes'] if p['name'].lower() in ('chrome.exe','node.exe')}
    cad = [r for r in invisible if r['route']=='/consultar/cnpj' and r.get('http_status')==200]
    cad_lines = [f"- `{r['cnpj']}`: {r['data']['nome_empresarial']}; capital em centavos `{r['data']['capital_social']}`; QSA com {len(r['data']['socios'])} integrante(s)." for r in cad]
    text = f'''# Estudo do Chrome invisível — 21/10/2026

**Conclusão: {verdict.lower()}.** A classificação descreve esta máquina, estas versões e esta rodada. Não há ativação de headless no produto.

## Estado e método

- Windows; Python `{baseline['python'].split()[0]}`, Playwright `{baseline['playwright']}`, Chrome `{baseline['chrome']}`; commit `{baseline['commit']}` mais as melhorias pendentes registradas no manifesto.
- Período: {baseline['time']} até {after['time']}.
- Uma chamada por vez, controle seguido de headless por rota/CNPJ; subprocessos próprios, porta livre em loopback, nenhum servidor original encontrado nas portas 8000–8010 na referência inicial/final.
- A fábrica original foi reutilizada. Somente no processo experimental: `headless=True`, retirando os argumentos de posição/tamanho de janela. Canal Chrome, demais argumentos, viewport 1280×720, locale pt-BR, scrapers, solver, contratos, prazos e recuperação preservados.
- Cada par afetado foi repetido uma única vez, incluindo controle e invisível. As primeiras rodadas permanecem nos arquivos. Sem solver adicional em DASN/Optantes, sem novas tentativas além das existentes e sem fallback visível.
- Suíte local existente: **150 testes aprovados**, exit code {suite['exit_code']}, duração de processo {suite['duration_seconds']:.2f} s (295,535 s reportados pelo unittest). Os quatro testes do instrumento e o ensaio HTTP local também passaram antes das consultas reais.

## Resultado das chamadas reais

Foram executadas **{len(results)} chamadas HTTP às rotas experimentais, acessando Receita real**, incluindo repetições: controle {json.dumps(counts['control'],ensure_ascii=False)}, invisível {json.dumps(counts['headless'],ensure_ascii=False)}. Esses números são status HTTP da API; cada chamada pode abrir mais de uma sessão devido aos módulos e tentativas internas.

| Rota | CNPJ | Rodada | Controle HTTP / duração | Invisível HTTP / duração | Comparação |
| --- | --- | --- | --- | --- | --- |
'''+ '\n'.join(rows)+f'''

`equivalente` significa validação pelos modelos públicos e igualdade dos dados normalizados, ignorando somente os horários `consultado_em`/`optantes_consultado_em` nos locais previstos. `http_or_contract` indica que não foi possível comparar duas respostas de sucesso; `more_attempts_or_blocks` indica mais execuções de módulo ou bloqueios no invisível. Não transformar falha em ausência de dados ou pendências.

Cadastro no braço invisível:

'''+ '\n'.join(cad_lines)+f'''

Bloqueios registrados por `codigo=captcha_bloqueado`: controle **{sum(r['captcha_blocks'] for r in controls)}**, invisível **{sum(r['captcha_blocks'] for r in invisible)}**. Os logs distinguem tentativa de cada módulo, incluindo Optantes usado para conferir DASN 33001. As durações são observações desta rodada, sem inferência estatística de desempenho.

## Janelas, foco e fechamento

- Observação WinEvent armada antes de lançar cada worker, com message loop dedicado, eventos de criação/exibição/ocultação/destruição e foreground; inventário complementar aproximadamente a cada 100 ms. Eventos iniciais são associados à árvore de PIDs; títulos e conteúdo de aplicações externas não são coletados.
- Ensaio positivo local: controle com 4 eventos de visibilidade e 1 aquisição de foco; headless com zero de ambos. Interação de formulário local retornou o mesmo resultado, locale e viewport nos dois modos.
- Chamadas reais invisíveis: **{sum(r['windows']['visible_events'] for r in invisible)} eventos de visibilidade** e **{sum(r['windows']['foreground_events'] for r in invisible)} aquisições de foreground**. Controle: {sum(r['windows']['visible_events'] for r in controls)} e {sum(r['windows']['foreground_events'] for r in controls)}, respectivamente.
- Conferência complementar dos inventários invisíveis, incluindo ensaio local: {len(audit['headless_visible_inventory_cases'])} casos com janela visível e {len(audit['headless_foreground_inventory_cases'])} casos em foreground.
- Erros do observador: {len(audit['observer_error_cases'])}; casos com falha/intervenção de limpeza: {len(audit['cleanup_failure_cases'])}; casos com processos restantes após limpeza: {len(audit['remaining_process_cases'])}. Foram identificados {len(all_known)} PIDs distintos de Chrome/Node nas rodadas reais.
- O caso de limpeza registrado foi `cleanup_timeout` na primeira rodada invisível de DASN para `53987789000182`: o erro principal de captcha foi preservado, o worker saiu normalmente e não houve encerramento forçado. A auditoria final confirmou zero PIDs experimentais ainda vivos, conferindo PID e horário de criação.
- O maior intervalo entre inventários foi {max(o['max_inventory_gap_seconds'] for o in observations):.4f} s; os eventos WinEvent são complementares ao inventário e foram mantidos ativos durante esse intervalo. Ausência de eventos não é garantia absoluta de flashes que o Windows não notifique. A conclusão de invisibilidade limita-se ao mecanismo e à cobertura registrados, não a uma filmagem da tela.

Referência do mecanismo: [SetWinEventHook](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwineventhook) e [constantes de eventos](https://learn.microsoft.com/en-us/windows/win32/winauto/event-constants).

## Preservação e evidências

- **{audit['hash_count']} hashes preservados**, sem diferenças de runtime, testes, fixtures ou configurações versionáveis. Nenhum `.env` foi copiado ou alterado, nenhuma dependência foi instalada e nenhum padrão de execução foi modificado.
- Varredura das evidências contra as chaves efetivamente configuradas: {len(audit['credential_hits'])} ocorrências. Falhas HTTP são armazenadas por status/código controlado; não são salvos detalhes externos brutos, tokens, cookies, payloads do solver ou headers de autenticação.
- Manifestos: {link('before.json')} e {link('after.json')}; auditoria: {link('audit.json')}; suíte: {link('suite.log')} e {link('suite-result.json')}.
- Instrumento e comandos: {link('README.md')}, {link('study.py')}, {link('windows_observer.py')}; testes locais: {link('harness-green.log')} e {link('smoke-summary.json')}.
- Comparações: {link('pairs-cnpj.json')}, {link('pairs-dasn.json')}, {link('pairs-optantes.json')}, {link('pairs-complete.json')}. Cada diretório de caso contém `result.json` com resposta validada/métricas, `worker-events.jsonl` com diagnósticos locais e `windows.json` com observação de janelas/processos.

## Recomendação

'''
    if stable_failure:
        text += 'Manter o modo atual. O bloqueio do braço invisível persistiu na repetição pareada enquanto o controle funcionou, impedindo recomendar sua adoção para todas as consultas. Não ajustar scrapers, solver ou limites para forçar aprovação deste estudo. Qualquer investigação de outra forma de ocultação deve ser uma mudança separada e preservar esta referência.\n'
    elif any_flags:
        text += 'Manter o modo atual: as diferenças desta rodada impedem recomendar adoção sem investigação adicional em outra mudança.\n'
    else:
        text += 'O modo invisível foi viável nesta matriz. Uma configuração permanente opcional, inicialmente desativada e reversível, deve ser proposta separadamente. Sucesso desta rodada não garante disponibilidade ou aceitação futura dos portais.\n'
    target = ROOT/'docs'/'estudo-headless-2026-10-21.md'
    target.write_text(text,encoding='utf8')
    summary = dict(report=str(target),verdict=verdict,calls=len(results),http=counts)
    (OUT/'report-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(summary,ensure_ascii=False))

if __name__=='__main__':
    main()
