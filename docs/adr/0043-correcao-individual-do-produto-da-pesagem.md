# ADR-0043 — Correção individual do produto da pesagem

Status: aceita por solicitação explícita do usuário; validação física separada.

Data: 12/10/2026.

## Contexto

O operador precisa corrigir o produto de uma pesagem disponível diretamente pelo corpo de seu card, sem mudar o produto selecionado na balança nem as outras pesagens. A escolha mantém o peso e recalcula o total pelo preço atual do produto escolhido. Essa correção explícita amplia a preservação dos snapshots prevista na ADR-0013: mudanças comuns no cadastro continuam sem reescrever pesagens.

## Decisão

- O corpo do card é um link acessível por toque e teclado que abre o diálogo nas duas versões do atendimento. Incluir e Descartar ficam fora do link e conservam suas ações. Há página convencional para navegação sem JavaScript.
- O diálogo mostra peso, produto e total registrados, além dos produtos ativos por kg com preço e total calculado. A confirmação ocorre ao escolher o produto. Fechar ou Escape sai sem alteração.
- `change_measurement_product` altera somente produto, descrição, preço por kg, total e revisão da pesagem disponível. Peso líquido, tara, instante, identidade de captura, dispositivo e parâmetros de estabilidade permanecem. Cálculo usa centavos, gramas, Decimal e arredondamento HALF_UP existentes. Totais fora do limite não são aceitos.
- Cada pesagem recebe uma revisão, iniciada em 1 pela migration gerada `measurements.0003_measurement_revision`. Correção, consumo, descarte e liberação incrementam a revisão. Correção exige a revisão da pesagem e do produto exibidas; mudança concorrente gera conflito, sem sobrescrita silenciosa. Repetir uma correção com a revisão antiga também gera conflito.
- A gravação ocorre em transação SQLite IMMEDIATE, junto do evento `MEASUREMENT_PRODUCT_CHANGED`, com snapshots comerciais anterior/novo e peso preservado. A revisão é conferida dentro da transação, assim como a disponibilidade. Consumo e correção não podem editar simultaneamente um snapshot já utilizado.
- Os cards enviam a revisão na inclusão, rejeitando um toque baseado em valores anteriores à correção. Chamadas internas antigas do serviço podem omitir a revisão; seguem consumindo o snapshot corrente de forma transacional. Retry de inclusão já concluída retorna seu item original.
- Pesagens USED/DISCARDED não aceitam correção. Ao remover/cancelar um item e liberar a pesagem, uma nova correção é possível; os snapshots dos itens anteriores e dos documentos impressos permanecem congelados.
- Sucesso fecha o diálogo e atualiza os fragments, mantendo a comanda selecionada. Conflito mantém o diálogo com dados atuais e atualiza a lista disponível; uma pesagem já consumida ou descartada desaparece da lista e não oferece escolha.

## Alternativas e consequências

Trocar o produto da balança alteraria as próximas capturas e não resolveria a correção individual. Recriar a pesagem perderia sua identidade e dados físicos. Comparar apenas produto e preço não detectaria alteração seguida de retorno aos mesmos valores; a revisão evita esse caso.

A migration deve ser aplicada na etapa explícita de instalação/atualização com backup, nunca na abertura. Sua geração e testes não alteram o banco operacional. Não há mudança no leitor, no ciclo da balança, no spooler ou na seleção global de produto. Commit, push e publicação exigem autorização própria.

## Validação

Testes cobrem recalcular e arredondar, mudança isolada, histórico transacional, retry da captura, revisões antigas, preço alterado, produto inválido/inativo/UN, limite monetário, consumo/liberação, snapshots anteriores, CSRF, runtime, navegação convencional e dois layouts. Disputas SQLite reais usam conexões distintas para duas correções e para correção versus inclusão.
