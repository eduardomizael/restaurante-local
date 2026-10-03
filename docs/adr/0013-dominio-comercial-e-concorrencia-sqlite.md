# ADR-0013 — Domínio comercial e concorrência SQLite

- Status: Aceito para o recorte de implementação do domínio.
- Data: 2026-10-03.
- Complementa: ADR-0012 e os contratos locais de medições/comandas; não altera a stack.

## Contexto

A fundação foi registrada em commits após autorização expressa. O próximo recorte precisa persistir várias comandas e medições compartilhadas, preservar valores históricos e impedir dois usos simultâneos da mesma medição em SQLite. Não há bloqueio de linha útil com `select_for_update()` nesse banco.

## Decisão

1. Separar Product, Measurement, Order/OrderItem/OrderSequence em apps próprios. DomainEvent registra histórico no core, dentro da mesma transação da alteração; não incluir segredos em eventos.
2. Persistir dinheiro em centavos e peso em gramas inteiras. Forms convertem textos com vírgula ou ponto, sem milhares ou expoentes. Produtos usam UN ou KG. Cálculo por kg usa Decimal e `ROUND_HALF_UP` por item.
3. Serializar services de escrita com transações curtas `IMMEDIATE`, timeout limitado e erro de conflito explícito quando o banco está ocupado. Nenhuma leitura física ou espera externa ocorre dentro dessas transações.
4. Consumo exige atualização condicional AVAILABLE → USED e criação do item na mesma transação. Índice único parcial permite no máximo um vínculo ativo por medição. Remoção/cancelamento tornam o vínculo inativo e devolvem a medição; histórico continua persistido.
5. Captura, abertura de comanda e inclusão de item exigem UUID de operação estável nos retries. Inclusões repetidas devolvem o registro anterior; chave reutilizada com outro destino/dados recebe conflito. Retry de um item removido não o reativa.
6. Numeração é alocada na mesma transação, com singleton e número único. Ajustar o próximo número não renumera nem reutiliza comandas encerradas. Ao encontrar um número já ocupado, a alocação pula para o seguinte livre.
7. Editar produto exige sua revisão atual, evitando sobrescrever uma edição concorrente. A troca de produto da balança desmarca o anterior atomicamente; somente um produto ativo em KG pode estar selecionado. Ausência de configuração comercial bloqueia captura comercial.
8. Snapshots de medições e itens são preservados pelos services. A finalização com snapshot documental e PrintJob será implementada em conjunto com impressão; não oferecer finalização comercial sem persistir seu documento.

## Consequências e limites

As restrições estruturais residem no banco; consistência entre status de medição e vínculo é responsabilidade transacional dos services. Writes diretas por ORM não são a API de domínio. Histórico não é excluído automaticamente.

Limites técnicos atuais: 1–2.147.483.647 para número de comanda; 1–100.000 unidades ou 1–1.000.000 g por item; preço/total individual entre 0 e 9.000.000.000.000 centavos. Limites de estabilidade e peso físico homologado pertencem ao adaptador/ciclo, ainda pendentes. TARA é informativa e nunca é subtraída novamente do peso líquido.

Testes concorrentes usam banco temporário em arquivo, transações reais e conexões distintas. Rascunhos, vínculos e valores congelados são verificados após reabrir os dados em processo independente. Migrations são geradas por Django, revisadas e aplicadas somente por instalação explícita ou testes isolados.

Não foram concluídas as telas comerciais, captura automática persistente, impressão ou homologação física. Esses trabalhos continuam no plano.
