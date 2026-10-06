# Instalação e atualização por Git e uv

Canal para os computadores administrados internamente. Código aprovado vem da `main`; executáveis continuam disponíveis pela `release`. Contrato: [ADR-0038](adr/0038-atualizacao-por-git-e-pacotes-na-release.md).

## Primeira instalação

1. Instale Git e uv compatíveis com a arquitetura do Windows. Abra um novo terminal e confira `git --version` e `uv --version`. Não precisa instalar RTK, npm ou PyInstaller na máquina final.
2. Clone o repositório público, já contendo este instalador na main:

   ```powershell
   git clone --branch main https://github.com/eduardomizael/restaurante-local.git
   cd restaurante-local
   .\Instalar-codigo.bat
   ```

3. Aguarde a preparação do Python 3.13, dependências e banco. Abra pelo atalho **Restaurante Local** na área de trabalho.

O atalho abre uma janela dedicada em tela cheia usando Edge ou, na sua ausência, Chrome, instalado num caminho padrão do Windows. Para sair, use **Status → Encerrar aplicação**, confirme e aguarde: o sistema e sua janela serão fechados. **Continuar usando** mantém o atendimento aberto. Outras janelas do navegador permanecem abertas. Se você fechou somente a janela, reabra pelo atalho; o atendimento continua em execução. Consulte a [ADR-0039](adr/0039-janela-dedicada-em-tela-cheia.md).

Para preferir janela maximizada, com o programa fechado configure `"browser_mode": "maximized"` em `installation.json` na pasta de dados, preservando os campos existentes. O padrão é `"fullscreen"`. Essa opção só funciona após instalar a versão que implementa a ADR-0039. Perfil temporário do navegador fica em `dados/browser/<sessão>` e é removido ao sair normalmente; perfis de sessões interrompidas podem permanecer. Banco e backups não ficam nesse perfil.

Python é baixado pelo uv quando necessário. Internet é necessária na preparação e nas atualizações. O computador final informado usa Windows de 32 bits: Git/uv e Python precisam funcionar em x86, independentemente do processador x64. Esse caminho ainda precisa de validação nessa máquina; o uv classifica Windows x86 como suporte de melhor esforço.

Programa: `%LOCALAPPDATA%\Programs\RestauranteLocal`. Dados: `%LOCALAPPDATA%\RestauranteLocal`, salvo configuração explícita. O clone inicial pode ser guardado para suporte; o atalho não depende dele. Não execute o `Iniciar.bat` de desenvolvimento desse clone como atalho operacional.

Para instalação personalizada, execute `Instalar-codigo.bat -InstallRoot "C:\caminho\RestauranteLocal"`. Dados devem permanecer fora dessa pasta. Não copiar banco, `.env`, logs ou backups do desenvolvimento.

## Converter a instalação existente

Encerre por **Status → Encerrar aplicação** ou **Sair** na bandeja. Execute `Instalar-codigo.bat` da cópia completa do repositório. O caminho padrão é o mesmo da instalação por pacote; banco, configurações, histórico e backups são preservados. Se usou outro caminho, passe seu `-InstallRoot`. O instalador prepara a versão por código com backup e troca o atalho após sucesso. Falha mantém o apontador anterior; falha após começar migrations bloqueia abertura até suporte/atualização concluída.

## Atualizações seguintes

Ao abrir pelo atalho, o atualizador consulta a main e compara seu SHA com o instalado. Se houver mudança, Git busca o commit exato para outra pasta, uv prepara seu ambiente conforme `uv.lock`, a ferramenta confere a aplicação e executa `initialize_local` com backup antes de ativar a versão. Não gera Release nem compila executáveis. Pode demorar mais se houver dependências novas; os downloads disponíveis no cache do uv são reutilizados.

Com a aplicação já aberta, o atalho somente reabre a interface. Não atualiza durante atendimento. Sem rede, abre a versão instalada. Falha de download ou dependências conserva a anterior; falha na preparação dos dados bloqueia abertura e preserva backups. Não há rollback automático de schema. Para repetir, feche a aplicação e execute `%LOCALAPPDATA%\Programs\RestauranteLocal\Atualizar.bat`.

Logs da atualização: `update.log` e `update-error.log` na raiz instalada quando iniciada pelo atalho. A consulta Git tem prazo de 15 segundos; downloads e preparação possuem limites maiores. `current.json` identifica `mode: source`, arquitetura, commit e pasta. `previous.json` registra o apontador anterior; não editá-lo para reverter após migrations sem avaliar o banco. Pastas incompletas e versões antigas são conservadas para diagnóstico; não são limpas automaticamente.

Configuração compartilhada `.env` fica na raiz da instalação e é copiada para cada versão antes da preparação. `source-settings.json` guarda o endereço do repositório e a branch main. Não alterar `.venv` ou código instalado manualmente. A aplicação usa o Python da versão instalada diretamente; uv não sincroniza dependências em cada execução.

## Autenticação e remoção

Repositório público não requer login. Para privado, configure uma deploy key SSH somente de leitura na conta Windows que abre a aplicação. Execute `Instalar-codigo.bat -Repository git@github.com:organizacao/repositorio.git`. Prepare a chave e o reconhecimento do host previamente; o atualizador não solicita credenciais interativas. A URL é persistida, mas nenhuma chave é copiada para o programa. Não usar tokens na URL. Uma troca de repositório deve usar código compatível com os dados existentes.

`Desinstalar.bat` funciona nos dois modos, com escolha de preservar ou apagar dados/backups. Git, uv e o clone de origem permanecem instalados. Ao preservar dados, `.env` e `source-settings.json` são guardados em `preserved-installation`. Voltar para executáveis na mesma instalação é recusado: exige avaliar versões e compatibilidade do banco; o canal por pacote permanece disponível para instalações separadas.

## Publicação

Trabalhar em `codex/develop`, validar e revisar antes do PR para main. Merge autorizado na main disponibiliza código imediatamente aos atualizadores, mesmo se o workflow ainda estiver em execução. O workflow de código executa checks, conferência de migrations e testes, sem empacotar.

Quando desejar pacotes, promover a main para release. O workflow Windows compila/testa x86/x64, publica a Release e o site. O ambiente `github-pages` deve autorizar a branch release, com Pages usando GitHub Actions. Esses requisitos são conferidos na publicação; instalar a aplicação na máquina final continua sendo uma etapa separada.

Referências: [Python pelo uv](https://docs.astral.sh/uv/guides/install-python/), [lockfile e sincronização](https://docs.astral.sh/uv/concepts/projects/sync/), [suporte de plataformas](https://docs.astral.sh/uv/reference/policies/platforms/).
