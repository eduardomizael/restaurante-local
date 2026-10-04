# ADR-0019 — Impressão sem fechamento da comanda

Status: aceita. Data: 03/10/2026. Complementa ADR-0014, ADR-0017 e ADR-0018.

## Decisão

Atendendo à instrução atual do usuário, oferecer **Imprimir sem fechar** como ação principal na prévia. Conservar a ação separada **Finalizar e imprimir**. A primeira mantém a comanda em DRAFT, sem alterar itens, medições ou horário de fechamento; a segunda continua encerrando somente a selecionada.

Cada impressão sem fechamento cria seu próprio documento imutável e trabalho persistente na mesma transação SQLite IMMEDIATE. A relação de documentos com comandas passa de um-para-um para muitos-para-um. O campo `is_final` diferencia cópias durante atendimento do documento de fechamento; uma restrição parcial garante somente um documento final por comanda. Documentos antigos recebem `is_final=True`, preservando seus conteúdos, identificadores e trabalhos. Migration `printing/0003` gerada pelo Django e revisada, sem escrita manual.

Revisão do fingerprint e destino da impressora, UUID de idempotência, recuperação de envio incerto e execução de transporte fora da transação continuam obrigatórios. O mesmo UUID não pode representar impressão aberta e fechamento. Enquanto qualquer envio da comanda estiver pendente ou em andamento, recusar outro envio, inclusive segunda via de um snapshot anterior. Novos envios após conclusão são explícitos e criam novos snapshots. Segunda via usa exatamente o documento selecionado, sem consultar o catálogo atual.

O histórico apresenta tanto impressões durante atendimento quanto fechamentos. Uma rota por documento permite consultar uma impressão anterior mesmo após editar ou cancelar a comanda; a prévia de uma comanda aberta continua mostrando os itens atuais. Cancelar após imprimir não apaga o documento enviado e mantém a regra existente de liberar vínculos de medições.

## Apresentação e compatibilidade

Novos snapshots usam DTO versão 4. Na impressão sem fechamento, indicar **COMANDA ABERTA** e horário de impressão, sem inventar finalização. Preservar as apresentações das versões 1, 2 e 3. Nos produtos marcáveis, retirar a linha de valor lançado abaixo do produto. As marcações `[X]` indicam unidades inseridas; se a quantidade exceder os espaços, mostrar somente a quantidade por escrito. O subtotal geral continua incluindo todos os lançamentos.

## Instalação e validação

Com o aplicativo fechado, executar `initialize_local` para backup e atualização do banco antes de abrir o novo código. A abertura normal continua recusando schema pendente e não migra automaticamente. Não atualizar a instalação operacional como efeito implícito dos testes.

Testes cobrem snapshots sucessivos e fechamento posterior, idempotência, edição após impressão, cancelamento, rollback, prévia obsoleta, envios pendentes, concorrência SQLite entre impressão aberta e fechamento, métodos/CSRF e histórico por identidade do documento. Ensaio da migration com documento e trabalho existentes confirmou preservação de conteúdo, fingerprint, relacionamento e comanda finalizada. Ensaio visual em instalação temporária simulada: envio sem fechar concluído, retorno ao atendimento com comanda 1 aberta e documento sem total abaixo da Coca. Não houve envio físico.
