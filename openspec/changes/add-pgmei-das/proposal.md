# Proposal

## Why

A DocAPI consulta cadastro, DASN e Optantes, mas ainda não oferece os períodos do PGMEI nem a emissão dos respectivos DAS. O fluxo fornecido pelo usuário permite adicionar essas operações reutilizando o navegador e a recuperação existentes, com resultados verificáveis e sem perder documentos quando parte do processamento falhar.

## What Changes

- Adicionar `POST /consultar/pgmei`, recebendo CNPJ e consultando todos os anos disponibilizados pelo portal, sem realizar apuração.
- Adicionar `POST /emitir/das`, recebendo CNPJ, competências explícitas `YYYY-MM` e data de pagamento opcional; emitir DAS mensais somente para os períodos solicitados.
- Retornar identificação, situações, disponibilidade de emissão, valores, datas e alertas disponíveis, distinguindo dados não obtidos de ausência confirmada.
- Entregar os PDFs originais em Base64 no JSON, associados às competências abrangidas; um arquivo pode reunir várias guias mensais.
- Preservar resultados e falhas por ano ou competência em respostas parciais; registrar explicitamente uma geração cujo resultado ficou indeterminado.
- Reutilizar configuração do Chrome, classificação de erros e recuperação com até três tentativas em sessões novas, pausas de 2 e 5 segundos e prazo compartilhado de 180 segundos por requisição. Não reenviar apurações após envio de resultado incerto.
- Documentar os contratos novos no OpenAPI e cobrir aquisição, emissão, PDFs e recuperação com testes offline determinísticos.

## Capabilities

### New Capabilities

- `pgmei-consulta`: consulta de todos os anos do PGMEI, com identificação conferida, dados por competência e resultados parciais explícitos.
- `das-emissao`: emissão seletiva de DAS mensais, data de pagamento opcional, entrega dos PDFs e recuperação consciente do envio.

### Modified Capabilities

Nenhuma. Não há especificações principais publicadas em `openspec/specs/`; a mudança existente de Optantes mantém seu escopo e não será alterada.

## Impact

- Extensão aditiva dos modelos Pydantic e das rotas FastAPI; manter entradas, respostas e comportamento das consultas atuais, inclusive o agregado `/consultar`.
- Novo scraper PGMEI e orquestração de consulta/emissão, reutilizando a fábrica e o fechamento de navegador existentes. A generalização mínima da recuperação deve preservar a validação e as regras atuais de DASN/Optantes.
- Sem nova dependência de runtime por princípio: Playwright, Pydantic, biblioteca padrão e `unittest` já sustentam aquisição, Base64 e testes.
- Execução síncrona, cálculo exclusivo do portal e arquivos temporários descartados ao encerrar a sessão. Fora do escopo: DAS consolidado, pagamento, alteração de benefício previdenciário, persistência de PDFs, jobs assíncronos e inclusão do PGMEI no agregado existente.
- A inspeção real anterior encontrou bloqueio `13896` antes da seleção dos anos. O trecho pós-identificação é fundamentado na gravação fornecida e no manual oficial, e não será apresentado como fluxo real já validado. Isso não impede implementação e testes locais; homologação real será adicional, com a fábrica de navegador de produção.
