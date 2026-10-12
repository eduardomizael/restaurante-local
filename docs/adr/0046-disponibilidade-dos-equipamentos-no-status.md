# ADR-0046 — Disponibilidade dos equipamentos no Status

Status: aceita. Data: 12/10/2026.

## Decisão

Exibir no Status dois indicadores independentes da operação comercial: acesso à balança e disponibilidade da fila da impressora no Windows. Priorizar PCs modestos e não executar I/O de hardware nas views.

A balança reutiliza exclusivamente as leituras do worker existente, sem consultas seriais extras nem outra conexão COM. Registrar em memória a última resposta válida e seu instante monotônico. Publicar falhas de leitura separadamente das falhas comerciais: um erro ao gravar a pesagem não transforma uma resposta válida em desconexão. Na leitura pausada não afirmar conectividade; em operação normal uma resposta com mais de 5 segundos perde a confirmação atual.

Em impressão RAW, iniciar explicitamente um único `PrinterMonitor` no inicializador. Consultar a configuração e a fila usando `OpenPrinterW`/`GetPrinterW`, nível 6, imediatamente e depois esperar 10 segundos após cada consulta. Nenhum documento é criado, nenhum byte é enviado à impressora. Fechar o handle em cada consulta e a conexão de banco entre ciclos. Erros viram um resultado em memória e podem se recuperar no próximo ciclo. Resultados com mais de 30 segundos são apresentados como desatualizados. Não iniciar monitor nem consultar spooler no modo de prévia/simulação.

A consulta fica separada do worker de impressão, do servidor HTTP e da balança. Uma consulta lenta não bloqueia atendimento ou envio de comandas e não provoca outras sondagens simultâneas. O monitor compartilha o sinal de encerramento e aguarda com `Event.wait`, interrompível imediatamente. Aplicar a proteção de encerramento já usada pelos workers: aguardar até 3 segundos e manter o mutex se a chamada nativa não tiver terminado. Chamadas de spooler dependem do Windows/driver e não têm timeout Python cancelável; não iniciar threads descartáveis para simular esse timeout.

O Status atualiza sua apresentação a cada 2 segundos, exibindo somente o resultado em memória. O polling do atendimento continua independente. Agrupar peso, estado da pesagem, disponibilidade, porta, última resposta, falhas e botão de pausar/retomar em um único card da balança. Manter a impressora em outro card com todas as suas informações. Exibir textos além de cores. Runtime parado ou modo simulado nunca aparece como equipamento físico confirmado.

## Limites e referências

“Disponível no Windows” significa fila consultável sem impedimento informado, não confirmação física de impressão. Informações como offline, falta de papel ou tampa aberta dependem do que o Windows/driver reporta. Não produzir página de teste automaticamente.

- [Microsoft — PRINTER_INFO_6](https://learn.microsoft.com/en-us/windows/win32/printdocs/printer-info-6).
- [Microsoft — GetPrinter](https://learn.microsoft.com/en-us/windows/win32/printdocs/getprinter).

Sem migration, escrita periódica no banco, nova dependência ou homologação de equipamento físico. Sem benchmark no PC final nesta entrega.

## Validação

Suíte completa: 306 testes executados, 1 ignorado, sem falhas. Os testes do recurso verificam consulta read-only e fechamento de handles, códigos de estado do Windows, intervalo de 10 segundos, troca de fila, recuperação de falha, encerramento interrompível e retenção do mutex quando o monitor não encerra. Para a balança, cobrem ausência de resposta e separação entre acesso ao equipamento e falha comercial. Requisições HTTP repetidas não acionam sondagens.

Chrome com banco em memória, pasta de dados temporária e estados de hardware injetados: disponibilidade, falha, pausa, resultado desatualizado e simulação. Cards alcançáveis por rolagem e sem overflow horizontal em 1024×600, 800×600 e 390×650. Nenhuma consulta a equipamento físico ou impressão real durante a validação.
