# Proposal

## Why

As consultas atuais de cadastro CNPJ, DASN, Optantes e consulta completa já funcionam, mas o Chrome ainda usa modo com janela, mesmo posicionado fora da tela. É necessário avaliar invisibilidade total no Windows sem colocar em risco esse estado validado, representando o uso habitual de uma consulta por vez.

## What Changes

- Executar um estudo descartável em processos separados, comparando o modo atual com `headless=True`, com alterações somente em memória nos parâmetros de abertura do navegador.
- Preservar servidor em uso, arquivos da aplicação, configurações e melhorias ainda não commitadas; não introduzir opção permanente nem alterar o padrão de execução.
- Executar a suíte local e comparar consultas reais dos casos já homologados, incluindo QSA, desfecho DASN 33001 e consulta completa.
- Medir correção, tentativas, bloqueios, duração, fechamento dos processos, ausência de janelas e ausência de roubo de foco, em execuções sequenciais.
- Produzir evidências e uma recomendação de viabilidade, inviabilidade nas condições testadas ou resultado inconclusivo. Uma eventual opção permanente depende de outra mudança.

## Capabilities

### New Capabilities

Nenhuma. Este estudo não acrescenta comportamento permanente ao sistema. A mudança declara `skip_specs: true`; os critérios experimentais estão em `design.md` e `tasks.md`.

### Modified Capabilities

Nenhuma. A especificação `optantes-consulta` e os contratos existentes serão usados como referência de validação, sem deltas.

## Impact

- O experimento reutilizará a fábrica de navegador, orquestração, rotas e modelos existentes, sem editar `app/`, testes existentes, dependências, `.env`, Docker ou configuração pública.
- Scripts descartáveis, logs e respostas do estudo serão mantidos em um diretório próprio de evidências sob `output/`; a conclusão será documentada em relatório próprio sob `docs/`.
- Chamadas reais acessarão Receita e o solver já configurado; cadastro poderá consumir créditos. Tokens, cookies e chaves não serão incluídos nas evidências.
- Fora do escopo: concorrência, Docker, PGMEI, mudanças de scraper ou captcha, disfarce de características do navegador, adoção automática e fallback para janela visível.
