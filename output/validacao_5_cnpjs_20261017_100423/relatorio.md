# Validação real de cinco CNPJs

Executada em 17/10/2026, das 10:05 às 10:11 (Brasília), usando uma instância local nova da API com o código atual e acesso real aos portais da Receita. Nenhum scraper foi simulado. Foram feitas 15 requisições HTTP, sequencialmente.

**Resultado: validação integral não aprovada.** Três consultas DASN retornaram HTTP 200 com payloads consistentes. As demais consultas encontraram os impedimentos abaixo.

| CNPJ | Completa | DASN | Optantes |
| --- | --- | --- | --- |
| 43.996.591/0001-01 — ELIANE | 502 — CAPTCHA | 502 — conferência Optantes | 502 — painel de eventos |
| 45.726.608/0001-36 — IVANUSA | 502 — CAPTCHA | 200 — aprovada | 502 — painel de eventos |
| 53.987.789/0001-82 — BARBARA | 502 — CAPTCHA | 502 — conferência Optantes | 502 — painel de eventos |
| 57.435.953/0001-08 — JOSEANE | 502 — CAPTCHA | 200 — aprovada | 502 — painel de eventos |
| 12.309.631/0001-76 — FRANCISCO | 502 — CAPTCHA | 200 — aprovada | 502 — painel de eventos |

## Resultados DASN obtidos

- IVANUSA: cinco declarações, sem pendências retornadas; MEI não marcada como baixada.
- JOSEANE: cinco declarações, baixa em 26/08/2025 e pendência do ano de 2025 preservadas simultaneamente.
- FRANCISCO: cinco declarações, sem pendências retornadas; MEI não marcado como baixado.
- ELIANE e BARBARA: DASN respondeu 33001 e iniciou a conferência em Optantes. A falha em Optantes impediu a confirmação, sem devolver listas vazias como sucesso.

Os três payloads HTTP 200 passaram pela validação dos modelos e pelas verificações de presença de declarações, razão social e consistência de pendências/baixa. Esses resultados descrevem as respostas obtidas neste teste, sem comprovar quitação fiscal.

## Impedimentos encontrados

1. **Cadastro CNPJ:** o CAPTCHA não foi resolvido. A variável `NOPECHA_API_KEY` não está configurada neste ambiente. Todas as consultas completas terminaram com HTTP 502 na etapa cadastral.
2. **Optantes:** os cinco CNPJs terminaram com `Optantes - Eventos Futuros (Simples Nacional): limites do painel inválidos`. Uma captura adicional confirmou que os painéis de eventos e Transportador estão em `#maisInfoComplementar`, dentro de `#maisInfo`. O snapshot exige que o pai imediato seja `#maisInfo`, portanto marca esses painéis como não complementares e os rejeita.
3. **Segundo problema no snapshot real de ELIANE:** o intervalo do histórico SIMEI também contém a seção de períodos IBS/CBS com `Informação indisponível`. Um experimento local ajustando somente a identificação por ancestralidade alcançou outra falha, `Períodos Anteriores (SIMEI): consulta incompleta ou erro da origem`. Assim, corrigir somente o pai do painel não basta para esse caso.

Nenhum arquivo da aplicação foi alterado nesta validação. Os problemas de Optantes estão em trechos fora da simplificação anterior e foram registrados separadamente.

## Evidências

- `relatorio.json`: status HTTP, respostas completas, duração e resultado das verificações das 15 chamadas.
- `recuperacao.log`: códigos locais de execução e tentativas, sem cookies ou tokens.
- `optantes_diagnostico.json`: estrutura dos painéis da captura adicional de ELIANE.
- `optantes_snapshot.json`: snapshot fiscal que reproduz a falha sem nova consulta externa.
- `optantes_diagnostico.png`: captura visual da página recebida.
- `validar.py` e `diagnosticar_optantes.py`: scripts usados na validação e no diagnóstico.
