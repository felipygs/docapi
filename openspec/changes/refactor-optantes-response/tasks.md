# Tasks

## 1. Evidências e regressão dos históricos

- [x] 1.1 Criar `tests/fixtures/optantes/` com versões offline dos HTMLs de IVANUSA e BARBARA disponíveis nos caminhos de `design.md`, removendo dependências de rede/scripts de extensão e registrando proveniência no comentário de cada fixture; verificar que os conteúdos fiscais e títulos permanecem íntegros e `page.set_content()` não acessa serviços externos.
- [x] 1.2 Criar fixture ELIANE reconstruída do texto e JSON fornecidos, marcada explicitamente sintética, com três períodos somente no Simples, evento futuro de 2027 e SIMEI `Não Existem`; adicionar regressão em `tests/test_optantes_parser.py` e verificar que o extrator atual falha no isolamento antes da correção.
- [x] 1.3 Acrescentar casos sintéticos inversos (Simples vazio/SIMEI preenchido), painéis reordenados e IDs de eventos duplicados, documentados nos próprios testes; verificar que as asserções exigem isolamento completo e preservação de ordem sem depender de captura de portal.

## 2. Contrato e serialização de Optantes

- [x] 2.1 Substituir os modelos de Optantes em `app/models.py` pelo contrato definido em `design.md`, incluindo identificação, horário local, situações, eventos tipados, Transportador e extensões; verificar testes unitários de campos obrigatórios, datas, booleanos e rejeição de string/null como lista de eventos.
- [x] 2.2 Implementar omissão localizada de `campos_adicionais`, `dados_adicionais` e `detalhes` vazios, sem excluir nulls significativos de datas; verificar `model_dump(mode='json')` e serialização do modelo agregado com cenários vazios e preenchidos, usando recurso suportado pela versão efetiva de Pydantic.
- [x] 2.3 Atualizar as descrições e exemplos dos modelos para o novo contrato, incluindo `possui_periodos: false`, listas vazias confirmadas e evento `descricao`/`data_efeito`; verificar schema gerado e exemplo de ELIANE validando pelo novo modelo com `simei.periodos_anteriores: []`.

## 3. Extração delimitada e normalização

- [x] 3.1 Separar aquisição de snapshot DOM e transformação/validação em módulo específico de Optantes e restringir históricos aos intervalos dos respectivos rótulos; verificar que os testes da seção 1 passam e que a tabela de eventos nunca é interpretada como histórico.
- [x] 3.2 Extrair identificação, abrangência, horário e situações integrais com reconhecimento positivo/negativo explícito; verificar testes de CNPJ consultado distinto da matriz, caixa/acentos, SIMEI ativo sintético, ausência de data e texto de situação desconhecido, que deve gerar erro externo.
- [x] 3.3 Extrair eventos por painel e cabeçalhos Descrição do Evento/Data Efeito, com todas as linhas e ordem original; verificar eventos em ambos regimes, múltiplos registros, ausência explícita, data vazia permitida e data não vazia inválida rejeitada, sem modificar utilitários de CNPJ/DASN.
- [x] 3.4 Preservar colunas extras de períodos/eventos como lista de coluna/valor e conteúdo de seções fiscais novas em `dados_adicionais`; verificar casos com cabeçalhos extras repetidos, preservação de todas as células e exclusão de scripts, botões, comentários e conteúdo conhecido já normalizado.
- [x] 3.5 Extrair MEI Transportador como booleano de ausência explícita ou detalhes integrais de conteúdo preenchido, sem inventar um esquema de períodos; verificar fixture vazia real e preenchida sintética com cabeçalhos/linhas preservados, além de mensagem de erro/estado ambíguo que não pode virar true.
- [x] 3.6 Validar cabeçalhos obrigatórios, limites, contagem de células e datas estritamente, com erros que identifiquem seção/campo; verificar 502 esperado na camada de serviço para cabeçalho obrigatório ausente/duplicado, linha malformada e datas inválidas, sem truncamento ou null silencioso.

## 4. Carregamento complementar e integridade

- [x] 4.1 Integrar a nova extração a `consultar_optantes`, aguardando término do carregamento de `AjaxMaisInfo`, lendo `#spnMsgErro` e validando todos os painéis obrigatórios; verificar testes com Ajax simulado de sucesso, erro, timeout, conteúdo já expandido e botão desabilitado sem conteúdo válido.
- [x] 4.2 Manter erro de extração/origem como RuntimeError (502) e timeout como 504, sem ampliar retries ou alterar sessão para contornar captcha; verificar testes de `_safe_call`/rota para cada falha e ausência de HTTP 200 parcial e de segredos nas mensagens.
- [x] 4.3 Garantir que listas vazias resultam apenas de `Não Existem` na seção correta e não de valores padrão; verificar remoção de cada seção obrigatória individualmente e conteúdo vazio pós-Ajax, exigindo erro em vez de falso negativo.

## 5. Publicação do novo contrato e integração

- [x] 5.1 Atualizar `app/api.py` para versão 2.0.0 e documentar a quebra de eventos texto/null para lista, semântica de listas vazias, horário sem fuso e integridade all-or-nothing; verificar `app.openapi()` com novos exemplos e tipos, sem mudar rotas, entrada ou schemas de cadastro/DASN.
- [x] 5.2 Validar respostas HTTP reais do app em ambiente de teste local com serviços externos simulados, usando `unittest` e servidor efêmero/cliente HTTP da biblioteca padrão se não houver cliente de testes instalado; verificar payload e omissão condicional da rota individual e do bloco agregado, sem chamar Receita/captcha nos testes obrigatórios.
- [x] 5.3 Identificar referências aos modelos/campos de Optantes no repositório e atualizar apenas as afetadas pela substituição, registrando a divergência preexistente do CLI sem refatorá-lo integralmente; verificar que não restam consumidores novos de eventos string/null e que CNPJ/DASN mantêm os schemas anteriores.
- [x] 5.4 Executar a suíte completa com `.venv\Scripts\python.exe -m unittest discover -s tests -v` e conferir `git diff --check`; verificar que as regressões do SIMEI e os cenários de eventos/erros passam e registrar claramente qualquer requisito de Chrome/Playwright faltante, sem chamar rede como substituto de teste offline.
- [x] 5.5 Quando a origem estiver disponível, executar smoke test visível de `/consultar/optantes` para ELIANE, IVANUSA e BARBARA, capturando HTML preenchido de ELIANE se possível; verificar três períodos somente no Simples e evento de 2027 no momento da consulta, ou documentar mudanças reais da origem/bloqueio sem tratar dados de 2026 como estado permanente. Essa checagem externa é suplementar e não substitui os testes offline.

## Workflow follow-up

- Revisar o resultado antes de arquivar; o andamento da implementação é registrado nos checkboxes acima.
- Auditoria de consumidores: `OptantesResponse` é compartilhado pelas rotas individual e agregada; não foram encontrados novos consumidores de eventos texto/null. `main.py` já utiliza chaves antigas como `situacao_simples` e `periodos_simples_anteriores`, além de estruturas antigas de cadastro/DASN; esse reparo preexistente do CLI permanece fora do escopo aprovado.
- Verificação final: 83 testes passaram (`unittest discover -s tests -v`), `git diff --check` e `openspec validate refactor-optantes-response --strict` aprovados. Revisão de retorno confirmou as cinco correções com sete reproduções/guards locais aprovados.
- Smoke da versão atual em `http://127.0.0.1:8002`: ELIANE, IVANUSA e BARBARA responderam 200 em 16/10/2026. ELIANE confirmou três históricos apenas no Simples e evento Exclusão de Ofício - Débitos com efeito 2027-01-01; SIMEI vazio. Respostas completas: `C:/Users/Felipe/.cursor/browser-logs/cdp-response-Runtime.evaluate-2026-10-17T02-07-37-010Z.json`. HTML real básico/expandido ELIANE: `C:/Users/Felipe/.cursor/browser-logs/cdp-response-Runtime.evaluate-2026-10-17T02-08-37-611Z.json`. Captura visual: `C:/Users/Felipe/AppData/Local/Temp/cursor/screenshots/page-2026-10-17T02-08-44-760Z.png`. Transportador preenchido continua coberto apenas por cenários sintéticos; contêiner não foi executado.
- Após implementação e revisão, solicitar arquivamento em workflow próprio e verificar a especificação consolidada.
