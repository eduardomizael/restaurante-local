# Restaurante Local

Distribuição em 06/10/2026: [instalação por Git e uv](docs/INSTALACAO_POR_CODIGO.md), com atualização automática do código da `main` pelo atalho. O usuário prepara Git e uv na máquina final e executa `Instalar-codigo.bat` uma vez. Pacotes executáveis e o site são publicados somente pela branch `release`. Consulte a [ADR-0038](docs/adr/0038-atualizacao-por-git-e-pacotes-na-release.md). A validação no Windows x86 final permanece uma etapa própria.

Atualização em desenvolvimento: encerramento touch pelo botão **Encerrar aplicação**, com confirmação, conforme [ADR-0028](docs/adr/0028-encerramento-touch-pela-interface.md). Distribuição com pacotes **x86 (Windows de 32 bits)** e **x64 (Windows de 64 bits)** e atualização por arquitetura, conforme [ADR-0029](docs/adr/0029-distribuicao-windows-x86-e-x64.md). Não inclui WebView2. O código é disponibilizado pela main; executáveis e site, pela release.

Aplicação autônoma de pesagem, pré-inserção de itens e impressão de comandas para um PC Windows 10/11, com interface touch em Django e operação offline.

Raiz: `D:\restaurante-local`. Projeto independente de `D:\restaurante`; não compartilha ambiente, imports, banco, configuração ou agentes com ele.

## Estado atual

Fundação Django e primeiro recorte do inicializador implementados: Waitress em loopback, mutex por diretório de dados, diagnóstico touch, HTMX local, leitura simulada, pausa/retomada, bandeja e encerramento coordenado. Dependências próprias fixadas em `pyproject.toml` e `uv.lock`. Histórico organizado em commits semânticos em português; novos commits exigem pedido explícito.

Backend comercial implementado: products, measurements e orders, snapshots em centavos/gramas, captura persistente explícita, múltiplos rascunhos, inclusão/remoção, consumo único, descarte manual e cancelamento isolado. Commits deste recorte autorizados expressamente pelo usuário. Consulte [entrega do domínio](docs/IMPLEMENTACAO_DOMINIO.md).

Atendimento touch implementado: cadastro de produtos, múltiplas comandas, produtos rápidos, inclusão manual em UN/KG, teclado numérico, correções, cancelamento, descarte confirmado e ajuste da numeração. O worker persiste automaticamente as pesagens do simulador, mesmo sem navegador aberto. Consulte [entrega de atendimento e captura](docs/IMPLEMENTACAO_ATENDIMENTO_CAPTURA.md).

Documento e fila simulada implementados: cabeçalho/rodapé, preview contínuo de 80 mm, finalização somente da selecionada, snapshot congelado, histórico e segunda via confirmada. Consulte [entrega documental](docs/IMPLEMENTACAO_DOCUMENTO_IMPRESSAO.md).

Integração real implementada: configuração de porta/fila, leitura COM3 e impressão Windows RAW em balanca. Consulte [entrega de hardware](docs/IMPLEMENTACAO_HARDWARE_REAL.md). O usuário considera balança e impressão funcionais para a entrega atual. O pacote Windows e a atualização web pela release estão implementados; configuração do deploy está descrita no manual. `--preview-print` utiliza somente simulador, sem papel ou spooler. Captura automática de 236 g e impressão da comanda nº 2 foram confirmadas neste ciclo. Ensaios físicos adicionais permanecem documentados para ajustes posteriores.

## Desenvolvimento e execução

Para entender e reproduzir a distribuição, consulte [Como empacotar para Windows](docs/EMPACOTAMENTO_WINDOWS.md). Na máquina de desenvolvimento Windows x64 com Git, dê dois cliques em **Empacotar.bat**: ele prepara ferramentas locais, testa e gera os pacotes x86/x64 em `dist/`. O comando não publica no GitHub.

O trabalho diário fica em **`codex/develop`**, a branch permanente de desenvolvimento. Commits enviados a ela não criam Releases nem atualizam a máquina final. Após revisão e validação, abrir PR para **`main`**; seu merge autorizado disponibiliza o código ao atualizador Git/uv. Para gerar/publicar executáveis, promover a main para **`release`**. Após promoção, sincronizar `codex/develop` com a main e continuar nela.

Para a máquina final com Git/uv, use [instalação por código](docs/INSTALACAO_POR_CODIGO.md). O [canal de executáveis](docs/DISTRIBUICAO_WINDOWS.md) continua disponível pela release. Build: `rtk proxy uv run --no-sync --group build --cache-dir .uv-cache python packaging/build.py --version 0.1.0`. `Instalar-codigo.bat` instala o canal de código; os arquivos `Iniciar.bat`/`Atualizar.bat` da raiz abaixo continuam sendo ferramentas de desenvolvimento. Scripts operacionais estão em `packaging/windows/`. Publicação dos workflows, criação da release remota e ativação do Pages são etapas externas.

O atendimento é otimizado para a área real do navegador no PC touch: **1280 × 673 pixels CSS**, medida no painel físico de 1920 × 1200. Comandas ficam à esquerda, detalhes no centro e produtos à direita. Cabeçalhos e pesagens compactos permitem manter subtotal, impressão, cancelamento e busca visíveis; listas maiores rolam dentro dos próprios painéis, preservando botões de pelo menos 48 px. Avisos ou áreas ainda menores podem exigir rolagem da página. Telas grandes continuam aproveitando o espaço adicional. O cadastro exibe produtos em três colunas. Não exige migration. Consulte a [ADR-0033](docs/adr/0033-atendimento-na-area-css-do-pc-integrado.md).

### Abertura por arquivos no Windows

Com o ambiente de desenvolvimento já preparado, dê dois cliques em `Iniciar.bat` para abrir o aplicativo com os equipamentos reais. O arquivo inicia servidor, workers e bandeja e abre o navegador. Fechar o navegador não encerra o aplicativo; use **Sair** na bandeja. Não feche a janela do terminal para encerrar normalmente.

Ao detectar instalação/banco ausente ou banco desatualizado, `Iniciar.bat` pergunta se deseja atualizar com backup e iniciar. Escolha **S** para preparar os dados e continuar a abertura na mesma janela, ou **N** para sair sem atualizar. O banco atualizado abre diretamente, sem essa pergunta. Uma falha da atualização impede a abertura; não há migrations silenciosas.

`Atualizar.bat` continua disponível para preparação ou atualização direta, sempre com o aplicativo fechado. Ambos os fluxos usam `initialize_local`, que faz backup dos dados existentes antes de atualizar o banco e impede atualização enquanto outra instância estiver aberta. O atualizador não instala dependências nem atualiza o código.

Para criar o atalho na área de trabalho, clique com o botão direito em `Iniciar.bat` e escolha **Enviar para → Área de trabalho (criar atalho)**; no Windows 11, pode ser necessário **Mostrar mais opções**. Os arquivos usam sua própria pasta como diretório de trabalho, inclusive quando chamados por atalho.

Para simulação no desenvolvimento, execute `Iniciar.bat --simulate --preview-print` em um terminal. Os dois arquivos da raiz aceitam os argumentos de seus respectivos comandos e mantêm a mensagem de erro visível em caso de falha. Eles usam diretamente o Python da `.venv` deste projeto, preparada com uv, e exigem `rtk` no PATH; a abertura não depende de uv, cache ou internet. `Iniciar.bat` também respeita `UV_PROJECT_ENVIRONMENT` quando definido, para usar o ambiente próprio de cada arquitetura durante os testes de empacotamento. O pacote final usa scripts próprios, inicializador sem console e runtime/dependências incluídos.

### Comandos técnicos

Requer Python 3.13 e uv para desenvolvimento. Os comandos são executados nesta raiz:

```powershell
rtk proxy uv sync --frozen --cache-dir .uv-cache
rtk proxy uv run --offline --no-sync python manage.py initialize_local
rtk proxy uv run --offline --no-sync python manage.py run_local --simulate --preview-print
```

### Variáveis de ambiente

A aplicação carrega o arquivo `.env` em UTF-8 da raiz deste projeto usando `django-environ`, com defaults tipados. O arquivo local está fora do Git; `.env.example` contém o modelo versionado. Em outra instalação, copie `.env.example` para `.env`. A ausência do arquivo não impede a execução. Os comandos `run_local`, `initialize_local` e os dois arquivos `.bat` usam a mesma configuração.

| Variável | Default | Uso |
| --- | --- | --- |
| `DEBUG` | `False` | Diagnóstico Django; manter `False` na operação. |
| `TIME_ZONE` | `America/Sao_Paulo` | Fuso horário da aplicação. |
| `LOCAL_WEIGHING_DATA_DIR` | `%LOCALAPPDATA%\RestauranteLocal` | Diretório de banco, configuração, logs e backups, fora da pasta do programa. |
| `SECRET_KEY` | Chave local gerada por `initialize_local` | Override opcional; omitir para manter a chave da instalação. |

Variáveis já definidas no ambiente do processo têm prioridade sobre o `.env`, conforme o [comportamento de django-environ](https://django-environ.readthedocs.io/en/stable/api.html). Isso permite isolar dados de testes sem alterar o arquivo local. Reinicie o programa para carregar alterações. Alterar o diretório seleciona outra instalação e não move os dados existentes. Porta HTTP e configuração de equipamentos continuam na configuração da instalação, com as etapas próprias de atualização; não são duplicadas no `.env`.

`initialize_local` é a etapa explícita de instalação/atualização: gera segredo local e aplica migrations; em dados existentes, salva backup consistente de SQLite e configuração antes de atualizar. Exige o programa fechado. `run_local` nunca migra o banco; `Iniciar.bat` pode executar a etapa depois da confirmação S/N e então tentar abrir novamente. Inclui as migrations nativas de `contenttypes` e as migrations geradas dos apps core, products, measurements, orders e printing.

Dados padrão: `%LOCALAPPDATA%\RestauranteLocal`, fora dos arquivos do programa. Para testes ou outra instalação, definir `LOCAL_WEIGHING_DATA_DIR` antes de executar os comandos. Nunca apontar para os dados do Restaurante anterior. Porta padrão `8765`; alterar com `initialize_local --port 8766`, com programa fechado.

Para executar sem bandeja/navegador:

```powershell
rtk proxy uv run --offline --no-sync python manage.py run_local --simulate --preview-print --no-tray --no-browser
```

Abrir `http://127.0.0.1:8765/` após a mensagem de prontidão. Encerrar com **Sair** na bandeja ou Ctrl+C sem bandeja. Fechar o navegador não encerra o processo. Segunda execução confirma a identidade HTTP da instância existente antes de abrir sua interface e não duplica leitor/servidor. A abertura atual usa o navegador padrão; perfil próprio e kiosk ficam para distribuição.

Para os equipamentos reais, execute o comando run_local sem --simulate e sem --preview-print, após atualização explícita com o programa fechado. As flags selecionam os transportes independentemente; trabalhos antigos de simulação não passam a imprimir em papel.

## Validação

```powershell
rtk proxy uv run --offline --no-sync python manage.py check --settings=config.test_settings
rtk proxy uv run --offline --no-sync python manage.py test --settings=config.test_settings
rtk proxy uv run --offline --no-sync python manage.py makemigrations --check --dry-run --settings=config.test_settings
```

198 testes isolados usam diretórios/banco temporários, simuladores e backend falso de bandeja; não abrem navegador, porta serial ou spooler. Cobrem Waitress em loopback, backup, processos distintos, falhas, CSRF, encerramento, invariantes comerciais, captura, atendimento, documentos/segunda via, recuperação de envio incerto, concorrência SQLite e desinstalação Windows, incluindo atalho criado em pasta de teste pelo Windows Script Host. O ensaio `packaging/smoke.py` verifica adicionalmente o executável compilado, instalação, atualização web e desinstalação com dados temporários e transportes simulados. Consulte os registros da [fundação](docs/IMPLEMENTACAO_FUNDACAO.md), do [domínio](docs/IMPLEMENTACAO_DOMINIO.md), do [atendimento](docs/IMPLEMENTACAO_ATENDIMENTO_CAPTURA.md) e da [impressão simulada](docs/IMPLEMENTACAO_DOCUMENTO_IMPRESSAO.md).

## Documentação

- [Plano e requisitos de produto](docs/PLANO_APLICACAO_LOCAL_PESAGEM.md).
- [Estrutura técnica e inicializador](docs/ESTRUTURA_TECNICA_APLICACAO_LOCAL.md).
- [Decisão Django e interface touch](docs/adr/0012-aplicacao-autonoma-django-touch.md).
- [Referência de balança e impressora](docs/REFERENCIA_HARDWARE.md).
- [Impressão sem fechamento](docs/adr/0019-impressao-sem-fechamento.md).
- [Peso fixado ao estabilizar](docs/adr/0020-peso-fixado-antes-da-retirada.md).
- [Refeições e marcações preenchidas](docs/adr/0018-refeicoes-e-marcacoes-preenchidas.md).
- [Cabeçalho ampliado e itens alinhados](docs/adr/0017-layout-compacto-da-comanda.md).
- [Modelo visual da comanda](docs/references/order-slip-reference.png).
- [Registro da separação](docs/SEPARACAO_PROJETOS.md).

## Escopo

Várias comandas abertas, pesagens compartilhadas, produtos rápidos, peso manual, numeração sequencial, configurações e impressão em bobina contínua de 80 mm. Descarte de medições somente manual. Sem estoque, caixa, pagamento ou emissão fiscal.

Equipamentos integrados: COM3 e fila Windows `balanca`, editáveis na tela Equipamentos. Backend Django/SQLite, Templates/HTMX e assets locais; entrada técnica `manage.py run_local`.

Não instalar, migrar ou iniciar o sistema antigo para desenvolver este projeto. O usuário confirmou acentos, largura de 48 caracteres e corte do teste RAW nº 7; leituras de zero e 236 g coincidiram com o visor. Homologação física completa permanece pendente.

## Atualização: impressão sem fechar e peso fixado

Na prévia, **Imprimir sem fechar** mantém a comanda editável e preserva cada documento no histórico; **Finalizar e imprimir** continua disponível separadamente. Itens marcáveis usam [X] sem valor adicional abaixo da linha. A tela fixa o peso após a captura estável e só libera outra medição depois de zero.

Esta atualização inclui a migration printing/0003. Feche o aplicativo com **Sair** na bandeja, execute initialize_local (backup automático) e depois run_local. Nenhuma atualização automática ocorre ao abrir. Documentos já salvos mantêm seu formato original.

## Atualização: área de configurações

A navegação superior reúne Atendimento, Produtos, Histórico, Configurações e Status. Em **Configurações**, os submenus **Geral**, **Numeração**, **Documento** e **Equipamentos** acessam os respectivos formulários. Em **Geral**, edite o nome mostrado na barra superior e no título das páginas. O cabeçalho impresso continua sendo configurado separadamente em Documento. Os indicadores real/simulado da barra e o rodapé técnico global foram removidos.

Esta atualização inclui a migration `configuration/0002`. Feche o aplicativo pela bandeja, execute `Atualizar.bat` para backup e atualização do banco e depois `Iniciar.bat`. Consulte a [ADR-0022](docs/adr/0022-area-de-configuracoes-e-nome-da-aplicacao.md).

## Atualização: tags no catálogo

Em Produtos, clique nas tags **Balança**, **Aparece na comanda** ou **Acesso rápido** para salvar a opção sem recarregar a página. Tags preenchidas estão marcadas; tags com contorno estão desmarcadas. O produto da balança aparece em uma seção própria no topo. Selecionar outro produto ativo por KG transfere a seleção automaticamente, mantendo no máximo um produto da balança. Esta alteração não cria migrations; reabra o programa para carregar o código atualizado.

## Atualização: inclusão por diálogo

No atendimento, clicar em um produto abre um diálogo com quantidade/peso e teclado numérico. **Confirmar e adicionar** inclui na comanda selecionada e atualiza itens e subtotal sem sair da tela. Cancelar fecha sem incluir; erros mantêm o diálogo para correção. Não exige migration; reabra o programa para carregar o código atualizado.

## Atualização: posicionamento da comanda

Novas impressões usam o layout conforme a referência: número/data na mesma linha, preços e valores das refeições à direita, subtotal de refeições em negrito à direita, produtos e marcações em colunas e total manual/rodapé centralizados. Os textos adicionais retirados da referência não aparecem no novo papel. Documentos já salvos e suas segundas vias mantêm o layout original. O reposicionamento e negrito não exigem migration; reabra o programa. Consulte a [ADR-0023](docs/adr/0023-layout-da-comanda-conforme-referencia.md).

## Comparação das telas de atendimento

O **Atendimento principal**, na raiz `/`, usa a tela compacta escolhida: peso e pesagens na mesma linha, comandas de 248 pixels, itens e produtos rápidos na proporção 1 : 0,8. **Adicionar produto** fica no rodapé dos produtos rápidos e abre o catálogo com filtro durante a digitação. **Prévia e impressão** abre a comanda em diálogo, com **Imprimir** e **Imprimir e fechar**; o ícone ao lado de **Cancelar comanda** acessa a página de prévia existente. Após solicitar a impressão, o atendimento é retomado; o modo simulado é identificado no diálogo.

Em **Status → Comparar telas de atendimento**, **Versão alternativa** abre a tela anterior, também disponível em `/attendance/alternative/`, com catálogo permanente. **Atendimento principal** retorna à tela compacta. As versões compartilham comandas e pesagens; suas ações preservam os respectivos destinos. Não exige migration. Consulte a [ADR-0037](docs/adr/0037-promocao-do-atendimento-compacto.md).

## Atualização: logo do restaurante

Feche a aplicação e execute **Atualizar.bat**, ou abra **Iniciar.bat** e confirme a atualização oferecida, para aplicar a nova migration com backup. Em **Configurações → Documento**, selecione uma logo PNG ou JPG de até 2 MB e salve. A imagem aparece em preto e branco, centralizada acima do cabeçalho. Sem logo, nenhum espaço é reservado. Para trocar, envie outra imagem; para retirar, marque **Remover logo atual** e salve. Documentos salvos e segundas vias preservam sua imagem original. Prévia e envio RAW foram validados com dados de exemplo e spooler falso; confirmar a imagem na impressora instalada ainda é necessário. Consulte a [ADR-0024](docs/adr/0024-logo-opcional-na-comanda.md).
