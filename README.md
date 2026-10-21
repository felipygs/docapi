# docapi

Execute `python main.py --server` e envie `POST /consultar/cnpj` com
`{"cnpj":"37482317000111"}`. CNPJ com mascara tambem e aceito.

Instale `requirements.txt` e configure `NONECAP_API_KEY` no `.env` da raiz
(modelo em `.env.example`). A aplicacao carrega esse arquivo automaticamente;
variaveis ja definidas no ambiente tem prioridade. O `.env` e ignorado pelo Git.
Em Docker, injete a variavel com `--env-file .env`.

A consulta completa (`POST /consultar`) executa cadastro, DASN e Optantes
sequencialmente. O cadastro tem prazo total de 180 segundos, incluindo
abertura do navegador e tentativas de captcha; DASN e Optantes mantem seus
prazos de 180 segundos por modulo, com ate cinco segundos adicionais por
fechamento de navegador. Prazo esgotado retorna HTTP 504. O servidor registra
inicio, duracao e codigo de resultado por modulo sem registrar CNPJ ou tokens.

O cadastro usa o portal atual da Receita, com hCaptcha via
[NoneCap](https://nonecap.com/api-reference/), e consulta o QSA na mesma sessao.
O retorno mantem `CadastroResponse`, incluindo capital social em centavos.
Dados de outro CNPJ, resposta incompleta ou falha no QSA retornam erro;
socios vazios representam ausencia confirmada na origem.

Homologacao de 17/10/2026: [relatorio](docs/validacao-cnpj-2026-10-17.md).
