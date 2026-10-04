# ADR-0023 — Layout da comanda conforme referência visual

Status: aceita. Data: 04/10/2026. Complementa ADR-0017 e ADR-0018.

## Contexto e decisão

O usuário enviou uma referência com reposicionamento de elementos e remoção de textos da comanda. Aplicar o formato às novas prévias e impressões como versão documental 5, mantendo renderização das versões 1–4 sem alteração.

Cabeçalho ampliado e centralizado. Na linha seguinte, número **COMANDA #n** à esquerda e data/hora **dd/mm/aaaa HH:MM:SS** à direita. Nas impressões, usar o instante congelado da impressão/finalização; na prévia, usar a abertura da comanda, sem inserir um relógio variável no fingerprint. A segunda via conserva a data original e sua identificação explícita.

Seção **REFEIÇÕES**: descrição à esquerda e preço por UN/KG à direita; abaixo, quantidade ou pesagem com peso à esquerda e valor à direita. Subtotal de refeições alinhado à direita. A seção de produtos inicia diretamente com **PRODUTO / R$ / MARCAÇÕES**, preservando colunas, preços históricos, marcações preenchidas e aviso de quantidade que excede a capacidade das caixas. Não duplicar refeições entre os produtos.

Remover do novo papel os rótulos de finalização/impressão, **COMANDA ABERTA**, **PRÉ-INSERIDAS**, **ACRÉSCIMOS MANUSCRITOS**, legenda de marcações, subtotal geral pré-inserido e instrução de preenchimento manual. Manter metadados de abertura/fechamento e todos os valores comerciais no snapshot. Após o último separador, reservar duas linhas vazias, centralizar o total manual e reservar três linhas vazias antes do rodapé centralizado.

Manter 48 colunas, bobina de 80 mm, header scale 2 e quebra de nomes longos. HTML, simulador e RAW compartilham o mesmo renderer e os limites do cabeçalho. A nova versão não requer migration, atualização automática de banco ou mudança de transportes.

## Validação e limites

Atualização de 04/10/2026: novos snapshots usam a versão 6, com subtotal das refeições em negrito na prévia HTML e comandos ESC/POS `ESC E` ativados somente nessa linha e desativados imediatamente depois. O tamanho permanece normal para preservar 48 colunas. Versões 1–5 conservam a apresentação original, inclusive em segunda via. A lista de linhas destacadas é derivada pelo renderer compartilhado, sem inserir controles no texto comercial. Papel continua em 80 mm; o perfil RAW não adiciona as margens de 4 mm usadas apenas na prévia web. A área física imprimível até as bordas não foi medida.

Testes verificam alinhamentos, data, espaçamento, ausência dos textos removidos, cabeçalho compartilhado, largura máxima, nomes/preços longos, excedente de quantidade e preservação do layout versão 4. Testes existentes verificam documentos congelados, segundas vias, idempotência e transporte RAW com spooler falso.

Prévia renderizada no navegador com dados de exemplo, sem banco operacional ou envio ao spooler. A referência fornece o posicionamento; preços e subtotais continuam calculados a partir dos itens reais, sem copiar valores comerciais da imagem. A confirmação física deste layout em papel permanece pendente.
