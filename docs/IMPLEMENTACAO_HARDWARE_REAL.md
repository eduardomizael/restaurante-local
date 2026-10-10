# Integração com os equipamentos instalados

Leitores configuráveis de 10/10/2026: USECB2 e PROT F agora implementados e selecionáveis em **Configurações → Balança e impressora**, conforme [ADR-0042](adr/0042-leitores-seriais-e-protocolo-configuravel.md). As descrições anteriores de aplicativo restrito a USECB2 registram a fase do diagnóstico. Antes de usar esta mudança, fechar o aplicativo e executar `rtk proxy uv run --offline --no-sync python manage.py initialize_local` na pasta do projeto para backup e migrations. A implementação não executou essa atualização no banco operacional. Depois selecionar o mesmo protocolo em [F][3] e na tela. No PROT F, retirada admite negativo estável; líquido positivo é capturado sem novo desconto e a tara fica não informada. Validação integrada física pendente.

Diagnóstico interpretado PROT F: `rtk proxy uv run --offline --no-sync python manage.py diagnose_hardware --scale --protocol PROT_F --samples 10 --port COM3`, com aplicação fechada. USECB2 permanece o padrão. Esse diagnóstico não cria medição/comanda ou imprime. Usar o protocolo correspondente à seleção física; não usar quadros de um protocolo como outro.

Verificação de protocolos em 10/10/2026: o diagnóstico oferece `--scale --probe passive --duration 10` para escuta sem comandos, e `--scale --probe query --duration 10` para consulta 0x04 a cada segundo. As duas sondas mostram blocos brutos em hex/texto, sem tratá-los como quadros comerciais ou exigir 150 bytes, e fecham a porta ao terminar. Duração de 1 a 60 s e limite de 65536 bytes. Não podem ser combinadas com impressão. Os blocos podem ser fragmentos ou múltiplos quadros; não representam automaticamente medições. A sonda conserva 9600 8N2 e DTR/RTS desligados. Mudança de protocolo é manual e autorizada; o aplicativo comercial ainda requer USECB2. Voltar a USECB2 antes de reabri-lo.

Complemento de 10/10/2026: silêncio completo após duas consultas mantém a conexão e admite recuperação por até cinco segundos desde a última amostra válida no perfil físico, descartando estabilidade anterior e exigindo três novas leituras. Falhas prolongadas, quadros inválidos e desconexão conservam rearme por zero. A mensagem de captura bloqueada é distinta da confirmação de peso salvo. Consulte [ADR-0041](adr/0041-recuperacao-limitada-de-silencio-serial.md); este complemento substitui descrições anteriores de fechamento obrigatório após duas consultas vazias. Confirmação operacional pendente.

Atualização de 10/10/2026: perfil físico passa a exigir três leituras consecutivas entre −2 e +2 g para liberar outro prato, com mínimo comercial de 40 g. O peso capturado não sofre desconto. A faixa inicialmente implementada de 0/+2 g foi ampliada a pedido do usuário; sinal negativo é preservado como leitura técnica e não cria medição comercial. Consulte [ADR-0040](adr/0040-retorno-proximo-de-zero-na-balanca-fisica.md) e a referência de hardware para evidências e limites.

Diagnóstico de transição autorizado, com aplicativo fechado: `rtk proxy uv run --offline --no-sync python manage.py diagnose_hardware --scale --samples 60 --interval 500 --port COM3 --show-frames`. O comando registra tamanhos, tempos e quadros, continua após falhas e encerra com resumo; não grava pesagens. Deixe sem carga no início, coloque e retire um prato durante a coleta. Não alterar tara nem protocolo durante o ensaio. Até 120 consultas, intervalo de 0 a 2000 ms, prazo de transporte de até dois segundos por consulta. A saída pode conter valores enviados pela balança; não adicionar logs ao Git.

Entrega em 03/10/2026, autorizada pelo usuário. Adaptadores seriais e Windows RAW próprios, configuração touch de porta/fila e indicação do modo na interface. A instalação usual não foi alterada pelos ensaios; usamos dados temporários.

## Operação

Com o programa fechado, executar `rtk proxy uv run --offline --no-sync python manage.py initialize_local` para atualizar o schema com backup. Em seguida, `rtk proxy uv run --offline --no-sync python manage.py run_local` inicia a COM3 e a fila `balanca`, editáveis em Equipamentos. Selecionar um produto KG para a balança. O ciclo precisa observar zero, estabilizar três leituras e aguardar retirada após uma captura.

`--simulate --preview-print` mantém o ambiente totalmente simulado. As flags também podem ser usadas separadamente. O modo de entrega fica congelado por trabalho: iniciar RAW não imprime filas antigas de simulação. Mudanças de porta reiniciam a captura; mudanças de impressora afetam apenas novos trabalhos. A prévia precisa ser revista após troca de modo/fila.

Diagnósticos explícitos, com a aplicação fechada para liberar COM3:

```powershell
rtk proxy uv run --offline --no-sync python manage.py diagnose_hardware --scale --samples 3 --port COM3
rtk proxy uv run --offline --no-sync python manage.py diagnose_hardware --print-test --printer balanca
```

O segundo comando imprime um recibo de teste sem valor comercial. Nenhum dos dois cria comanda ou medição comercial. Sem flags, o comando não acessa hardware.

## Transporte e recuperação

Uma consulta sem qualquer byte recebido admite uma única repetição na mesma conexão, com prazo total de dois segundos e timestamp da consulta original. Quadros parciais, inválidos ou excedentes não são repetidos; duas consultas vazias fecham a conexão e exigem zero. A decisão e a evidência estão na [ADR-0016](adr/0016-repeticao-limitada-de-consulta-sem-resposta.md).

O parser aceita o envelope e os campos observados em quadros de 150 bytes. Leituras truncadas, controles inesperados e campos repetidos são rejeitados; a conexão é fechada para reconexão e o ciclo exige zero. PESO L já é líquido; tara é preservada como informação. Valores monetários do equipamento não são utilizados.

A impressão usa cp860, tabela ESC/POS 3, 48 colunas, avanço e corte; rejeita caracteres não representáveis e controles antes de abrir o spooler. Escritas parciais são completadas. SPOOL_ACCEPTED significa aceitação pelo Windows e guarda o número do trabalho. Não confirma papel. Resultado incerto não é reenviado automaticamente; segunda via exige ação explícita.

Referências técnicas: [pySerial API](https://pyserial.readthedocs.io/en/latest/pyserial_api.html), [WritePrinter](https://learn.microsoft.com/en-us/windows/win32/printdocs/writeprinter) e [StartDocPrinter](https://learn.microsoft.com/en-us/windows/win32/printdocs/startdocprinter).

## Evidências e limites

Teste RAW nº 7: usuário confirmou acentos legíveis, 48 caracteres e corte correto. COM3 respondeu com zero e cinco leituras de 236 g; usuário confirmou 0,236 kg no visor e retirada com retorno a zero. A referência informada de 234 g diverge 2 g do equipamento; não houve calibração nem compensação por software.

Testes automatizados cobrem enquadramento, fragmentação, prazo, reconexão, escrita parcial, resultado incerto, proteção entre modos, configuração concorrente e fila congelada. Não acessam COM/spooler reais. Permanecem pendentes ensaios físicos de oscilação, sobrecarga, desconexão, falta de papel, múltiplos ciclos e documento longo. Não há declaração de homologação metrológica ou de distribuição final.

O usuário relatou oscilação entre 234 e 236 g, informou que a mesa não está bem nivelada e aceitou o ensaio de leitura como sucesso. A persistência automática não foi comprovada neste ensaio: respostas rejeitadas reiniciaram a exigência de zero antes da colocação. Sua lógica permanece coberta pelos testes automatizados; repetir um ciclo físico completo em apoio nivelado.

## Continuação do ensaio — captura e comanda reais

O diagnóstico da transição identificou consulta sem nenhum byte recebido, além de um quadro desalinhado após resposta atrasada. O enquadramento estrito foi mantido. A repetição limitada de consulta vazia foi implementada conforme ADR-0016. Vinte leituras consecutivas de zero responderam corretamente.

Após reinício e zero confirmado, a colocação física gerou automaticamente a medição nº 1: 236 g, tara zero, origem SERIAL:COM3. A tela mostrou “Pesagem salva” e o banco continha exatamente uma medição enquanto o objeto oscilava entre 234 e 236 g. Produto e preço eram fictícios e explicitamente de teste: R$ 100,00/kg, total R$ 23,60.

Pela interface, a medição foi incluída na comanda nº 2, devolvida à lista por remoção do item e novamente incluída, sem nova captura nem alteração de peso/preço congelados. Finalização pela prévia criou um único trabalho RAW; o Windows aceitou o trabalho nº 8, com uma tentativa. O banco confirmou a medição USED, comanda nº 2 FINALIZED e comanda nº 1 ainda DRAFT. A confirmação física do papel é separada da aceitação pelo spooler.

Suíte completa: 118 testes aprovados, com SQLite em arquivo; check de migrations sem alterações pendentes. Evidências visuais de desenvolvimento ficam em `outputs/`, ignorado pelo Git. Os commits foram autorizados pelo usuário após a validação; nenhum push foi realizado.

O usuário confirmou a retirada do objeto e a aplicação voltou a zero, pronta para o próximo prato. Confirmou também que a comanda nº 2 saiu completa e correta: 0,236 kg, subtotal R$ 23,60, campos manuscritos e corte. A persistência automática e a saída física desta comanda estão comprovadas neste ciclo.

Após reinício em zero, o banco preservou exatamente uma medição USED e o mesmo trabalho SPOOL_ACCEPTED nº 8, com uma tentativa, sem nova impressão. Encerramento coordenado removeu o registro de instância e liberou o mutex; abertura independente da COM3 confirmou zero após a liberação. Falhas físicas de sobrecarga, falta de papel, desconexão e ensaio prolongado continuam pendentes; o ciclo bem-sucedido não equivale à homologação metrológica.
