# ADR-0017 — Cabeçalho ampliado e itens manuscritos alinhados

Status: aceita. Data: 03/10/2026. Complementa ADR-0014 e ADR-0015.

## Contexto

O usuário solicitou aumentar o nome no cabeçalho e colocar produto, preço e marcações manuais na mesma linha, seguindo a foto de referência. O documento congelado existente usa cabeçalho normal e marcações em outra linha. Alterar a renderização dessa versão mudaria documentos históricos e suas segundas vias.

## Decisão

Novos documentos usam DTO versão 2, com parâmetros de apresentação congelados em `layout`. Continuar lendo e imprimindo a versão 1 com sua apresentação original, sem migrar os snapshots existentes.

Ampliar somente o cabeçalho para duas vezes a largura e a altura. Distribuir o nome em linhas de até 24 caracteres, centralizadas, no perfil de 48 colunas. A prévia HTML separa cabeçalho e corpo; o transporte RAW aplica `GS ! 0x11` ao cabeçalho e restaura `GS ! 0x00` antes do corpo. Referência do comando: [Epson ESC/POS](https://download4.epson.biz/sec_pubs/pos/reference_en/escpos/gs_exclamation.html).

Reservar 20 colunas para todos os nomes e pelo menos seis para todos os preços, alinhados à direita. A largura do preço considera o maior valor entre as variantes históricas do documento inteiro. O restante recebe marcações `[ ]`; com preços usuais cabem seis marcações por linha. Identificar preço por quilo com `(KG)` no nome e uma legenda. Os nomes do catálogo da foto e das refeições cabem integralmente nessa coluna; nomes maiores continuam na coluna do produto, sem perder texto ou deslocar preço e marcações. Cada variante histórica conserva seu preço explícito.

Mostrar a quantidade já lançada somente quando houver lançamento. Manter itens pré-inseridos, subtotal, total manuscrito, rodapé, altura contínua e regras de finalização. O texto comercial e a fronteira do cabeçalho são compartilhados pela prévia e pelo transporte; não inserir comandos de impressora no DTO ou nas telas.

## Validação e consequências

123 testes aprovados. Novos casos verificam alinhamento, nomes longos, preços grandes, compatibilidade da versão 1 e bytes de ampliação/restauração antes de abrir o spooler. Revisão visual em instalação temporária simulada com os produtos da referência, 236 g a R$ 59,90/kg e refeição à vontade de R$ 39,90. Nenhuma alteração de schema ou de dados operacionais.

A ampliação física deste novo layout ainda precisa de confirmação em papel. Os ensaios físicos anteriores de acentos, 48 colunas e corte não comprovam o novo tamanho do cabeçalho. A aplicação em execução precisa ser encerrada pela bandeja e reaberta para carregar o código; não requer atualização de banco.
