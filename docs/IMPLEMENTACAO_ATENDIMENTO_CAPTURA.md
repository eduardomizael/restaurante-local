# Atendimento touch e captura simulada

## Atualização de 12/10/2026 — Campo É refeição

Em **Produtos**, marque **É refeição** na opção rápida do card ou no formulário de edição para agrupar novas inclusões com as refeições da comanda. A marcação é independente do nome, da unidade e de **Aparece na comanda**. Novos produtos e produtos existentes após a atualização começam desmarcados: confira o cadastro antes de novas capturas/inclusões.

A classificação é copiada para novas pesagens e itens. Alterações posteriores no cadastro não mudam esses snapshots; a troca explícita do produto de uma pesagem disponível também copia a classificação do produto escolhido. Itens/pesagens anteriores à migration conservam a regra histórica e documentos salvos permanecem iguais. Produtos não alimentares por kg ficam na área de marcações, com peso e valor lançados visíveis. Decisão e migrations: [ADR-0044](adr/0044-classificacao-explicita-de-refeicoes.md). Banco operacional não alterado.

Validação: suíte de 285 testes aprovada, com um teste nativo ignorado por exigir opt-in. Oito testes novos cobrem classificação explícita, snapshots e upgrade de registros existentes; testes anteriores de catálogo e impressão foram adaptados à opção explícita. Chrome conferido em 1280×673, 1024×600, 800×600, 390×650 e 1920×1200, com banco isolado e dados fictícios: opções rápidas, criação, edição, preservação das outras opções e agrupamento na prévia aprovados, sem erros JavaScript, rolagem horizontal ou alvos menores que 48 px. `makemigrations --check --dry-run` e `git diff --check` aprovados. Sem ensaio físico, commit ou publicação.

## Atualização de 12/10/2026 — Correção do produto de uma pesagem disponível

Tocar no corpo de um card de pesagem disponível abre o diálogo **Produto da pesagem**, com peso original, produto/total registrados e opções ativas por kg. Cada opção mostra preço atual e total recalculado. Escolher altera somente aquela pesagem, fecha o diálogo e atualiza seu card; Incluir e Descartar continuam separados. Fechar ou Escape cancela. A troca não altera o produto global da balança nem os dados físicos da captura.

Revisões da pesagem e do produto protegem o envio contra alterações concorrentes. Se a pesagem já foi incluída/descartada, o diálogo informa o conflito, remove o card da lista disponível e bloqueia a escolha. Se produto/preço ou pesagem mudaram, os valores são atualizados para nova escolha. Histórico registra antes/depois em transação. A inclusão a partir do card também confere sua revisão; snapshots de itens e documentos anteriores permanecem intactos. Decisão e migration: [ADR-0043](adr/0043-correcao-individual-do-produto-da-pesagem.md). Nenhuma migration foi aplicada ao banco operacional.

Validação: suíte de 277 testes aprovada, com um teste nativo ignorado por exigir opt-in; 13 testes novos verificam correção, conflitos, cálculo e concorrência real SQLite. Chrome conferido nas duas versões do atendimento em 1280×673, 1024×600, 800×600, 390×650 e 1920×1200, com dados fictícios e banco isolado. Seleção, recálculo, atualização posterior, comanda preservada, Escape, Incluir/Descartar separados e consumo por outra página com diálogo aberto funcionaram, sem erros JavaScript, rolagem horizontal ou alvos menores que 48 px. `makemigrations --check --dry-run` e `git diff --check` aprovados. Sem hardware, commit ou publicação.

## Atualização de 12/10/2026 — Produto da balança no atendimento

O card de peso mostra o produto selecionado e oferece **Trocar produto** nas duas versões do atendimento. Tocar na indicação abre um diálogo com produtos ativos por kg, preço por kg e destaque do produto atual. A escolha atualiza o card e fecha o diálogo, sem navegar ou trocar a comanda selecionada. Fechar ou Escape sai sem alterar. Sem produto selecionado, o mesmo controle oferece **Escolher produto**; sem candidatos, o diálogo aponta para o cadastro.

A seleção usa o serviço transacional existente do cadastro, com revisão do produto e transferência atômica da marca Balança. Produtos inativos, por unidade e revisões desatualizadas são rejeitados. As pesagens já capturadas mantêm produto e preço históricos; a escolha vale para novas capturas. As mensagens do card foram encurtadas: **Pode colocar o prato**, **Aguardando estabilidade**, **Pesagem salva. Retire o prato**, **Retire o prato e aguarde zerar**, **Sem resposta. Aguarde** e **Escolha o produto da balança**. Nenhuma mudança no protocolo ou ciclo de captura.

Validação: suíte de 264 testes aprovada, com um teste nativo de navegador ignorado por exigir opt-in. Conferência no Chrome com banco isolado e dados fictícios em 1280×673, 1024×600, 800×600, 390×650 e 1920×1200: seleção, atualização posterior, Escape, duas versões do atendimento, alvos de toque de ao menos 48 px e ausência de rolagem horizontal ou erros JavaScript. Sem ensaio físico, commit ou publicação.

## Atualização de 10/10/2026 — Teclado do Windows por tipo de campo

Campos atendidos pelo teclado numérico próprio usam `inputmode="none"`: valores decimais, quantidades, ordenação dos produtos, próxima numeração e inclusão manual em diálogo. Esse atributo orienta o navegador a não mostrar o teclado virtual nesses campos. Buscas e campos de texto continuam com entrada normal, permitindo o teclado do Windows quando sua abertura automática estiver habilitada. Não há alteração nas configurações do Windows. A supressão efetiva deve ser conferida no Windows/Edge do computador final.

## Atualização de 10/10/2026 — Confirmação de descarte em diálogo

O botão **Descartar** abre um diálogo na própria tela nas duas versões do atendimento, com identificação, produto, peso e valor da pesagem. **Voltar sem alterar** e Escape fecham a confirmação. Confirmar atualiza a lista sem navegação e mantém a comanda selecionada. Durante o envio, os botões e o fechamento por Escape ficam bloqueados; conflitos aparecem no diálogo. A proteção do serviço contra descarte de pesagem já utilizada permanece. Sem JavaScript, a página de confirmação continua disponível.

Testes HTTP cobrem os dois layouts, ausência de confirmação, uso concorrente da pesagem, preservação das outras pesagens e navegação convencional. Nenhuma mudança de hardware ou banco de dados.

## Atualização de 10/10/2026 — Destaque visual do peso e do estado

O card do Atendimento omite o protocolo serial e destaca o peso líquido com fonte de 48 px, números tabulares e alto contraste. As mensagens têm fundo colorido, texto reforçado e ícone: verde para pronta ou salva, azul para estabilização/simulação, amarelo para retorno ao zero ou recuperação, vermelho para falha/configuração e cinza para leitura parada/pausada. O texto continua identificando o estado sem depender apenas da cor; a mensagem usa `role="status"`.

Alteração de apresentação, sem mudança no ciclo de captura. Os 55 testes existentes de atendimento touch e layout compacto passaram. Sem ensaio visual em navegador ou hardware real neste ajuste.

## Atualização de 10/10/2026 — Status e lista de pesagens na mesma resposta

O usuário relatou pesagens com a mensagem **Peso fixado · pesagem salva · aguardando zero** que só apareciam na lista após sair e voltar ao Atendimento. Isso confirma gravação com apresentação desatualizada nesse cenário; não comprova a causa de eventuais falhas seriais anteriores.

O Atendimento passa a consultar status e listas em uma única atualização HTMX de 500 ms. O status é lido antes das consultas comerciais: uma captura ocorrida durante a montagem da resposta não publica uma mensagem de sucesso mais nova que a lista. A próxima consulta entrega o estado atualizado. A resposta 204 exige tanto a revisão comercial quanto a revisão do runtime inalteradas; uma nova leitura também permite renovar a lista. A tela Status conserva seu diagnóstico próprio. Proteções de destino, diálogos, ações em envio e página oculta continuam vigentes.

Validação: 52 testes de atendimento, captura, layouts e inclusão por diálogo aprovados. Novos casos cobrem mensagem de captura e medição na mesma resposta, mudança técnica sem evento comercial e captura concorrente durante a consulta. Sem migrations, hardware real, commit ou publicação. Confirmação da correção no equipamento do usuário permanece pendente.

## Atualização de interface — 03/10/2026

Atendimento reorganizado a partir da referência visual do projeto Restaurante: faixa horizontal de medições acima de duas colunas; cards de comandas à esquerda e detalhes à direita. Os cards mostram número, situação, horário de abertura, quantidade de lançamentos ativos e subtotal. A selecionada tem destaque e rótulo. Em telas estreitas, as comandas passam para uma faixa horizontal acima dos detalhes.

O card **Inicializador**, seus detalhes e pausa/retomada permanecem apenas em **Status**. O atendimento apresenta peso e estado da balança em um resumo compacto. O fragmento de atualização mantém essa separação, inclusive após polling. Produtos rápidos e busca ficam em **Adicionar produtos**, expansível no painel da selecionada; subtotal e ações ficam na parte inferior, com posicionamento sticky no desktop.

HTMX local atualiza seleção e abertura de comanda, busca de produtos, inclusão de medição e remoção de item. Seleção/abertura substituem a área de atendimento e atualizam a URL; inclusão/remoção e polling atualizam medições, cards e itens. A busca substitui somente os resultados. Inclusão manual com quantidade, confirmação de descarte/cancelamento e prévia/impressão continuam em telas próprias com navegação normal. As operações preservam a alternativa HTTP tradicional, CSRF, idempotência e destino explícito.

Polling permanece em 500 ms, com resposta 204 quando a revisão não mudou. Campos de busca e seções abertas não são substituídos pelas atualizações automáticas. As posições de rolagem das listas são preservadas. Requisições interativas compartilham sincronização e interrompem polling pendente; respostas de outra comanda são rejeitadas. O histórico recarrega dados atuais, sem restaurar snapshots de atendimento do cache HTMX. Se a selecionada for encerrada em outra janela, seus controles de produtos são removidos sem escolher outra comanda automaticamente.

Validação: 141 testes passaram, incluindo separação inicializador/balança, criação idempotente e seleção via HTMX, histórico, consumo/remoção e totais dos cards, conflitos, busca com destino explícito e encerramento concorrente observado pelo polling. `check` sem erros e `makemigrations --check --dry-run` sem alterações. Verificação no navegador com banco temporário e transportes simulados: seleção, inclusão/remoção, busca, nova comanda e histórico; layouts de 1280 × 900 e 390 × 844 sem overflow horizontal da página. Nenhum envio para COM ou spooler; toque físico não homologado por essa verificação.

Implementação em 03/10/2026, independente do projeto anterior. Fluxo: implementação direta, validação e revisão; sem hardware real, impressão física ou commit implícito.

## Entrega

A raiz HTTP abre o atendimento. É possível cadastrar/editar produtos, selecionar o produto ativo em KG da balança, definir acesso rápido e participação na futura comanda impressa. Edição usa revisão otimista e preserva snapshots históricos.

O atendimento permite abrir várias comandas, alternar destino, incluir medições compartilhadas uma única vez, lançar UN ou peso manual, remover itens, cancelar somente a selecionada e descartar somente a medição confirmada. Cancelamento devolve as medições vinculadas à lista; descarte exige confirmação. A numeração pode ser ajustada sem reutilizar números existentes. A impressão permanece desabilitada até a entrega documental.

Forms fazem parsing com Decimal, services aplicam regras e transações, selectors retornam snapshots e templates apresentam centavos/gramas. O subtotal exibido é calculado a partir dos mesmos itens consultados. POSTs têm CSRF, destino explícito e chaves idempotentes nas operações correspondentes; rejeitam novas escritas quando o runtime inicia o encerramento.

Assets são locais. Controles têm alvos de pelo menos 48 px, foco visível e rótulos; preços, quantidades e pesos oferecem teclado numérico modal com precisão apropriada. O teclado físico continua disponível. Polling de 500 ms pausa com página oculta, campo em edição, teclado aberto ou formulário em envio. Respostas já em trânsito também são recusadas nesses casos. Revisão do domínio evita substituir listas inalteradas; identidade explícita impede resposta atrasada de mudar a comanda selecionada. Pesquisa e formulário de inclusão não são substituídos pelo fragmento.

## Captura e recuperação

`CaptureCycle` é uma máquina de estados sem ORM, threads ou serial. `ScaleCaptureController` observa produto/revisão e chama o service comercial; o worker possui e fecha sua conexão Django. Nada é iniciado por import, view ou AppConfig.

Perfil **SIMULATION_ONLY**, ainda sem homologação física: três amostras recentes consecutivas, variação máxima de 2 g, tara constante, zero até 10 g e peso comercial mínimo de 11 g. Idade e intervalo máximos: 2 s. Movimento, amostra antiga/futura/repetida, peso inválido e falha de leitura impedem captura válida. O intervalo normal de 500 ms produz janela de aproximadamente 1 s; os limiares não constituem contrato do equipamento real.

Início, retomada, reconexão e mudança do produto/preço exigem observar zero antes de capturar. Após salvar, o ciclo espera retirada, sem duplicar um prato mantido na balança. Não é necessário ter comanda aberta. Retirada não apaga medições persistidas. Conflito de banco mantém a chave do candidato para nova tentativa; mudança de revisão comercial impede congelar preço diferente daquele observado pelo ciclo. Falha ou retirada antes de uma captura ser persistida pode exigir recolocação do prato; a garantia de recuperação cobre dados já gravados, e o erro é apresentado no status.

## Validação

68 testes aprovados: os 45 anteriores e 23 de atendimento/captura. Novos casos incluem cadastro e edição obsoleta, duas comandas/três pratos, UN/KG manual, destino explícito, retries, CSRF, confirmação, correção, numeração, fragmentos, zero/retirada, oscilação/tara/movimento, idade, preço alterado, falha de persistência e worker real com desconexão simulada em SQLite em arquivo. Sem novas migrations.

Verificação manual no navegador local com dados temporários separados: pausa, abertura de comanda, inclusão de pesagem de 252 g, teclado numérico para duas unidades de bebida, retorno ao atendimento e subtotal de R$ 29,09 (R$ 15,09 + R$ 14,00). Layout observado no painel estreito e em 1280 × 900; sem erros de console. Essa verificação não substitui ensaio de toque em monitor físico Windows.

## Próximo incremento

Este incremento documental foi concluído em seguida; consulte [Documento e impressão simulada](IMPLEMENTACAO_DOCUMENTO_IMPRESSAO.md) para entrega, testes e pendências atuais.

Configuração de cabeçalho/rodapé e DTO documental congelado; preview em bobina contínua de 80 mm, finalização isolada da selecionada e fila simulada com idempotência/recuperação de resultado incerto. Adaptadores COM/RAW, perfil de estabilidade definitivo e distribuição Windows continuam pendentes.

## Atualização de 04/10/2026 — Tags editáveis no catálogo

As opções **Balança**, **Aparece na comanda** e **Acesso rápido** aparecem em todos os cards como checkboxes estilizados em tags. Desmarcadas têm contorno; marcadas têm preenchimento e símbolo de confirmação. Clique ou espaço no teclado salva imediatamente por POST/HTMX e substitui somente o fragmento do catálogo, preservando a busca fora dele. Os alvos têm pelo menos 48 px e foco visível.

Uma seção própria **Produto da balança** destaca a seleção atual, mesmo se não corresponder à busca. O produto não se repete entre os demais. Somente produtos ativos por KG podem assumir a função; nos demais, essa tag fica indisponível. Marcar outro produto transfere a seleção usando o serviço e a restrição única já existentes. Desmarcar o selecionado deixa a balança sem produto configurado e a captura continua respeitando a regra existente de exigir produto ativo por KG.

O novo serviço `set_product_flag` aceita apenas as três opções e usa a revisão exibida, leitura e escrita na mesma transação SQLite IMMEDIATE. Preserva preço, descrição, unidade, ordenação e outras flags. O selector lê a seleção e os outros cards em um snapshot consistente. A transferência incrementa as revisões dos produtos envolvidos e não altera medições ou documentos históricos.

Durante a requisição, bloquear temporariamente as tags disponíveis do catálogo para evitar ações concorrentes no fragmento; controles originalmente indisponíveis permanecem assim. Erros de validação e revisão obsoleta retornam estado confirmado e mensagem. Falhas de conexão ou HTTP sem fragmento de validação restauram os checkboxes ao último estado confirmado. Exigir POST, CSRF e runtime ativo.

Sem novas migrations. Sete testes específicos cobrem seleção única, transferência, remoção de seleção, atualização isolada, filtros, candidatos inválidos, revisões obsoletas e proteção HTTP. Validação visual em dados temporários com simuladores confirmou transferência sem recarga, marcação/desmarcação, acionamento pelo teclado e recuperação após alteração em outra sessão. Nenhum equipamento real ou banco operacional foi usado.

## Atualização de 04/10/2026 — Inclusão por diálogo

Cards de produtos rápidos e resultados do catálogo abrem um diálogo sobre o atendimento com teclado numérico integrado. Em UN, inicia com quantidade 1 e o primeiro dígito substitui o valor; em KG, solicita peso com até três casas decimais. O teclado físico também funciona. Confirmar faz POST com CSRF, destino explícito e a mesma chave idempotente do serviço existente; retorna itens, cards e subtotal por HTMX e fecha o diálogo somente após sucesso. A URL e a comanda selecionada permanecem iguais.

Validação inválida ou conflito mantém o diálogo e a chave da operação para correção. Cancelar ou Esc antes do envio não grava; durante o envio, bloquear os botões e Esc para não confundir cancelamento com uma inclusão já em processamento. Polling não substitui conteúdo enquanto o diálogo está aberto. Respostas para outra comanda são rejeitadas. A página de inclusão original permanece como alternativa HTTP sem HTMX.

Cinco testes específicos cobrem fragmento com teclado, UN/KG, idempotência, atualização de totais, destino adulterado, validação, comanda encerrada e alternativa HTTP. No navegador com simuladores, incluir duas unidades de Suco atualizou o subtotal para R$ 14,00 sem sair da tela; quantidade zero manteve o diálogo com erro, e cancelar não criou outro item. Sem migrations ou alteração de dados operacionais.
