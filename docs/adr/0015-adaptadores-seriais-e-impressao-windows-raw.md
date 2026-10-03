# ADR-0015 — Adaptadores seriais e impressão Windows RAW

Status: aceita. Data: 03/10/2026.

## Contexto

O usuário autorizou integrar e testar os equipamentos instalados. A COM3 respondeu ao protocolo observado e a fila `balanca` recebeu um teste RAW. Simulação continua necessária para testes isolados e para desenvolvimento sem equipamentos.

## Decisão

Adicionar pySerial 3.5 e um adaptador serial com abertura tardia, leitura fragmentada e prazo de um segundo. Usar 9600/8N2, DTR/RTS desligados, consulta 0x04 e enquadramento estrito de 150 bytes. Extrair PESO L em gramas com Decimal; não descontar TARA novamente. Fechar a conexão após falha e tentar uma nova abertura na leitura seguinte; exigir zero antes de nova captura.

Adicionar transporte Windows RAW com ctypes, conteúdo ESC/POS local, cp860/tabela 3 e corte. Serializar somente o documento congelado. Persistir modo e nome da fila em cada trabalho. Trabalhos PREVIEW nunca são enviados pelo consumidor RAW e vice-versa. Aceitação completa pelo spooler recebe SPOOL_ACCEPTED e identificador técnico; não equivale à confirmação de papel. Falhas anteriores ao início do documento são FAILED; falhas posteriores são UNKNOWN e não têm reenvio automático.

Configurar porta e fila em tela própria, com revisão otimista. Troca de porta é aplicada entre leituras e reinicia o ciclo. A fila congelada de trabalhos existentes não muda. As views não acessam hardware. Finalização rejeita prévia criada em outro modo ou com configuração de impressora desatualizada.

`run_local` usa os equipamentos por padrão. `--simulate` e `--preview-print` selecionam independentemente os transportes de desenvolvimento. A instalação/atualização continua explícita e faz backup; a abertura não aplica migrations. Dados comerciais de validação ficam em instalação temporária independente.

## Alternativas

Manter somente simuladores adiaria uma integração já autorizada. Imprimir pelas views bloquearia HTTP e prejudicaria recuperação. Reutilizar configuração ou código do projeto anterior violaria o isolamento. Tratar retorno do spooler como papel confirmado produziria uma garantia indevida.

## Consequências

Testes automatizados usam adaptadores falsos e banco temporário. Diagnóstico físico é um comando separado e explícito. Há suporte ao quadro observado, não a todo protocolo possível da família de balanças. Limiares de estabilidade continuam pendentes de homologação completa. Chamadas do spooler podem bloquear; encerramento mantém o mutex se o worker não terminar no prazo.

## Evidência física

COM3 identificada como USB-SERIAL CH340. Leituras completas de zero e 236 g foram recebidas; o usuário confirmou 0,236 kg no visor e retorno a zero. O peso inicialmente informado era 234 g: a diferença de 2 g não foi corrigida em software. Fila `balanca`, driver POS-80 11.3.0.0, porta USB002. Trabalho RAW nº 7 teve acentos, 48 caracteres e corte confirmados pelo usuário. Falta de papel, desconexão física, sobrecarga e metrologia permanecem pendentes.
