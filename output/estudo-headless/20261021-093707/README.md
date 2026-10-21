# Instrumento descartável: Chrome invisível

Não é configuração da DocAPI e não altera arquivos do produto. Usa o workspace atual, inclusive mudanças pendentes. Cada caso cria um servidor loopback próprio em subprocesso sem console; o modo de controle encaminha os parâmetros originais. O braço `headless` troca somente esse parâmetro e remove posição/tamanho de janela. A fábrica e limpeza originais permanecem em uso.

Da raiz do projeto, com o Python existente:

```powershell
.\.venv\Scripts\python.exe output/estudo-headless/20261021-093707/test_harness.py
.\.venv\Scripts\python.exe output/estudo-headless/20261021-093707/study.py smoke
.\.venv\Scripts\python.exe output/estudo-headless/20261021-093707/study.py real --group cnpj
.\.venv\Scripts\python.exe output/estudo-headless/20261021-093707/study.py real --group dasn
.\.venv\Scripts\python.exe output/estudo-headless/20261021-093707/study.py real --group optantes
.\.venv\Scripts\python.exe output/estudo-headless/20261021-093707/study.py real --group complete
```

O ensaio local precisa de Chrome, mas não acessa Receita ou solver. `real` exige `smoke-summary.json` aprovado e `suite-result.json` com exit code zero. A matriz possui 2 cadastros, 5 DASN, 5 Optantes e 1 completa; cada caso é pareado controle/invisível. Cada par com falha, divergência, aumento de tentativas/bloqueios, falha de limpeza ou janela/foco no invisível é repetido somente uma vez. Nenhuma execução sobrescreve diretório já existente. Para reproduzir uma rodada completa, copiar somente os scripts para outro diretório exclusivo sob `output/estudo-headless/`, gerar os manifestos e executar novamente a suíte nesse diretório.

O timeout HTTP é 800 segundos, abrangendo a soma dos módulos. Isso não altera os prazos internos da aplicação. Os logs coletados admitem somente o vocabulário diagnóstico local. Detalhes de falha HTTP e stderr do servidor não são salvos. Respostas fiscais de sucesso são mantidas para comparação; revisar antes de compartilhar.

O observador usa WinEvent fora de contexto, com message loop em thread dedicada, para criação, exibição, ocultação, destruição e foreground. O controle local deve gerar janela e o headless não deve gerar janela/foreground. Eventos iniciais são guardados em memória para associação posterior aos PIDs da árvore experimental. Inventários complementares ocorrem aproximadamente a cada 100 ms. Só eventos próprios são salvos; eventos externos viram uma contagem, sem títulos/conteúdo. O mecanismo não oferece garantia absoluta contra flashes que o Windows não notifique. Referências: [SetWinEventHook](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setwineventhook), [constantes de eventos](https://learn.microsoft.com/en-us/windows/win32/winauto/event-constants).

Ao finalizar cada chamada, o harness solicita encerramento do servidor e espera saída. Depois verifica os processos conhecidos; encerramento forçado é limitado aos descendentes identificados, conferindo o horário de criação para evitar matar PID reutilizado. Qualquer intervenção conta como falha de limpeza. Não usar `taskkill /IM chrome.exe`, não encerrar Chrome de usuário e não reiniciar servidor original.

`windows.json` preserva eventos e inventários; `worker-events.jsonl` contém parâmetros e diagnósticos locais; `result.json` contém resposta validada, duração e indicadores. `pairs-<grupo>.json` mantém as duas rodadas quando necessárias. Nenhuma aprovação local implica adoção do modo invisível no produto.
