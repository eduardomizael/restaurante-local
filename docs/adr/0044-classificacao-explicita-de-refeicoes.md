# ADR-0044 — Classificação explícita de refeições

Status: aceita por solicitação explícita do usuário.

Data: 12/10/2026.

## Contexto

A ADR-0018 identificava refeições pela unidade KG ou pelo nome iniciado em Refeição/À vontade. O usuário solicitou um campo **É refeição** no cadastro para definir os produtos de fato pertencentes a esse grupo, sem depender desses critérios.

## Decisão

- `Product.is_meal` é booleano, inicialmente falso, editável no formulário e nas opções rápidas do catálogo. É independente de unidade, nome, Balança, Acesso rápido e Aparece na comanda. Novos produtos e produtos existentes após a migration começam desmarcados; o operador deve marcar explicitamente os desejados antes de novas capturas/inclusões.
- O campo define a área de refeições para novos itens. Produtos não marcados permanecem na área de produtos/marcações. Produtos por kg não marcados exibem também peso e valor lançados nessa área, evitando omissão dos dados de consumo.
- Novas capturas copiam `is_meal` do produto para `Measurement`. Inclusões da balança copiam o snapshot da pesagem para `OrderItem`; inclusões manuais copiam o cadastro vigente. A correção explícita de produto de uma pesagem disponível, conforme ADR-0043, também substitui sua classificação e a registra no histórico antes/depois.
- Alterar a opção no cadastro vale para novas capturas/inclusões e não reclassifica itens ou pesagens já registrados. A nova informação integra os snapshots comerciais. O serviço de produto valida o booleano e a revisão, preservando os outros campos ao editar uma opção rápida.
- Para preservar registros anteriores, `Measurement.is_meal` e `OrderItem.is_meal` admitem NULL apenas como marcador de compatibilidade. Migrations geradas deixam os snapshots existentes em NULL. A antiga regra de nome/unidade é aplicada exclusivamente a esses snapshots, por `legacy_meal_classification`, sem consultar a classificação atual do produto. Os serviços de novas capturas/inclusões sempre gravam booleanos.
- Documentos já salvos mantêm seu DTO e classificação originais, inclusive em segunda via. Novos documentos continuam usando o campo booleano `is_meal` já existente no DTO. Variantes não alimentares por kg recebem `weight_grams` adicional; a renderização só acrescenta peso/valor quando esse dado estiver presente, preservando os snapshots anteriores.
- Itens classificados como refeição não geram uma linha manuscrita vazia duplicada, mesmo quando o cadastro atual perdeu a marcação. Se houver itens históricos não alimentares do mesmo produto, eles continuam em sua área própria.

## Alternativas e consequências

Continuar inferindo pelo nome ou pela unidade contrariaria a decisão explícita no cadastro. Reclassificar itens ao imprimir faria alterações do catálogo mudarem comandas antigas. Preencher automaticamente os produtos com a heurística anterior perpetuaria uma classificação que o usuário quer controlar.

Migrations geradas e revisadas: `products.0002_product_is_meal`, `measurements.0004_measurement_is_meal` e `orders.0002_orderitem_is_meal`. Aplicação somente na atualização explícita com backup; nenhum acesso ou alteração ao banco operacional durante o desenvolvimento. Não há mudança no protocolo/ciclo da balança nem no transporte de impressão.

## Validação

Testes verificam opções rápidas, formulário, revisão concorrente, validação booleana, nomes/unidades sem classificação implícita, refeições por unidade, produtos por kg não alimentares, captura, correção individual, preservação de itens/documentos e migração de registros anteriores. A regra de classificação da ADR-0018 fica substituída para novos snapshots; sua compatibilidade histórica permanece.
