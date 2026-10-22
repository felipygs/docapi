# Homologação do cadastro CNPJ — 17/10/2026

A consulta `POST /consultar/cnpj` foi adaptada ao portal atual da Receita
Federal, que usa uma aplicação Angular e respostas JSON para cadastro e QSA.
O contrato público `CadastroResponse` foi preservado.

## Alterações

- Carregamento automático do `.env`, sem substituir variáveis do ambiente.
  A chave fica em `NONECAP_API_KEY`; `.env` permanece ignorado pelo Git.
- Navegação pela página atual, preenchimento explícito do CNPJ e resolução
  do hCaptcha com NoneCap. O callback registrado pelo portal recebe o token
  e habilita o botão de consulta. O user agent retornado pelo solver é usado
  nas requisições seguintes.
- Aquisição das respostas geradas pela própria interface da Receita.
  O QSA é consultado pelo botão, preservando a sessão e o estado da página.
- Validação de identidade, nome, datas, situação, natureza jurídica, CNAEs e
  QSA. Falha de aquisição do QSA não produz uma lista de sócios vazia.
- Capital social continua expresso em centavos. Valores mascarados com
  asteriscos são convertidos para `null`.

## Evidências reais

As chamadas foram feitas a um servidor Uvicorn local, acessando Receita e
NoneCap reais, sem substituir navegador, scraper ou solver.

| CNPJ | Nome retornado | HTTP | Capital em centavos | Integrantes no QSA |
|---|---|---|---:|---:|
| 37.482.317/0001-11 | THIARLLES BARBOSA DE SOUSA | 200 | 400000 | 0 |
| 00.000.000/0001-91 | BANCO DO BRASIL SA | 200 | 12000000000000 | 41 |

No primeiro caso, o comprovante mostrou situação ATIVA, abertura em
22/06/2020, CNAE principal 49.30-2-01 e endereço em Imperatriz/MA.
O portal informou expressamente que a natureza jurídica 213-5 não permite
preenchimento do QSA; a ausência de integrantes foi confirmada na origem.

Os JSONs retornados estão em
[output/homologacao_cnpj_20261017/http_37482317000111.json](https://github.com/felipygs/docapi/blob/864491503e8961bd5c2400c9776a6ad943d12e5d/output/homologacao_cnpj_20261017/http_37482317000111.json) e
[output/homologacao_cnpj_20261017/http_00000000000191.json](https://github.com/felipygs/docapi/blob/864491503e8961bd5c2400c9776a6ad943d12e5d/output/homologacao_cnpj_20261017/http_00000000000191.json).
As capturas iniciais de comprovante/QSA, respostas da origem e scripts de
reprodução estão no mesmo diretório. Nenhuma credencial ou token foi gravado
nessas evidências.

## Limites observados

Duas chamadas iniciais do CNPJ informado concluíram a aquisição, mas receberam
502 porque o fechamento do Chrome ultrapassou os cinco segundos permitidos
enquanto havia testes de navegador concorrentes. Uma medição posterior sem
essa concorrência fechou o navegador em 0,48 segundo; a chamada HTTP seguinte
retornou 200 em 15,64 segundos. A proteção de limpeza foi mantida.

O resultado comprova esses casos nesta data. Disponibilidade da Receita,
resolução de captcha e tempo de fechamento do navegador continuam sujeitos
às condições externas e da máquina. Nenhuma alteração foi implantada em
servidor remoto.

## Verificação local

Os testes novos cobrem conversão do cadastro, QSA com sócios, filial, CNAEs
numerosos, identidade divergente, campos incompletos, resolução NoneCap,
proteção de credenciais nos erros, callback da interface, captcha rejeitado
e falha HTTP do QSA. Os testes de aquisição usam Chromium real com rede
interceptada por fixtures locais; não gastam créditos.

Comando da suíte completa:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Log: [output/homologacao_cnpj_20261017/testes-locais.log](https://github.com/felipygs/docapi/blob/864491503e8961bd5c2400c9776a6ad943d12e5d/output/homologacao_cnpj_20261017/testes-locais.log).
Resultado: **146 testes passaram**, sem falhas, em 540,479 segundos.
Compilação Python (`compileall`) e `git diff --check` também passaram.

Referência de integração: [API oficial NoneCap](https://nonecap.com/api-reference/).
