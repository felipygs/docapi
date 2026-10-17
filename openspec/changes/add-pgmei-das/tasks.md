# Tasks

## 1. Contratos e validação de dados

- [ ] 1.1 Adicionar os modelos de consulta PGMEI, resultados por ano/competência, falhas e arquivos conforme o design; verificar testes de validação de null, estados e coerência entre resultados e arquivos, preservando os modelos atuais.
- [ ] 1.2 Adicionar `DasEmissaoRequest` com CNPJ, competências não vazias normalizadas/deduplicadas/ordenadas e data civil ISO opcional; verificar testes de duplicatas, espaços, meses inválidos, lista vazia, datas inválidas e rejeição de timestamps numéricos antes de navegar.
- [ ] 1.3 Implementar transformação de snapshots do PGMEI com situação integral, disponibilidade, benefício, valores em centavos e datas ISO; verificar testes de ausência explícita, dados incompletos, valores preenchidos inválidos e competência duplicada.
- [ ] 1.4 Adicionar exemplos serializáveis dos contratos e documentar centavos, null, `completo`/`parcial` e estados de emissão em `docs/pgmei.md`; verificar que os exemplos validam nos modelos e não inferem quitação de dados ausentes.

## 2. Aquisição do PGMEI sem efeitos de emissão

- [ ] 2.1 Adicionar `PGMEI_URL` e identificação pelo scraper usando somente os dígitos do CNPJ, seletores estáveis e a identificação exibida pela origem; verificar em Chrome com rede interceptada CNPJ preenchido, identidade correta/ausente/divergente e bloqueio `13896`.
- [ ] 2.2 Implementar descoberta dos anos e leitura de um ano com esperas de conteúdo/erro em navegação e Ajax; verificar fixtures com anos não consecutivos, linhas desabilitadas e resposta sem tabela, sem depender da posição do dropdown.
- [ ] 2.3 Preservar toasts e modal informativo de dívida ativa antes de fechá-los, sem alterar benefício ou confirmar operação fiscal adicional; verificar testes de alertas visíveis/ocultos e marcações preservadas.
- [ ] 2.4 Registrar a origem das fixtures reconstruídas da gravação/manual e os seletores pós-identificação que ainda não foram confirmados na origem; verificar uma consulta local com contador de apurações igual a zero e documentação explícita da limitação de evidência real.

## 3. Recuperação compartilhada e serviço de consulta

- [ ] 3.1 Generalizar minimamente o executor existente para aceitar validação PGMEI opcional, preservando os defaults de DASN/Optantes; verificar todos os testes atuais de recuperação, payload inválido, cleanup e limite de prazo/tentativas.
- [ ] 3.2 Implementar progresso por requisição fora do navegador e serviço de consulta que retome somente os anos pendentes em sessão nova; verificar isolamento de cookies/storage, até três tentativas globais e pausas de 2/5 segundos sem reconsultar anos concluídos.
- [ ] 3.3 Finalizar os estados de anos interrompidos e não processados ao esgotar tentativas/prazo, devolvendo parcial somente com ao menos um ano utilizável; verificar sucesso parcial, 502/504 sem dados, identidade divergente após progresso, cancelamento e fechamento com erro.
- [ ] 3.4 Documentar em `docs/confiabilidade.md` o prazo de 180 segundos compartilhado, tolerância de limpeza e política parcial exclusiva de PGMEI/DAS; verificar que a documentação mantém as garantias vigentes de DASN/Optantes e o agregado existente.

## 4. Preparação e envio seletivo de DAS

- [ ] 4.1 Implementar agrupamento anual, classificação de indisponibilidades e seleção exata dos períodos elegíveis; verificar testes com vários anos, mês ausente/desabilitado, seleções preexistentes e benefício marcado, contando somente as competências solicitadas nos envios.
- [ ] 4.2 Aplicar data de pagamento opcional e aguardar atualização/validação dos valores, preservando a sugestão quando omitida; verificar testes de data aceita, rejeitada, omitida e seleção alterada pelo portal antes de conferir o lote final.
- [ ] 4.3 Registrar estado de possível envio antes do clique e validar confirmação individual por competência; verificar que toast genérico não confirma todas as linhas e que resultado faltante/ambíguo vira `indeterminado`, sem novo envio na mesma requisição.
- [ ] 4.4 Integrar a emissão ao progresso e à recuperação global, preservando gerações confirmadas e lotes indeterminados; verificar falha pré-envio em outro ano, timeout pós-envio, sessão perdida e cancelamento com no máximo um envio por competência.
- [ ] 4.5 Documentar em `docs/pgmei.md` a preservação de benefício, indisponibilidades, envio indeterminado e ausência de garantia de idempotência entre chamadas distintas; verificar correspondência dos exemplos com os testes de resultado parcial e nenhuma instrução de reenvio automático.

## 5. PDFs, rotas e contrato HTTP

- [ ] 5.1 Capturar PDF nativo por download/popup/resposta conforme o adaptador do portal, validando assinatura e recusando HTML de sessão expirada; verificar em Chrome interceptado os caminhos suportados e igualdade byte a byte após decodificar o Base64.
- [ ] 5.2 Associar cada PDF às competências do lote confirmado e conservar `gerado_sem_pdf` em falha do documento; verificar um PDF com várias guias, falha de download sem reapuração e documentos preservados depois de recriar/fechar a sessão.
- [ ] 5.3 Garantir descarte de diretórios/arquivos temporários e observadores em sucesso, erro e cancelamento; verificar limpeza com falhas simuladas e ausência de dependência de URL de sessão no conteúdo entregue.
- [ ] 5.4 Publicar `/consultar/pgmei` e `/emitir/das` com modelos próprios e `_safe_call`, preservando contratos antigos; verificar HTTP real em loopback para 200 completo/parcial, 422, 400, 502, 504 e resultado indeterminado utilizável.
- [ ] 5.5 Atualizar OpenAPI e exemplos de `docs/pgmei.md` com entrada, data opcional, estados, Base64 e limites de prazo/reenvio; verificar esquema, serialização e ausência de execução PGMEI implícita em `/consultar`.

## 6. Verificação integrada

- [ ] 6.1 Executar `python -m unittest discover -s tests -v` e `python -m pip check` no ambiente Python do projeto; verificar a suíte nova e a regressão completa de cadastro, DASN, Optantes, recuperação e HTTP sem depender da Receita.
- [ ] 6.2 Executar `openspec validate add-pgmei-das --strict` e conferir o diff final; verificar que contratos existentes e alterações locais anteriores foram preservados e registrar o alcance dos testes e eventuais limitações de homologação real.

## Workflow follow-up

- Homologação real adicional usa a mesma fábrica de navegador das consultas existentes; registrar separadamente consulta de leitura e emissão real, com as competências explicitamente escolhidas pelo usuário. Bloqueio externo persistente deve ser reportado sem substituir testes offline por falsa confirmação.
