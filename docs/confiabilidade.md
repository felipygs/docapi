# Recuperação de consultas DASN e Optantes

Cada módulo usa até três tentativas, com um navegador e contexto novos por
tentativa. Cookies e armazenamento da tentativa anterior não são reaproveitados.
As esperas entre tentativas são de 2 e 5 segundos. O prazo de recuperação é de
180 segundos por módulo; cada fechamento tem tolerância de até 5 segundos,
inclusive quando a requisição é cancelada. Falha de limpeza não substitui o
erro original da consulta e não é apresentada como sucesso.
O proxy e o cliente HTTP precisam ter timeout compatível com esse prazo.

São repetidos timeouts e falhas de rede reconhecidas. Em Optantes, respostas
HTTP 408, 429 e 5xx do carregamento complementar também permitem recuperação.
Erros desconhecidos não são automaticamente considerados transitórios.

Uma mensagem de bloqueio Captcha permite nova submissão normal em sessão limpa,
dentro do mesmo limite de três tentativas e 180 segundos. Bloqueio persistente
encerra a consulta. Não há solver, interação automática com desafios nem
repetição sem limite. Uma consulta bloqueada ou esgotada não
representa ausência de pendências. A disponibilidade da Receita continua sendo
uma dependência externa.

## Integridade dos resultados

- DASN exige nome empresarial e declarações extraídas, anos e status reconhecidos
  e datas válidas. Extinção exige data de baixa e preserva a pendência de entrega.
- Quando a página DASN exibe um CNPJ identificado, ele deve coincidir com o
  solicitado. Se esse identificador não estiver disponível, não há confirmação
  independente de identidade; o campo de entrada não é usado como prova.
- Optantes preserva a validação de completude, históricos, datas e ausência
  explícita. O CNPJ matriz deve compartilhar a raiz de oito dígitos do consultado;
  uma filial pode ter os seis últimos dígitos diferentes.
- Os modelos públicos são validados antes de aceitar sucesso. Dados incompletos
  e identidade divergente encerram a consulta sem repetir a mesma falha.

A consulta completa executa cadastro, DASN e Optantes separadamente. Se um módulo
precisar ser repetido, os módulos anteriores já concluídos não são executados de
novo. A resposta completa continua sem sucesso parcial. Cadastro CNPJ não ganhou
recuperação nesta alteração.

## Erros públicos

Uma resposta DASN 33001 recebe conferência em Optantes. Quando não há
enquadramento atual, períodos anteriores nem eventos futuros SIMEI, a API retorna
HTTP 200 com `status=nao_optante_simei_confirmado_por_optantes`, `codigo_origem=33001`
e a data da evidência. `declaracoes`, `pendentes`, `mei_baixada` e `data_baixa`
ficam `null`: não foram verificadas. Esse desfecho não é obtenção de declarações
nem prova de quitação fiscal. Se houver divergência ou falha na conferência, a
API retorna erro. A consulta completa reutiliza Optantes obtido na conferência.
O formato das respostas com declarações obtidas permanece o anterior.
Essa conferência pode consumir os prazos de ambos os módulos (DASN e Optantes),
até 180 segundos por módulo mais limpeza. Clientes que utilizam somente DASN
precisam aceitar esse tempo adicional para o desfecho 33001.

Os painéis de Optantes também podem trazer situações e históricos IBS/CBS.
Esses conteúdos são preservados em `dados_adicionais`, separados da situação
e dos históricos SIMEI; sua indisponibilidade não é interpretada como falha
na consulta SIMEI, enquadramento ou desenquadramento. Painéis complementares
podem estar em contêineres internos de `#maisInfo`, como `#maisInfoComplementar`.

O formato continua sendo `{"detail": "mensagem"}`.

| HTTP | Significado |
| --- | --- |
| 400 | CNPJ rejeitado pela consulta ou pela origem |
| 422 | Requisição rejeitada pela validação FastAPI |
| 502 | Bloqueio, indisponibilidade, dados incompletos ou identidade divergente |
| 504 | Timeout ou prazo de recuperação esgotado |

Os registros de recuperação incluem módulo, tentativa, duração e código de erro,
sem copiar CNPJ, cookies, tokens ou o texto bruto da exceção externa.

## Verificação local

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
```

A suíte inclui cenários de timeout seguido de sucesso, isolamento de sessões,
limite de tentativas, prazo global, cancelamento, fechamento e erros definitivos.
Os testes com Chrome usam páginas locais e respostas interceptadas, sem consultas
à Receita ou resolução de Captcha. Testes reais são uma validação adicional e não
garantem sucesso futuro para os mesmos CNPJs.

## Referência validada em 17/10/2026

A validação real de DASN e Optantes com cinco CNPJs concluiu as dez chamadas
com HTTP 200. Dois bloqueios foram recuperados na segunda tentativa por nova
submissão normal, sem solver. A suíte local terminou com 137 testes aprovados.

O [registro da validação](validacao-dasn-optantes-2026-10-17.md) documenta os
casos, os resultados e as correções dos painéis complementares e históricos
IBS/CBS. Esse é o comportamento verificado de referência; falhas futuras devem
ser investigadas comparando código, respostas da origem e tentativas, sem
presumir necessidade de solver para esses dois módulos.
