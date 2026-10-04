# ADR-0018 — Refeições separadas e marcações preenchidas

Status: aceita. Data: 03/10/2026. Complementa ADR-0017 e substitui a apresentação de itens definida na ADR-0014 para novos documentos.

## Contexto e decisão

O usuário determinou que a área de pré-inseridos mostre somente refeições, sem marcações manuais. Os outros produtos devem aparecer na área manuscrita, indicando os lançamentos nos próprios espaços de marcação.

Novos snapshots usam DTO versão 3. Conservar todos os itens e valores no documento, mas apresentar no topo somente refeições. O catálogo atual identifica refeições por unidade KG ou por nome iniciado em `REFEIÇÃO` ou `À VONTADE`, ignorando acentos e caixa. Essa regra é específica do catálogo local, sem novo campo ou mudança de banco; classificações por outras categorias ou produtos por kg que não sejam refeições exigem definição própria. A classificação de cada item considera sua descrição/unidade históricas e fica congelada no snapshot.

Excluir refeições da área manuscrita mesmo quando marcadas no cadastro como **Aparece na comanda**. Outros produtos seguem a união do catálogo marcado com itens lançados, inclusive os inativados após o lançamento. Congelar quantidade e total por variante de descrição/unidade/preço, mantendo preços históricos explícitos.

Preencher um espaço `[X]` por unidade já lançada e deixar os demais `[ ]` para novos acréscimos. A quantidade total e o valor lançado aparecem também por escrito, garantindo leitura inequívoca quando houver mais unidades que espaços disponíveis. Não gerar papel proporcional a quantidades grandes. A legenda distingue lançamentos e novos acréscimos.

Mostrar **SUBTOTAL REFEIÇÕES** no topo e **SUBTOTAL PRÉ-INSERIDO** após a área manuscrita, incluindo todos os lançamentos. Preservar o campo de total manual. Não cobrar produtos apenas reservados para marcação nem alterar valores do domínio, finalização ou consumo de pesagens.

## Compatibilidade e validação

Documentos versões 1 e 2 continuam usando suas apresentações originais, inclusive segundas vias e fronteira/tamanho do cabeçalho RAW. A versão 3 conserva a ampliação e as colunas da ADR-0017. Não atualizar snapshots existentes nem consultar o catálogo na reimpressão.

127 testes aprovados, incluindo refeições excluídas das marcações apesar da configuração de catálogo, unidades assinaladas, excesso de quantidade, variantes históricas com quantidades próprias, subtotais e compatibilidade das duas versões anteriores. Validar a prévia em instalação temporária simulada; o novo layout físico continua pendente de confirmação em papel. Nenhuma migration ou alteração dos dados operacionais.
