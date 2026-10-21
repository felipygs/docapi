# Design

## Context

Ver `proposal.md` para a motivação. A decisão do usuário é estudar invisibilidade total no Windows, com consultas sequenciais e validação local mais Receita real, antes de introduzir configuração permanente.

- `app/browser.py` centraliza Chrome via Playwright, com `channel="chrome"`, `headless=False`, viewport 1280×720 e locale `pt-BR`. Fora de Linux, acrescenta posição fora da tela e tamanho de janela 1×1. O fechamento limita a limpeza a cinco segundos.
- `app/consultar.py` importa a fábrica e mantém contextos novos por tentativa, recuperação DASN/Optantes e consulta completa sequencial. O cadastro usa solver e prazo próprio; DASN 33001 exige conferência em Optantes.
- Os testes de aquisição dos três módulos já usam Chrome headless com conteúdo local/interceptado. Isso comprova exercitabilidade local, não aceitação pelos portais reais.
- As homologações de 17/10 e o diagnóstico de 20/10 documentam referências reais. Houve bloqueios recuperados e fechamento lento com navegadores concorrentes; os testes deste estudo não devem concorrer entre si.
- Existem alterações não commitadas, fixtures e evidências anteriores. Usar somente HEAD perderia parte do estado que funciona. A mudança aberta `add-pgmei-das` não participa deste estudo.

## Goals / Non-Goals

**Goals:** comparar modos no mesmo estado de código, distinguir falha externa de diferença observada entre modos e produzir uma conclusão auditável, incluindo o limite da observação de janelas/foco.

**Non-Goals:** instalar dependências, atualizar Chrome/Playwright, modificar arquivos de runtime ou testes existentes, mudar políticas de captcha/recuperação, implantar uma configuração ou garantir equivalência estatística futura.

## Decisions

### 1. Experimento descartável com alteração em memória

Criar o harness e as evidências em `output/estudo-headless/<data-hora>/` e o relatório em `docs/estudo-headless-<data>.md`. Os scripts são instrumentos reproduzíveis do estudo, não parte do produto. A única edição permanente fora das evidências será o relatório.

Executar uma instância experimental de Uvicorn em subprocesso, vinculada somente a loopback e a uma porta livre própria. Importar a aplicação atual do workspace e envolver a chamada a `chromium.launch` apenas nesse processo. Reutilizar a função original `create_browser` e seu fechamento; no braço invisível, substituir `headless` por `True` e retirar somente `--window-position` e `--window-size`. Manter canal, demais argumentos, locale e viewport. No braço de controle, encaminhar todos os parâmetros sem alteração. Registrar os parâmetros efetivos, sem credenciais.

Encerrar cada instância antes de mudar de modo. Não editar `.env`, reutilizar porta/processo do servidor em uso, introduzir fallback visível ou alterar defaults. A alternativa de editar a fábrica e revertê-la depois é rejeitada porque expõe o estado de trabalho e o servidor a uma mudança desnecessária. Usar checkout limpo de HEAD também é rejeitado por excluir melhorias pendentes.

Registrar antes e depois hashes dos arquivos da aplicação, testes, main, dependências e configurações versionáveis, além de status Git e PID/porta do servidor existente quando encontrado. Não copiar `.env` ou segredos para o manifesto. Qualquer alteração concorrente no código invalida a comparação e deve ser registrada, nunca sobrescrita.

### 2. Matriz pareada, HTTP real e execução sequencial

Executar a suíte completa existente com `.venv/Scripts/python.exe -m unittest discover -s tests -v`, salvando saída e código de retorno. Uma falha local preexistente impede conclusão favorável; registrar e encerrar o estudo sem corrigir o produto nesta mudança.

Usar as rotas reais da instância experimental, validando respostas com os modelos públicos existentes. Para cada combinação de rota e CNPJ abaixo, executar primeiro o modo atual e depois o invisível, aguardando encerramento e limpeza antes de prosseguir:

| Rota | CNPJs sem máscara |
| --- | --- |
| `/consultar/cnpj` | `37482317000111`, `00000000000191` |
| `/consultar/dasn` | `43996591000101`, `45726608000136`, `53987789000182`, `57435953000108`, `12309631000176` |
| `/consultar/optantes` | os mesmos cinco CNPJs da linha DASN |
| `/consultar` | `45726608000136` |

São 26 chamadas iniciais, uma por vez, sem alterar tentativas internas. O cliente deve admitir a soma dos prazos existentes de todos os módulos e limpeza, sem encurtar a consulta completa. Reutilizar Receita e solver reais, sem mocks nas chamadas externas; não resolver desafios adicionais em DASN/Optantes.

Comparar estruturas normalizadas pelos mesmos modelos, ignorando somente `consultado_em` e `optantes_consultado_em` nos locais previstos. Conferir identidade, listas e nulabilidade, capital em centavos, QSA, históricos, eventos, baixa/pendência e conferência 33001. Não exigir que a situação fiscal permaneça idêntica à de outubro de uma evidência anterior: comparar os dois modos na rodada atual e registrar mudanças de origem.

Preservar respostas de sucesso e resumos controlados de falha com modo, caso, status HTTP, duração e logs locais de módulo/tentativa/código. Não gravar payloads do solver, headers de autenticação, cookies, tokens ou exceções externas brutas. Os CNPJs dos casos ficam identificados nas evidências do estudo, não são acrescentados aos logs da aplicação.

Repetir o par completo uma única vez se houver falha HTTP, divergência de dados, mais tentativas/bloqueios no braço invisível ou falha de limpeza. Não repetir apenas o invisível nem apagar a primeira rodada. Diferenças de duração são apresentadas por caso e modo, sem inferir desempenho estatístico a partir desta amostra.

### 3. Janelas, foco e processos pertencentes ao experimento

Armar observação de eventos de criação/exibição de janela e troca de foreground do Windows antes de cada lançamento, com horários e PID da janela. Atribuir eventos à árvore de processos do harness experimental, preservando eventos iniciais para associação posterior. Complementar com inventário de janelas e processos após abertura e fechamento. Não usar somente a posição fora da tela ou ausência de screenshot como prova de invisibilidade.

Registrar qualquer janela visível de processo pertencente ao braço invisível, ainda que fora da tela, e qualquer foreground adquirido por esses processos. Não confundir troca de foco feita pelo usuário ou por outra aplicação com interferência do Chrome experimental. Não capturar texto/conteúdo de janelas de outras aplicações.

O observador deve estar ativo desde antes do lançamento até depois da limpeza e registrar sua cobertura e eventuais lacunas. Se a máquina não oferecer observação suficiente de flashes/foco, declarar essa parte inconclusiva; uma amostragem sem eventos não prova ausência absoluta de flashes.

Verificar que os PIDs do experimento terminaram. Em falha, encerrar somente processos comprovadamente pertencentes ao experimento e registrar a intervenção como falha de limpeza. Não matar Chrome globalmente nem tocar no servidor original.

### 4. Conclusão conservadora e evidências completas

Classificar como **viável nos cenários testados** apenas se suíte local passar, todos os casos invisíveis retornarem resultados completos e compatíveis com os controles, sem aumento observado de bloqueios/tentativas, sem falhas de limpeza e com observação de invisibilidade/foco satisfatória.

Classificar como **inviável nas condições testadas** quando um problema do braço invisível persistir na repetição pareada e o controle funcionar. Classificar como **inconclusivo** se ambos falharem, a origem mudar impedindo comparação, houver lacunas de observação ou qualquer divergência permanecer sem explicação. Recuperação posterior não deve ocultar falha da primeira rodada; incerteza sobre regressão impede recomendar adoção.

O relatório deve conter matriz de resultados, falhas inclusive recuperadas, versões, datas, comandos, cobertura de observação, localização das evidências e conclusão com limites. Se viável, recomendar uma mudança futura para configuração opcional inicialmente desativada; não implementá-la nesta mudança. A conclusão não equivale a ausência garantida de bloqueios futuros.

## Risks / Trade-offs

- Portais e solver variam no tempo → controles pareados próximos, repetição limitada e conclusão inconclusiva quando não houver atribuição segura.
- Chamadas de cadastro consomem créditos → limitar à matriz aprovada e à única repetição dos pares afetados; preservar registros das tentativas internas.
- Chrome headless pode receber tratamento diferente da origem → medir sem alterar user agent, solver ou scrapers além do comportamento já existente.
- Observação de eventos pode ter lacunas → registrar cobertura e não declarar invisibilidade comprovada quando faltar evidência.
- Servidor original pode receber tráfego durante o estudo → preservar sua operação, registrar interferência concorrente observada e não atribuir degradação ao modo invisível sem evidência.
- Segredos em falhas externas → usar códigos/mensagens controlados e revisar os arquivos de evidência antes de entregar.

## Migration Plan

Não há migração ou deploy. Ao terminar, encerrar apenas os processos experimentais, confirmar hashes/status preservados fora das evidências e relatório e manter o servidor original em execução. Descartar o experimento significa não incorporá-lo ao runtime; os scripts podem permanecer junto das evidências para reprodução. Nenhum resultado deste estudo ativa o modo invisível no produto.
