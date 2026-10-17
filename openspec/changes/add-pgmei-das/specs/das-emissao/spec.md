# Spec Delta

## Purpose

Permitir a emissão seletiva de DAS mensais no PGMEI e a entrega dos documentos originais em Base64, preservando resultados por competência e impedindo reenvio automático quando uma apuração pode já ter sido realizada.

## ADDED Requirements

### Requirement: Entrada explícita de emissão
O sistema MUST oferecer `POST /emitir/das` com `cnpj`, lista não vazia `competencias` em `YYYY-MM` e `data_pagamento` opcional em `YYYY-MM-DD`. Competências MUST ser normalizadas, deduplicadas e ordenadas antes do processamento. Entrada inválida MUST ser rejeitada antes de acessar o portal.

#### Scenario: Competências repetidas e anos distintos
- **WHEN** a entrada informa `2025-03`, `2024-01` e novamente `2025-03`
- **THEN** são processadas exatamente `2024-01` e `2025-03`, uma vez cada

#### Scenario: Entrada de competência ou data inválida
- **WHEN** a lista está vazia, contém mês fora de 01 a 12 ou a data informada não é uma data civil ISO válida
- **THEN** a API responde HTTP 422 sem iniciar navegação ou emissão

### Requirement: Conferência de identidade e elegibilidade
O sistema MUST conferir a identidade exibida pela origem e a disponibilidade de cada competência antes do envio. Períodos não oferecidos ou desabilitados MUST receber resultado explícito de indisponibilidade, sem serem substituídos por outros períodos. Dados de identidade ausente ou divergente MUST impedir o envio na sessão afetada.

#### Scenario: Mistura de competências disponíveis e indisponíveis
- **WHEN** um mês solicitado está habilitado e outro está desabilitado ou ausente
- **THEN** somente o mês habilitado pode ser enviado
- **AND** o outro recebe resultado com motivo de indisponibilidade, sem alegação de pagamento

#### Scenario: Identidade divergente antes da geração
- **WHEN** a origem identifica um CNPJ diferente do solicitado
- **THEN** nenhuma apuração é enviada nessa sessão
- **AND** a inconsistência não é repetida automaticamente como falha transitória

### Requirement: Seleção exata e emissão mensal
O sistema MUST gerar DAS mensais apenas para as competências explícitas da requisição, agrupadas pelo ano da origem. O sistema MUST NOT acionar Selecionar Todos nem emissão consolidada. A seleção final MUST ser conferida antes de enviar a apuração.

#### Scenario: Tela com doze meses disponíveis
- **WHEN** o cliente solicita apenas janeiro e março de um ano
- **THEN** somente esses dois meses são selecionados e enviados
- **AND** os demais dez meses não são incluídos mesmo que a tela os apresente previamente selecionados

### Requirement: Data de pagamento e valores da origem
Quando `data_pagamento` for informada, o sistema MUST aplicá-la e aguardar a atualização dos valores pelo portal antes da geração. Quando omitida, MUST manter a data sugerida pela origem. O sistema MUST retornar a data efetivamente utilizada quando disponível e MUST NOT recalcular tributos, multa ou juros localmente.

#### Scenario: Data de pagamento informada
- **WHEN** o cliente informa uma data aceita pelo portal
- **THEN** a geração usa os valores atualizados pela Receita para essa data
- **AND** a resposta identifica a data efetivamente utilizada

#### Scenario: Data omitida ou rejeitada pela origem
- **WHEN** nenhuma data é informada
- **THEN** a automação preserva a sugestão do portal sem impor a data do relógio local
- **AND** uma data explícita rejeitada pelo portal produz falha antes do envio, sem substituição silenciosa

### Requirement: Preservação de informações previdenciárias e alertas
O sistema MUST preservar as marcações de benefício previdenciário apresentadas pela origem e registrar os avisos relevantes do processamento. O sistema MUST NOT alterar essas marcações nem iniciar pagamento como efeito da emissão de DAS.

#### Scenario: Benefício previamente marcado
- **WHEN** uma competência solicitada apresenta benefício previdenciário marcado
- **THEN** a geração mantém essa informação e os cálculos da origem
- **AND** a automação não marca ou desmarca benefício de nenhum outro período

#### Scenario: Aviso informativo de dívida ativa
- **WHEN** um aviso informativo antecede a seleção dos períodos
- **THEN** a resposta preserva a mensagem
- **AND** fechar o aviso não transforma competências indisponíveis em elegíveis

### Requirement: Confirmação individual de geração
O sistema MUST confirmar a geração por competência nos resultados da origem, preservando números de apuração, números de DAS, valores e datas disponíveis. Um clique ou toast genérico de sucesso MUST NOT bastar como confirmação de todas as competências enviadas.

#### Scenario: Resultado com parte das competências enviadas
- **WHEN** a origem confirma uma competência, mas omite outra incluída no envio
- **THEN** somente a primeira é marcada como gerada
- **AND** a outra permanece com resultado indeterminado, sem reenvio automático

### Requirement: Entrega dos PDFs originais em Base64
O sistema MUST retornar os PDFs originais obtidos da origem como arquivos com nome, tipo `application/pdf`, competências abrangidas e `conteudo_base64`. Um arquivo MUST poder representar várias guias mensais. Conteúdo não PDF MUST NOT ser entregue como documento válido.

#### Scenario: PDF único contendo várias guias mensais
- **WHEN** a origem fornece um PDF com os DAS de janeiro e março selecionados
- **THEN** a resposta entrega um arquivo associado às duas competências
- **AND** a decodificação Base64 reproduz os mesmos bytes do arquivo recebido

#### Scenario: Sessão expirada no lugar do documento
- **WHEN** a tentativa de obter o PDF devolve HTML de identificação ou mensagem de erro
- **THEN** o conteúdo não é publicado como PDF nem convertido em PDF local
- **AND** a falha de obtenção do documento é indicada nas competências afetadas

### Requirement: Recuperação antes do envio
Antes de enviar uma apuração, o sistema MUST reutilizar o limite de três tentativas em sessões independentes, com pausas de 2 e 5 segundos e prazo global de 180 segundos compartilhado pela requisição. Somente falhas transitórias reconhecidas e bloqueio Captcha MUST permitir repetição; resultados anteriores MUST ser preservados.

#### Scenario: Falha ao preparar o segundo ano
- **WHEN** o primeiro ano já teve geração confirmada e o segundo falha antes do envio
- **THEN** a recuperação mantém os resultados do primeiro ano e retoma apenas o trabalho pendente
- **AND** o primeiro ano não é emitido novamente

### Requirement: Resultado indeterminado sem reenvio
Depois que o envio puder ter ocorrido, uma falha sem confirmação MUST produzir resultado explícito `indeterminado` para as competências afetadas. O sistema MUST NOT reenviar essas competências automaticamente, inclusive após timeout, nova sessão ou recuperação de outro ano.

#### Scenario: Timeout após envio da apuração
- **WHEN** o envio foi iniciado e a confirmação não chega antes da falha
- **THEN** as competências sem confirmação são registradas como indeterminadas
- **AND** nenhuma tentativa posterior da mesma requisição as reenvia
- **AND** a resposta esclarece que a emissão pode ter ocorrido e exige conferência antes de nova solicitação

### Requirement: Geração confirmada preservada sem PDF
Se a geração estiver confirmada e apenas a obtenção do PDF falhar, o sistema MUST preservar a confirmação e os identificadores recebidos. O resultado MUST indicar `gerado_sem_pdf`; nova tentativa de obtenção do arquivo MUST NOT executar novamente a apuração.

#### Scenario: Documento indisponível após geração confirmada
- **WHEN** o número do DAS foi obtido, mas o download falha
- **THEN** a competência permanece identificada como gerada, com erro específico do PDF
- **AND** a resposta não inclui um arquivo vazio nem desfaz a confirmação da geração

### Requirement: Respostas parciais e falhas totais
O sistema MUST preservar resultados úteis e falhas por competência, com status global explícito. HTTP 200 parcial MUST identificar itens indisponíveis, não processados, indeterminados ou sem PDF. Sem resultado utilizável, a API MUST retornar 502 para falha externa ou 504 para timeout, sem representar a emissão como concluída.

#### Scenario: Geração parcial entre dois anos
- **WHEN** um ano produziu dados e PDFs e outro falhou
- **THEN** a API retorna HTTP 200 parcial com documentos preservados e falhas associadas aos períodos afetados

#### Scenario: Envio indeterminado é informação operacional utilizável
- **WHEN** houve possível envio, mas nenhuma geração pôde ser confirmada
- **THEN** a API retorna HTTP 200 parcial com os resultados indeterminados explícitos e nenhum PDF inventado
- **AND** o status não declara emissão concluída

#### Scenario: Falha integral anterior ao envio
- **WHEN** o portal impede todo o acesso e nenhum resultado por competência foi obtido
- **THEN** a API retorna 502 ou 504 conforme a natureza da falha
- **AND** não retorna uma lista vazia como sucesso de emissão

### Requirement: Cancelamento e descarte de arquivos
O sistema MUST liberar sessões e arquivos temporários em sucesso, erro e cancelamento. Cancelamento MUST NOT iniciar nova emissão. Os arquivos MUST ser transferidos para a resposta antes do descarte e MUST NOT depender de URLs da sessão do navegador ou de armazenamento permanente.

#### Scenario: Resposta concluída e sessão encerrada
- **WHEN** o navegador é fechado após a emissão
- **THEN** os PDFs em Base64 da resposta continuam íntegros e utilizáveis
- **AND** os arquivos temporários da operação são descartados

#### Scenario: Cliente cancela durante a emissão
- **WHEN** a requisição é cancelada antes ou depois de iniciar o envio
- **THEN** o navegador é encerrado e não ocorre reenvio automático
- **AND** o servidor não registra o cancelamento como confirmação de geração ou de ausência de geração
