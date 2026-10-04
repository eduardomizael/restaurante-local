# ADR-0026 — Atendimento touch em tela horizontal

Status: aceita. Data: 04/10/2026. Complementa ADR-0012.

## Contexto e decisão

O usuário definiu operação em tela touch horizontal de 1920 × 1200, sem uso em dispositivos móveis ou telas verticais. Priorizar a área de trabalho do atendimento e reduzir rolagem da página, preservando alvos de pelo menos 48 × 48 px.

O atendimento usa a altura disponível do navegador, descontando a navbar compartilhada e o cabeçalho. Remover o limite anterior de 1600 px de largura. Organizar pesagens em faixa superior e, abaixo, comandas abertas, seleção de produtos e itens da comanda em três áreas simultâneas. A coluna de produtos exibe acesso rápido e busca no catálogo permanentemente, sem expansões intermediárias. `orders/product_choice.html` compartilha o botão de inclusão entre atalhos e catálogo; ambos continuam abrindo o diálogo de quantidade.

Usar quatro colunas para atalhos, três para escolhas do catálogo e três para cartões no cadastro de produtos. Subtotal e ações de impressão/cancelamento ficam fora da rolagem dos itens. Listas de comandas, produtos, itens e pesagens preservam acesso ao excedente por rolagem local; não cortar registros para caber na tela. Manter a posição das listas durante atualizações HTMX e reiniciar a lista de itens ao trocar de comanda. Pesagens, itens históricos, valores e ações HTTP continuam iguais.

O corpo do atendimento usa `100dvh` com painéis dimensionados por flex/grid e `min-height: 0`; não depende de uma altura fixa da navbar. O layout exige largura mínima de 1440 px e elimina a adaptação específica do atendimento para empilhamento em celulares. A referência de validação é a área CSS do navegador em 1920 × 1200: escala de exibição do Windows, zoom e barras do navegador podem reduzir a área efetiva. Muitos registros e descrições extensas ainda podem exigir rolagem dentro dos painéis.

## Validação e limites

Validar o navegador na resolução de referência com instalação temporária, doze comandas, doze atalhos, seis pesagens disponíveis e sete itens. A página inteira deve medir 1920 × 1200 sem excedente horizontal/vertical; subtotal e ações devem ficar visíveis. Confirmar inclusão via diálogo, atualização de subtotal, troca de comanda, pesquisa e preservação de destinos. Não iniciar COM ou spooler durante a validação. Mudança de interface sem migration.

Resultado: 48 testes dos fluxos touch, diálogo, configuração e catálogo aprovados. Conferência em navegador confirmou área de 1920 × 1200 sem rolagem da página, doze atalhos e sete itens completos. Inclusão de duas unidades atualizou R$ 115,46 para R$ 125,46; remoção, inclusão de pesagem, troca de comanda, pesquisa e estado sem seleção foram conferidos com dados temporários. Excedente de pesagens permaneceu acessível pela rolagem horizontal do painel. Em 1920 × 1080, o subtotal e as ações também permaneceram dentro da área visível, com alvos mínimos preservados. Capturas de exemplo em `outputs/attendance-1920x1200.png` e `outputs/products-1920x1200.png`, fora do Git.
