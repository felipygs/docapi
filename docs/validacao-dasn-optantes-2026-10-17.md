# Referência validada: DASN e Optantes

Em **17/10/2026, das 10:27:34 às 10:30:04, horário de Brasília**, os cinco
CNPJs abaixo passaram nas duas rotas individuais: **dez chamadas reais,
dez respostas HTTP 200**, com validação dos modelos públicos e conferências
de identidade e consistência. A execução usou uma instância nova da API,
Windows, Python 3.14.7 e Chrome, com acesso aos portais reais da Receita.

Este resultado fica registrado como referência verificada para o projeto.
DASN e Optantes usam submissões normais e podem recuperar bloqueios em sessão
nova, dentro de até três tentativas e 180 segundos por módulo. Nesta rodada
não houve solver nem interação com desafios. O cadastro CNPJ não fez parte
da validação.

## Consultas aprovadas

| CNPJ | DASN | Optantes |
| --- | --- | --- |
| 43.996.591/0001-01 | 200 — 33001 confirmado por Optantes | 200 |
| 45.726.608/0001-36 | 200 — declarações obtidas | 200 |
| 53.987.789/0001-82 | 200 — 33001 confirmado por Optantes | 200 |
| 57.435.953/0001-08 | 200 — declarações obtidas | 200 |
| 12.309.631/0001-76 | 200 — declarações obtidas | 200 |

- Em 53.987.789/0001-82, Optantes recebeu bloqueio durante a conferência DASN
  e concluiu na segunda tentativa.
- Em 57.435.953/0001-08, DASN recebeu bloqueio e concluiu na segunda tentativa.
  A resposta preservou simultaneamente a baixa em 26/08/2025 e a pendência de 2025.
- Nos dois desfechos 33001, `declaracoes`, `pendentes`, `mei_baixada` e
  `data_baixa` permaneceram `null`, pois não foram consultados. Isso não confirma
  ausência de pendências.
- Os históricos Simples/SIMEI foram mantidos separados, com contagens de
  3/0, 1/1, 0/0, 1/1 e 2/2, respectivamente, na ordem da tabela.
- Situações e históricos IBS/CBS foram preservados em `dados_adicionais`.

As respostas resumidas e os dados da verificação estão no
[arquivo de evidências](validacoes/2026-10-17-dasn-optantes.json).

## Correções confirmadas pelo teste real

O portal retornou painéis de Eventos Futuros e Transportador sob
`#maisInfoComplementar`, descendente de `#maisInfo`. O parser passou a reconhecer
essa ancestralidade, mantendo a rejeição de painéis fora de `#maisInfo`.

O histórico IBS/CBS passou a delimitar seu próprio intervalo. Seus textos,
inclusive `Informação indisponível`, e suas tabelas ficam em dados adicionais,
sem contaminar a interpretação do histórico SIMEI.

A captura anterior bem-sucedida não continha esse contêiner nem o histórico
IBS/CBS. A exigência de pai direto já existia no commit `0fd8427`, anterior à
simplificação. A comparação isolada com o HEAD confirmou que a versão anterior
de Optantes rejeitava os novos textos e a versão corrigida concluía a consulta.

## Verificação local

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

**137 testes aprovados**, sem falhas ou testes ignorados, em 553,447 segundos.
A suíte usou páginas locais e respostas interceptadas e foi executada depois
das dez consultas reais. Inclui retry, prazo global, cancelamento, fechamento,
integridade DASN, conferência 33001, respostas HTTP e quatro regressões novas
dos painéis e históricos IBS/CBS.

`git diff --check` aprovado. O OpenAPI permaneceu idêntico ao estado anterior
da correção do parser; as mudanças de recuperação e do desfecho 33001 já
estavam presentes nessa referência.

Os resultados descrevem essa execução. Estados fiscais e disponibilidade da
origem podem mudar; sucesso de consulta não comprova quitação fiscal.
