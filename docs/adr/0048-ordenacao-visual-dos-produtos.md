# ADR-0048 — Ordenação visual dos produtos

Status: aceita; validação em navegador com dados fictícios, homologação no equipamento touch pendente.

Data: 12/10/2026.

## Contexto

O cadastro possui `slip_order` e `quick_access_order`, mas editar números individualmente não permite organizar visualmente as sequências. O usuário aprovou subseções com cards, arraste e botões Subir/Descer, salvamento automático e ordens independentes.

## Decisão

Em refinamento solicitado pelo usuário em 12/10/2026, separar Produtos em Catálogo e Organizar listas, seguindo a navegação secundária de Relatórios e Configurações. Manter Produto da balança em destaque no catálogo editável e ordenar os demais produtos alfabeticamente, sem diferenças de acentos ou maiúsculas, independentemente dos campos de posição. A subseção Organizar listas reúne Ordem na comanda e Ordem dos produtos rápidos, com todos os produtos ativos marcados para cada finalidade. Um produto pode participar de ambas com posições distintas. As listas são verticais, roláveis, lado a lado em telas largas e empilhadas nas menores. Alvos de interação têm pelo menos 48 × 48 px.

Usar SortableJS 1.15.7, distribuído localmente com licença MIT em `static/vendor/`. A aplicação não consulta CDN nem exige npm. O arraste ocorre somente pela alça; os botões oferecem operação por toque/teclado e POST convencional sem JavaScript. Não há transferência por arraste entre listas: participação continua controlada pelas tags do catálogo.

O form interpreta a lista completa de IDs e o fingerprint do estado exibido. O service adquire uma transação SQLite IMMEDIATE, verifica participação e posições persistidas, rejeita duplicados, ausentes e membros externos, e salva posições consecutivas apenas no campo correspondente. O fingerprint depende dos IDs e posições daquela lista; a reordenação da outra lista não causa conflito. Produtos com posições alteradas recebem nova revisão, protegendo contra formulários de edição antigos. A gravação e o evento `PRODUCT_LIST_REORDERED` são atômicos.

Respostas HTMX de ordenação recuperam as duas listas do banco em um snapshot, incluindo erros 400/409. Rolagem interna e foco nos botões são preservados. Enquanto há requisição de ordenação, arraste e controles de escrita são desabilitados. Em falha de transporte, a interface restaura a sequência anteriormente exibida e informa que não foi possível confirmar a gravação: uma resposta perdida pode ocorrer após o banco salvar, exigindo recarga para conferir. Scripts de arraste são carregados somente na subseção de organização; POST convencional retorna a essa mesma subseção.

Reutilizar os campos existentes, sem migration. A ordem rápida chega ao atendimento pelo seletor existente; a ordem da comanda chega às novas prévias e snapshots. Refeições mantêm sua seção própria; a ordenação não modifica os itens históricos nem documentos já congelados. Produtos desmarcados ou inativados saem da lista; ao voltar, usam a posição que conservaram, com os desempates existentes (`id` no papel e descrição/ID no acesso rápido).

## Validação

Testes cobrem persistência, consumidores, independência das listas, busca sem filtragem da sequência, revisões antigas, participação alterada, entradas inválidas, rollback, POST convencional, CSRF, runtime indisponível, assets locais e duas gravações simultâneas com o mesmo fingerprint em SQLite. Conferência visual usa banco temporário, dados fictícios e nenhum worker de hardware.

Arraste por mouse e botões por mouse/teclado foram exercitados no Chrome. Conferência responsiva contempla 1920 × 1200, 1280 × 673, 1024 × 600, 800 × 600 e 390 × 650, sem corte horizontal e com controles de pelo menos 48 px. Duas abas confirmaram recuperação da ordem em conflito; busca manteve listas completas; marcar/desmarcar acesso rápido atualizou a participação. Com servidor de prévia encerrado, o botão mostrou a falha de confirmação e manteve a sequência anterior. Funcionamento por toque físico ainda exige ensaio no equipamento.

Suíte completa: `uv run --offline --no-sync --cache-dir .uv-cache python manage.py test --settings=config.test_settings`, 330 testes, OK, um teste nativo com opt-in desativado. A primeira execução dentro do sandbox encontrou erros de permissão nas pastas temporárias do Windows; a execução com acesso normal passou. Após ampliar a verificação de documento salvo, segunda via e prévia antiga, os 11 testes de `tests.test_product_ordering` passaram novamente. Sintaxe JavaScript e `git diff --check` aprovados. Nenhuma impressão física ou publicação foi realizada.

Após separar Catálogo e Organizar listas, a suíte completa passou com 331 testes e o mesmo teste opcional ignorado. Os 19 testes de ordenação e tags passaram, incluindo catálogo alfabético após reordenação das duas listas, nomes com acentos/maiúsculas, navegação ativa e POST convencional de volta à subseção. No Chrome com dados fictícios, botão Descer confirmou Ordem salva; ao retornar ao Catálogo a sequência alfabética permaneceu. Em 1024 × 600, a subseção empilha as listas sem corte horizontal e os links de navegação medem 48 px de altura.
