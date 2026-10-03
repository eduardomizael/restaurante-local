# Referência de hardware — Restaurante Local

Consolidado em 03/10/2026 a partir de evidências do projeto Restaurante. Este documento não exige acesso ao projeto anterior e não declara o aplicativo novo homologado.

## Balança

Perfil observado para US 31/2 POP-S: USB/serial por COM; solicitação pelo byte 0x04, sem terminador; 9600 baud, 8 bits, sem paridade, 2 stop bits; DTR/RTS desligados; timeout de referência 1 segundo. Porta inicial deste projeto: COM3, configurável.

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
