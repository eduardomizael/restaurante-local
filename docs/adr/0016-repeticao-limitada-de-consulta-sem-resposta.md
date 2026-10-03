# ADR-0016 — Repetição limitada de consulta sem resposta

Status: aceita. Data: 03/10/2026. Complementa ADR-0015.

## Contexto

Nos ensaios de captura real, uma consulta durante a transição de zero para peso não recebeu nenhum byte em um segundo. O adaptador fechou a porta, reiniciou o ciclo e passou a exigir zero quando o objeto já estava colocado. Vinte consultas consecutivas em zero responderam corretamente. O registro técnico distinguiu ausência de resposta de quadro parcial ou incorreto.

## Decisão

Repetir somente uma consulta que não recebeu nenhum byte e não tem bytes adicionais pendentes. Manter a mesma conexão durante essa repetição e descartar o buffer antes da nova consulta. Limitar a operação a dois prazos de um segundo, contados desde a primeira consulta. Preservar o timestamp inicial para que a validação de idade não transforme uma resposta antiga em nova.

Quadro parcial, inválido ou excedente não admite essa repetição: continua causando fechamento e rearme por zero. Duas consultas vazias também causam fechamento. Não relaxar critérios de estabilidade, consumo único ou retorno ao zero. O protocolo não oferece identificador de consulta; o timestamp conservador limita a idade mesmo se uma resposta atrasada chegar na segunda tentativa.

## Alternativas e consequências

Ignorar falhas indefinidamente permitiria capturas após interrupções longas. Aumentar globalmente o timeout atrasaria todo diagnóstico. Uma única repetição de consulta vazia permite recuperar silêncio breve, preservando validação de idade e tratamento de falhas persistentes. O encerramento continua aguardando o leitor; o prazo de três segundos comporta a operação serial de até dois segundos.

Testes isolados cobrem resposta vazia seguida de quadro válido, timestamp original, duas respostas vazias, quadros parciais e persistência de uma captura por ciclo. Confirmação física do novo ciclo deve ser registrada na entrega de hardware.
