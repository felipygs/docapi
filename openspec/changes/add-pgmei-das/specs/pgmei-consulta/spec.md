# Spec Delta

## Purpose

Disponibilizar os dados de todos os anos oferecidos pelo PGMEI, preservando a identificação do contribuinte e distinguindo períodos consultados de falhas ou dados indisponíveis, sem realizar apuração durante a consulta.

## ADDED Requirements

### Requirement: Consulta de todos os anos disponíveis
O sistema MUST oferecer `POST /consultar/pgmei` com entrada `cnpj`, aceitando o formato com ou sem máscara já adotado pela API. O sistema MUST descobrir os anos disponibilizados pela origem e processá-los sequencialmente, sem presumir um intervalo fixo de anos.

#### Scenario: Consulta de contribuinte com vários anos
- **WHEN** a origem oferece os anos 2023, 2024 e 2026
- **THEN** a resposta identifica esses três anos e o resultado individual de cada um
- **AND** não inventa registros de 2025 nem limita a consulta ao ano corrente

#### Scenario: Entrada rejeitada antes de navegar
- **WHEN** o CNPJ não atende à validação de entrada vigente
- **THEN** a requisição é rejeitada sem consultar a Receita
- **AND** o comportamento de validação das rotas existentes permanece inalterado

### Requirement: Identificação independente da entrada
O sistema MUST retornar CNPJ normalizado e nome empresarial extraídos da identificação da origem. O CNPJ identificado MUST corresponder ao solicitado. O campo preenchido pelo cliente MUST NOT ser usado como confirmação de identidade; ausência ou divergência de identificação MUST impedir a aceitação dos dados afetados.

#### Scenario: Identificação confirmada
- **WHEN** a origem identifica o CNPJ solicitado e seu nome empresarial
- **THEN** a resposta contém o CNPJ com 14 dígitos e o nome integral

#### Scenario: Identidade ausente ou divergente
- **WHEN** a página não identifica o contribuinte ou identifica outro CNPJ
- **THEN** os dados dessa página não são aceitos como resultado do CNPJ solicitado
- **AND** a falha é definitiva para a sessão, sem repetição automática dessa inconsistência

### Requirement: Dados e disponibilidade por competência
O sistema MUST retornar, para cada período apresentado, competência `YYYY-MM`, situação integral e indicação explícita de disponibilidade de emissão. O sistema MUST preservar apuração, benefício previdenciário, valores e datas quando informados pela origem, sem deduzir pagamento ou quitação pela possibilidade de seleção.

#### Scenario: Situações diferentes no mesmo ano
- **WHEN** o portal apresenta períodos pagos, devedores, a vencer e desabilitados
- **THEN** cada período preserva sua situação e disponibilidade própria
- **AND** um período desabilitado não é automaticamente classificado como pago

#### Scenario: Valores e datas disponíveis
- **WHEN** uma competência informa principal, multa, juros, total, vencimento e acolhimento
- **THEN** os valores monetários são representados em centavos e as datas em ISO
- **AND** os valores são os calculados pela origem, sem recálculo local de tributos

### Requirement: Ausência de dados sem falsa ausência de débitos
Dados não obtidos MUST ser representados como indisponíveis, com erro ou motivo associado. Valores ausentes MUST NOT virar zero, e competências não coletadas MUST NOT virar listas vazias de sucesso. Conteúdo preenchido com valor ou data inválidos MUST ser tratado como falha de integridade.

#### Scenario: Ano com falha de leitura
- **WHEN** um ano foi descoberto, mas sua tabela não pôde ser lida integralmente
- **THEN** o ano aparece com estado de falha e competências indisponíveis
- **AND** não aparece como ano consultado sem débitos

#### Scenario: Valor preenchido malformado
- **WHEN** a origem apresenta uma data ou quantia não vazia que não pode ser interpretada
- **THEN** os dados afetados não são aceitos como leitura concluída
- **AND** o conteúdo inválido não é silenciosamente substituído por null ou zero

### Requirement: Consulta sem apuração ou emissão
A consulta MUST limitar-se à leitura dos anos, períodos, valores e avisos disponíveis. O sistema MUST NOT enviar apuração, gerar DAS, iniciar pagamento ou alterar marcações de benefício previdenciário durante `POST /consultar/pgmei`.

#### Scenario: Botão de geração disponível na tela
- **WHEN** a tabela de períodos é exibida com o botão Apurar/Gerar DAS habilitado
- **THEN** a consulta coleta os dados sem acionar a geração
- **AND** a resposta de consulta não contém PDFs produzidos por essa operação

### Requirement: Alertas da origem preservados
O sistema MUST preservar mensagens relevantes da origem, inclusive avisos de dívida ativa, indisponibilidade do ano e pendências que impeçam a leitura. Fechar um aviso informativo MUST NOT apagar seu conteúdo da resposta nem confirmar uma operação fiscal adicional.

#### Scenario: Aviso de dívida ativa antes dos períodos
- **WHEN** a origem exibe um modal informativo de dívida ativa e permite continuar a leitura
- **THEN** o aviso é registrado antes de fechar o modal
- **AND** os períodos são consultados com suas situações originais

### Requirement: Recuperação limitada e resultados parciais
O sistema MUST permitir até três tentativas em sessões independentes, com esperas de 2 e 5 segundos e prazo global de 180 segundos por requisição. A recuperação MUST repetir somente falhas transitórias reconhecidas ou bloqueio Captcha, preservando os anos já validados e sem reiniciar limites por ano.

#### Scenario: Bloqueio isolado seguido de sucesso
- **WHEN** a primeira tentativa retorna bloqueio `13896` e a seguinte permite acesso
- **THEN** a nova tentativa usa sessão sem cookies ou armazenamento da anterior
- **AND** os anos são processados dentro do limite original da requisição

#### Scenario: Falha após um ano concluído
- **WHEN** 2023 foi validado e a leitura de 2024 sofre falha transitória
- **THEN** a recuperação preserva o resultado de 2023 e retoma o trabalho pendente
- **AND** uma falha persistente não apaga os dados válidos de 2023

#### Scenario: Prazo esgotado durante a consulta
- **WHEN** o prazo global termina após a conclusão de pelo menos um ano
- **THEN** a API retorna HTTP 200 com status parcial, dados válidos preservados e falhas dos anos restantes
- **AND** os anos não processados são identificados sem aparentar consulta concluída

### Requirement: Erros externos e liberação de recursos
Sem nenhum ano utilizável, o sistema MUST retornar 502 para falha externa ou 504 para timeout, em vez de sucesso vazio. Bloqueio persistente MUST encerrar a recuperação. Sessões e recursos temporários MUST ser liberados também em erro e cancelamento, sem expor cookies, tokens ou exceções externas brutas.

#### Scenario: Bloqueio persistente desde a identificação
- **WHEN** todas as tentativas retornam bloqueio Captcha sem nenhum ano obtido
- **THEN** a resposta é HTTP 502 e não declara ausência de pendências
- **AND** todas as sessões criadas são encerradas

#### Scenario: Timeout sem resultado e cancelamento
- **WHEN** a origem não permite obter nenhum ano dentro do prazo
- **THEN** a resposta é HTTP 504
- **AND** um cancelamento do cliente encerra a sessão sem iniciar nova tentativa

### Requirement: Contratos existentes preservados
As novas respostas e a política de sucesso parcial MUST ser exclusivas das novas rotas PGMEI/DAS. O sistema MUST preservar contratos, validação e comportamento das rotas de cadastro, DASN, Optantes e consulta completa.

#### Scenario: Consulta completa após a extensão
- **WHEN** um cliente chama `/consultar` com o contrato atual
- **THEN** recebe os mesmos módulos e regras de sucesso ou falha vigentes
- **AND** a chamada não passa a consultar PGMEI ou emitir DAS implicitamente
