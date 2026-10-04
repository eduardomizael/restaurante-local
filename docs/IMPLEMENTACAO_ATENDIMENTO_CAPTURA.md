# Atendimento touch e captura simulada

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
