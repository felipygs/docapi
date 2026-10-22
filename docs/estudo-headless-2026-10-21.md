# Estudo do Chrome invisível — 21/10/2026

**Conclusão: inviável nas condições testadas.** A classificação descreve esta máquina, estas versões e esta rodada. Não há ativação de headless no produto.

## Estado e método

- Windows; Python `3.14.7`, Playwright `1.64.0`, Chrome `141.0.7390.109`; commit `73581723aea2eb0f4ee5e7745e085477afcfd518` mais as melhorias pendentes registradas no manifesto.
- Período: 2026-10-21T09:37:34.043591-03:00 até 2026-10-21T10:12:13.212201-03:00.
- Uma chamada por vez, controle seguido de headless por rota/CNPJ; subprocessos próprios, porta livre em loopback, nenhum servidor original encontrado nas portas 8000–8010 na referência inicial/final.
- A fábrica original foi reutilizada. Somente no processo experimental: `headless=True`, retirando os argumentos de posição/tamanho de janela. Canal Chrome, demais argumentos, viewport 1280×720, locale pt-BR, scrapers, solver, contratos, prazos e recuperação preservados.
- Cada par afetado foi repetido uma única vez, incluindo controle e invisível. As primeiras rodadas permanecem nos arquivos. Sem solver adicional em DASN/Optantes, sem novas tentativas além das existentes e sem fallback visível.
- Suíte local existente: **150 testes aprovados**, exit code 0, duração de processo 298.38 s (295,535 s reportados pelo unittest). Os quatro testes do instrumento e o ensaio HTTP local também passaram antes das consultas reais.

## Resultado das chamadas reais

Foram executadas **48 chamadas HTTP às rotas experimentais, acessando Receita real**, incluindo repetições: controle {"200": 24}, invisível {"502": 22, "200": 2}. Esses números são status HTTP da API; cada chamada pode abrir mais de uma sessão devido aos módulos e tentativas internas.

| Rota | CNPJ | Rodada | Controle HTTP / duração | Invisível HTTP / duração | Comparação |
| --- | --- | --- | --- | --- | --- |
| `/consultar/cnpj` | `37482317000111` | 1 | 200 / 18.523 s | 200 / 13.552 s | equivalente |
| `/consultar/cnpj` | `00000000000191` | 1 | 200 / 14.602 s | 200 / 15.194 s | equivalente |
| `/consultar/dasn` | `43996591000101` | 1 | 200 / 15.502 s | 502 / 41.449 s | http_or_contract, more_attempts_or_blocks |
| `/consultar/dasn` | `43996591000101` | 2 | 200 / 23.223 s | 502 / 37.075 s | http_or_contract, more_attempts_or_blocks |
| `/consultar/dasn` | `45726608000136` | 1 | 200 / 9.006 s | 502 / 36.194 s | http_or_contract, more_attempts_or_blocks |
| `/consultar/dasn` | `45726608000136` | 2 | 200 / 10.22 s | 502 / 45.913 s | http_or_contract, more_attempts_or_blocks |
| `/consultar/dasn` | `53987789000182` | 1 | 200 / 16.201 s | 502 / 54.599 s | http_or_contract, more_attempts_or_blocks, cleanup_failure |
| `/consultar/dasn` | `53987789000182` | 2 | 200 / 44.767 s | 502 / 84.327 s | http_or_contract, more_attempts_or_blocks |
| `/consultar/dasn` | `57435953000108` | 1 | 200 / 17.587 s | 502 / 58.419 s | http_or_contract, more_attempts_or_blocks |
| `/consultar/dasn` | `57435953000108` | 2 | 200 / 9.428 s | 502 / 45.448 s | http_or_contract, more_attempts_or_blocks |
| `/consultar/dasn` | `12309631000176` | 1 | 200 / 23.901 s | 502 / 53.652 s | http_or_contract, more_attempts_or_blocks |
| `/consultar/dasn` | `12309631000176` | 2 | 200 / 27.015 s | 502 / 38.383 s | http_or_contract, more_attempts_or_blocks |
| `/consultar/optantes` | `43996591000101` | 1 | 200 / 9.438 s | 502 / 29.043 s | http_or_contract, more_attempts_or_blocks |
| `/consultar/optantes` | `43996591000101` | 2 | 200 / 13.91 s | 502 / 53.58 s | http_or_contract, more_attempts_or_blocks |
| `/consultar/optantes` | `45726608000136` | 1 | 200 / 18.669 s | 502 / 42.928 s | http_or_contract, more_attempts_or_blocks |
| `/consultar/optantes` | `45726608000136` | 2 | 200 / 8.087 s | 502 / 40.251 s | http_or_contract, more_attempts_or_blocks |
| `/consultar/optantes` | `53987789000182` | 1 | 200 / 8.558 s | 502 / 34.194 s | http_or_contract, more_attempts_or_blocks |
| `/consultar/optantes` | `53987789000182` | 2 | 200 / 9.461 s | 502 / 31.462 s | http_or_contract, more_attempts_or_blocks |
| `/consultar/optantes` | `57435953000108` | 1 | 200 / 7.805 s | 502 / 31.923 s | http_or_contract, more_attempts_or_blocks |
| `/consultar/optantes` | `57435953000108` | 2 | 200 / 8.849 s | 502 / 38.036 s | http_or_contract, more_attempts_or_blocks |
| `/consultar/optantes` | `12309631000176` | 1 | 200 / 8.902 s | 502 / 29.899 s | http_or_contract, more_attempts_or_blocks |
| `/consultar/optantes` | `12309631000176` | 2 | 200 / 8.848 s | 502 / 24.047 s | http_or_contract, more_attempts_or_blocks |
| `/consultar` | `45726608000136` | 1 | 200 / 35.596 s | 502 / 65.553 s | http_or_contract, more_attempts_or_blocks |
| `/consultar` | `45726608000136` | 2 | 200 / 64.063 s | 502 / 62.925 s | http_or_contract, more_attempts_or_blocks |

`equivalente` significa validação pelos modelos públicos e igualdade dos dados normalizados, ignorando somente os horários `consultado_em`/`optantes_consultado_em` nos locais previstos. `http_or_contract` indica que não foi possível comparar duas respostas de sucesso; `more_attempts_or_blocks` indica mais execuções de módulo ou bloqueios no invisível. Não transformar falha em ausência de dados ou pendências.

Cadastro no braço invisível:

- `00000000000191`: BANCO DO BRASIL SA; capital em centavos `12000000000000`; QSA com 41 integrante(s).
- `37482317000111`: THIARLLES BARBOSA DE SOUSA; capital em centavos `400000`; QSA com 0 integrante(s).

Bloqueios registrados por `codigo=captcha_bloqueado`: controle **6**, invisível **66**. Os logs distinguem tentativa de cada módulo, incluindo Optantes usado para conferir DASN 33001. As durações são observações desta rodada, sem inferência estatística de desempenho.

## Janelas, foco e fechamento

- Observação WinEvent armada antes de lançar cada worker, com message loop dedicado, eventos de criação/exibição/ocultação/destruição e foreground; inventário complementar aproximadamente a cada 100 ms. Eventos iniciais são associados à árvore de PIDs; títulos e conteúdo de aplicações externas não são coletados.
- Ensaio positivo local: controle com 4 eventos de visibilidade e 1 aquisição de foco; headless com zero de ambos. Interação de formulário local retornou o mesmo resultado, locale e viewport nos dois modos.
- Chamadas reais invisíveis: **0 eventos de visibilidade** e **0 aquisições de foreground**. Controle: 191 e 45, respectivamente.
- Conferência complementar dos inventários invisíveis, incluindo ensaio local: 0 casos com janela visível e 0 casos em foreground.
- Erros do observador: 0; casos com falha/intervenção de limpeza: 1; casos com processos restantes após limpeza: 0. Foram identificados 833 PIDs distintos de Chrome/Node nas rodadas reais.
- O caso de limpeza registrado foi `cleanup_timeout` na primeira rodada invisível de DASN para `53987789000182`: o erro principal de captcha foi preservado, o worker saiu normalmente e não houve encerramento forçado. A auditoria final confirmou zero PIDs experimentais ainda vivos, conferindo PID e horário de criação.
- O maior intervalo entre inventários foi 0.7994 s; os eventos WinEvent são complementares ao inventário e foram mantidos ativos durante esse intervalo. Ausência de eventos não é garantia absoluta de flashes que o Windows não notifique. A conclusão de invisibilidade limita-se ao mecanismo e à cobertura registrados, não a uma filmagem da tela.

Referência do mecanismo: [SetWinEventHook](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwineventhook) e [constantes de eventos](https://learn.microsoft.com/en-us/windows/win32/winauto/event-constants).

## Preservação e evidências

- **36 hashes preservados**, sem diferenças de runtime, testes, fixtures ou configurações versionáveis. Nenhum `.env` foi copiado ou alterado, nenhuma dependência foi instalada e nenhum padrão de execução foi modificado.
- Varredura das evidências contra as chaves efetivamente configuradas: 0 ocorrências. Falhas HTTP são armazenadas por status/código controlado; não são salvos detalhes externos brutos, tokens, cookies, payloads do solver ou headers de autenticação.
- Manifestos: [before.json](https://github.com/felipygs/docapi/blob/864491503e8961bd5c2400c9776a6ad943d12e5d/output/estudo-headless/20261021-093707/before.json) e [after.json](https://github.com/felipygs/docapi/blob/864491503e8961bd5c2400c9776a6ad943d12e5d/output/estudo-headless/20261021-093707/after.json); auditoria: [audit.json](https://github.com/felipygs/docapi/blob/864491503e8961bd5c2400c9776a6ad943d12e5d/output/estudo-headless/20261021-093707/audit.json); suíte: [suite.log](https://github.com/felipygs/docapi/blob/864491503e8961bd5c2400c9776a6ad943d12e5d/output/estudo-headless/20261021-093707/suite.log) e [suite-result.json](https://github.com/felipygs/docapi/blob/864491503e8961bd5c2400c9776a6ad943d12e5d/output/estudo-headless/20261021-093707/suite-result.json).
- Instrumento e comandos: [README.md](https://github.com/felipygs/docapi/blob/864491503e8961bd5c2400c9776a6ad943d12e5d/output/estudo-headless/20261021-093707/README.md), [study.py](https://github.com/felipygs/docapi/blob/864491503e8961bd5c2400c9776a6ad943d12e5d/output/estudo-headless/20261021-093707/study.py), [windows_observer.py](https://github.com/felipygs/docapi/blob/864491503e8961bd5c2400c9776a6ad943d12e5d/output/estudo-headless/20261021-093707/windows_observer.py); testes locais: [harness-green.log](https://github.com/felipygs/docapi/blob/864491503e8961bd5c2400c9776a6ad943d12e5d/output/estudo-headless/20261021-093707/harness-green.log) e [smoke-summary.json](https://github.com/felipygs/docapi/blob/864491503e8961bd5c2400c9776a6ad943d12e5d/output/estudo-headless/20261021-093707/smoke-summary.json).
- Comparações: [pairs-cnpj.json](https://github.com/felipygs/docapi/blob/864491503e8961bd5c2400c9776a6ad943d12e5d/output/estudo-headless/20261021-093707/pairs-cnpj.json), [pairs-dasn.json](https://github.com/felipygs/docapi/blob/864491503e8961bd5c2400c9776a6ad943d12e5d/output/estudo-headless/20261021-093707/pairs-dasn.json), [pairs-optantes.json](https://github.com/felipygs/docapi/blob/864491503e8961bd5c2400c9776a6ad943d12e5d/output/estudo-headless/20261021-093707/pairs-optantes.json), [pairs-complete.json](https://github.com/felipygs/docapi/blob/864491503e8961bd5c2400c9776a6ad943d12e5d/output/estudo-headless/20261021-093707/pairs-complete.json). Cada diretório de caso contém `result.json` com resposta validada/métricas, `worker-events.jsonl` com diagnósticos locais e `windows.json` com observação de janelas/processos.

## Recomendação

Manter o modo atual. O bloqueio do braço invisível persistiu na repetição pareada enquanto o controle funcionou, impedindo recomendar sua adoção para todas as consultas. Não ajustar scrapers, solver ou limites para forçar aprovação deste estudo. Qualquer investigação de outra forma de ocultação deve ser uma mudança separada e preservar esta referência.
