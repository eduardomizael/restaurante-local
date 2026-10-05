# ADR-0032 — Atendimento em área útil reduzida

Status: aceita. Data: 05/10/2026. Substitui a exigência de largura mínima e a ausência de adaptação da ADR-0026.

## Contexto

A foto enviada pelo usuário mostra controles cortados lateralmente e na parte inferior do atendimento, sem rolagem da página. A largura mínima de 1440 px e o `overflow: hidden` do corpo impediam acesso quando a área CSS disponível era menor. A resolução física não garante a área útil do navegador, devido à escala do Windows, zoom e barras.

## Decisão

Remover a largura mínima do corpo e permitir rolagem da página. Preservar o layout de três áreas simultâneas nas telas grandes. Abaixo de 1440 px de largura ou até 850 px de altura, usar altura natural, listas com rolagem local e limites de altura, colunas flexíveis e ações empilhadas. Até 1100 px, produtos e itens se empilham; até 700 px, as comandas também. Cabeçalho e busca podem quebrar linha. Manter alvos mínimos de 48 × 48 px.

Dimensionar linhas dos grids roláveis pelo conteúdo para evitar sobreposição de descrições e preços. Preservar identificadores de listas e o mecanismo existente de preservação de rolagem HTMX.

Por solicitação do usuário em 05/10/2026, a ordem horizontal é: comandas abertas à esquerda, detalhes da comanda no centro e **Adicionar produtos** à direita. A largura maior permanece destinada aos produtos; a divisória fica à esquerda desse painel. Quando a área exige empilhamento, os detalhes precedem os produtos, seguindo a mesma ordem do HTML e da navegação por teclado.

## Alternativas e consequências

Exigir tela cheia ou reduzir zoom não resolve todas as escalas e diminui os controles touch. A adaptação aumenta a rolagem vertical em áreas menores, mas mantém subtotal, impressão, cancelamento e busca alcançáveis. Em telas grandes, subtotal e ações continuam fora da rolagem dos itens. Sem migration ou mudança nas regras comerciais.

## Validação e limites

42 testes de atendimento, diálogo e catálogo aprovados. Chrome headless com HTML gerado pelos templates Django e banco isolado em memória: doze comandas, treze atalhos, seis pesagens e sete itens. Áreas CSS verificadas: 1920 × 1200, 1920 × 1080, 1366 × 640, 1280 × 720, 1024 × 600, 800 × 600 e 390 × 650. Sem excedente horizontal na página, ações dentro do conteúdo rolável e alvos de pelo menos 48 px. As duas áreas de 1920 px mantiveram ausência de rolagem da página; as demais permitiram rolagem vertical. Excedentes das listas permaneceram roláveis.

Capturas locais em `outputs/touch-1280x720.png` e `outputs/touch-1920x1200.png`, fora do Git. A verificação de layout usa HTML estático com o CSS real; não simula gestos físicos nem valida atualizações HTMX. Nenhuma COM, impressão física ou atualização da máquina final foi executada. A confirmação no equipamento da foto permanece pendente.
