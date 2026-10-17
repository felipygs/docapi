# Validação de DASN e Optantes — cinco CNPJs

**Dez consultas HTTP reais aprovadas:** DASN e Optantes responderam HTTP 200 para os cinco CNPJs. Execução em 17/10/2026, das 10:27:34 às 10:30:04, horário de Brasília, com instância nova da API, código atual e portais reais. Nenhuma consulta cadastral foi executada.

| CNPJ | Contribuinte | DASN | Optantes |
| --- | --- | --- | --- |
| 43.996.591/0001-01 | ELIANE | 200 — 33001 confirmado em Optantes | 200 |
| 45.726.608/0001-36 | IVANUSA | 200 — declarações obtidas | 200 |
| 53.987.789/0001-82 | BARBARA | 200 — 33001 confirmado em Optantes | 200 |
| 57.435.953/0001-08 | JOSEANE | 200 — declarações obtidas | 200 |
| 12.309.631/0001-76 | FRANCISCO | 200 — declarações obtidas | 200 |

## Conferências das respostas

- Todos os payloads foram validados pelos modelos públicos, com conferência de identidade em Optantes e consistência de declarações, pendências e baixa na DASN.
- ELIANE preservou três períodos anteriores somente no Simples e nenhum no SIMEI. O evento futuro de exclusão permaneceu no Simples.
- IVANUSA preservou um histórico em cada regime; FRANCISCO, dois em cada regime; JOSEANE, um em cada regime; BARBARA, listas históricas vazias confirmadas.
- JOSEANE manteve a baixa em 26/08/2025 e a pendência de 2025 simultaneamente.
- ELIANE e BARBARA receberam o desfecho `nao_optante_simei_confirmado_por_optantes`. Declarações e pendências ficaram `null`, pois não foram consultadas; não foram convertidas em listas vazias.
- As situações e os históricos IBS/CBS foram preservados em `dados_adicionais`, separados do SIMEI.

## Tentativas normais observadas

Os logs confirmam a recuperação já existente, sem solver ou resolução de desafios:

- BARBARA: Optantes recebeu bloqueio na primeira tentativa durante a conferência DASN e concluiu na segunda.
- JOSEANE: DASN recebeu bloqueio na primeira tentativa e concluiu na segunda.
- Os limites permaneceram em até três tentativas e 180 segundos por módulo. Não houve repetição externa ilimitada.

## Auditoria do histórico e correção

A captura anterior que havia funcionado não continha `#maisInfoComplementar` nem os históricos IBS/CBS presentes na captura atual. A exigência de pai direto `#maisInfo` já existia no commit `0fd8427`, anterior à simplificação desta conversa.

Uma comparação isolada, carregando o código do HEAD sem sobrescrever arquivos da aplicação, mostrou:

- DASN: tanto HEAD quanto código atual receberam bloqueio explícito da origem naquele momento. O código atual classificou esse bloqueio para o executor de recuperação.
- Optantes: HEAD falhou ao interpretar o SIMEI com os novos textos; o código atual concluiu a consulta.

O ajuste no parser reconhece painéis descendentes de `#maisInfo`, inclusive sob `#maisInfoComplementar`, e delimita o histórico IBS/CBS separadamente. Campos, rotas, modelos e OpenAPI não foram alterados por essa correção. Foram acrescentados testes para contêiner intermediário, histórico IBS/CBS em diferentes posições, preservação de tabelas adicionais e rejeição de histórico SIMEI incompleto.

## Evidências

- `relatorio.json`: respostas integrais, status HTTP, duração e validação das dez chamadas.
- `recuperacao.log`: tentativas e códigos locais, inclusive os dois bloqueios recuperados na segunda tentativa.
- `correcao-optantes.diff`: alteração do parser em relação ao início da correção.
- `validar.py`: script de validação HTTP, sem mocks.
- `testes-locais.log`: saída da suíte local.
- Auditoria anterior: `../validacao_dasn_optantes_20261017_101748/auditoria_historico.json`.

## Verificação local concluída

Comando: `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`.

Resultado: **137 testes aprovados**, em 553,447 segundos, sem falhas ou testes ignorados. Inclui os quatro testes novos de regressão do parser, além dos cenários de retry, timeout, cancelamento, fechamento, respostas HTTP, nulabilidade e schemas. A suíte usou páginas locais e respostas interceptadas; as dez consultas reais foram executadas separadamente, antes dela.

`git diff --check` aprovado. O OpenAPI foi comparado com o estado anterior desta correção e permaneceu idêntico.

Esses resultados registram o comportamento observado nesta rodada. Não representam verificação de quitação fiscal.
