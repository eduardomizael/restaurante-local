# ADR-0041 — Recuperação limitada de silêncio serial

Status: aceita. Data: 10/10/2026. Complementa ADR-0040; substitui na ADR-0016 o fechamento obrigatório e rearme imediato após duas consultas completamente vazias.

## Contexto

Após liberar o próximo prato, o usuário observou estabilização seguida de solicitação de retirada sem captura. O diagnóstico físico registrou cinco ausências de resposta em 60 consultas, incluindo leituras em zero. O registro do runtime em 10/10/2026 confirmou sucessivas exceções de ausência de resposta após duas consultas. O worker tratava silêncio como falha física genérica, reiniciando o ciclo antes de completar três amostras comerciais. Não houve evidência de que o ciclo confirmasse um candidato sem persistir.

## Decisão

Distinguir `ScaleNoResponseError` de quadros parciais, inválidos, excedentes e erros de porta. Duas consultas sem nenhum byte continuam limitadas a aproximadamente dois segundos por chamada. Somente esse caso mantém a porta aberta; cada consulta seguinte descarta o buffer como antes. Fechamento explícito e erros físicos continuam liberando a conexão.

No runtime físico, permitir recuperação de silêncio por até cinco segundos contados desde a última amostra válida, sem prorrogar o prazo em falhas sucessivas. Conferir o prazo no fim da consulta sem resposta e na chegada da próxima leitura. Não fabricar peso, zero ou indicador de estabilidade.

Descartar amostras comerciais acumuladas antes do silêncio e exigir três leituras novas recentes com variação de até 2 g e tara constante. Preservar a liberação obtida em zero somente dentro desse prazo. Se nenhuma liberação ocorreu, continuar exigindo zero. Se já houve captura confirmada, conservar seu candidato e o bloqueio de retirada para impedir duplicação. Reiniciar contagem de retorno próximo de zero ao interromper. Acima do prazo, ou após qualquer outra falha física, exigir novamente três leituras entre −2/+2 g. Pausa, mudança de configuração e regras comerciais permanecem vigentes.

Publicar estado `RECOVERING` durante recuperação breve. A mensagem WAITING_ZERO passa a dizer explicitamente que a captura está bloqueada, distinguindo-a de WAITING_REMOVAL, que confirma persistência. O simulador padrão conserva recuperação desativada; ensaios específicos injetam o parâmetro físico. Registrar o limite nos parâmetros históricos da medição.

## Alternativas e consequências

Aumentar tolerância de peso não corrige ausência de bytes. Exigir zero a cada silêncio breve repete o bloqueio constatado. Ignorar silêncio sem prazo poderia reutilizar uma liberação antiga. Manter a conexão evita tratar silêncio como desconexão presumida, mas não resolve sua causa física. O limite de cinco segundos é técnico e provisório; foi escolhido para comportar uma consulta vazia de dois segundos e retomada curta, e ainda exige confirmação operacional. Não houve troca de protocolo, compensação comercial ou publicação.

## Validação e limites

Testes automatizados cobrem o worker com duas amostras comerciais, silêncio e três novas amostras até persistência única; prazo fixo em silêncios sucessivos; prazo expirado na chegada; ausência de liberação sem zero; bloqueio de captura já salva; reuso de handle e descarte do buffer após consulta vazia. Falhas genéricas e quadros parciais continuam nos testes de reconexão e rearme. Não foi realizado novo acesso físico neste incremento. A correção não comprova a causa do silêncio serial nem homologação física.
