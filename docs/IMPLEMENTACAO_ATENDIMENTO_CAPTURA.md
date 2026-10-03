# Atendimento touch e captura simulada

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


Configuração de cabeçalho/rodapé e DTO documental congelado; preview em bobina contínua de 80 mm, finalização isolada da selecionada e fila simulada com idempotência/recuperação de resultado incerto. Adaptadores COM/RAW, perfil de estabilidade definitivo e distribuição Windows continuam pendentes.
