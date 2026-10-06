# ADR-0035 — Produtos rápidos e filtro na alternativa

Status: aceita; homologação física pendente.

Data: 05/10/2026.

## Contexto

O usuário rejeitou a primeira composição da alternativa e pediu aproveitar a largura da coluna de comandas, restaurar a barra de produtos rápidos e manter o catálogo completo no botão Adicionar produto. A busca deve filtrar enquanto digita.

## Decisão

Revisar somente a versão alternativa. A coluna de comandas permanece com 248 pixels nas telas horizontais; os itens ficam ao centro e a lateral direita contém exclusivamente produtos marcados como acesso rápido. Cabeçalho e linhas de itens retomam a apresentação da tela atual. Em telas estreitas, os painéis se empilham e permitem rolagem.

O botão Adicionar produto abre um diálogo com todos os produtos ativos, sem repetir o acesso rápido. O campo Filtrar produtos atualiza o catálogo por HTMX após 200 ms sem nova digitação, substituindo requisições anteriores do próprio filtro. O filtro ignora diferenças de maiúsculas/minúsculas conforme o seletor existente; texto vazio restaura o catálogo. A inclusão usa o teclado numérico e os mesmos serviços comerciais. A navegação convencional continua disponível como alternativa sem JavaScript.

## Alternativas e consequências

Exibir o catálogo permanentemente repetiria produtos e consumiria espaço. Filtrar apenas após botão não atende ao pedido. A separação do acesso rápido e do catálogo evita IDs duplicados nos fragmentos. Não há migration nem mudança na tela padrão.

Esta decisão revisa a disposição descrita na ADR-0034. A escolha definitiva da versão e a homologação no equipamento touch continuam pendentes.

Janelas baixas preservam as três colunas quando a largura supera 900 pixels: a altura reduzida habilita rolagem, mas não desloca os produtos rápidos para baixo. O empilhamento depende somente da largura. A verificação de posição compara as coordenadas do painel de itens e dos produtos rápidos, incluindo 1280 × 550 e 1024 × 550.

O botão Adicionar produto fica no rodapé do painel de produtos rápidos, fora da lista rolável e sem encolher, assim como as ações no rodapé da comanda. Nas três colunas, a comanda aberta mantém 248 pixels e as áreas de itens e produtos rápidos dividem o espaço restante na proporção 1 : 0,8.

O topo da alternativa não exibe os títulos Atendimento local e Comandas e pesagens. Peso líquido fica à esquerda em uma área de 248 pixels; pesagens disponíveis ficam ao lado na mesma linha. Ambos pertencem ao workspace, mantendo as atualizações independentes por HTMX e o peso inicial ao criar ou trocar comanda. Somente em largura de até 700 pixels o topo se empilha.

## Validação

Testes Django cobrem a separação entre produtos rápidos e catálogo, resposta filtrada e restauração do catálogo, além das operações existentes. Verificação no Chrome com dados fictícios cobre cinco áreas de tela, seleção pelos produtos rápidos, filtro durante digitação, ausência de resultados, limpeza do filtro e inclusão por diálogo. Em 1280 × 673, ações principais permanecem visíveis, sem corte horizontal, com rolagem nas listas.
