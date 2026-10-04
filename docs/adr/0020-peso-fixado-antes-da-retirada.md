# ADR-0020 — Peso fixado ao estabilizar e rearme por zero

Status: aceita. Data: 03/10/2026. Complementa ADR-0013 e ADR-0016.

## Contexto e decisão

O usuário observou o peso fixado na tela somente ao retirar o prato e determinou captura ao estabilizar, com nova medição somente após zero. O ciclo já persistia imediatamente após três amostras estáveis; o destaque da tela publicava todas as leituras posteriores e podia divergir do peso capturado. A atualização de listas também ficava suspensa enquanto um campo permanecesse com foco.

Após persistir e confirmar o candidato, manter o peso destacado igual ao peso capturado durante WAITING_REMOVAL. Publicar separadamente `live_weight_grams` para diagnóstico, sem recalcular a medição persistida. Aguardar leitura fresca de exatamente zero, sem indicador de movimento, antes de liberar outra captura. Alterar o limiar padrão de zero de 10 g para 0 g; conservar tolerância de estabilidade de 2 g, mínimo comercial de 11 g, janela de três amostras e validação de idade. Os parâmetros continuam congelados na medição.

Na atualização dos fragmentos, o foco em campo não bloqueia sozinho as listas e o estado técnico. Continuar protegendo diálogos abertos, formulários em envio e página oculta. Os fragmentos não substituem os campos de busca ou formulários de edição. Ao pausar, reconectar, falhar ou alterar configuração, os bloqueios e rearme conservadores do ciclo continuam válidos.

## Validação e limites

Teste com worker e persistência reais, adaptador simulado e leituras controladas: após 0, 252, 252, 252 g, a medição existe antes de remover o prato; leitura posterior de 400 g mantém destaque em 252 g e não cria outra medição. Somente 0 e três leituras estáveis de 300 g produzem a segunda medição. Outro teste confirma que 5 g e zero com movimento não rearmam.

Ensaio visual simulado mostrou 236 g fixados enquanto as leituras seguintes eram 400 g, com **Peso fixado · pesagem salva · aguardando zero**. Os dados operacionais e equipamentos reais não foram usados. O novo comportamento visual e o rearme estrito por zero ainda precisam de confirmação com o equipamento físico.
