# Consulta completa: diagnostico de 20/10/2026

O log anterior registrava `POST /consultar` com HTTP 502, sem a mensagem do
erro nem os diagnosticos dos modulos. Nao e possivel atribuir retrospectivamente
esse 502 a uma etapa especifica.

## Reproducao com 45.726.608/0001-36

Foram executadas consultas reais contra os portais, sem mocks:

| Execucao | Resultado | Duracao |
| --- | --- | --- |
| Orquestracao direta, antes dos ajustes | Cadastro, DASN e Optantes completos | 51,36 s |
| `POST /consultar`, antes dos ajustes | HTTP 200, contrato validado | 40,01 s |
| `POST /consultar`, servidor reiniciado com ajustes | HTTP 200, contrato validado | 32,62 s |

Na primeira reproducao, a DASN recebeu bloqueio de captcha na tentativa 1 e
concluiu na tentativa 2, usando a recuperacao ja existente. Isso demonstra uma
falha transitoria recuperada nessa execucao; nao comprova a causa do 502 anterior.

Na ultima chamada, os logs registraram CNPJ em 12,964 s, DASN em 9,673 s e
Optantes em 9,209 s, todos com `codigo=ok`. A resposta inclui os tres blocos,
cinco declaracoes DASN e identidade Optantes correspondente ao CNPJ consultado.

## Ajustes

- O cadastro passa a ter prazo total de 180 segundos, abrangendo abertura,
  aquisicao e tentativas de captcha. Ao expirar, a rota retorna HTTP 504;
  o fechamento continua com a tolerancia existente de ate cinco segundos.
- O comando `python main.py --server` ativa os logs INFO de `app`, antes
  suprimidos pela configuracao padrao. Cada modulo registra inicio e resultado
  com duracao, tentativa e codigo local, sem mensagem externa, CNPJ ou token.
- As etapas continuam sequenciais. Os prazos sao por modulo e os resultados
  das etapas ja concluidas nao sao novamente consultados nas tentativas seguintes.

## Evidencias

- [output/server.before-diagnostico.stdout.log](https://github.com/felipygs/docapi/blob/864491503e8961bd5c2400c9776a6ad943d12e5d/output/server.before-diagnostico.stdout.log): HTTP 502 anterior.
- [output/diagnostico_completa_45726608000136.json](https://github.com/felipygs/docapi/blob/864491503e8961bd5c2400c9776a6ad943d12e5d/output/diagnostico_completa_45726608000136.json): primeira reproducao.
- [output/diagnostico_completa_http_45726608000136.json](https://github.com/felipygs/docapi/blob/864491503e8961bd5c2400c9776a6ad943d12e5d/output/diagnostico_completa_http_45726608000136.json): HTTP antes dos ajustes.
- [output/validacao_completa_45726608000136.json](https://github.com/felipygs/docapi/blob/864491503e8961bd5c2400c9776a6ad943d12e5d/output/validacao_completa_45726608000136.json): HTTP com os ajustes.
- [output/server.stderr.log](https://github.com/felipygs/docapi/blob/864491503e8961bd5c2400c9776a6ad943d12e5d/output/server.stderr.log): diagnosticos por modulo do servidor atualizado.
- [output/testes-consulta-completa.log](https://github.com/felipygs/docapi/blob/864491503e8961bd5c2400c9776a6ad943d12e5d/output/testes-consulta-completa.log): suite local de regressao.

Os testes de regressao verificam prazo total, liberacao da sessao, HTTP 504
sem dados parciais e ativacao dos diagnosticos pelo comando do servidor.
Suite completa: **150 testes aprovados em 268,742 segundos**, sem falhas,
com `.venv/Scripts/python.exe -m unittest discover -s tests -v`.
Compilacao Python e `git diff --check` tambem aprovados. A revisao do ajuste
nao encontrou problemas que exigissem alteracao.
As chamadas bem-sucedidas nao garantem disponibilidade futura dos portais.
