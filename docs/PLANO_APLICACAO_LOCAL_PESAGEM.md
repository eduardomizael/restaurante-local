# Plano da aplicação local de pesagem e impressão

Data: 03/10/2026. Status: **escopo e fluxo definidos; Django e interface web touch escolhidos; estrutura técnica especificada para implementação**. Este documento planeja uma aplicação independente; não modifica o Restaurante atual.

Andamento em 03/10/2026: fundação, domínio comercial, atendimento touch, captura automática simulada e documento/fila simulada implementados. Captura automática real e impressão de uma comanda foram verificadas; ensaios físicos de falha, homologação completa e distribuição permanecem pendentes. Consulte os registros da [fundação](IMPLEMENTACAO_FUNDACAO.md), [domínio](IMPLEMENTACAO_DOMINIO.md), [atendimento](IMPLEMENTACAO_ATENDIMENTO_CAPTURA.md) e [documento](IMPLEMENTACAO_DOCUMENTO_IMPRESSAO.md). Os requisitos abaixo continuam sendo o contrato alvo.

## 1. Objetivo e limites

Criar um programa independente para capturar automaticamente pesos estáveis, pré-inserir refeições e produtos em uma comanda local e imprimir essa comanda com espaços para lançamentos manuscritos posteriores pelos atendentes de mesa.

Autonomia significa funcionar sem o servidor Restaurante, banco existente, internet ou sincronização comercial. A nova aplicação usa seu próprio Django e banco local, iniciados pelo programa no mesmo PC. O projeto atual serve como referência de protocolo, testes e operação; o novo programa não importa módulos nem compartilha arquivos de configuração ou dados do agente atual.

Escopo confirmado: somente um PC com **Windows 10 ou 11**, conectado fisicamente à balança na **COM3** e à impressora com nome **balanca**, a mesma impressora térmica do projeto base. Papel de **80 mm em bobina contínua**, com comprimento suficiente para todas as linhas; o formato do driver `Printer Paper (80 x 210 mm)` não limita a comanda a 210 mm. Porta e impressora poderão ser alteradas na tela de configuração. Largura útil e corte serão ensaiados.

Fora do MVP: estoque, caixa, pagamentos, emissão fiscal, nuvem, acesso remoto, integração com outro sistema e sincronização entre instalações. A aplicação termina sua responsabilidade operacional ao finalizar e imprimir a comanda; os itens acrescentados à mão não são digitados de volta nem gerenciados por ela.

## 2. Referências verificadas

As evidências herdadas do projeto base foram consolidadas em [Referência de hardware](REFERENCIA_HARDWARE.md). Esse documento é autossuficiente e separa resultados observados de pendências de homologação; o projeto não precisa de acesso ao repositório antigo.

- Perfil serial observado: US 31/2 POP-S, consulta `0x04`, `9600 8N2`, DTR/RTS desativados, quadro observado de 150 bytes, campo `PESO L` e tara informativa separada.
- `PESO L` já é líquido; não subtrair tara novamente. O domínio novo usa `net_weight_grams`.
- Três amostras dentro de 2 g e retorno ao zero em até 10 g são referências para ensaio, não critérios físicos definitivamente homologados.
- Impressão ESC/POS em bobina de 80 mm, perfil ensaiado de 48 colunas e spooler RAW Windows. Acentos, largura útil, corte e falta de papel exigem validação nesta instalação.
- [Imagem de referência da comanda](references/order-slip-reference.png), preservada neste projeto. Produtos e preços da foto não são dados iniciais confirmados.

## 3. Requisitos confirmados e decisões abertas

Confirmado pelo usuário:

- O cliente coloca o prato na balança; a medição estável aparece automaticamente para o atendente, sem botão de confirmação por prato.
- O atendente informa o valor calculado por peso; o cliente escolhe verbalmente entre **no peso** e **à vontade**; o atendente registra a escolha.
- Vários pratos podem ser pesados antes de lançar seus itens na comanda. As medições permanecem disponíveis depois da retirada do prato.
- A tela oferece produtos de acesso rápido para inclusão pelo atendente.
- Ao terminar os lançamentos, o atendente clica em **Imprimir comanda**. Essa ação finaliza somente a comanda selecionada e mantém as medições disponíveis na lista compartilhada.
- O papel contém os itens lançados e espaços para novos itens manuscritos pelos atendentes de mesa.
- Toda a operação ocorre na aplicação nova, em um único PC, sem caixa ou documento fiscal.
- Cadastro simples de produtos com descrição, valor unitário e unidade. Produto por peso pode ser marcado como o produto medido pela balança.
- À vontade é um produto comum, que pode ser inserido sem selecionar uma medição. Qualquer produto pode ser adicionado diretamente à comanda.
- Cada produto pode ser marcado para acesso rápido; os marcados aparecem em botões de fácil inclusão na tela.
- Podem existir **várias comandas abertas ao mesmo tempo**. A interface permite abrir, selecionar e alternar entre elas; impressão ou cancelamento afeta somente a selecionada.
- As pesagens entram em uma **lista compartilhada de medições disponíveis**, sem comanda definida na captura. O atendente pode inserir cada medição em qualquer comanda aberta, uma única vez.
- Produtos por peso também podem ser inseridos manualmente com quantidade digitada em kg, sem usar uma medição da balança.
- O cadastro tem a opção **Aparece na comanda**, independente do acesso rápido. Produtos marcados têm espaço reservado no papel mesmo sem lançamento.
- Qualquer produto efetivamente inserido é impresso com sua quantidade e espaços para acréscimos manuais, mesmo sem a opção Aparece na comanda.
- O papel mostra todas as refeições, por peso ou à vontade, e comporta todas as linhas necessárias. Marcações vazias usam a capacidade da linha; oito espaços são referência suficiente, não um limite obrigatório.
- Tela de configuração inclui balança/porta COM, impressora, nome do cabeçalho, rodapé e próximo número da comanda.
- Numeração começa em 1, segue continuamente sem reinício diário e pode ser ajustada por **Número da próxima comanda**.
- Imprimir ou cancelar uma comanda não descarta medições disponíveis. O atendente descarta manualmente as que não serão usadas; não há expiração automática.
- Correção/remoção de itens antes da impressão, recuperação após reinício, histórico e reimpressão foram aceitos pelo usuário.
- A imagem enviada em 03/10/2026 é referência visual do papel, não uma fonte autoritativa de cadastro, preços ou dados do estabelecimento.
- Interação prioritariamente por **tela de toque**. Interface web local em Django Templates, HTMX, CSS e JavaScript mínimo, aberta no navegador em modo fullscreen/kiosk configurável.
- Inicializador único sobe o servidor Django local e o agente de hardware, permanecendo na bandeja perto do relógio. Um comando próprio do `manage.py` é a entrada técnica; o operador usa atalho sem terminal.

**Reformulação vigente:** a regra de uma única comanda e descarte no fechamento foi substituída por múltiplas comandas, medições compartilhadas e descarte manual. A confirmação do usuário sobre descarte prevalece sobre as descrições anteriores deste planejamento.

As respostas anteriores sobre catálogo, impressão, numeração e Windows foram incorporadas; não permanecem como perguntas abertas. Preços, produtos, cabeçalho e rodapé serão informados nas respectivas telas. Propostas técnicas de implementação: unidades iniciais `UN` e `KG`, arredondamento monetário para centavos, histórico local sem exclusão automática e quantidade já lançada separada das marcações de acréscimo.

### Cadastro de produtos

- Campos confirmados: `description`, `unit_price`, `unit`, `is_scale_product`, `is_quick_access` e `appears_on_order_slip` (**Aparece na comanda**).
- Propostas complementares: `active`, ordem de acesso rápido e ordem no papel. Essas opções não ampliam o sistema para estoque ou caixa.
- O valor unitário de um produto em `KG` é o preço por quilograma. Para `UN`, é o preço por unidade. À vontade usa `UN`.
- Proposta: exatamente um produto por peso selecionado para a captura; impedir seleção de produto unitário e impedir leitura comercial sem produto/preço configurado.
- Cada medição guarda descrição, unidade, preço/kg e total calculado vigentes na captura. Mudanças no cadastro não reescrevem medições ou documentos anteriores.
- Itens adicionados diretamente guardam descrição, unidade, quantidade e preço vigentes na inclusão. O produto à vontade não precisa de associação a um produto pesado.
- Quantidade digitada de produto por peso aceita kg com até três casas decimais e é convertida para gramas inteiras; proposta de validação: quantidade positiva e preço não negativo. Inclusão manual não consome uma medição disponível e registra origem `MANUAL`; inclusão da balança registra `SCALE` e referência à medição.

### Configuração do programa

- Balança: seleção entre portas COM detectadas e entrada manual; porta inicial `COM3`, protocolo, baud rate, bits, paridade, stop bits, timeout e intervalo de consulta. Endereço físico no transporte atual é a porta COM; outros transportes não entram automaticamente no escopo.
- Impressora: seleção da fila do Windows, inicialmente `balanca`; largura útil/colunas, codificação, avanço e corte. Papel contínuo de 80 mm, sem paginação fixa de 210 mm.
- Impressão: nome no cabeçalho e texto do rodapé configuráveis; pré-visualização do documento. Conteúdo do papel respeita os produtos marcados e os efetivamente lançados.
- Numeração: **Número da próxima comanda**, inicialmente 1. Alterar não renumera comandas existentes. Proposta: aceitar somente inteiro positivo ainda não utilizado e alocar atomicamente, pulando números já ocupados; nunca reutilizar número de comanda cancelada ou impressa.
- Parâmetros de estabilidade em configuração técnica, com valores iniciais derivados da referência e confirmação física antes da produção.
- Alterar porta/protocolo exige parar e reiniciar a comunicação de forma controlada. Não modificar uma amostra em curso ou o conteúdo de medições já capturadas. Configuração inválida não substitui a última configuração válida.
- Histórico, rascunhos e configuração persistem após reinício. Configurações de impressão e linhas do catálogo são congeladas em cada documento finalizado.

## 4. Fluxo da operação

1. Atendente abre o programa, verifica equipamentos e inicia a leitura.
2. A aplicação consulta a balança e mostra peso atual e estado da conexão.
3. Peso positivo, recente e estável cria automaticamente uma medição persistente com identificador único, peso líquido e horário, **sem vínculo a uma comanda**. Produto da balança, preço/kg e valor por peso são congelados para que o valor informado ao cliente seja o lançado depois.
4. A medição entra na lista de disponíveis. O atendente informa o valor por peso e registra a escolha do cliente ao incluir a refeição na comanda.
5. Retirar o prato rearma a captura; outros pratos geram novas medições, independentemente do lançamento das anteriores.
6. O atendente abre ou seleciona uma comanda e insere nela uma medição disponível, com o total congelado. Também pode incluir diretamente qualquer produto, inclusive à vontade ou produto em kg com quantidade digitada. Inclusão direta não consome medição automaticamente.
7. O atendente inclui produtos pelos botões de acesso rápido ou pela busca no cadastro completo. Proposta: cada toque em produto unitário acrescenta uma unidade, com ajuste ou remoção antes de imprimir. Produtos em kg oferecem seleção de medição ou entrada manual de quantidade.
8. **Imprimir comanda** congela todos os itens e o documento, finaliza somente a comanda selecionada e cria o trabalho de impressão em uma transação local. As medições disponíveis permanecem intactas.
9. O trabalho é enviado à impressora `balanca`. Falha preserva a comanda finalizada e permite tentar novamente com o mesmo número e documento. A finalização libera o próximo atendimento; o estado de impressão continua visível separadamente.
10. Alternativamente, **Cancelar comanda** encerra somente o rascunho selecionado sem imprimir e invalida seus itens, preservando histórico. Proposta: pedir confirmação quando houver itens e devolver à lista as medições que estavam vinculadas a esses itens. As medições já disponíveis e as outras comandas permanecem intactas.
11. O atendente pode selecionar uma medição disponível e usar **Descartar medição**. A ação retira somente aquela medição da lista e registra o descarte; não apaga itens ou medições já usadas. Descarte em lote, se oferecido, exige seleção explícita e confirmação do conjunto.

Estados físicos propostos: `STOPPED`, `WAITING_ZERO`, `MEASURING`, `STABILIZING`, `WAITING_REMOVAL` e `ERROR`. A transição para estabilidade grava a medição automaticamente e passa a aguardar retirada; não existe espera por escolha para liberar o próximo prato. Ao iniciar ou reconectar, exigir retorno ao zero antes de armar um novo ciclo reduz o risco de repetir um prato após reinício. Esse comportamento deve ser validado na operação.

Peso ao vivo e medição capturada são objetos diferentes. A medição salva permanece na lista após retirada, variação de peso ou desconexão. Um prato ainda sobre a balança não gera outra medição apenas porque seu peso variou ou uma comanda foi impressa; é necessário observar retorno ao zero.

### Montagem e fechamento

- Proposta de tela: lista de comandas abertas, ação **Nova comanda** e identificação clara da selecionada; peso atual e conexão; lista compartilhada de medições com peso e valor e ação **Inserir na comanda selecionada**; produtos rápidos e busca; itens, subtotal, **Imprimir comanda** e **Cancelar comanda**. Cadastro, configurações e histórico ficam em telas próprias. À vontade aparece como produto, sem exigir pesagem.
- Vincular medição e criar o item ocorrem na mesma transação. Uma medição não pode originar dois itens ativos.
- Remover itens do rascunho é permitido. Proposta: remover um item pesado devolve sua medição à lista compartilhada; após finalizar, o documento permanece imutável e pode ser reimpresso.
- A identidade da comanda só é definida ao vincular a medição. A ação registra explicitamente a comanda destinatária; alternar a seleção da tela não pode redirecionar uma inclusão já iniciada.
- Pode haver captura sem nenhuma comanda aberta. As medições permanecem na lista compartilhada aguardando destino. Finalizar uma comanda não exige finalizar as demais nem iniciar nova captura física.
- Descarte manual retira da lista operacional, preservando histórico com motivo `MANUAL_DISCARD`. Somente medições `AVAILABLE` podem ser descartadas; não existe expiração automática ou limpeza da lista no fechamento.
- O impresso contém itens pré-inseridos e área manuscrita. Não recalcular total após anotações feitas no papel.

### Modelo de comanda impressa

Referência: fotografia fornecida pelo usuário em 03/10/2026. Elementos observados: nome do estabelecimento centralizado; número e data/hora; título **VALOR** e valor destacado; preço/kg e peso; lista de produtos com preço unitário e várias marcações vazias; campo **TOTAL A PAGAR R$** para preenchimento; separadores e mensagem no rodapé.

Adaptação necessária ao fluxo confirmado:

- Na área superior, imprimir somente refeições efetivamente inseridas, com descrição, quantidade, unidade, valor unitário e total; refeições pesadas também identificam peso e preço/kg. Refeições não aceitam marcação manual. Os demais produtos lançados aparecem na área manuscrita com suas unidades assinaladas.
- Suportar várias pesagens e itens à vontade. O exemplo de uma única pesagem não limita a comanda nova a um prato.
- Mostrar todas as refeições, por peso ou à vontade, com suas quantidades e valores; para cada pesagem, imprimir peso e preço/kg correspondentes. Substituir o destaque de uma única refeição do exemplo por uma relação de todas as refeições e respectivos valores.
- A lista com espaços manuscritos é a união dos produtos com **Aparece na comanda** e dos produtos efetivamente inseridos, excluindo refeições. Produto inserido sem essa marcação também imprime quantidade lançada e espaços; produto marcado sem lançamento imprime preço e espaços, sem gerar cobrança ou item de domínio.
- Evitar duplicar a linha de marcação do mesmo produto; assinalar [X] por unidade já lançada e reservar [ ] para acréscimos. Quantidade e valor lançado ficam explícitos, mesmo acima da capacidade das marcações. Preservar variantes históricas de preços e os detalhes das refeições. Subtotal de refeições e subtotal de todos os lançamentos ficam identificados separadamente.
- Reservar tantos espaços de marcação quanto couberem na largura útil da linha, usando oito como referência suficiente. Descrições longas podem ocupar linha adicional para preservar legibilidade e área de escrita.
- Manter campo de total final para preenchimento manual. O subtotal pré-inserido e esse total final possuem significados diferentes.
- Congelar também nomes, preços e ordem das linhas manuscritas, cabeçalho e rodapé no documento finalizado. Reimpressão não usa o catálogo atualizado.
- Validar legibilidade, largura útil, comprimento variável, corte e espaço de escrita em bobina contínua de 80 mm. Imprimir todas as linhas antes do corte; sem truncamento ou quebra fixa em 210 mm. A largura de 48 colunas da referência não será tratada como garantia universal.
- Não importar os produtos/preços da foto como dados iniciais sem solicitação. Cabeçalho e rodapé vêm da configuração local.

## 5. Arquitetura proposta

Projeto localizado em `D:\restaurante-local`, com ambiente, dependências, testes e distribuição independentes. Não importa código, configuração ou banco de `D:\restaurante`.

Base escolhida: Python, **Django + SQLite + Templates + HTMX + CSS/JS**, servidor WSGI local Waitress, adaptador serial com pySerial, impressão Windows RAW/ESC-POS e bandeja com pystray. A tela operacional e as configurações são web; Tkinter deixa de ser a interface proposta. Assets, fontes e ícones são locais. Não adotar DRF, SPA, Redis ou Celery neste escopo. Versões e dependências serão fixadas em ambiente próprio após verificar compatibilidade e licenças.

Decisão registrada na [ADR-0012](adr/0012-aplicacao-autonoma-django-touch.md). Organização de módulos, ciclo do inicializador e contratos estão em [Estrutura técnica](ESTRUTURA_TECNICA_APLICACAO_LOCAL.md). O recorte inicial do inicializador já existe; os demais contratos serão implementados por incremento.

| Camada | Responsabilidade |
| --- | --- |
| Domínio | Medição, ciclo físico, comanda, quantidades, produtos e cálculo por peso ou preço fixo. |
| Services | Capturar automaticamente, abrir/selecionar comanda, vincular, incluir/remover item, finalizar/cancelar, descartar medição manualmente, configurar sequência e solicitar reimpressão. |
| Models/selectors | Django ORM, restrições de persistência e consultas de pendências/histórico. |
| Adaptadores | Serial, impressora e simuladores. Não aplicam regras comerciais. |
| Interface | Peso ao vivo, medições compartilhadas, comandas abertas e selecionada, produtos rápidos, cadastro, configuração, histórico e diagnóstico. |

Inicializador mantém a bandeja no fluxo principal e inicia Waitress, leitor serial e fila de impressão em threads próprias. Workers chamam services; views chamam forms, services e selectors. Navegador não acessa hardware. Uma única instância controla equipamento e dados, independentemente do número de janelas do navegador. Não iniciar workers em imports, `AppConfig.ready()`, views ou `runserver`. Transações de banco não permanecem abertas durante comunicação física.

Tela touch: controles de pelo menos 48 px, ícones com rótulo nas ações relevantes, teclado numérico para peso/quantidade/preços, seleção inequívoca da comanda, feedback de toque e nenhuma operação dependente de hover. Atualização do peso e lista por polling local de regiões pequenas, sem recarregar a tela ou interromper edição.

Dados ficam em diretório gravável do usuário, separado do executável. Configurações são validadas e salvas atomicamente. Banco, logs e configuração operacional ficam fora do Git. Atualizações preservam dados; backup consistente e restauração integram a entrega.

## 6. Persistência e confiabilidade

- Medição: UUID, número legível, dispositivo, peso líquido em gramas inteiras, tara informativa quando disponível, horário de captura e parâmetros de estabilidade usados.
- Produto e preço: cadastro local para refeição por kg, refeição à vontade e produtos rápidos; snapshots preservam valores informados e lançados. Valores monetários usam centavos inteiros e/ou Decimal com arredondamento explícito, nunca float.
- Medição: `AVAILABLE`, `USED` ou `DISCARDED`, sem comanda na captura, com referência ao item quando usada e motivo quando descartada. O estado físico e o estado de impressão são independentes.
- Comanda/item: número sequencial único e estados `DRAFT`, `FINALIZED` e `CANCELLED`; vários rascunhos podem coexistir. Restrição de unicidade impede que uma medição gere mais de um vínculo ativo; vincular exige medição disponível e comanda aberta. Quantidade e preço ficam congelados na finalização. Cancelamento não reutiliza número.
- Trabalho de impressão: UUID, referência da comanda, conteúdo completo congelado incluindo área manuscrita, tentativas, erro e identificador do spooler quando disponível.
- Histórico técnico: capturas, vínculos, descartes manuais, finalizações, alterações de preço/configuração e reimpressões. Login e identificação individual do operador não foram solicitados; avaliar somente se houver necessidade.

Salvar a medição no momento da captura. No clique de impressão, finalizar a comanda selecionada e salvar seu trabalho antes de enviar bytes, sem modificar as medições disponíveis. Estados de impressão propostos: `PENDING`, `SUBMITTING`, `SPOOL_ACCEPTED`, `FAILED` e `UNKNOWN`. Aceitação pelo spooler não prova saída física do papel. Queda após iniciar envio pode deixar resultado incerto: mostrar intervenção e permitir reimpressão explícita, sem reenvio automático cego. Reimpressão mantém o identificador e os itens originais; proposta: identificar como segunda via. Repetir o clique não cria outra finalização, numeração ou trabalho de impressão inicial.

O parser novo deve rejeitar resposta incompleta, campo ausente, peso negativo, sobrecarga conhecida e leitura antiga. Enquadramento e mensagens de erro precisam de capturas homologadas. Não copiar a fila JSON atual como armazenamento definitivo de histórico comercial.

## 7. Sequência de implementação e critérios de aceite

Em 03/10/2026, cadastro/atendimento touch, captura automática simulada e recorte documental da etapa 4 estão implementados e validados em 94 testes. Etapas 2–4 permanecem parciais: faltam configuração de equipamentos, serial real, homologação de estabilidade e transporte físico RAW/ESC-POS. Cabeçalho/rodapé, documento congelado, preview, histórico e segunda via simulada já existem. Evidências e limites: [Atendimento e captura](IMPLEMENTACAO_ATENDIMENTO_CAPTURA.md) e [Documento e impressão](IMPLEMENTACAO_DOCUMENTO_IMPRESSAO.md).

| Etapa | Entrega | Evidência obrigatória |
| --- | --- | --- |
| 0 — Especificação técnica | Consolidar arquitetura, tela de várias comandas e papel contínuo. | Exemplo com duas comandas e medições compartilhadas; descarte exclusivamente manual documentado; arquitetura própria registrada sem modificar a ADR atual. |
| 1 — Fundação e inicializador | Django próprio, SQLite, Templates/HTMX, simuladores, comando run_local e bandeja. | Inicialização sem Restaurante/internet, dupla execução sem duplicar COM/servidor, abertura após prontidão, fechamento do navegador não encerra captura, Sair libera porta e servidor, diagnóstico de falha e preservação dos dados. |
| 2 — Captura | Serial na COM3, estados físicos e captura automática estável. | Quadros fragmentados/incompletos, oscilação, zero, leitura antiga e desconexão; uma medição por prato; retirada preserva pendência; vários pratos acumulam medições. |
| 3 — Cadastro, configuração e atendimento | Produtos/preços/unidades, balança, lista rápida, Aparece na comanda, configuração e múltiplas comandas sequenciais. | Inclusão manual em kg; à vontade sem pesagem; medição disponível vinculável a qualquer rascunho uma única vez; alternância não redireciona ações; correções e recuperação de todos os rascunhos; ajuste de sequência sem colisão. |
| 4 — Impressão e fechamento | Todas as refeições, união do catálogo marcado e itens lançados, marcações, papel contínuo, impressão e cancelamento. | Documento sem truncamento após 210 mm; produto não marcado lançado imprime quantidade/espaços; produto marcado não lançado não compõe subtotal; somente comanda selecionada encerra; medições disponíveis preservadas; descarte manual só afeta selecionadas disponíveis; duplo clique idempotente; falha não perde documento; segunda via fiel. |
| 5 — Distribuição | Runtime Windows, atalho sem terminal, navegador fullscreen/kiosk, assets locais, logs, backup e manual. | Windows 10/11 sem ambiente de desenvolvimento; offline; controles touch de 48 px e teclado numérico; instalação limpa; atualização preserva dados; backup restaurado e pendências recuperadas. |
| 6 — Homologação | Ensaio com os equipamentos e operação piloto. | Pesos conhecidos, tara, retirada antes/depois de estabilizar, vários pratos e comandas, preservação da lista no fechamento, descarte manual, reconexão, reinício com prato, acentos, espaço para escrita, corte, falta de papel e queda durante impressão. |

Cada etapa vira tarefa pequena com arquivos permitidos, fora de escopo e critérios verificáveis. O Codex implementa e revisa diretamente; harness e agentes externos permanecem desativados. Não iniciar servidores, executar hardware, instalar dependências ou alterar migrations do Restaurante como parte deste planejamento.

Primeiro marco demonstrável: **cadastrar produtos e configurar cabeçalho; abrir comandas 1 e 2; simular três pratos; inserir pesagens em comandas diferentes; incluir à vontade, peso manual e bebida; imprimir somente a comanda 1 em preview com todas as refeições e marcações; manter a comanda 2 aberta e a terceira medição disponível; descartar essa medição por ação manual**. Verificar cancelamento, mudança do próximo número, recuperação de rascunhos e falha de impressão. Depois acrescentar os adaptadores reais, separando defeitos de fluxo dos problemas físicos.

## 8. Fontes técnicas da proposta

- [Comandos próprios do Django](https://docs.djangoproject.com/en/5.2/howto/custom-management-commands/).
- [SQLite no Django e suas limitações de concorrência](https://docs.djangoproject.com/en/5.2/ref/databases/#sqlite-notes).
- [Waitress para Windows](https://docs.pylonsproject.org/projects/waitress/en/stable/).
- [Ícone de bandeja com pystray](https://pystray.readthedocs.io/en/latest/usage.html).
- [SQLite na biblioteca padrão, transações e backup](https://docs.python.org/3/library/sqlite3.html).
- [API serial e parâmetros de comunicação](https://pyserial.readthedocs.io/en/latest/pyserial_api.html).
- [WritePrinter e envio de dados RAW no Windows](https://learn.microsoft.com/en-us/windows/win32/printdocs/writeprinter).

Estas fontes sustentam a viabilidade técnica; os critérios de operação e a compatibilidade física precisam da definição de produto e dos ensaios descritos acima.
# Atualização de implementação — 03/10/2026

Os adaptadores próprios COM3/Windows RAW e a tela Equipamentos foram implementados conforme [ADR-0015](adr/0015-adaptadores-seriais-e-impressao-windows-raw.md). O teste RAW nº 7 teve acentos, 48 caracteres e corte confirmados pelo usuário. Leituras de zero e 236 g corresponderam ao visor; uma nova colocação informou 234 g. Homologação metrológica, cenários físicos de falha e distribuição permanecem pendentes. O registro detalhado está em [integração real](IMPLEMENTACAO_HARDWARE_REAL.md).

Continuação: captura automática de 236 g e saída completa da comanda nº 2 confirmadas; retorno ao zero, reinício sem duplicação e liberação da COM3 verificados. Consulta sem resposta admite uma repetição limitada conforme ADR-0016. Suíte: 118 testes aprovados.
