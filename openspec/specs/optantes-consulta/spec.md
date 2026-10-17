# optantes-consulta Specification

## Purpose

Disponibilizar uma consulta de Optantes fiel à Receita, com identificação, situações atuais, históricos independentes, eventos futuros estruturados e informações de MEI Transportador, sem confundir ausência de registros com falhas de coleta.

## Requirements

### Requirement: Contrato único estruturado de Optantes
O sistema MUST substituir o contrato de `POST /consultar/optantes` e do bloco `optantes` de `POST /consultar` pelo mesmo formato estruturado, mantendo as rotas e a entrada `cnpj`. O sistema MUST usar listas de eventos, sem aliases do texto legado. Contratos de cadastro e DASN MUST permanecer inalterados.

#### Scenario: Resposta individual e bloco agregado equivalentes
- **WHEN** a mesma representação de Optantes é serializada pela consulta individual e pela completa
- **THEN** ambos os pontos de saída expõem o mesmo conjunto de campos, tipos e regras
- **AND** `eventos_futuros` é uma lista, nunca string ou null
- **AND** não há campos de compatibilidade duplicando a resposta anterior

### Requirement: Identificação do contribuinte e abrangência
O sistema MUST retornar `cnpj_consultado`, `cnpj_matriz`, `nome_empresarial` e `abrange_todos_estabelecimentos`, usando CNPJs com 14 dígitos. O booleano de abrangência MUST refletir a nota da origem; informação ambígua ou ausente MUST NOT ser convertida silenciosamente em false.

#### Scenario: Consulta de estabelecimento e identificação da matriz
- **WHEN** a entrada é um CNPJ válido e a origem informa identificação da matriz e nota de abrangência
- **THEN** `cnpj_consultado` corresponde à entrada sem máscara
- **AND** `cnpj_matriz` e `nome_empresarial` correspondem à origem, mesmo que os dois CNPJs sejam diferentes
- **AND** `abrange_todos_estabelecimentos` é true para a nota conhecida de abrangência integral

### Requirement: Horário da consulta sem fuso inventado
O sistema MUST retornar `consultado_em` como data/hora local ISO 8601 derivada de Data da consulta. O sistema MUST NOT substituir esse horário pelo relógio do coletor nem adicionar fuso que a origem não informa.

#### Scenario: Horário fornecido para ELIANE
- **WHEN** a origem exibe `15/10/2026 18:08:45`
- **THEN** `consultado_em` é `2026-10-15T18:08:45`, sem Z ou offset presumido

### Requirement: Situação atual independente dos eventos futuros
Cada regime MUST expor `situacao` integral, `data_desde` e o booleano atual (`optante` no Simples, `enquadrado` no SIMEI). O sistema MUST reconhecer explicitamente situações positivas e negativas; texto desconhecido MUST resultar em erro externo, nunca false presumido. Eventos futuros MUST NOT alterar o enquadramento atual retornado.

#### Scenario: Optante com exclusão futura
- **WHEN** a origem informa Simples optante desde 01/01/2026 e exclusão com efeito em 01/01/2027
- **THEN** `simples_nacional.optante` é true e `data_desde` é `2026-01-01`
- **AND** a exclusão aparece exclusivamente na lista de eventos futuros desse regime

#### Scenario: SIMEI não enquadrado
- **WHEN** a situação é `NÃO enquadrado no SIMEI`, sem data
- **THEN** `simei.enquadrado` é false, `data_desde` é null e `situacao` preserva o texto

### Requirement: Históricos separados por regime e completos
Cada regime MUST retornar `periodos_anteriores` com todas as linhas na ordem da origem e os campos `data_inicial`, `data_final` e `detalhamento`. O sistema MUST vincular cada histórico ao respectivo rótulo, nunca copiar registros de outro regime ou de uma tabela de eventos. Períodos consecutivos MUST NOT ser fundidos.

#### Scenario: Três períodos do Simples e nenhum no SIMEI
- **WHEN** a origem de ELIANE informa períodos do Simples 01/01/2025–31/12/2025, 01/01/2024–31/12/2024 e 25/10/2021–31/12/2023 e SIMEI `Não Existem`
- **THEN** o Simples contém exatamente as três linhas, em datas ISO e com seus detalhamentos completos
- **AND** `simei.periodos_anteriores` é `[]`, inclusive quando existe uma tabela de eventos futuros na página

#### Scenario: Históricos nos dois regimes
- **WHEN** a origem possui uma tabela de histórico do Simples e outra do SIMEI
- **THEN** cada lista contém somente as linhas da sua seção, sem omissões nem duplicação cruzada

### Requirement: Eventos futuros com descrição e data de efeito
Cada regime MUST retornar `eventos_futuros` como lista de objetos contendo `descricao` integral e `data_efeito` ISO, obtidos de Descrição do Evento e Data Efeito. O sistema MUST preservar todas as linhas na ordem da origem, sem deduplicar nem transformar os cabeçalhos em registros. Falhas de interpretação MUST NOT apagar eventos.

#### Scenario: Exclusão por débitos informada para 2027
- **WHEN** a origem mostra `Exclusão de Ofício - Débitos` com Data Efeito `01/01/2027` no Simples
- **THEN** `simples_nacional.eventos_futuros` contém `{"descricao":"Exclusão de Ofício - Débitos","data_efeito":"2027-01-01"}`
- **AND** o registro não infere valor, exigibilidade ou regularização de débitos

#### Scenario: Eventos independentes em ambos os regimes
- **WHEN** existem múltiplos eventos no Simples e eventos no SIMEI
- **THEN** todas as linhas são retornadas somente no regime correspondente, independentemente da ordem dos painéis ou de IDs repetidos

### Requirement: Ausência confirmada em listas vazias
O sistema MUST retornar `[]` para históricos e eventos somente quando a respectiva seção declarar explicitamente ausência de registros. Listas vazias MUST NOT representar erro, seção ausente ou conteúdo ainda não carregado. O sistema MUST NOT acrescentar booleanos redundantes de existência às listas.

#### Scenario: Não existem eventos futuros no SIMEI
- **WHEN** o painel de eventos futuros do SIMEI foi carregado e exibe `Não Existem`
- **THEN** `simei.eventos_futuros` é `[]`, não null e não false

#### Scenario: Carregamento complementar incompleto
- **WHEN** históricos carregaram mas o painel de eventos de um regime está ausente ou vazio sem declaração de ausência
- **THEN** não é emitida resposta de sucesso com eventos vazios

### Requirement: MEI Transportador sem inferências sobre formato desconhecido
O sistema MUST retornar `mei_transportador.possui_periodos` como booleano. Ausência explícita MUST produzir false e omitir `detalhes`. Conteúdo preenchido reconhecido MUST produzir true e `detalhes` com texto integral e todas as tabelas (`cabecalhos`, `linhas`), sem presumir colunas ainda não observadas. Mensagem de erro MUST NOT ser classificada como período.

#### Scenario: Não existem períodos de Transportador
- **WHEN** a seção carregada de MEI Transportador informa `Não Existem`
- **THEN** `mei_transportador` é `{"possui_periodos":false}`

#### Scenario: Conteúdo preenchido com colunas ainda não normalizadas
- **WHEN** a seção apresenta registros válidos de MEI Transportador
- **THEN** `possui_periodos` é true e `detalhes` preserva todos os textos, cabeçalhos e células na ordem da origem
- **AND** nenhuma data, tipo de período ou condição de enquadramento é inventada

### Requirement: Preservação de dados adicionais sem duplicação habitual
O sistema MUST preservar colunas adicionais de períodos e eventos em `campos_adicionais` (lista de `coluna` e `valor`) e seções fiscais desconhecidas em `dados_adicionais` (lista de `secao`, `texto` e `tabelas`). Esses campos MUST ser omitidos quando vazios. Conteúdo já normalizado MUST NOT ser repetido como tabela bruta em registros conhecidos.

#### Scenario: Coluna nova em evento conhecido
- **WHEN** um evento possui as duas colunas esperadas e outra coluna com informação adicional
- **THEN** descrição e data são normalizadas e a coluna adicional é preservada em `campos_adicionais`, inclusive seu rótulo e valor

#### Scenario: Nova seção fiscal complementar
- **WHEN** a origem apresenta uma seção de resultado não modelada além de todas as seções obrigatórias válidas
- **THEN** `dados_adicionais` preserva título, texto e todas as tabelas dessa seção
- **AND** comentários HTML, controles de navegação e scripts não são tratados como resultado fiscal

### Requirement: Falhas externas não produzem falso sucesso
O sistema MUST emitir HTTP 502 para erro complementar, seção obrigatória ausente, situação desconhecida ou tabela obrigatória ambígua; timeout externo MUST produzir HTTP 504. A resposta de erro MUST identificar a seção e a causa, sem cookies ou tokens. O sistema MUST NOT devolver HTTP 200 parcial ou booleanos false por falha de extração.

#### Scenario: Erro ao carregar Mais informações
- **WHEN** a origem informa falha no carregamento complementar
- **THEN** a API responde 502 com `detail` identificando Optantes e a etapa complementar

#### Scenario: Data não vazia inválida em evento
- **WHEN** a coluna Data Efeito contém um valor não vazio que não pode ser interpretado como data
- **THEN** a API responde 502 identificando eventos futuros do respectivo regime, em vez de descartar a linha ou converter o valor para null

#### Scenario: Timeout externo
- **WHEN** expira o prazo de navegação ou carregamento da consulta
- **THEN** a API responde 504 e não representa o timeout como ausência de registros

### Requirement: Alertas e normalização preservam significado
O sistema MUST manter `alertas` como lista de mensagens visíveis distintas e preservar os textos integrais de situações, descrições e detalhamentos. Datas civis MUST usar YYYY-MM-DD. Datas opcionais explicitamente ausentes MUST usar null; valores não vazios inválidos MUST produzir erro externo. Espaços de layout não significativos podem ser normalizados sem remover conteúdo.

#### Scenario: Resultado sem alertas
- **WHEN** todas as seções foram consultadas e não existem alertas visíveis
- **THEN** `alertas` é `[]` e as descrições completas permanecem disponíveis em seus campos

### Requirement: OpenAPI declara a migração de contrato
A documentação pública MUST descrever a quebra de compatibilidade, campos, tipos, nulabilidade, ausência confirmada e erros do novo contrato. O sistema MUST atualizar a versão declarada da API para 2.0.0 e incluir exemplos com evento futuro e SIMEI sem histórico, sem modificar os esquemas cadastral e DASN.

#### Scenario: Consumidor consulta o contrato publicado
- **WHEN** um consumidor acessa o OpenAPI após a implantação
- **THEN** encontra eventos como arrays tipados, MEI Transportador e identificação, versão 2.0.0 e aviso de substituição de texto/null por lista
- **AND** o esquema agregado referencia o mesmo contrato de Optantes usado pela rota individual
