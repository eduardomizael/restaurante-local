# ADR-0034 — Versão alternativa do atendimento

Status: aceita para comparação; escolha definitiva e homologação física pendentes.

Data: 05/10/2026.

## Contexto

O usuário forneceu HTML do Google Stitch e pediu uma versão alternativa, preservando a tela atual. A referência organiza pesagens no topo, comandas à esquerda e itens à direita. O PC integrado oferece área CSS de 1280 × 673, apesar dos 1920 × 1200 pixels físicos.

## Decisão

Disponibilizar `/attendance/alternative/`, acessível em **Status → Comparar telas de atendimento → Versão alternativa**. A rota padrão continua com o atendimento atual. A alternativa oferece retorno à versão atual, preservando a comanda selecionada.

Usar pesagens em faixa com rolagem horizontal, comandas e itens com rolagem interna e rodapé com subtotal, prévia/impressão e cancelamento. **Adicionar produto** abre um diálogo com acesso rápido, catálogo e busca; escolher um produto abre o teclado numérico existente. Sem JavaScript, os links oferecem navegação convencional.

Manter o estilo verde, os assets locais e alvos de toque de pelo menos 48 × 48 pixels. Não copiar CDN, fontes externas ou regras comerciais sugeridas pela referência. Serviços, seletores, dinheiro, pesagens e documentos continuam compartilhados entre as versões. O parâmetro explícito `layout=alternative` preserva a apresentação nas ações e retornos; não introduz preferência global ou alteração do banco.

## Alternativas e consequências

Substituir diretamente a tela existente impediria a comparação solicitada. Uma cópia independente das regras de negócio criaria divergências; a alternativa reutiliza as operações e os fragmentos comuns. Os detalhes da comanda têm um template próprio, selecionado também nas atualizações HTMX.

Em áreas menores, liberar rolagem da página e empilhar painéis conforme a largura. Não existe migration. A escolha definitiva do layout depende da avaliação do usuário.

## Validação

Testes Django verificam separação das telas, seleção e criação de comandas, inclusão idempotente, pesquisa, atualização HTMX, confirmação e retorno de impressão em modo de prévia. Chrome com dados fictícios verificou 1280 × 673, 1920 × 1200, 1024 × 600, 800 × 600 e 390 × 650, sem corte horizontal ou alvos menores que 48 pixels. Em 1280 × 673, controles principais ficaram visíveis sem rolagem global; listas com excedente têm rolagem própria. Interações de seleção, busca, diálogos, inclusão, consumo de pesagem e remoção foram exercitadas no navegador. Não equivale a homologação no equipamento touch.
