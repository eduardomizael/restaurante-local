# ADR-0040 — Retorno próximo de zero na balança física

Status: aceita. Data: 10/10/2026. Substitui o requisito de zero exato da ADR-0020 para o perfil físico US 31/2 POP-S; conserva o peso fixado após persistência.

## Contexto

O usuário relatou plataforma sem carga com resíduo de 2 g e influência de vento, bloqueando o rearme até acionar tara. Autorizou o ajuste e o diagnóstico serial. Informou capacidade 6/15/31 kg, divisões 2/5/10 g, mínimo 40 g e protocolo USECB2. A foto de seu manual descreve USECB2 de 80 bytes; isso não substitui as evidências dos quadros recebidos nesta instalação.

## Decisão

No runtime físico, reconhecer retirada após três leituras consecutivas recentes de líquido entre −2 e +2 g, sem indicação de movimento. Uma leitura acima dessa faixa ou com movimento reinicia a contagem. Início, pausa, reconexão, mudança comercial, amostra inválida ou intervalo excessivo continuam exigindo nova sequência. Peso negativo nessa faixa é somente leitura técnica de plataforma vazia; nunca é captura comercial. Valores abaixo de −2 g continuam causando rearme conservador. Não converter falha em zero.

Complemento ainda em 10/10/2026: após o primeiro ajuste de 0 a +2 g, o usuário relatou oscilação para mais ou menos e solicitou desconsiderá-la. O parser passa a preservar sinal explícito no peso líquido para diagnóstico e avaliação pelo ciclo, mantendo tara não negativa e enquadramento estrito. O simulador padrão conserva zero exato. A validade de um quadro com peso negativo não autoriza sua persistência comercial. A aceitação de sinal foi testada em quadros sintéticos; nenhum quadro físico negativo foi registrado no diagnóstico anterior.

Após o complemento bilateral, 64 testes de captura e hardware passaram. Novos casos cobrem quadros com sinal, tara negativa recusada, retorno −2/+2/−2 sem duplicação ou alteração comercial, segunda captura após retirada e rejeição de −4 g. Nenhum ensaio físico adicional foi iniciado nesse complemento.

Preservar três leituras comerciais com variação máxima de 2 g e tara constante. Alinhar o mínimo comercial do perfil físico a 40 g. A tolerância de retirada não é desconto, tara adicional ou ajuste do peso salvo. Congelar o limiar e a quantidade de amostras de retorno nos parâmetros históricos da medição. O simulador conserva seus parâmetros anteriores; o ciclo puro recebe esses valores explicitamente.

Manter o protocolo serial e o parser estrito de 150 bytes. Ampliar `diagnose_hardware` para ensaio finito de até 120 consultas com intervalo, tamanho, duração, erros e quadro hexadecimal opcional. Continuar após erro para observar recuperação, fechar a porta ao terminar e retornar falha ao final se qualquer consulta falhar. Nenhuma medição comercial é criada. Não repetir impressão após diagnóstico serial malsucedido.

## Alternativas e consequências

Exigir zero absoluto mantém o bloqueio observado. Aceitar uma única leitura próxima de zero libera o ciclo com um mergulho transitório; três leituras reduzem esse risco. Um limiar de 40 g confundiria carga mínima com plataforma vazia. Trocar de protocolo sem captura real exigiria suposições sobre enquadramento e sinalização. A tolerância não remove a influência física do vento; proteção da corrente de ar e nivelamento continuam necessários para qualidade da medição.

## Validação e limites

104 testes aprovados, incluindo sequência 0/2/0 g, interrupção por 4 g/movimento/reset/intervalo, ausência de duplicação, mínimo de 40 g e preservação integral do peso comercial. Diagnóstico com transporte injetado comprova registro de 80 e 150 bytes, continuidade e fechamento após falha. O sandbox bloqueou arquivos temporários e sockets em testes de fundação; a repetição autorizada fora dele passou.

Consulta física autorizada em COM3: dez respostas válidas de 150 bytes, líquido 0 g, tara 308 g, duração entre 0,233 e 0,397 s. Nenhuma falha. Ensaio seguinte de 60 consultas, com colocação/retirada orientada ao usuário: 55 válidas de 150 bytes e cinco falhas com **zero bytes**, cada uma após duas consultas e cerca de dois segundos. Leituras válidas mostraram 396 g e depois 0 g, tara constante de 308 g. Também houve silêncio após o retorno a zero. A recuperação ocorreu sem alterar protocolo ou tara. Não houve quadro válido de 80 bytes. A porta foi fechada ao final. Uma primeira tentativa dentro do sandbox não conseguiu abrir a porta; os resultados físicos acima são da execução autorizada fora dele.

Ausência de resposta é apresentada explicitamente pelo adaptador, em vez da mensagem genérica de quadro incompleto. Preservar a exigência conservadora de rearme após falha de transporte; a tolerância de 2 g não deve mascarar silêncio serial. Diagnóstico confirma intermitência, mas não determina se sua origem é firmware, instabilidade física ou transporte/cabo. Confirmação do novo rearme no aplicativo permanece pendente. Sem publicação ou mudança do protocolo do equipamento.
