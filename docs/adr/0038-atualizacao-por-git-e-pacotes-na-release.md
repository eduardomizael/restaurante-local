# ADR-0038 — Atualização por Git e pacotes na release

Data: 06/10/2026. Status: aceita para implementação conforme solicitação do usuário.

## Contexto

O uso é interno. Empacotar e publicar executáveis a cada alteração torna a entrega de código mais demorada. O usuário manterá Git e uv instalados no computador final e deseja preservar a distribuição por executáveis.

## Decisão

Desenvolver em `codex/develop`, promover código revisado para `main` e atualizar instalações por código a partir dela. A branch `release` recebe versões aprovadas da main quando se desejar gerar/publicar executáveis x86/x64 e o canal web existente. Substitui na ADR-0027 o vínculo obrigatório entre main e build/Release; preserva seus contratos de dados separados, backup, exclusão e bloqueio após falha de migrations. Não criar nem publicar branches implicitamente.

O primeiro uso requer Git/uv no PATH e uma cópia completa do repositório para executar `Instalar-codigo.bat`. Esse comando instala em LocalAppData/Programs/RestauranteLocal e cria o atalho. Pode converter a instalação por pacote nesse mesmo caminho, com o programa fechado, preservando dados e `.env`; instalações personalizadas passam `-InstallRoot`. A cópia inicial é apenas a origem do instalador, não a instalação operacional.

O atualizador consulta `refs/heads/main`, fixa o SHA consultado e baixa esse commit por Git para uma pasta própria `versions/<SHA-256 do SHA>`. Não faz pull/reset no código em uso. Cria uma `.venv` por versão com `uv sync --locked --no-dev --no-default-groups`, Python 3.13 e arquitetura da instalação. O ambiente é criado no caminho definitivo para não mover uma venv. Atualizador e dependências de execução excluem o grupo de build. Registros e apontadores são trocados atomicamente; scripts de bootstrap são copiados após preparar o banco. Pastas incompletas permanecem identificáveis para suporte; não remover versões automaticamente.

O mesmo `update.lock` serializa instalação, atualização, abertura e desinstalação. Aplicação ativa não é atualizada: a abertura reabre a interface e atualização manual é recusada. `initialize_local` mantém seu mutex, backup consistente e migrations na etapa própria do atualizador. Antes de preparar dados, um marcador bloqueia abertura; qualquer falha posterior mantém o bloqueio até concluir a atualização. Falha anterior, inclusive rede/dependências, preserva a versão instalada. O inicializador usa diretamente `pythonw.exe` da venv, sem uv ou rede durante a execução. O atalho consulta atualizações antes de abrir, salvo `-SkipUpdate` para manutenção.

O repositório público não requer credenciais. Repositórios privados podem usar URL SSH e uma deploy key somente de leitura configurada no Git do usuário; passar `-Repository` ao instalador. Não colocar credenciais em URLs ou nos arquivos distribuídos. Git não solicita credenciais interativas; consultas/downloads possuem timeout. Dados locais, backups, logs e `.env` nunca vêm do desenvolvimento.

## Consequências e limites

Git e uv passam a ser requisitos apenas do canal por código. O canal de executáveis continua sem eles. A main é produção: novas aberturas podem consumir imediatamente um commit publicado, sem aguardar o CI terminar; revisão e testes devem preceder a promoção. O CI de código não gera pacotes. Os pacotes e o site só são publicados pela release.

Não prometer rollback do banco; retorno a versão antiga após migrations exige avaliar/restaurar backup. Troca de volta para pacote na mesma instalação é recusada; exige planejamento de compatibilidade do banco. Não instalar serviços, drivers nem início automático. Não testar hardware real como efeito implícito deste trabalho.

Windows x86 precisa validar Git, uv, download do Python e wheels no computador final; suporte de uv é Tier 3 (melhor esforço). Testes locais com dados temporários e simuladores são distintos de homologação física e execução do CI no GitHub.

## Validação local

Em 06/10/2026: `check`, `makemigrations --check --dry-run` e suíte completa com 221 testes passaram no Windows x64. Ensaio com repositório Git temporário e uv real cobriu primeira instalação, atualização entre commits, backups, falha de rede, recusa com mutex ativo, abertura pelo atalho pythonw após falha de consulta, encerramento HTTP com CSRF e desinstalação preservando dados. Os workers usaram simuladores. Nenhum hardware, serviço, publicação remota ou build de executáveis foi executado neste incremento. A branch release foi criada somente localmente, a partir da main; alterações continuam em codex/develop, sem commit/push.
