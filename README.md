# docapi

Execute `python main.py --server` e envie `POST /consultar/cnpj` com
`{"cnpj":"37482317000111"}`. CNPJ com mascara tambem e aceito.

No Windows, com as dependencias instaladas na `.venv`:

```powershell
.\.venv\Scripts\python.exe main.py --server
```

A pagina de testes fica em `http://localhost:8000/docs`. Para usar a CLI,
execute `python main.py <CNPJ>`; `--json` acrescenta a resposta completa em JSON
ao resumo. DASN nao consultada e apresentada como tal, sem afirmar ausencia
de pendencias.

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

Homologacao de 17/10/2026: [relatorio no historico](https://github.com/felipygs/docapi/blob/df7d856c832c70c161c8b0358f034c3e3e0d8a5b/docs/validacao-cnpj-2026-10-17.md).

Logs, capturas e experimentos devem ficar em `output/`, ignorado pelo Git.
As evidencias antigas foram retiradas da pasta de trabalho e continuam no
[historico do projeto](https://github.com/felipygs/docapi/tree/864491503e8961bd5c2400c9776a6ad943d12e5d/output).

O utilitario `scripts/batch_optantes_xlsx.py` requer `openpyxl`, opcional para a
API: instale com `python -m pip install openpyxl`. O lote retoma o cache mais
recente disponivel em `output/`, inclusive de outro dia, e tenta novamente
consultas que falharam.

Para desenvolvimento, `python -m pip install -r requirements-test.txt` instala
tambem a dependencia do exportador. Execute a suite offline com
`python -B -m unittest discover -s tests -v`, com Google Chrome instalado e
`PYTHON_DOTENV_DISABLED=1` para isolar a configuracao local. O CI executa essa
suite no Python 3.12 antes de publicar a imagem.

As fachadas `app.consultar`, `app.models` e `app.captcha` preservam os imports
existentes. A coordenacao fica em `consulta_service`, os prazos e sessoes em
`execution`, e as regras de resultado DASN em `dasn_outcome`. Cada scraper
mantem seu protocolo; os parsers transformam dados sem executar consultas.

Pontos conhecidos preservados nesta refatoracao: a validacao de entrada HTTP
pode retornar 422 apesar do 400 documentado para CNPJ invalido; NoPeCHA mantem
polling por iteracoes, mensagens de erro externas e seu tipo de timeout;
cancelar a espera de `asyncio.to_thread` nao interrompe a thread do solver.
O tratamento HTTP atual tambem preserva mensagens de excecoes genericas.
Essas correcoes de comportamento exigem mudancas separadas.
