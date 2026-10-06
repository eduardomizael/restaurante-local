# ADR-0033 — Atendimento na área CSS do PC integrado

Status: aceita por solicitação do usuário. Data: 05/10/2026. Complementa ADR-0032 e substitui a referência principal de dimensionamento da ADR-0026.

## Contexto

Medição enviada pelo usuário no equipamento: `screen` 1280 × 800, área disponível 1280 × 760, `innerWidth`/`innerHeight` 1280 × 673 e `devicePixelRatio` 1,5. A resolução física informada de 1920 × 1200 não representa a área CSS entregue ao aplicativo. A medição anterior de cerca de 1260 × 670 era uma aproximação visual no Chrome do computador de desenvolvimento.

## Decisão

Adotar **1280 × 673 pixels CSS** como referência principal do atendimento. Para largura acima de 1100 px e altura entre 600 e 850 px, aproveitar a altura do navegador com cabeçalhos, espaçamentos e cartões compactos. Manter comandas à esquerda, detalhes no centro e produtos à direita. A faixa de pesagens mantém descrição, identificação, horário, preço/kg e ações, com rolagem horizontal para o excedente e vertical se uma descrição muito longa exigir.

Listas de comandas, itens, atalhos e catálogo rolam dentro de seus painéis. Subtotal, impressão e cancelamento ficam fora da lista de itens; Nova comanda e busca permanecem acessíveis. Atalhos e catálogo usam três colunas. Preservar alvos de pelo menos 48 × 48 px e identificadores usados pela preservação de rolagem HTMX. Sem esconder controles ou dados comerciais para caber.

Manter a rolagem da página como saída quando avisos, nome extenso do restaurante ou área ainda menor aumentarem a altura mínima. Abaixo dos limites desse modo compacto, permanece a adaptação da ADR-0032. Não exigir mudança de zoom ou escala do equipamento.

## Validação e limites

35 testes de atendimento e diálogo aprovados. Chrome headless, templates Django reais, banco isolado em memória e CSS local: doze comandas, treze atalhos, seis pesagens e sete itens com descrições extensas. Em **1280 × 673**, sem excedente horizontal ou vertical da página; Nova comanda, busca, subtotal, impressão e cancelamento dentro da área visível, listas excedentes roláveis e botões de pelo menos 48 px.

Conferidos também 1280 × 720, 1366 × 640, 1920 × 1080, 1920 × 1200, 1024 × 600, 800 × 600 e 390 × 650. As áreas menores permitem rolagem da página. Estado sem seleção/pesagens cabe na referência; mensagens de conexão/erro e nome extenso permitem rolagem adicional sem cortar ações. Captura em `outputs/touch-1280x673.png`, fora do Git.

Verificação visual e geométrica em HTML estático: não comprova gesto físico ou interação HTMX no equipamento. Sem migration, hardware, impressão real ou publicação. A confirmação na máquina touch depende de instalar a versão com esta alteração.
