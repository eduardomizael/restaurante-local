# Fundação e primeiro recorte do inicializador

Data: 03/10/2026. Tipo: implementação direta e validação, sem agentes externos, push ou acesso ao projeto anterior. Commits da fundação autorizados expressamente pelo usuário.

## Implementado

- Django 5.2.17, Python 3.13, SQLite com `IMMEDIATE` e timeout de 5 segundos; nenhum model comercial neste incremento.
- `initialize_local`: preparação explícita, segredo local aleatório, migrations e backup SQLite consistente junto da configuração existente. Bloqueia atualização com runtime ativo.
- `run_local --simulate --preview-print`: mutex Windows por diretório de dados, schema validado sem migrar, Waitress loopback, confirmação HTTP de identidade/prontidão e abertura posterior do navegador.
- Segunda execução reutiliza somente a instância confirmada. Porta ocupada ou início parcial falho encerra componentes e libera mutex.
- Worker determinístico com peso em gramas, pausa/retomada, diagnóstico de falha e fechamento de adaptador. Não cria medições comerciais nem valores.
- Bandeja com Abrir atendimento, Status, Pausar/Retomar e Sair, no fluxo principal; modo sem bandeja encerra com Ctrl+C.
- Tela inicial e status com templates, CSS próprio, HTMX 2.0.8 local, polling de 500 ms pausado em aba oculta e durante POST, ações por POST/CSRF e controles de pelo menos 48 px. Não há campos comerciais ou teclado numérico ainda.
- Dados, segredo, banco, backups e logs rotativos separados do programa; assets servidos com lista explícita mesmo com DEBUG falso.

## Evidência automatizada

19 testes em Windows no ambiente de desenvolvimento, sem hardware real ou navegador visível:

- cópia de estado entre threads, pausa, falha de leitura e fechamento do simulador;
- HTTP, assets locais, bloqueio de GET/POST sem CSRF e recusa de ações após início do encerramento;
- exclusão via mutex e segunda execução em processo distinto sem duplicar componentes;
- instalação e atualização em diretório temporário, backup e bloqueio da atualização durante execução;
- migrations ausentes recusadas sem aplicação automática;
- Waitress real, conexão keep-alive, encerramento de threads e reutilização da porta;
- fechamento dos sockets na própria thread do loop HTTP, evitando corrida com `select` no Windows; exceções não tratadas em threads fazem os testes falhar;
- porta ocupada, identidade incorreta e início parcial falho;
- leitor que excede prazo mantém mutex até parada efetiva/saída do processo;
- callbacks da bandeja via backend falso e limpeza após falha.

`check` sem problemas; `makemigrations --check --dry-run` sem alterações. Migrations comerciais não foram escritas manualmente nem geradas, porque ainda não há models comerciais.

## Pendências e limitações

A etapa 1 está parcialmente concluída. Faltam worker/fila e preview documental de impressão, persistência do domínio, formulário de configuração e menu correspondente, ensaio visual da bandeja, navegador com perfil próprio/kiosk e distribuição sem ferramentas de desenvolvimento. `--preview-print` é uma barreira de modo seguro nesta fundação, não um preview já funcional. Execução sem ambas as flags de simulação é recusada.

O servidor e o adaptador são encerrados antes de liberar mutex. Em timeout de worker ou requisições, a exclusão é mantida até a saída do processo; não há transporte físico ou trabalho de impressão incerto neste incremento. Logs registram início, falhas e encerramento; diagnóstico de impressão e recuperação de `UNKNOWN` pertencem à implementação da fila.

A interface foi validada por renderização HTML e testes HTTP, sem avaliação visual interativa de toque. A bandeja nativa e a abertura do navegador foram implementadas mas testadas com substitutos; não declarar homologação de Windows 10/11, kiosk ou hardware físico.

Próximo recorte: models e services de produtos, medições e comandas, restrições de banco e testes concorrentes com SQLite em arquivo; depois persistência da captura e documento congelado/fila de impressão. Não há nova definição de produto necessária para iniciar esse trabalho.

## Dependências e proveniência

Versões diretas fixadas no pyproject e transitivas no lockfile. Licenças conferidas nos metadados instalados: Django BSD-3-Clause, Waitress ZPL-2.1, pystray LGPLv3, Pillow MIT-CMU. A distribuição ainda deve incluir os avisos/licenças aplicáveis; não há empacotamento final neste incremento.

HTMX 2.0.8 vendorizado do [repositório oficial](https://github.com/bigskysoftware/htmx/tree/v2.0.8), com licença local em `static/vendor/HTMX-LICENSE.txt`. SHA-256 do JS: `22283ef68cb7545914f0a88a1bdedc7256a703d1d580c1d255217d0a50d31313`. Nenhum asset depende de CDN em execução.

Compatibilidade consultada em fontes primárias: [Django 5.2 LTS](https://docs.djangoproject.com/en/5.2/releases/5.2/), [Django 5.2.17](https://pypi.org/project/Django/5.2.17/), [Waitress](https://docs.pylonsproject.org/projects/waitress/en/latest/), [pystray](https://pypi.org/project/pystray/) e [HTMX](https://htmx.org/docs/). pySerial e transporte de impressão Windows serão acrescentados somente ao implementar seus adaptadores.
