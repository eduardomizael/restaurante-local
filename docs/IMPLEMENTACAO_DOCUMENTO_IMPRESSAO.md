# Documento, fechamento e impressão simulada

Entrega em 03/10/2026, conforme [ADR-0014](adr/0014-documento-congelado-e-fila-simulada.md). Implementação e revisão diretas, sem commit implícito, spooler, COM, instalação de serviço ou alteração de dados operacionais.

## Como usar

1. Em **Documento**, informar nome no cabeçalho e rodapé. Salvar não muda documentos anteriores. Equipamentos permanecem fora desta tela neste recorte.
2. Abrir e selecionar comanda, incluir itens e tocar **Prévia e impressão simulada**. A prévia não finaliza nem cria trabalho. Cabeçalho configurado e ao menos um item são necessários para confirmar.
3. Revisar o papel contínuo. **Finalizar e simular impressão** encerra somente a selecionada e grava seu documento/trabalho na mesma transação. Mudança comercial depois da prévia exige nova revisão. Outras comandas e medições disponíveis permanecem intactas.
4. A fila mostra **Simulada — sem impressão física** quando o simulador valida o conteúdo completo. Histórico reúne documentos e resultados. **Ampliar prévia para leitura** muda apenas a apresentação na tela.
5. Segunda via tem confirmação própria, conserva conteúdo/preços originais e acrescenta identificação de via. Falha conhecida ou resultado incerto ficam visíveis e não são reenviados automaticamente. Confira o resultado antes de solicitar nova via.

## Documento e persistência

DTO JSON versão 1, único por comanda, inclui cabeçalho/rodapé, número, horários, todas as refeições e produtos lançados com quantidades/preços individuais, subtotal e linhas manuscritas. União por identidade do produto cobre marcados ativos e efetivamente lançados, inclusive produtos posteriormente inativados. Preços históricos distintos continuam explícitos; uma linha de marcações por produto. Produto reservado sem lançamento não gera cobrança. Há oito espaços no perfil de 48 colunas e campo **TOTAL A PAGAR R$** para preenchimento manual.

Texto web e texto recebido pelo simulador vêm do mesmo renderer. Bobina de 80 mm com altura variável, sem paginação fixa de 210 mm. Prévia é HTML escapado, sem executar texto configurado como markup. A ampliação visual não altera DTO ou renderização comercial.

Migration `printing/0001_initial.py` gerada com Django e revisada: singleton de configuração, documento one-to-one protegido e trabalhos com UUID único, um inicial por documento, um envio ativo e restrição coerente de status/tentativa/datas. Não houve edição manual de migration. Aplicação somente em testes/instalação temporária explícita. Para atualizar uma instalação existente: fechar o programa e executar `initialize_local`, que salva backup antes de migrar; abertura normal bloqueia schema pendente e nunca migra automaticamente.

## Fila e recuperação

Worker independente do navegador, criado somente pelo inicializador. SQLite IMMEDIATE protege finalização, solicitação, claim e resultado; transporte ocorre fora da transação. Snapshot já está salvo quando o transporte recebe texto. Estados: PENDING, SUBMITTING, SIMULATED, FAILED e UNKNOWN; SIMULATED é específico deste modo e não representa papel impresso.

Mutex exclusivo precede recuperação. Novo runtime converte tentativas interrompidas SUBMITTING em UNKNOWN e preserva documentos. PENDING continua normalmente. UNKNOWN/FAILED só originam novo trabalho após ação explícita. Falha na gravação do resultado deixa SUBMITTING sem reenviar e requer reinício para classificá-lo como UNKNOWN. Encerramento termina envio simulado corrente; trabalho aceito pelo HTTP durante drenagem pode permanecer PENDING até a próxima abertura. Se o worker não encerra no prazo, mutex não é liberado como se o processo estivesse parado.

## Validação e limites

94 testes aprovados, incluindo 24 novos testes de impressão e dois de ciclo do inicializador. Casos: finalização isolada/atômica/idempotente; rollback; prévia obsoleta; união e preços históricos; documento longo com 70 produtos, mais de 300 linhas e rodapé preservado; CSRF, métodos e HTML escapado; segunda via fiel; transporte fora da transação; falha antes do envio, resultado incerto e falha de persistência; worker real; finalizações/cancelamento/claims concorrentes em SQLite em arquivo; recuperação em processos distintos sem reenvio.

Ensaio de navegador com dados temporários: duas comandas e três pesagens; configurar cabeçalho/rodapé; finalizar a comanda 1 com 252 g e uma refeição à vontade, subtotal R$ 50,99; simular segunda via; confirmar comanda 2 aberta com 300 g e terceira pesagem de 400 g disponível. Histórico mostra ambas as simulações. Não é homologação física de tela touch ou impressora.

Pendentes: serial real e sua configuração, perfil físico da balança, configuração/transportes Windows RAW e ESC/POS, acentos/colunas/avanço/corte, distribuição e piloto. Próximo recorte sugerido: configuração operacional e parser serial testado com quadros simulados, antes de conectar equipamentos reais.

## Atualização do layout em 03/10/2026

Conforme [ADR-0017](adr/0017-layout-compacto-da-comanda.md), novos documentos usam a versão 2: nome no cabeçalho com largura e altura dobradas, produto e preço em colunas fixas e seis marcações manuais na mesma linha para preços usuais. Todos os nomes do catálogo da referência cabem na coluna de 20 caracteres; nomes maiores continuam nessa coluna sem truncamento. A coluna dos preços tem seis caracteres ou a largura do maior preço do documento, aplicada igualmente a todos os itens. Quantidades já lançadas continuam explícitas quando existentes.

Documentos versão 1 e suas segundas vias preservam o formato anterior. Nenhuma migration ou alteração de dados operacionais. A suíte atual tem 123 testes aprovados; prévia ampliada revisada no navegador em instalação temporária simulada. O novo tamanho físico do cabeçalho ainda não foi confirmado em papel. Para carregar o código atualizado, sair pela bandeja e iniciar novamente com run_local. Os próximos passos de hardware citados na entrega original acima já foram implementados; consulte o registro de hardware e as ADRs 0015 e 0016.

## Refeições e unidades assinaladas

A versão 3 ([ADR-0018](adr/0018-refeicoes-e-marcacoes-preenchidas.md)) mostra somente refeições na área superior e exclui refeições das marcações. Produtos por unidade aparecem na área manuscrita com um [X] por unidade lançada e os demais espaços [ ] livres. Quantidade e valor lançado continuam explícitos, inclusive quando a quantidade excede os espaços. Subtotal de refeições e subtotal de todos os lançamentos têm rótulos distintos; não há cobrança dos espaços vazios. Versões 1 e 2 permanecem fiéis na reimpressão. 127 testes aprovados; sem migration ou alterações dos dados operacionais.
