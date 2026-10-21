# Tasks

## 1. Referência e preservação do estado

- [x] 1.1 Criar o diretório exclusivo `output/estudo-headless/<data-hora>/` e registrar versões, commit, status Git, hashes dos arquivos de runtime/testes/configurações versionáveis e PID/porta do servidor existente quando encontrado; verificar que o manifesto inclui melhorias pendentes e não contém `.env`, chaves ou tokens.
- [x] 1.2 Executar `.venv/Scripts/python.exe -m unittest discover -s tests -v` sem outros testes de navegador concorrentes, salvar log e código de retorno e conferir contagens de sucesso/falha; se falhar, documentar resultado inconclusivo e encerrar com a preservação prevista em 4.2, sem corrigir o produto.

## 2. Harness e observação descartáveis

- [x] 2.1 Criar no diretório de evidências um harness que inicie Uvicorn em subprocesso/loopback/porta livre, envolva `chromium.launch` só em memória e execute um modo por vez; verificar com página local que controle preserva parâmetros e invisível muda somente `headless` e remove os argumentos de posição/tamanho, mantendo viewport, locale e fechamento originais.
- [x] 2.2 Instrumentar eventos Windows de criação/exibição de janela e foreground antes do lançamento, com atribuição por árvore de PIDs e inventários após abertura/fechamento; verificar em ensaio local que detecta janela do controle, distingue processos externos, cobre o ciclo do invisível e registra lacunas sem capturar títulos/conteúdo de outras aplicações.
- [x] 2.3 Implementar captura de resultados HTTP, validação pelos modelos existentes e comparação que ignore apenas os horários previstos no desenho; verificar com dados locais que uma divergência fiscal permanece detectável, os horários são ignorados e uma falha é registrada sem token ou exceção externa bruta.
- [x] 2.4 Documentar junto ao harness os comandos, modos, matriz, repetição limitada e encerramento seguro; verificar que o ensaio local inicia/encerra apenas seus processos e deixa hashes e PID do servidor original preservados.

## 3. Comparação real sequencial

- [x] 3.1 Executar o par controle/invisível de `/consultar/cnpj` para `37482317000111` e `00000000000191`, um caso por vez; verificar status, `CadastroResponse`, identidade, capital, QSA e evidências de tentativa, duração, janelas/foco e limpeza, usando o solver existente.
- [x] 3.2 Executar pares de `/consultar/dasn` para `43996591000101`, `45726608000136`, `53987789000182`, `57435953000108` e `12309631000176`; verificar os modelos públicos, declarações, baixa/pendências ou conferência 33001 conforme a resposta atual da origem, além das mesmas métricas e evidências por modo.
- [x] 3.3 Executar pares de `/consultar/optantes` para os cinco CNPJs de 3.2; verificar contratos, identidade, situações, históricos, eventos, dados adicionais e ausência explicitamente confirmada, preservando evidências completas de cada modo.
- [x] 3.4 Executar o par de `/consultar` para `45726608000136`, com timeout de cliente compatível com a soma dos módulos; verificar `ConsultaResponse`, os três blocos completos, sequência e ausência de repetição indevida das etapas concluídas, além das métricas de invisibilidade/limpeza.
- [x] 3.5 Repetir uma única vez cada par afetado por falha HTTP, divergência de dados, mais bloqueios/tentativas no invisível ou falha de limpeza; verificar que a repetição contém ambos os modos, mantém a primeira rodada e não altera limites internos nem amplia a matriz.

## 4. Conclusão e encerramento

- [x] 4.1 Consolidar `docs/estudo-headless-<data>.md` com comandos, versões, matriz, durações, tentativas/bloqueios, diferenças, cobertura de janelas/foco, limitações e links às evidências; verificar a classificação pelos critérios do desenho e impedir recomendação de adoção diante de falha, aumento de bloqueios ou resultado inconclusivo.
- [x] 4.2 Encerrar apenas a árvore experimental, revisar evidências para segredos e comparar hashes/status/PID do servidor com o manifesto inicial; verificar que não houve alteração de runtime, configuração ou testes existentes, não restam processos experimentais e nenhuma opção permanente foi ativada.

## Workflow follow-up

- Se o estudo for favorável, propor em outra mudança uma configuração opcional e reversível, inicialmente desativada. Não implementá-la como parte deste estudo.
