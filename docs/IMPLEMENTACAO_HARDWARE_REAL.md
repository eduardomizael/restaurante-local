# Integração com os equipamentos instalados

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
