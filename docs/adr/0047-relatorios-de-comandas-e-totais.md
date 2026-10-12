# ADR-0047 — Relatórios de comandas e totais

Data: 12/10/2026. Status: aceita por solicitação do usuário.

## Contexto

O Histórico listava documentos de impressão, podendo repetir a mesma comanda. A operação precisa localizar todas as comandas por período, escolher versões preservadas para reimpressão e imprimir totais consolidados ou um relatório completo por dia.

## Decisão

Substituir **Histórico** por **Relatórios**, com **Comandas** e **Totais**, seguindo a navegação de Configurações. Atualiza a composição do menu das ADRs 0022 e 0028. O Histórico de mudanças no Status continua independente.

- Selecionar pela **data de abertura** no fuso da aplicação; datas inclusivas com limites de meia-noite local. Até 366 dias por consulta, explicitados na interface, para limitar prévias e lotes.
- Comandas: todas as situações, uma linha por comanda, 25 por página. Documentos internos ordenados cronologicamente como versões. Abrir e reimprimir usam o documento imutável existente; uma comanda sem documento não possui segunda via.
- Totais: contar situações **atuais** (abertas, fechadas, canceladas), sem reconstruir a situação passada. Somar somente itens ativos das fechadas. Comanda aberta em um dia e fechada depois participa do dia de abertura.
- Agrupar itens por identidade do produto, descrição histórica e unidade. Descrições/unidades diferentes geram linhas separadas; preços diferentes acumulam quantidades e valores na mesma linha. UN soma unidades; KG soma gramas e apresenta quilogramas. Dinheiro em centavos, apresentação com Decimal, sem recálculo pelo cadastro atual.
- Consolidado: contagens, quantidade/peso e valor acumulado de cada item, mais valor total calculado. Diário: exatamente esse formato para cada dia, inclusive sem movimento. De 01/10/2026 a 30/10/2026 são 30 relatórios.
- Apenas lançamentos registrados entram no cálculo; anotações manuscritas não estão no banco. Total não equivale a confirmação de pagamento.

## Impressão

Prévia e worker compartilham texto de 48 colunas para o perfil térmico de 80 mm. Imprimir um dia ou todos, com um trabalho/corte por dia. Simulação não acessa fila Windows.

Prévia assinada pelo servidor, com validade de uma hora, enviada em POST com CSRF. Validar modo e revisão de fila e guardar exatamente o conteúdo revisado, sem consultar novamente as comandas. Totais são lidos em transação consistente curta; nenhum hardware é acessado em views ou transações.

Ampliar `PrintJob` com `report_content` (snapshot JSON) e `report_batch_key` (UUID indexado); `document` aceita NULL. Constraint exige exatamente uma origem: documento de comanda ou relatório com lote. Relatórios são INITIAL. Registros anteriores conservam documento e estado. Migration gerada por `makemigrations`; instalação/atualização continua explícita e com backup.

Worker compartilhado mantém simulação, falha confirmada, aceitação pelo spooler, incerteza e recuperação. UUIDs derivados do lote/índice tornam repetições idempotentes, inclusive imprimir um dia e depois o lote. Inserção do lote em uma transação SQLite; resultado incerto nunca tem repetição automática.

Página própria apresenta resultados por trabalho e atualiza enquanto houver pendências. `/printing/history/` redireciona para Comandas; links dos documentos continuam válidos.

## Validação e limites

Validar datas locais, agrupamentos, equivalência diário/consolidado, versões sem duplicação, alteração após prévia, CSRF, expiração, mudança de modo/fila, idempotência, constraints SQLite, falhas e recuperação. Revisar controles touch e rolagem em viewports reduzidos. Impressão física de relatórios exige ensaio autorizado; simulação e transporte injetado não comprovam legibilidade no papel.

Validação realizada em 12/10/2026: suíte completa com 319 testes, OK, sendo um teste de navegador nativo ignorado por opt-in. Inclui 13 testes de relatórios e concorrência real entre conexões SQLite. `makemigrations --check --dry-run` sem divergências e `git diff --check` sem erros. A execução completa exigiu saída do sandbox pelos erros de permissão na pasta temporária do Windows.

Navegador: dados isolados em `outputs/report-preview-data`, runtime com `--simulate --preview-print --no-tray --no-browser`, sem acesso a equipamento real. Conferidos 30 envios diários concluídos no simulador, envio consolidado e segunda via da versão escolhida. Viewports reduzidos de 390 × 650, 800 × 600 e 1024 × 600, além da captura em 1024 × 900: sem rolagem horizontal da página nas consultas verificadas; controles visíveis revisados com alvo mínimo de 48 px. Captura local ignorada pelo Git em `outputs/reports-preview.jpg`. Runtime de validação encerrado ao final. Migration aplicada somente aos bancos de teste/validação; banco operacional preservado.
