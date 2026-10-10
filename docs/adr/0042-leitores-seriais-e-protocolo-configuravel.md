# ADR-0042 — Leitores seriais e protocolo configurável

Status: aceita. Data: 10/10/2026. Complementa ADR-0015, ADR-0040 e ADR-0041.

## Contexto

O usuário solicitou leitores para protocolos diferentes e seleção na aplicação. USECB2 foi observado em respostas de 150 bytes com peso líquido e tara. Em consultas com visor negativo, não respondeu. PROT F respondeu a 0x04 com peso líquido positivo (396/398 g), negativo (−494/−496 g) e indicação de instabilidade `IIIIII`. Escutas passivas de dez segundos não observaram transmissão espontânea em nenhum dos dois protocolos. Isso não comprova ausência de envio por tecla ou outros modos.

## Decisão

Disponibilizar USECB2 e PROT F em Configurações → Balança e impressora, com USECB2 como padrão para configurações existentes. A seleção é explícita, versionada e validada no form, service e banco. Não detectar protocolo por tentativa de interpretar dados ambíguos. A troca física é feita pelo operador em [F][3]; salvar na aplicação não envia comando de configuração à balança. Protocolos sem enquadramento verificado não são oferecidos.

Manter transporte compartilhado lazy em 9600 8N2, DTR/RTS desligados e consulta 0x04. A fábrica instancia o leitor correspondente à seleção. O worker fecha o leitor anterior e substitui entre consultas quando a revisão muda, exigindo nova sequência de retirada antes de capturar. Sem I/O em imports, forms, views ou AppConfig.ready().

USECB2 conserva seu parser estrito de 150 bytes, net/tara e bloqueio de valores fora do limiar de retorno de ±2 g. PROT F usa envelope STX/ETX: pesos observados de nove bytes, com sinal/espaço e duas casas inteiras mais três decimais; instabilidade observada de oito bytes (`STX IIIIII ETX`). O leitor acumula fragmentos até ETX ou limite de nove bytes, com timeout e rejeição de excedentes. Estados desconhecidos, incluindo sobrecarga sem quadro homologado, são recusados como falha. Não transformar instabilidade em zero na interface nem em medição comercial.

No PROT F, retirada é confirmada por três amostras recentes sem movimento, com peso líquido ≤ +2 g e diferença máxima de 2 g entre mínimo e máximo da sequência. Assim, peso negativo estável com tara ativa libera o próximo prato. Isso indica condição para novo ciclo, não ajuste do zero físico. Se a tara estiver incorreta, um peso negativo estável também liberará o ciclo; a configuração de tara continua responsabilidade da balança. Capturas comerciais seguem positivas, mínimo de 40 g, três amostras com variação total máxima de 2 g e sem duplicação até a retirada. Não alterar automaticamente para cinco amostras ou mediana sem decisão específica. Recuperação breve de silêncio da ADR-0041 permanece limitada a cinco segundos.

PROT F não informa tara no quadro observado. Tornar `Measurement.tare_grams` nullable e guardar NULL quando desconhecida, preservando valores históricos existentes. Não representar ausência como zero e não reutilizar tara de uma leitura USECB2 anterior. Congelar protocolo nos parâmetros históricos, junto aos limites do ciclo. Dinheiro e peso comercial continuam derivados exclusivamente de inteiro líquido positivo; nunca descontar tara novamente.

## Migrations e operação

Models revisados e migrations geradas por `makemigrations`: campo e constraint de protocolo em configuração; tara nullable nas medições. Padrão USECB2 preserva instalações existentes. Atualização do banco deve ocorrer com aplicativo fechado, backup e `initialize_local`, nunca automaticamente na abertura. A geração e testes usam banco isolado; o banco operacional não foi alterado neste incremento.

Após atualizar, selecionar na balança e na tela o mesmo protocolo. Para PROT F, retirar carga e aguardar sequência negativa/zero estável antes de colocar o prato. A tela mostra o protocolo da última leitura válida. Diagnóstico aceita `--protocol USECB2` ou `--protocol PROT_F`; a sonda bruta permanece disponível e não cria registros comerciais.

## Validação e limites

188 testes aprovados de protocolos, configuração HTTP, ciclo, domínio, recuperação, inicializador e impressão simulada. Casos específicos cobrem quadros reais resumidos em fixtures, fragmentação, instabilidade de oito bytes, formato inválido, seleção e revisão obsoleta, troca e fechamento entre consultas, negativo variável que não rearma, negativo estável que rearma, captura líquida de 396 g com tara NULL, oscilação, duplicação e interrupção de estabilidade por movimento. Migrations geradas revisadas e check sem pendências. Testes de subprocessos exigiram execução fora do sandbox por restrições de arquivos temporários; nenhum hardware real foi usado nesta implementação.

Os ensaios físicos anteriores fundamentam o parser; ainda falta confirmar o fluxo completo da aplicação configurada em PROT F, inclusive tara, falhas, retirada e documento. Não há homologação metrológica, commit ou publicação implícitos.
