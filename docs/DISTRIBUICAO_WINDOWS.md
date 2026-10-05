# Instalação e atualização — Windows x64

O pacote inclui os executáveis, Python, dependências, templates e assets. A máquina final não precisa de Python, uv, npm, rtk ou Git. A operação é offline; somente o download das atualizações exige internet. Balança e impressora usam os drivers já instalados no Windows. A branch **main** é a versão de produção: cada push gera, testa e publica os executáveis em um servidor web.

## Primeira instalação

1. Baixe `RestauranteLocal-windows-x64.zip` na [última versão do repositório](https://github.com/eduardomizael/restaurante-local/releases/latest) ou na [página de distribuição](https://eduardomizael.github.io/restaurante-local/) e extraia todo o ZIP. Também pode usar o ZIP gerado localmente em `dist/RestauranteLocal-windows-x64.zip`.
2. Execute `Instalar.bat`. Não execute diretamente de dentro do ZIP.
3. Abra **Restaurante Local** pelo atalho criado na área de trabalho.

O programa é instalado por usuário em `%LOCALAPPDATA%\Programs\RestauranteLocal`. Os dados permanecem em `%LOCALAPPDATA%\RestauranteLocal`: banco, configuração, logs e backups. A primeira instalação prepara o banco explicitamente. Não exige administrador nem configura início automático.

## Atualização ao abrir

O atalho consulta o manifesto web antes de iniciar. Havendo outro commit da main publicado, baixa e instala os executáveis novos com backup antes de abrir. Se o aplicativo já estiver em execução, somente reabre sua interface; não atualiza durante o atendimento. Sem internet ou com falha de download/verificação, abre a versão instalada. A consulta tem prazo de oito segundos; o download de um pacote novo pode levar mais tempo. Se a preparação do banco falhar, a abertura fica bloqueada até a atualização ser resolvida.

## Atualizar manualmente

1. Use **Sair** na bandeja para fechar o programa.
2. Execute `%LOCALAPPDATA%\Programs\RestauranteLocal\Atualizar.bat` (pode criar um atalho para esse arquivo).
3. Aguarde a mensagem de sucesso e reabra pelo atalho normal.

O atualizador consulta `latest.json`, compara o SHA do commit da main, baixa o ZIP correspondente e verifica SHA-256 antes de extrair. Instala os arquivos em outra pasta, executa a preparação do banco com backup e só então ativa a versão. Se o aplicativo estiver aberto, recusa a atualização. Essa preparação é uma etapa própria do atualizador; `run_local` continua sem executar migrations. Versões anteriores ficam guardadas; não é seguro voltar executáveis após uma alteração de schema sem restaurar o backup correspondente.

Sem internet, pode baixar e extrair o ZIP em outro computador e executar seu `Instalar.bat` na máquina final. Ele atualiza a mesma instalação, preservando os dados.

Uma falha antes da ativação mantém o apontador anterior. Uma migration que falha pode já ter alterado parte do schema; o backup é preservado, `update-failed.txt` bloqueia a abertura e a mensagem exige suporte antes de reabrir. Uma atualização bem-sucedida remove o bloqueio. Não há promessa de rollback automático do banco.

## Configurações e suporte

Porta COM, impressora, produtos e documento continuam nas telas da aplicação. Configuração opcional `.env` fica na raiz da instalação, fora das pastas de versões, e é copiada para a próxima versão. Não copie `.env` do ambiente de desenvolvimento. Alterar `LOCAL_WEIGHING_DATA_DIR` seleciona outro banco, sem mover dados.

Logs: `%LOCALAPPDATA%\RestauranteLocal\logs`. O backup da atualização inclui banco e `installation.json`; o `.env` compartilhado é preservado na raiz do programa. Fechar o navegador não encerra o programa; use a bandeja.

Os executáveis ainda não têm assinatura Authenticode. O Windows pode mostrar aviso de reputação ao executar o pacote baixado. Confirme a origem na página oficial; SHA-256 verifica integridade do download, não substitui assinatura do editor.

## Gerar e publicar a main

Desenvolvimento contínuo em `codex/develop`; produção em `main`. Trabalhar e concentrar alterações na `codex/develop`, abrir PR para `main` quando o conjunto estiver pronto e fazer merge somente após revisão, validação e autorização da publicação. A branch de desenvolvimento não publica Releases. Após o release, sincronizá-la com a `main` sem apagar histórico ou alterações em andamento.

Build executado em Windows x64, Python 3.13, com dependências fixadas no `uv.lock`:

```powershell
rtk proxy uv sync --frozen --group build --cache-dir .uv-cache
rtk proxy uv run --no-sync --cache-dir .uv-cache python manage.py test --settings=config.test_settings
rtk proxy uv run --no-sync --cache-dir .uv-cache python packaging/build.py --version 0.1.0
```

Resultado em `dist/`: ZIP, `.zip.sha256` e `update-web/` com página, manifesto e pacote identificado pelo hash. A revisão é o SHA de HEAD; em CI vem de `github.sha`. Nunca publicar `.env`, banco, dados, backups ou logs. O build usa lista explícita de assets e coleta avisos de licença das dependências.

O workflow `.github/workflows/windows-deploy.yml` testa, compila e verifica o pacote no Windows. Pull requests geram somente artefatos. Push na main ou execução manual na main cria automaticamente uma Release `windows-<SHA>` com ZIP e checksum e publica `update-web/` no GitHub Pages. O deploy só ocorre após todos os checks e o ensaio do executável passarem. Não é necessário criar tags ou Releases manualmente; commits diferentes da main atualizam mesmo mantendo a versão semântica 0.1.0. Cada commit tem sua Release preservada, e `releases/latest` aponta para a mais recente.

Configuração única no GitHub: **Settings → Pages → Source → GitHub Actions**. O endereço padrão é `https://eduardomizael.github.io/restaurante-local/latest.json`. Habilitar Pages e publicar o primeiro push são etapas externas; ter o workflow local não confirma deploy. Se usar outro servidor HTTPS, publique o mesmo diretório e coloque a URL do manifesto em `update-url.txt` na raiz da instalação. A distribuição web contém somente o programa. A máquina final não baixa o repositório nem recebe credenciais.

Publicações futuras seguem o fluxo normal de revisão e push/merge na main. Nunca enviar mudanças experimentais para main, pois máquinas fechadas receberão a atualização ao abrir. Este trabalho não autoriza commit ou push implícito.

Referência de empacotamento: [PyInstaller — runtime e localização de arquivos](https://pyinstaller.org/en/stable/runtime-information.html).

Referência de deploy: [GitHub Pages com workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).
