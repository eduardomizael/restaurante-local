# Estrutura técnica da aplicação local de pesagem

Atualização em 06/10/2026: [ADR-0038](adr/0038-atualizacao-por-git-e-pacotes-na-release.md) acrescenta instalações por Git/uv, versões por SHA, ambientes separados e abertura offline pela venv. Main distribui código aprovado; release publica executáveis. O manual atual do novo canal é [instalação por código](INSTALACAO_POR_CODIGO.md); registros datados abaixo descrevem a arquitetura anterior quando indicam publicação de pacotes pela main.

Incremento em 05/10/2026: encerramento touch pela interface sem navegador embutido ([ADR-0028](adr/0028-encerramento-touch-pela-interface.md)) e pacotes x86/x64 com atualização por arquitetura ([ADR-0029](adr/0029-distribuicao-windows-x86-e-x64.md)). Essas decisões complementam a distribuição x64 descrita anteriormente. Publicação destas alterações na main e validação no computador final ainda são etapas distintas.

Atualização em 05/10/2026: domínio, telas, configuração e transporte físico já foram implementados nos incrementos posteriores. A distribuição agora usa PyInstaller, executáveis Windows x64 e atualização web da main pelo atalho, com dados separados, backup e ativação por apontador. O contrato atual está na [ADR-0027](adr/0027-distribuicao-windows-e-atualizacao-por-release.md) e no [manual de distribuição](DISTRIBUICAO_WINDOWS.md); descrições abaixo de etapas ainda futuras registram o planejamento original.

Data: 03/10/2026. Especificação de implementação conforme [plano](PLANO_APLICACAO_LOCAL_PESAGEM.md) e [ADR-0012](adr/0012-aplicacao-autonoma-django-touch.md). Fundação e recorte inicial de `run_local` implementados em simulação; estado, comandos disponíveis e limitações em [Implementação da fundação](IMPLEMENTACAO_FUNDACAO.md). Models/services de produtos, medições e comandas implementados no [recorte de domínio](IMPLEMENTACAO_DOMINIO.md), conforme [ADR-0013](adr/0013-dominio-comercial-e-concorrencia-sqlite.md). Demais seções descrevem o contrato alvo, não funcionalidades já concluídas.

## 1. Projeto independente

Raiz independente: `D:\restaurante-local`, distribuição Python `local-weighing`, organizada em `config`, `apps`, `runtime` e `hardware`. `manage.py`, ambiente uv, pyproject, lockfile, settings, logs, assets próprios e primeiro recorte de models/migrations comerciais já existem. Impressão e configuração operacional ainda serão implementadas.

Estrutura prevista:

```text
restaurante-local/
  manage.py
  pyproject.toml
  uv.lock
  config/                 # settings, urls e wsgi
  apps/
    core/                 # DTOs, estado técnico e health check
    products/             # Product, forms, selectors, services, views
    measurements/         # Measurement e ciclo físico
    orders/               # Order, OrderItem e OrderSequence
    printing/             # PrintJob, snapshot e renderização ESC/POS
    configuration/        # AppConfiguration e tela de configuração
  runtime/
    application.py        # composição e encerramento
    tray.py               # menu da bandeja
    scale_worker.py
    print_worker.py
    instance_lock.py
  hardware/
    scale/                # serial e simulador
    printer/              # Windows RAW e preview
  apps/core/management/commands/run_local.py
  templates/              # atendimento, produtos, histórico, configurações
  static_src/             # CSS, módulos JS e ícones
  static/                 # assets da distribuição
  packaging/              # launcher sem console e runtime Windows
  tests/
```

Campos e nomes técnicos em inglês; UI e documentação em pt-BR. Não reutilizar implicitamente autenticação, catálogo ou dados do Restaurante. Não incluir DRF, Celery, Redis ou SPA. Componentes, ícones e estilos seguem as instruções locais em `AGENTS.md`, com assets próprios; nenhuma dependência por CDN.

## 2. Composição do runtime

```text
Atalho Windows → launcher → run_local
                              ├─ bandeja (fluxo principal)
                              ├─ Waitress → Django → navegador touch
                              ├─ ScaleWorker → MeasurementService → SQLite
                              └─ PrintWorker → Windows RAW → balanca
```

Um processo por instalação. A biblioteca da bandeja ocupa o fluxo principal; servidor e dois workers executam em threads próprias. Threads do Waitress atendem HTTP. O estado técnico compartilhado usa locks e DTOs; objetos ORM e conexões não são compartilhados entre threads.

O agente de hardware é um componente desse runtime novo, não o `scale_agent` existente. Ele só é iniciado uma vez pelo inicializador, independentemente de quantas páginas estiverem abertas. Importar Django, executar testes, `check` ou `makemigrations` nunca abre COM ou impressora.

### Entrada técnica e atalho

Contrato planejado, executado dentro do projeto novo:

```powershell
uv run python manage.py run_local
uv run python manage.py run_local --simulate --preview-print
uv run python manage.py run_local --no-tray --no-browser
```

`--simulate` garante que nenhuma porta serial seja aberta; `--preview-print` garante que nenhum byte seja enviado à impressora. `--no-tray` deixa o comando em primeiro plano até Ctrl+C. O atalho operacional usa launcher `.pyw`/runtime `pythonw` empacotado e chama o mesmo entrypoint, sem console ou ambiente de desenvolvimento. Empacotamento final em `.exe` poderá envolver esse mesmo runtime; não criar uma segunda implementação do início.

### Sequência de início

1. Resolver diretório de dados e adquirir mutex Windows por instalação. Segunda execução abre a interface existente, após confirmar sua identidade, sem iniciar outro servidor ou leitor.
2. Validar configuração de instalação, permissão dos arquivos e schema esperado. Se faltarem migrations, bloquear o início e mostrar diagnóstico; o início normal não executa migrations nem muda dependências.
3. Criar runtime, estado técnico, servidor e workers. Carregar configurações operacionais e verificar produto por peso selecionado antes de capturar medições comerciais.
4. Vincular Waitress a `127.0.0.1`, em porta local configurável. Porta ocupada por outro programa resulta em erro; não matar processos ou conectar a um servidor desconhecido.
5. Confirmar prontidão HTTP e identificação da instância; depois abrir o navegador em fullscreen/kiosk configurável, com perfil próprio. Não encerrar janelas pessoais do navegador.
6. Iniciar captura com configuração válida e aguardar retorno ao zero para armar o ciclo. Falha da COM deixa a aplicação disponível para configuração e lançamentos manuais, com erro visível.
7. Mostrar bandeja com estado e ações. Falha parcial de início encerra os componentes já iniciados e libera os recursos.

Migrations do novo projeto são geradas pelo Codex depois da revisão dos models e aplicadas em etapa explícita de instalação/atualização, com backup, não automaticamente em toda abertura.

### Bandeja e encerramento

Menu: **Abrir atendimento**, **Configurações**, **Pausar leitura / Retomar leitura**, **Status** e **Sair**. Configurações e status detalhado abrem páginas Django. Ícone indica operação ou falha; detalhes não dependem apenas de cor.

Fechar o navegador não encerra captura ou impressão. **Sair** desabilita novas mutações/capturas, coordena a conclusão das operações já aceitas, solicita parada, fecha COM, aguarda workers com prazo, encerra HTTP e libera mutex. Não fechar o navegador pessoal nem matar processos por nome. Saída forçada após timeout é registrada; impressão em andamento pode ficar `UNKNOWN` e nunca será repetida automaticamente.

Não instalar serviço Windows ou início automático no login sem solicitação. Queda inesperada do processo para todos os componentes; nova abertura recupera os dados persistidos e rearma a balança somente depois do zero.

## 3. Domínio e banco

| Model | Responsabilidade |
| --- | --- |
| Product | Descrição, valor unitário, unidade, produto da balança, acesso rápido, Aparece na comanda e ordenação. |
| Measurement | Peso líquido, tara informativa, snapshot comercial, captura e AVAILABLE/USED/DISCARDED; nenhuma comanda na captura. |
| Order / OrderItem | Comandas DRAFT/FINALIZED/CANCELLED e itens com snapshots e origem MANUAL/SCALE. |
| OrderSequence | Próximo número configurável, alocação atômica e números únicos; existentes não são renumerados. |
| PrintJob | Documento completo congelado, tentativas e resultado PENDING/SUBMITTING/SPOOL_ACCEPTED/FAILED/UNKNOWN. |
| AppConfiguration | Hardware, cabeçalho, rodapé, layout e parâmetros operacionais versionados. |

Persistir peso em gramas, quantidade unitária inteira e dinheiro em centavos; Decimal para entrada/cálculo intermediário e arredondamento explícito. Não confiar em float/DecimalField do SQLite para invariantes monetárias. Transações curtas em services; configuração SQLite com `transaction_mode=IMMEDIATE` e timeout limitado, sem `ATOMIC_REQUESTS`. `select_for_update()` não garante exclusão no SQLite.

Consumo de medição usa atualização condicional de AVAILABLE para USED e criação do item na mesma transação, com restrição única para vínculo ativo. Duplo clique deve retornar o resultado anterior ou conflito claro, nunca outro item. Numeração, impressão e alterações de itens possuem idempotência própria. Cancelar/remover item pesado pode liberar sua medição, preservando histórico do vínculo desfeito.

Cada worker administra sua própria conexão Django e fecha conexões obsoletas; não abrir transação enquanto lê a serial, chama o spooler ou espera. Testes concorrentes usam SQLite em arquivo com conexões distintas, não apenas mock ou teste sequencial.

## 4. Hardware e impressão

Em 03/10/2026, documento versionado, configuração de texto, finalização atômica, preview, histórico e fila simulada estão implementados no app `printing`. Estado SIMULATED é distinto de aceitação física/spooler; UNKNOWN não é reenviado automaticamente. Decisão e limites: [ADR-0014](adr/0014-documento-congelado-e-fila-simulada.md) e [entrega documental](IMPLEMENTACAO_DOCUMENTO_IMPRESSAO.md). RAW/ESC-POS continuam contratos futuros.

`ScaleAdapter` retorna peso líquido, tara, indício de estabilidade, horário monotônico da amostra e falha física. O parser valida quadro completo e campo PESO L. `ScaleWorker` coordena consulta; a máquina de estados detecta estabilidade, grava uma medição única por ciclo e espera retirada. Ausência de marcador de movimento não é prova suficiente de estabilidade: combinar janela de amostras homologada e idade da leitura.

Simulador reproduz sequências determinísticas de zero, variação, estabilidade, retirada, desconexão e reconexão. Alteração de COM/configuração reinicia apenas o adaptador entre ciclos, sem perder medições persistidas.

HTTP de impressão cria snapshot e trabalho, sem falar com a impressora. `PrintWorker` processa um trabalho por vez, confirma gravação do estado de envio, chama RAW fora de transação e registra resultado. Reinício com estado SUBMITTING transforma resultado em UNKNOWN para revisão; não reenvia automaticamente. Trabalhos PENDING ainda não enviados podem continuar normalmente.

Snapshot inclui itens, todas as refeições, união de produtos marcados e lançados, preço das linhas manuscritas, espaços conforme largura, cabeçalho e rodapé. Comprimento variável em bobina de 80 mm. Preview e ESC/POS usam o mesmo DTO documental, com testes de equivalência de conteúdo; preview web não substitui homologação física.

## 5. Interface touch e HTTP local

Estado implementado em 03/10/2026: atendimento, catálogo, numeração, teclado numérico, captura persistente pelo simulador e telas documentais. Contratos de apresentação, polling e limites provisórios estão registrados em [Atendimento e captura](IMPLEMENTACAO_ATENDIMENTO_CAPTURA.md) e [Impressão simulada](IMPLEMENTACAO_DOCUMENTO_IMPRESSAO.md). Serial e impressão física continuam propostos. Os simuladores não alteram os contratos de hardware homologável.

Templates Django e HTMX retornam HTML e fragments; forms validam sintaxe, services calculam e persistem, selectors consultam. JavaScript cuida de teclado numérico, foco e feedback; não é autoridade de preços, comanda ou consumo da pesagem.

O atendimento organiza medições compartilhadas no topo, cards de comandas à esquerda e detalhes à direita, com resumo compacto da balança. Diagnóstico do inicializador fica somente em Status. HTMX atende seleção/abertura, busca, inclusão de medição, remoção de item e polling; formulários de quantidade, confirmações e prévia/impressão conservam páginas próprias. Os contratos de atualização parcial, sincronização e rolagem estão na atualização de [Atendimento e captura](IMPLEMENTACAO_ATENDIMENTO_CAPTURA.md).

Layout operacional: peso/status no topo, pesagens compartilhadas e comandas abertas à esquerda, itens da selecionada e produtos rápidos na área principal. Botões com área mínima 48 x 48 px, espaçamento, contraste, ícones locais com rótulos, estados de carregamento e foco. Configuração e cadastro também precisam funcionar por toque. Peso, quantidade e preço têm teclado numérico; textos usam o teclado touch do Windows quando necessário.

Polling local inicial de aproximadamente 500 ms, pausado em página oculta, atualiza somente peso/status e fragmentos de listas quando houver mudança. Não substituir campos em edição, teclado aberto ou seleção. Lista de medições captura destino explícito da ação; resposta atrasada não altera a comanda selecionada. Nenhuma página abre COM.

Servidor vinculado apenas a loopback; DEBUG falso na distribuição, Host/CSRF restritos aos endereços locais e mutações por POST com CSRF. Secret key gerada localmente, fora do Git. Recursos estáticos locais servidos pela distribuição sem depender do servidor de desenvolvimento. Não abrir acesso à LAN ou criar login/papéis no MVP sem requisito.

## 6. Configuração, instalação e validação

Arquivo mínimo de instalação: diretório de dados, porta HTTP, navegador/modo e segredo Django. Configuração de equipamentos e comercial fica em SQLite como fonte única, editável pela tela. Mudanças de instalação exigem reinício; mudanças operacionais têm revisão observada pelos workers. Não manter valores de hardware concorrentes no arquivo e no banco.

Diretório de dados separado dos arquivos instalados, com banco, logs rotativos, configuração e backups. Distribuir Python/runtime, assets e dependências resolvidas; operador não roda uv/npm/pip. Backup consistente inclui banco e configurações; atualização não sobrescreve dados. Compatibilidade, manutenção, licenças e versão fixada de Django, Waitress, HTMX, pySerial, pystray e transporte Windows serão verificadas antes de adicionar dependências.

Critérios do primeiro incremento do inicializador: inicialização e parada com servidor/serial/spooler falsos; bandeja e modo sem bandeja; dupla execução; prontidão antes de abrir navegador; falha da porta HTTP; fechamento de navegador; cancelamento de início parcial; encerramento com serial em timeout e impressão incerta. Depois validar em Windows 10/11 com simulador e, em etapa autorizada própria, hardware real.

Fontes: [comandos Django](https://docs.djangoproject.com/en/5.2/howto/custom-management-commands/), [SQLite no Django](https://docs.djangoproject.com/en/5.2/ref/databases/#sqlite-notes), [Waitress](https://docs.pylonsproject.org/projects/waitress/en/stable/) e [pystray](https://pystray.readthedocs.io/en/latest/usage.html).
# Atualização de implementação — 03/10/2026

Componentes de interface compartilhados (04/10/2026): `core/base.html` inclui `core/navbar.html` em todas as páginas; `core/navigation_link.html` apresenta os links do topo e das seções de configurações. O context processor determina a área atual, inclusive nas páginas internas. Estilos usam `.primary-nav` e `.configuration-nav`, sem sobrescritas da navbar por página ou regras globais para qualquer `nav`. Manter aparência e alvos mínimos de 48 px consistentes; extrair componentes reutilizáveis quando a mesma apresentação for usada em mais de um fluxo.

Integração física definida em [ADR-0015](adr/0015-adaptadores-seriais-e-impressao-windows-raw.md): `hardware/scale/serial_adapter.py` e `protocol.py` implementam leitura tardia e enquadramento; `runtime/configured_scale.py` aplica revisão entre leituras; `apps/configuration` persiste porta/fila. `hardware/printer/windows_raw.py` envia ESC/POS pelo spooler. `PrintJob` congela modo e fila, distingue simulação de SPOOL_ACCEPTED e preserva UNKNOWN sem reenvio automático. Views não acessam hardware e o início não aplica migrations. `run_local` usa transportes reais por padrão; flags independentes mantêm simulação para desenvolvimento. Consulte [entrega e evidências](IMPLEMENTACAO_HARDWARE_REAL.md).

A [ADR-0016](adr/0016-repeticao-limitada-de-consulta-sem-resposta.md) permite uma única repetição de consulta sem bytes recebidos, com limite total de dois segundos e timestamp original. Quadros parciais, inválidos e excedentes continuam fechando a conexão e exigindo zero. Captura real, consumo pela interface, impressão da selecionada, reinício sem duplicação e encerramento foram verificados na instalação temporária.
