# ADR-0014 — Documento congelado e fila simulada

- Status: Aceito para o recorte documental e simulado.
- Data: 2026-10-03.
- Complementa: ADR-0012 e ADR-0013; transporte físico continua pendente.

## Contexto

Finalização comercial não pode ocorrer sem documento recuperável. HTTP não controla spooler, e repetir um envio incerto pode produzir duas vias físicas. O papel reúne lançamentos históricos e produtos reservados para acréscimos manuscritos, sem recalcular preços após a finalização.

## Decisão

1. App `printing` possui configuração de cabeçalho/rodapé, `OrderDocument` e `PrintJob`. Configuração é singleton com revisão otimista; não inclui configuração de hardware neste recorte.
2. Documento único por comanda contém DTO JSON versionado, número, horários, cabeçalho/rodapé, todos os itens e seus snapshots, subtotal e união das linhas manuscritas. Linhas são agrupadas por identidade do produto; nomes/unidades/preços históricos distintos ficam explícitos, sem duplicar marcações. Produtos marcados sem lançamento não compõem subtotal.
3. Prévia de rascunho usa fingerprint do conteúdo comercial. A confirmação repete consultas sob transação SQLite IMMEDIATE, rejeita prévia obsoleta e salva documento, trabalho inicial e estado FINALIZED atomicamente. Exige cabeçalho configurado e pelo menos um item. Somente a comanda destinatária encerra; medições e outros rascunhos são preservados.
4. Texto contínuo de 48 colunas, sem limite de altura, é renderizado pelo mesmo código para web e simulador. O DTO registra bobina de 80 mm. Perfil físico, encoding e ESC/POS não estão homologados; essa renderização é referência documental, não substituto do transporte RAW.
5. Fila usa PENDING → SUBMITTING → SIMULATED/FAILED/UNKNOWN. SIMULATED não significa aceitação por spooler nem saída de papel. Intento e UUID da tentativa são persistidos antes do transporte, que roda fora da transação; resultado exige a mesma tentativa.
6. Inicializador recupera SUBMITTING como UNKNOWN após obter mutex e validar schema, antes de disponibilizar HTTP. Não reenvia UNKNOWN ou FAILED automaticamente. PENDING pode continuar após reinício. Se gravar resultado falhar, permanece SUBMITTING até recuperação no reinício; logs e histórico conservam evidência.
7. Segunda via exige confirmação explícita, usa o mesmo DTO e acrescenta rótulo SEGUNDA VIA no envio. UUID impede duplo clique; no máximo um envio ativo por documento. A tentativa anterior não é sobrescrita. Solicitação após falha também é identificada como segunda via, pois é uma nova tentativa documental explícita.
8. `PrintWorker` pertence ao runtime e possui sua conexão ORM/adaptador. Encerramento não inicia novos trabalhos; termina a simulação corrente limitada e fecha recursos antes de liberar mutex. POST já aceito que termina durante o encerramento pode deixar PENDING para a próxima abertura.

## Alternativas

Renderizar com catálogo atual na reimpressão perderia fidelidade histórica. Finalizar antes de salvar trabalho permitiria comanda encerrada sem documento. Enviar em view acoplaria requisição e hardware. Retentar resultados incertos automaticamente foi rejeitado por risco de duplicação.

## Consequências e limites

Snapshots são imutáveis pela API de services; alterações diretas por ORM não são uma API suportada. Restrições de unicidade e coerência de estados ficam no banco. Finalização e cancelamento concorrentes têm um único vencedor consistente.

Não há novo serviço externo, dependência ou hardware real. A futura adaptação física deve distinguir aceitação de spooler de impressão efetiva e preservar este protocolo de incerteza. Comprimento, marcações, acentos, largura, corte e falta de papel exigem ensaio autorizado.
