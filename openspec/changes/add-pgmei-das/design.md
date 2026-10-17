# Design

## Context

Ver `proposal.md` para motivação e as especificações `pgmei-consulta` e `das-emissao` para o comportamento normativo.

Estado observado em 17/10/2026:

- `app/api.py` publica FastAPI 2.0.0, usa modelos de `app/models.py` e converte `ValueError`, erros externos e timeouts em 400, 502 e 504. Rejeições de entrada Pydantic produzem 422. A política atual de Optantes não admite resposta parcial.
- `app/consultar.py` centraliza normalização do CNPJ e recuperação de DASN/Optantes. O executor aceita somente os dois módulos, valida modelos, cria uma sessão por tentativa, espera 2/5 segundos e usa prazo monotônico de 180 segundos, incluindo aquisição e validação.
- `app/browser.py` já configura Chrome com `headless=False`, locale `pt-BR`, argumentos e posicionamento adequados ao ambiente. `fechar_browser` limita a limpeza a cinco segundos e preserva o erro principal. O PGMEI deve usar essa mesma fábrica e fechamento.
- Não existe módulo PGMEI nem rota de emissão. Há testes `unittest`, aquisição com Chrome real e interceptação de rede, testes de recuperação e HTTP em loopback. Não é necessário introduzir outro framework de teste.
- A gravação do usuário identifica `#cnpj`, `#continuar`, `#selecionarTodos`, `#btnEmitirDas` e `#modalDetalhamentoDividaAtiva`, mas usa posições de dropdown e não contém a etapa de PDF. O CNPJ gravado inclui resíduo de máscara; esse valor não será reproduzido nem fixado no código.
- A inspeção anterior encontrou `13896` antes da seleção de anos. Os seletores pós-identificação ainda exigem confirmação pontual durante a implementação; as fixtures derivadas da gravação/manual serão identificadas como sintéticas.
- Há alterações de trabalho anteriores em modelos, API, navegador e recuperação; a implementação deve ser incremental, preservando essas alterações e a mudança de Optantes existente.

Referência externa: [Manual oficial do PGMEI](https://www.gov.br/receitafederal/pt-br/assuntos/noticias/2025/setembro/cartao-de-credito-e-uma-nova-opcao-de-pagamento-do-das-para-o-mei/manual_pgmei_2018.pdf), versão interna março/2024, seções 4.1 a 4.5. O manual distingue leitura/atualização de valores, envio de apuração e obtenção do PDF original. Ele orienta o fluxo; não comprova seletores atuais.

## Goals / Non-Goals

**Goals:**

- Fronteira explícita entre leitura recuperável, envio de apuração e obtenção de documento.
- Progresso por requisição mantido em memória e validado antes de ser aceito, inclusive quando o navegador precisa ser recriado.
- Alteração mínima da recuperação compartilhada, comprovada pela regressão de DASN/Optantes.

**Non-Goals:**

- Compartilhar cookies de clientes ou reaproveitar uma sessão que falhou; trocar o navegador de produção; introduzir solver como parte do PGMEI.
- Garantir execução exatamente uma vez entre requisições HTTP diferentes. Não haverá banco de idempotência, retomada persistente ou recuperação de resposta após cancelamento do cliente nesta versão.
- Recalcular valores fiscais, converter HTML em guia PDF ou dividir/recriar PDFs nativos.

## Decisions

### 1. Extensão aditiva e divisão entre aquisição, transformação e serviço

Adicionar `PGMEI_URL` à configuração e um scraper próprio com operações pequenas de identificação, descoberta dos anos, leitura de um ano, preparação/envio e obtenção do PDF. Separar transformação e validação do snapshot em um parser próprio, seguindo a separação já usada em Optantes.

Centralizar o progresso e os dois serviços públicos em `app/pgmei.py`, reutilizando os utilitários atuais de consulta e navegador. As novas rotas apenas validam entrada e encaminham a esses serviços; não acrescentar PGMEI ao agregado nem modificar a sequência dos módulos atuais.

Alternativas: transcrever Puppeteer criaria outro runtime e repetiria os problemas de offsets; inserir toda a emissão em `app/consultar.py` misturaria recuperação de leitura com efeitos de apuração. A separação proposta permite testar essas fronteiras diretamente.

### 2. Modelos públicos mínimos e estados explícitos

Adicionar modelos próprios em `app/models.py`, sem mudar os existentes:

- Consulta usa `ConsultaRequest`. Emissão usa `DasEmissaoRequest`: `cnpj`, `competencias: list[str]` não vazia e `data_pagamento: date | null`. Remover espaços externos das competências, validar exatamente `YYYY-MM` e mês 01–12, deduplicar e ordenar. Aceitar apenas data civil ISO na entrada, sem coerção de timestamp numérico.
- Resposta de consulta: `cnpj`, `nome_empresarial`, `status` (`completo`/`parcial`), `anos` e `alertas`. Cada ano contém `ano`, `status` (`consultado`, `indisponivel`, `erro`, `nao_processado`), `competencias`, `alertas` e `erro` opcional. `competencias=null` significa não obtidas; lista vazia só é admitida com ausência explícita confirmada pela origem.
- Uma competência consultada contém `competencia`, `situacao`, `disponivel_emissao`, `apurado`, `beneficio_inss`, `principal`, `multa`, `juros`, `total`, `data_vencimento` e `data_acolhimento`. Os dois primeiros fatos de apuração/benefício podem ser null se a origem não os informa. Valores monetários são inteiros em centavos ou null; datas são ISO ou null. Disponibilidade desconhecida invalida a linha, em vez de assumir false.
- Resposta de emissão: identificação, `status` (`completo`/`parcial`), `resultados`, `arquivos` e `alertas`. Cada resultado identifica `competencia`, `status` (`emitido`, `gerado_sem_pdf`, `indisponivel`, `indeterminado`, `erro`, `nao_processado`), identificadores de apuração/DAS como strings, valores/datas disponíveis, `data_pagamento_utilizada` e `erro` opcional.
- Arquivo: `nome`, `tipo=application/pdf`, `competencias` e `conteudo_base64`. Associar cada arquivo ao lote cuja geração foi confirmada, sem impor um PDF por competência.
- Falhas de item usam `{codigo, mensagem}` com mensagens controladas localmente. Textos fiscais e avisos da origem ficam nos campos próprios, sem copiar exceções com tokens ou URLs de sessão.

Um resultado de consulta é completo somente quando todos os anos descobertos estão consultados; uma emissão é completa somente quando todas as competências solicitadas estão emitidas com arquivo válido. Demais respostas utilizáveis são parciais. A política de sucesso parcial não se propaga aos modelos antigos.

Alternativa descartada: status inferido de listas vazias permitiria confundir ausência de dados com ausência de dívida. Duplicar bytes do mesmo PDF em cada resultado aumentaria a resposta sem acrescentar informação.

### 3. Aquisição e validação do conteúdo do portal

Preencher somente os 14 dígitos do CNPJ e conferir a identificação exibida fora do campo de entrada. Repetir essa conferência após reidentificação e antes de enviar apuração. Nome empresarial ausente ou CNPJ divergente são falhas definitivas; não aceitar dados dessa página. Progresso anterior de identidade já confirmada permanece válido.

Descobrir anos pelos valores e rótulos do controle exibido; não usar `nth-child(2)` para escolher ano. Processar em ordem crescente. Interpretar tabelas pelos cabeçalhos e limites locais do painel. Duplicidade de competência, célula obrigatória faltante ou valor preenchido inválido impedem validar o ano. Converter dinheiro com `Decimal` para centavos, sem ponto flutuante; não derivar situação pelo botão habilitado.

Esperar DOM, resposta de rede pertinente ou mensagem explícita conforme cada transição. Os alertas de PGMEI incluem toasts e modais; complementar a coleta localmente, sem alterar indiscriminadamente os seletores dos scrapers existentes. Capturar o modal de dívida ativa antes de fechá-lo. Não depender de um toast transitório nem de `wait_for_navigation` em atualizações Ajax.

Na consulta, abrir o ano e ler a tabela sem selecionar períodos nem enviar apuração. Quando houver falha de integridade isolada de um ano, registrar o erro e continuar somente se a sessão continuar identificada e utilizável. Divergência de identidade encerra a sessão e o processamento restante.

### 4. Recuperação compartilhada com progresso fora da sessão

Generalizar minimamente `_consultar_com_recuperacao` com um validador de resultado opcional para o novo módulo, mantendo a seleção e validação atuais quando omitido. Preservar assinaturas/chamadas existentes, classificação de exceções, logs, backoff, prazo e fechamento. Não ampliar a lista de exceções recuperáveis para erros genéricos.

Cada serviço PGMEI chama o executor uma vez por requisição, não uma vez por ano. O callback usa um objeto de progresso criado pelo serviço e mantido fora do navegador: identificação validada, anos descobertos, resultados confirmados, itens pendentes, estados de envio e bytes de arquivos. Ao recriar a sessão, reidentificar o contribuinte e retomar somente itens ainda recuperáveis.

O limite é de três tentativas/sessões no total e 180 segundos monotônicos compartilhados por todos os anos; não há renovação por competência. As pausas de 2 e 5 segundos e a espera por download fazem parte do prazo. O fechamento conserva a tolerância adicional de até cinco segundos já existente.

O progresso só recebe dados de ano/competência após sua validação. Quando recuperação ou prazo terminarem, o serviço marca o item interrompido com a falha e os demais pendentes como não processados. Se houver progresso utilizável, serializa resposta parcial; caso contrário, propaga erro tipado para `_safe_call`. Cancelamento externo não vira resposta parcial: registrar conservadoramente o estado de envio em memória, liberar recursos e propagar o cancelamento, sem retry.

Alternativas descartadas: executar recuperação separada por ano poderia multiplicar o prazo e as tentativas; repetir o callback sem progresso externo reconsultaria anos concluídos e poderia reenviar documentos.

### 5. Fronteira de envio por lote anual

Para cada ano solicitado, ler a tabela, separar competências elegíveis e registrar indisponibilidade explícita das demais. Desmarcar seleções prévias de períodos, selecionar exatamente o conjunto elegível e conferir o conjunto final. Não tocar em checkboxes de benefício previdenciário nem no controle de consolidação.

Se houver data informada, preenchê-la, acionar atualização e esperar término/validação antes do envio. Se a origem rejeitar a data, registrar a rejeição sem substituí-la. Sem parâmetro, manter a sugestão do portal. Conferir novamente identidade, ano e seleção após atualização.

Imediatamente antes de iniciar o clique que pode transmitir a apuração, marcar as competências do lote como `enviando`. Qualquer falha a partir desse ponto é conservadoramente indeterminada até haver confirmação individual. Não existe transição automática de `enviando`/`indeterminado` para pendente recuperável.

Após a resposta, validar tabela de DAS gerados e correspondência com o lote. Para cada competência confirmada, guardar imediatamente identificadores, valores e datas, inicialmente como `gerado_sem_pdf`. Competências omitidas ou com confirmação ambígua permanecem `indeterminado`; toast global não confirma essas linhas. Obter o PDF e promover somente resultados confirmados abrangidos pelo arquivo para `emitido`.

Uma falha de sessão após envio pode consumir nova tentativa apenas para outros anos ainda não enviados. Resultados gerados, indeterminados e indisponibilidades já confirmadas não são reapurados. Falha somente do PDF nunca chama Apurar/Gerar novamente; eventual recuperação do documento é uma leitura do recurso já gerado dentro do prazo e sem exigir nova apuração.

Não prometer proteção contra um cliente que repita outra requisição inteira após perder a resposta. Documentar esse limite no endpoint de emissão, especialmente para cancelamento e `indeterminado`.

### 6. Obtenção e ciclo de vida dos PDFs

Armar observação de download, popup ou resposta PDF antes de acionar Imprimir/Visualizar PDF, conforme o comportamento efetivamente observado. Consumir os bytes do documento nativo na mesma sessão, incluindo GET autenticado de URL de documento obtida do próprio fluxo quando necessário. Encerrar observadores que não forem utilizados.

Validar arquivo não vazio e assinatura PDF, rejeitando HTML de login/erro mesmo com HTTP 200 ou nome `.pdf`. Não usar `page.pdf()` nem produzir uma guia a partir da tela. Associar arquivo ao lote confirmado; não dividir ou juntar documentos. Usar nomes locais controlados, sem confiar em caminhos fornecidos pela origem.

Converter os bytes com a biblioteca padrão `base64` e guardá-los no progresso antes de liberar a sessão. Se houver arquivo temporário, usar diretório temporário exclusivo da requisição e limpeza em `finally`; downloads internos do Playwright são descartados ao fechar o contexto. Não persistir guias em `output/`, criar URLs públicas ou registrar Base64 nos logs.

### 7. Resposta HTTP e definição de resultado utilizável

- Consulta: ao menos um ano integralmente validado permite HTTP 200 parcial. Identificação ou lista de anos isoladas não bastam. Sem ano utilizável, propagar 502/504.
- Emissão: geração confirmada, indisponibilidade de competência explicitamente informada pela origem ou possível envio registrado como `indeterminado` são resultados utilizáveis. Havendo qualquer um deles, preservar o resultado em HTTP 200 parcial, mesmo sem PDF. Falhas genéricas e itens não processados, isoladamente, não bastam para HTTP 200.
- Bloqueio persistente/falha externa anterior a qualquer resultado utilizável: 502. Timeout sem resultado utilizável: 504. Rejeição de entrada: 422 ou 400 conforme o caminho atual de validação do CNPJ. Falha total preserva o envelope `{"detail": "mensagem"}` existente.
- Antes da resposta, validar o modelo público completo e coerência entre competências, resultados e arquivos. Uma falha inesperada de implementação não é promovida a ausência fiscal nem a sucesso parcial genérico.

Alternativa descartada: emitir 502 genérico depois de um possível envio perderia justamente a informação necessária para evitar repetição. `indeterminado` é um resultado operacional explícito, nunca confirmação de emissão.

### 8. Verificação e documentação

Reutilizar o padrão de Chrome real com contexto offline e `context.route` para identificação, anos, tabelas, atualização, confirmação e documento. Bloquear requisições inesperadas e contar envios do lote: o teste deve comprovar zero envios na consulta e no máximo um envio por competência durante recuperação.

Cobrir conversão de valores/datas, ausência versus falha, seleções preexistentes, preservação de benefício, modal de dívida ativa, datas explícitas/rejeitadas, PDF único com várias competências e HTML no lugar de PDF. Testar ambos os caminhos de documento relevantes ao adaptador implementado, inclusive popup/inline quando existentes.

Reutilizar o padrão de testes de recuperação para isolamento de sessões, 3 tentativas, pausas, prazo durante outro ano, sucesso parcial, falha de PDF, geração confirmada seguida de falha, resultado indeterminado, cancelamento e cleanup com erro. Validar HTTP/OpenAPI em loopback e executar toda a suíte de regressão existente.

Atualizar OpenAPI e documentação de confiabilidade com exemplos das duas rotas, Base64, centavos, status parcial e cuidados de reenvio. Manter a versão/documentação de migração 2.0.0 já testada: esta extensão não altera os contratos antigos. Homologação real adicional usa `create_browser`, não a sessão headless exploratória anterior; não é requisito de aprovação dos testes offline.

## Risks / Trade-offs

- [DOM pós-identificação ainda não confirmado em sessão real] → validar seletores pontuais contra a origem durante implementação, marcar fixtures reconstruídas como sintéticas e reportar honestamente o alcance da homologação.
- [Bloqueio Captcha persistente] → mesma fábrica e recuperação limitada dos módulos existentes; retornar falha explícita em vez de dados vazios. Não prometer ausência de bloqueio externo.
- [180 segundos insuficientes para todos os anos] → progresso validado preservado, status parcial e identificação dos anos/competências não concluídos; documentar timeout compatível no cliente/proxy.
- [Timeout ou cancelamento depois do envio] → estado conservador anterior ao clique e ausência de retry para o lote afetado; não há confirmação de execução exatamente uma vez entre chamadas.
- [PDFs em Base64 aumentam memória e tamanho da resposta] → processar anos sequencialmente e manter um arquivo por documento original, sem duplicar bytes por competência; armazenamento externo fica fora desta versão.
- [Refatoração do executor compartilhado altera consultas atuais] → parâmetro opcional, defaults preservados e regressão obrigatória antes de concluir a implementação.

## Migration Plan

1. Implementar contratos, aquisição e progresso com as novas rotas isoladas; preservar as alterações locais anteriores.
2. Validar as especificações OpenSpec e os testes novos/atuais. Publicar a extensão com exemplos e timeout de 180 segundos mais limpeza.
3. Consumidores adotam as rotas novas explicitamente; não há migração de dados nem ação fiscal durante startup/deploy.
4. Em rollback, retirar a exposição das rotas novas e reverter somente a extensão PGMEI. Uma apuração já enviada à Receita não é desfeita pelo rollback; resultados indeterminados exigem conferência no portal.
