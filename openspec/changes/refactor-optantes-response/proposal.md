# Proposal

## Why

A consulta de Optantes devolve eventos futuros como texto tabulado e omite identificação, horário e MEI Transportador; o exemplo fornecido de 43.996.591/0001-01 também evidencia históricos do Simples indevidamente atribuídos ao SIMEI. Precisamos de uma resposta concisa, estruturada e fiel à origem, sem transformar falhas de coleta em ausência de registros.

## What Changes

- **BREAKING**: substituir o contrato atual de `POST /consultar/optantes` e do bloco `optantes` em `POST /consultar`, conforme escolha expressa do usuário; `eventos_futuros` passa de texto/null para lista de objetos com `descricao` e `data_efeito`.
- Incluir identificação do contribuinte, CNPJ consultado versus matriz, data/hora exibida pela Receita e abrangência para todos os estabelecimentos.
- Preservar `optante`/`enquadrado` como booleanos, datas ISO, situações integrais e históricos completos e independentes por regime.
- Corrigir associação de tabelas quando apenas um dos regimes possui histórico, inclusive quando há uma tabela de eventos futuros na mesma página.
- Mapear MEI Transportador sem inventar colunas: ausência explícita como booleano e conteúdo preenchido preservado integralmente enquanto seu formato não está validado.
- Retornar listas vazias apenas para ausência explicitamente confirmada. Se a origem estiver incompleta ou ambígua, falhar com erro externo, sem HTTP 200 enganoso.
- Preservar colunas e seções novas em campos adicionais condicionais, sem repetir HTML bruto ou cabeçalhos já modelados na resposta habitual.
- Documentar a quebra no OpenAPI e cobrir os cenários conhecidos com testes offline e verificação integrada sem dependência obrigatória dos portais.

## Capabilities

### New Capabilities

- `optantes-consulta`: consulta íntegra de identificação, situações, históricos, eventos futuros e MEI Transportador, com contrato estruturado e isolamento entre Simples Nacional e SIMEI.

### Modified Capabilities

Nenhuma especificação existente: `openspec list --specs` não encontrou capacidades neste projeto.

## Impact

- Código afetado futuramente: `app/scrapers/optantes.py`, `app/scrapers/parsers.py` ou módulo de extração dedicado, modelos de Optantes em `app/models.py` e documentação de `app/api.py`.
- `ConsultaResponse.optantes` acompanha o mesmo modelo; nomes das rotas, entrada `cnpj`, contratos cadastral/DASN e sequência da consulta completa não mudam.
- Consumidores devem migrar o campo de eventos; não haverá alias legado, nova rota versionada ou resposta duplicada. A mudança exige identificar e atualizar eventuais referências locais aos modelos alterados.
- Não há testes no repositório nem dependência de testes dedicada em `requirements.txt`; planejar testes com `unittest` e Playwright já existente, sem dependência de runtime nova por princípio.
- Fora do escopo: refatoração geral de CNPJ/DASN, reparo do CLI já defasado em `main.py`, solução ou evasão de captcha, mudanças globais de validação do CNPJ, persistência de dados, PDF e certificação de débitos.
- Esta mudança contém somente planejamento; implementação depende de nova solicitação via apply.
