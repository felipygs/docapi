# Design

## Context

Ver `proposal.md` para motivação e `specs/optantes-consulta/spec.md` para o contrato normativo. A mudança inclui modelos e API, portanto este desenho é necessário, não um artefato condicional dispensável.

Estado observado:

- `app/scrapers/optantes.py` extrai situação do texto global e procura históricos em todos os `.panel-body, div`. Um ancestral contendo os dois rótulos pode associar sua primeira tabela ao SIMEI mesmo quando o texto desse regime diz `Não Existem`. No exemplo de ELIANE fornecido pelo usuário, as três linhas do Simples aparecem indevidamente no SIMEI. Há ainda risco de a tabela de eventos ser confundida com histórico. A causa está na associação ampla por ancestrais/posição, não nos dados fiscais.
- Eventos são capturados por regex no corpo inteiro e retornam string/null. `spnEvFutSimei` é repetido nos painéis dos dois regimes, então seu ID não identifica o regime.
- `#btnMaisInfo` carrega HTML via `Home/AjaxMaisInfo?cnpjHdn=...` para `#maisInfo`. O código espera apenas o título de históricos e não valida completude de todos os painéis. `#spnMsgErro` contém falhas complementares fora dos seletores genéricos de alerta.
- `OptantesResponse` é usado diretamente na rota individual e dentro de `ConsultaResponse`. `_safe_call` já converte RuntimeError em 502 e timeouts em 504.
- `data_br_para_iso` devolve null para valores inválidos; reutilizá-lo sem validação apagaria datas inválidas da origem. A solução deve distinguir ausência de formato inválido sem mudar o comportamento de CNPJ/DASN.
- `main.py` contém acessos antigos de vários módulos e já diverge do contrato atual. Não é um consumidor novo a reparar integralmente nesta mudança.
- Não foram encontrados testes ou especificações anteriores. Runtime atual: FastAPI, Pydantic, Playwright, requests e uvicorn; testes podem usar `unittest`/`unittest.mock` e Playwright já instalado.

Evidências disponíveis fora do repositório:

- HTML expandido de IVANUSA em `C:/Users/Felipe/.cursor/projects/c-Users-Felipe-dev-docapi/optantes-inspecao/45726608000136-expandido.html`: um histórico em cada regime, eventos e Transportador ausentes explicitamente.
- HTML fornecido de BARBARA em `C:/Users/Felipe/Downloads/Consulta Optantes.html`: ambos históricos e eventos ausentes explicitamente.
- Texto de consulta de ELIANE em 15/10/2026 18:08:45 e JSON atual fornecidos na conversa: três períodos só no Simples, evento `Exclusão de Ofício - Débitos` com efeito 01/01/2027 e histórico do SIMEI duplicado erroneamente na API. HTML preenchido ainda não capturado: fixture reconstruída desse caso deve ser marcada sintética, nunca apresentada como download real.

## Goals / Non-Goals

**Goals:**

- Um contrato novo e compacto, sem camada de compatibilidade, conforme decisão do usuário.
- Dados fiscais conhecidos normalizados e tipados; booleanos apenas para fatos binários confirmados; listas indicam múltiplos registros e sua ausência confirmada.
- Extração isolada por seção, validação explícita e comportamento idêntico entre a rota individual e o agregado.
- Preservação excepcional de dados novos sem colocar HTML bruto, textos tabulados de eventos ou cópia integral da página na resposta comum.
- Regressão determinística sem portais externos nos testes obrigatórios.

**Non-Goals:**

- Mudar sequência, paralelismo, rotas ou autenticação; fazer coleta parcial em HTTP 200; emitir documentos fiscais; classificar débitos ou providenciar regularização.
- Mudar o browser de produção ou automatizar desafios e evasão de captcha.
- Remodelar DASN/cadastro, o CLI inteiro ou o tratamento global de validação de CNPJ.
- Criar campos normalizados de Transportador sem evidência de seu formato preenchido.

## Decisions

### 1. Substituição direta com contrato explícito

A opção escolhida pelo usuário é substituir o formato atual e aceitar quebra. Manter as rotas existentes, declarar versão 2.0.0 em `FastAPI`, remover tipos/aliases legados de eventos e documentar migração. Criar versão paralela preservaria clientes, mas adicionaria uma superfície que o usuário recusou. A estratégia aditiva anterior foi descartada por duplicação de dados.

Campos obrigatórios do resultado:

- `cnpj_consultado`: string de 14 dígitos, entrada normalizada; separado de `cnpj_matriz` retornado pela origem.
- `cnpj_matriz`: string de 14 dígitos retornada pela Receita; o nome do campo já expressa o tipo matriz, sem `matriz: true` redundante.
- `nome_empresarial`: string não vazia integral.
- `consultado_em`: datetime local ISO sem timezone, derivado da origem; não do relógio do coletor.
- `abrange_todos_estabelecimentos`: bool derivado da nota; true para a frase conhecida. Somente notas explicitamente reconhecidas permitem false; ausência/variação ambígua causa 502.
- `simples_nacional`: `optante: bool`, `situacao: str`, `data_desde: date | null`, `periodos_anteriores: list[Periodo]`, `eventos_futuros: list[EventoFuturo]`.
- `simei`: mesmos campos, usando `enquadrado` em vez de `optante`.
- `mei_transportador`: `possui_periodos: bool`; `detalhes` somente quando houver conteúdo preenchido válido.
- `alertas`: lista de mensagens distintas, incluindo `[]` quando não há alertas.

Objetos compartilhados:

- `Periodo`: `data_inicial: date | null`, `data_final: date | null`, `detalhamento: str | null`. Campos continuam presentes, inclusive null se a célula explicitamente estiver vazia; valor não vazio inválido causa erro. Texto vazio de detalhamento é null.
- `EventoFuturo`: `descricao: str` não vazia e `data_efeito: date | null`; coluna esperada ausente causa 502. Célula de data explicitamente vazia pode ser null, mas data não vazia inválida causa 502.
- Em `Periodo` e `EventoFuturo`, `campos_adicionais` é opcional e contém lista de `{coluna, valor}`. A lista preserva ordem e cabeçalhos repetidos, que seriam perdidos num dicionário.
- `ConteudoSecao`: `texto: str`, `tabelas: list[Tabela]`; `Tabela` tem `cabecalhos: list[str]` e `linhas: list[list[str]]`, preservando todas as células. É usada em `mei_transportador.detalhes` e em entradas de `dados_adicionais` com o campo adicional `secao`.
- `dados_adicionais` é opcional, presente somente para seções fiscais desconhecidas. Não captura cabeçalhos já modelados, menus, botão de PDF, scripts ou modais comentados.

`possui_eventos`, contagens e flags por lista não serão adicionadas: `len(eventos_futuros)` já determina existência, sem perder detalhes. `situacao` repete parte do significado de booleano/data intencionalmente para preservar a redação original; a concisão não autoriza apagar esse texto solicitado pelo usuário. Não devolver repetidamente `Não Existem`: listas vazias confirmadas e o bool de Transportador codificam esse significado.

### 2. Sem resposta parcial: integridade antes de listas vazias

Para reduzir a complexidade do contrato, as quatro marcações de estado propostas durante a exploração não serão expostas em cada seção. Um HTTP 200 significa que identificação, horário, situação, ambos históricos, ambos eventos e Transportador foram reconhecidos e validados. `[]` significa ausência explícita; null só é permitido em campos escalares opcionais cujo valor está explicitamente ausente.

Falhas de navegação/carregamento continuam 504 quando são timeouts. Erro Ajax informado, seção obrigatória ausente após carregamento concluído, status desconhecido, tabela sem cabeçalhos esperados ou valor não vazio inválido geram RuntimeError com seção/campo, mapeado para 502. Não usar ValueError para falha da Receita: `_safe_call` a trataria como 400 do cliente. Evitar expor tokens/cookies nas mensagens. A resposta completa também não é entregue se Optantes falha, preservando a política já existente de falha total.

Alternativa rejeitada: flags `consultado`, `estado`, `erro`, `existe` em todas as seções com HTTP 200 parcial. É adequada para outro produto, mas aumenta resposta e permite consumidores ignorarem falhas. A integridade all-or-nothing deve constar nos exemplos e documentação.

### 3. Aquisição e extração desacopladas

Manter `consultar_optantes(page, cnpj_limpo, ...)` como orquestrador assíncrono de navegação e carregamento. Colocar o extrator DOM em um módulo pequeno específico, por exemplo `app/scrapers/optantes_parser.py`, com fronteira estável que receba uma página já carregada e produza um snapshot estruturado. A transformação/validação Python desse snapshot fica separada da rede e pode ser testada sem Receita.

Não adicionar BeautifulSoup ou requests como novo caminho de produção: Playwright já fornece DOM renderizado e o fluxo Ajax existente. Leitura de `page.content()` pode servir apenas para fixtures/evidência, sem alterar o contrato comum. Nenhuma captura deve exportar cookies/estado do navegador.

Aquisição:

1. Preencher CNPJ e aguardar Situação Atual como hoje.
2. Identificar `#btnMaisInfo`; se não estiver carregado, acionar e observar a resposta de AjaxMaisInfo e o estado da UI na mesma sessão.
3. Distinguir erro de `#spnMsgErro`, ausência de painel e timeout. Esperar loader terminar e validar todos os títulos obrigatórios dentro de `#maisInfo`, não apenas o primeiro histórico.
4. Se já estiver expandido/disabled, validar conteúdo em vez de tentar clicar ou assumir sucesso.
5. Não introduzir retries de captcha ou rotação de sessões nesta mudança; não ampliar tentativas de rede como solução do erro de associação.

### 4. Associação por limites locais, nunca tabelas globais

Indexar os painéis filhos de resultado por título normalizado apenas para comparação (espaços/case), preservando os textos originais. Usar os títulos Eventos Futuros (Simples Nacional), Eventos Futuros (SIMEI) e Transportador para delimitar cada conteúdo.

No painel de históricos, os dois rótulos podem compartilhar `.panel-body`. Percorrer nós irmãos a partir de cada rótulo e parar no próximo rótulo/seção. Aceitar `Não Existem` ou a tabela pertencente a esse intervalo. Não buscar primeira/segunda tabela em todos os ancestrais nem usar globalmente `querySelectorAll('table')[n]`. Esse limite corrige exatamente o caso Simples preenchido/SIMEI vazio e evita que uma tabela de eventos seja tomada por histórico. O caso inverso também deve ser coberto.

Ler colunas pelos cabeçalhos normalizados e validar obrigatórios, preservando sua ordem original. `Data Inicial`, `Data Final`, `Detalhamento` pertencem a períodos; `Descrição do Evento`, `Data Efeito` pertencem a eventos. Colunas adicionais ficam por linha em `campos_adicionais`. Ambiguidade de cabeçalho obrigatório duplicado, células faltantes ou linhas malformadas causa 502, nunca truncamento silencioso. Cabeçalhos extras repetidos são preservados como lista, sem sobreposição.

### 5. Situações e datas estritas sem regressão de outros módulos

Normalizar só para reconhecimento e manter o texto de origem para `situacao`. Reconhecer explicitamente padrões positivos/negativos do Simples e do SIMEI, incluindo diferença de caixa/acentos. Não calcular booleano pela ausência da palavra `não`: isso classificaria conteúdo desconhecido como true.

Usar conversores estritos locais ou wrappers dos utilitários existentes: null é aceito somente para ausência explícita; rejeitar datas não vazias inválidas. Não alterar a semântica global de `data_br_para_iso` usada por CNPJ/DASN. Pydantic deve usar tipos date/datetime apropriados e validação de strings/documentos, com `Field(default_factory=list)` para listas onde defaults forem necessários.

### 6. Transportador e extensões sem esquema fictício

Não dispomos de HTML real com Transportador preenchido. A ausência explícita é segura e retorna `{ "possui_periodos": false }`. Se a seção contiver registros/texto de períodos sem erro e com conteúdo substantivo reconhecido como resultado, retorna true com `detalhes` preservando o conteúdo integral e tabelas, sem inventar colunas. Em caso ambíguo, 502. O schema comporta resultado preenchido sem declarar que suas colunas já foram validadas.

Seções fiscais novas adicionais podem ser preservadas em `dados_adicionais`; elas não substituem a validação das seções obrigatórias. Omissão de campos opcionais vazios é feita na serialização dos modelos específicos, não com `response_model_exclude_none=True` global: esse filtro removeria nulls significativos de datas e afetaria o agregado. Testar a serialização FastAPI e `ConsultaResponse`, não apenas `model_dump` isolado. Implementação deve verificar os recursos disponíveis na versão efetiva de Pydantic para omissão condicional localizada, sem depender de funções não instaladas.

## Exemplo proposto para ELIANE

Este é um alvo de contrato derivado do texto fornecido pelo usuário, não resultado novo da API. Horário sem fuso e datas normalizadas; `situacao` mantém a redação da origem.

```json
{
  "cnpj_consultado": "43996591000101",
  "cnpj_matriz": "43996591000101",
  "nome_empresarial": "ELIANE S MURTA CONSULTORIO ODONTOLOGICO",
  "consultado_em": "2026-10-15T18:08:45",
  "abrange_todos_estabelecimentos": true,
  "simples_nacional": {
    "optante": true,
    "situacao": "Optante pelo Simples Nacional desde 01/01/2026",
    "data_desde": "2026-01-01",
    "periodos_anteriores": [
      {
        "data_inicial": "2025-01-01",
        "data_final": "2025-12-31",
        "detalhamento": "Excluída por Ato Administrativo praticado pela Receita Federal do Brasil"
      },
      {
        "data_inicial": "2024-01-01",
        "data_final": "2024-12-31",
        "detalhamento": "Excluída por Ato Administrativo praticado pela Receita Federal do Brasil"
      },
      {
        "data_inicial": "2021-10-25",
        "data_final": "2023-12-31",
        "detalhamento": "Excluída por Ato Administrativo praticado pela Receita Federal do Brasil"
      }
    ],
    "eventos_futuros": [
      {
        "descricao": "Exclusão de Ofício - Débitos",
        "data_efeito": "2027-01-01"
      }
    ]
  },
  "simei": {
    "enquadrado": false,
    "situacao": "NÃO enquadrado no SIMEI",
    "data_desde": null,
    "periodos_anteriores": [],
    "eventos_futuros": []
  },
  "mei_transportador": {
    "possui_periodos": false
  },
  "alertas": []
}
```

## Risks / Trade-offs

- [Quebra de clientes existentes] → Escolha aprovada explicitamente; versão 2.0.0 e exemplos de migração, sem suportar contrato duplo. Inventariar referências locais aos modelos.
- [Mudança de markup] → Limites por título/rótulo, validação de cabeçalhos e extensão sem perda; fixtures com ordem alterada e IDs duplicados.
- [Mais erros externos antes mascarados como vazio] → Decisão intencional para impedir dados fiscais falsos; mensagens de seção permitem diagnóstico. Sem HTTP 200 parcial.
- [Sem HTML real preenchido de ELIANE] → Marcar fixture reconstruída sintética, testar o comportamento conhecido e capturar HTML real no smoke test se disponível. Não alegar validação DOM real sem captura.
- [Formato Transportador desconhecido] → Modelo genérico lossless e ausência confirmada; fixture preenchida sintética valida preservação, não conformidade real do portal.
- [Trechos desconhecidos de situação] → Falhar com texto de diagnóstico seguro em vez de inferir enquadramento.
- [Testes assíncronos/browser no Windows] → `unittest.IsolatedAsyncioTestCase`, Playwright e browser local disponível; testes de rede opcionais e independentes do sucesso do captcha cadastral.
- [Compatibilidade de omissão condicional em Pydantic] → Escolher recurso suportado ou serializer localizado e validar schema/resultados nos dois endpoints; não mexer globalmente na omissão de campos.

## Migration Plan

1. Implementar em alteração separada após apply explícito, com regressões offline antes da troca de contrato.
2. Atualizar modelos, extração e OpenAPI em conjunto; nenhuma implantação intermediária que publique schema novo com payload antigo.
3. Publicar versão 2.0.0, avisando que eventos são listas e ausência é `[]`; novas informações de identificação/Transportador estão presentes. Dados históricos incorretos do SIMEI devem ser substituídos por nova consulta, não migrados como verdade.
4. Verificar `/consultar/optantes` pelo Swagger com ELIANE, IVANUSA e BARBARA quando a origem estiver acessível; verificar agregado com módulos externos simulados para não depender do cadastro com captcha. Live do agregado é opcional e separado.
5. Rollback reverte o conjunto inteiro da mudança e a versão publicada; não misturar serializers, modelos e exemplos de contratos diferentes. Nenhuma migração de banco é necessária.

## Open Questions

- Os cabeçalhos reais de MEI Transportador preenchido e variações de eventos futuros no SIMEI podem ser observados depois, sem mudar este contrato, pois já existe preservação genérica. A normalização adicional desses formatos será outra decisão baseada em HTML real.
