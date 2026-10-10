# Referência de hardware — Restaurante Local

Implementação posterior aos ensaios de 10/10/2026: USECB2 e PROT F agora possuem leitores configuráveis na aplicação ([ADR-0042](adr/0042-leitores-seriais-e-protocolo-configuravel.md)). A seleção física deve coincidir com a tela. PROT F registra líquido com sinal e instabilidade; a tara não é informada nesse quadro. Testes isolados aprovados; novo fluxo integrado com banco operacional ainda não foi ensaiado. As observações abaixo sobre falta de adaptador PROT F descrevem a etapa anterior.

Conclusão do ensaio PROT F de 10/10/2026: após retirada confirmada pelo usuário, consulta 0x04 recebeu nove respostas de nove bytes com peso líquido **−0,494/−0,496 kg**, sem silêncio durante dez segundos. O PROT F permite observar o valor negativo nesta instalação, ao contrário do silêncio observado nas consultas anteriores USECB2 com visor negativo. A sonda não interpreta comercialmente esses dados. A aplicação ainda não tem adaptador PROT F: é necessária implementação de enquadramento, sinal, instabilidade e rearme para tara negativa antes de adotá-lo na operação. O protocolo transmite líquido e estado, sem campo de tara no quadro observado. Foi orientado retorno manual a USECB2 antes de reabrir a aplicação.

Ensaio de protocolos em 10/10/2026, autorizado e com aplicativo fechado: escuta passiva de dez segundos em USECB2 recebeu zero bytes; após troca manual para PROT F, escuta passiva de dez segundos também recebeu zero bytes. No PROT F, consulta 0x04 respondeu com pesos líquidos 0,398 e 0,396 kg e uma indicação `IIIIII`, compatível com instabilidade descrita no manual. Pesos chegaram com envelope STX/ETX e sinal positivo representado por espaço, em nove bytes; a indicação observada de seis letras I entre STX/ETX tem oito bytes. Blocos de leitura podem fragmentar o envelope. Esse resultado comprova consulta nesse protocolo, mas não envio espontâneo em outros modos ou acionamento por tecla. Sonda bruta não criou pesagens nem enviou impressão. Leitura negativa e conclusão do ensaio ainda pendentes.

Recuperação de 10/10/2026: ausência completa de resposta foi identificada no registro do runtime como motivo do rearme durante a colocação. O tratamento passa a separar silêncio breve de quadro inválido/desconexão, conforme [ADR-0041](adr/0041-recuperacao-limitada-de-silencio-serial.md). O ajuste de software está validado com transporte injetado; a origem física da intermitência permanece indeterminada.

Complemento de 10/10/2026: tolerância de retirada ampliada de 0/+2 g para **−2/+2 g**, após relato do usuário sobre oscilação bilateral. Três leituras consecutivas recentes, sem movimento, continuam obrigatórias. O parser preserva o sinal do peso líquido; pesos negativos não são medições comerciais. Quadros negativos ainda não foram observados fisicamente; ensaios sintéticos passaram. Consulte [ADR-0040](adr/0040-retorno-proximo-de-zero-na-balanca-fisica.md). Esse complemento prevalece sobre a faixa unilateral registrada no ensaio abaixo.

Consolidado em 03/10/2026 a partir de evidências do projeto Restaurante. Este documento não exige acesso ao projeto anterior e não declara o aplicativo novo homologado.

## Balança

Perfil observado para US 31/2 POP-S: USB/serial por COM; solicitação pelo byte 0x04, sem terminador; 9600 baud, 8 bits, sem paridade, 2 stop bits; DTR/RTS desligados; timeout de referência 1 segundo. Porta inicial deste projeto: COM3, configurável.

Atualização de 10/10/2026: usuário confirmou USECB2 e especificações 6/15/31 kg, divisões 2/5/10 g, mínimo 40 g. Foto do manual descreve 80 bytes nesse protocolo, mas consulta física autorizada recebeu dez quadros completos de **150 bytes**, sem falhas (líquido 0 g, tara informativa 308 g). Ensaio seguinte de 60 consultas mostrou 396 g e depois 0 g: 55 respostas válidas de 150 bytes e cinco ausências completas de resposta após duas consultas (~2 s), inclusive após retorno a zero. Recuperação sem trocar protocolo/tara; porta fechada ao final. Conservar o parser correspondente aos quadros observados. A causa do silêncio ainda não foi determinada. Resíduo de 2 g relatado com vento motivou três leituras consecutivas entre 0 e 2 g para rearme e mínimo comercial de 40 g no runtime físico, conforme [ADR-0040](adr/0040-retorno-proximo-de-zero-na-balanca-fisica.md). Não houve calibração ou compensação do peso comercial. Confirmação do novo rearme no aplicativo ainda exige ensaio.

Quadro observado de 150 bytes, recebido em blocos, sem quebra de linha obrigatória. Exemplo textual do conteúdo:

```text
DATA: 00/00/00 VALID.: 00/00/00 TARA: 0.000kg PESO L: 0.252kg R$/kg: 0.00 TOTAL R$: ...
```

PESO L já é o peso líquido mostrado pelo equipamento. Não subtrair TARA novamente. Extrair somente PESO L como peso comercial, converter decimal para gramas sem float e preservar tara como informação. Os valores monetários do quadro não são autoridade comercial: o aplicativo usa seu próprio cadastro.

Referências iniciais de estabilidade: três leituras consecutivas dentro de 2 g, mínimo de 10 g e rearme após retorno a até 10 g. A ausência de INSTAVEL/UNSTABLE/MOTION/MOVIMENTO não comprova estabilidade. Não copiar essa hipótese como garantia física. Validar estabilidade, resolução e limites no equipamento antes de produção.

Pendências: capturas completas de zero, oscilação, pesos conhecidos, sobrecarga, erro, fragmentação e desconexão; validação do enquadramento e reconexão; identificação exata do modelo instalado. O novo fluxo captura automaticamente uma medição por prato e espera retirada; não depende de escolha do cliente nem de endpoint remoto.

## Impressora

Equipamento informado pelo usuário: mesma impressora térmica do projeto base, fila Windows balanca e bobina contínua de 80 mm. O formato do driver Printer Paper (80 x 210 mm) não impõe altura fixa ao documento.

Evidência de referência: ESC/POS, envio RAW pelo spooler Windows, perfil ensaiado de 48 colunas, inicialização, alinhamento, negrito, fontes, avanço e corte. Nome da fila é configurável, não identifica fabricante. cp860 é candidata de codificação, com acentos/cedilha a homologar.

Validar largura útil, comprimento variável, corte, legibilidade, falta de papel, desconexão e resultado incerto. Aceitação pelo spooler não prova saída física. Sem reenvio automático de trabalho incerto. TCP 9100 e QR Code não fazem parte do MVP e não foram comprovados por esta consolidação.

## Ensaios locais autorizados em 03/10/2026

COM3 identificada como USB-SERIAL CH340; quadro completo de zero e leituras de 236 g obtidos com o adaptador próprio. O usuário confirmou 0,236 kg no visor e retorno a zero. Peso inicialmente informado: 234 g; diferença de 2 g não compensada por software. Nova colocação apresentou 234 g. Respostas fora do enquadramento foram rejeitadas e reiniciaram a exigência de zero; não foram transformadas em peso comercial.

Fila `balanca`, driver POS-80 11.3.0.0, porta USB002. Teste RAW nº 7 teve acentos cp860/tabela 3, 48 caracteres e corte confirmados pelo usuário. Estes pontos estão comprovados para o equipamento instalado. Falta de papel, desconexão, documentos longos e homologação metrológica permanecem pendentes. Consulte [implementação](IMPLEMENTACAO_HARDWARE_REAL.md) e [ADR-0015](adr/0015-adaptadores-seriais-e-impressao-windows-raw.md).

Continuação do ensaio local: captura automática persistiu uma única medição de 236 g, mesmo com oscilação de 234–236 g. A comanda nº 2 foi enviada uma vez como trabalho RAW nº 8; o usuário confirmou peso, subtotal R$ 23,60 com preço fictício de teste, campos manuscritos e corte. A comanda nº 1 permaneceu aberta. Retorno ao zero, recuperação sem duplicação após reinício e liberação da COM3 foram verificados. Uma consulta vazia admite repetição limitada conforme [ADR-0016](adr/0016-repeticao-limitada-de-consulta-sem-resposta.md); quadros inválidos continuam sendo recusados.

## Modelo impresso e origem

[Fotografia fornecida pelo usuário](references/order-slip-reference.png). É referência de apresentação, não autorização para importar preços, cadastro, nome ou endereço web nela contidos. Requisitos atuais de várias refeições e linhas manuscritas prevalecem sobre o exemplo de uma única refeição.

Origem histórica consultada em 03/10/2026: docs/PROTOCOLO_BALANCA.md, docs/VALIDACAO_HARDWARE.md, scale_agent/src/scale_agent/protocols/serial.py e runtime.py do projeto Restaurante. Esses caminhos identificam a proveniência, não dependências ou instruções para o aplicativo novo.
