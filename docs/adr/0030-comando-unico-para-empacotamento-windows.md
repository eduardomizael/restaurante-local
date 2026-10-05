# ADR-0030 — Comando único para reproduzir o empacotamento

Data: 05/10/2026. Status: aceita conforme solicitação de facilitar a reprodução.

## Contexto

O empacotamento exigia preparar manualmente interpretador, ambiente e comandos; o workflow mantinha sua própria sequência. O usuário quer compreender o processo e reproduzi-lo facilmente.

## Decisão

Adicionar `Empacotar.bat` e `packaging/Build-Windows.ps1`, com x86/x64 por padrão e opção de uma arquitetura. Centralizar versões de Python, uv e RTK em `packaging/toolchain.json`; verificar SHA-256 dos downloads de ferramentas. Preparar ferramentas, caches e ambientes dentro do projeto, sem substituir o ambiente de desenvolvimento. Instalar Python com `--no-bin --no-registry`.

Usar o mesmo script no workflow do GitHub. A versão padrão vem de `pyproject.toml`; dependências vêm do lockfile congelado. Checks, migrations pendentes, testes e ensaio do executável são etapas do comando padrão. `-SkipTests` é somente para investigação e marca o relatório como não validado.

Registrar versão, revisão, alterações locais, ferramentas, arquitetura, hashes, log e conclusão em `dist/build-report.json`. Um lock impede duas execuções simultâneas do comando; relatório de sucesso só existe após todas as arquiteturas solicitadas passarem. Intermediários anteriores podem permanecer após falha e não representam uma entrega nova.

O comando não cria commits, troca branches, faz push ou publica. A publicação permanece no fluxo autorizado de PR/merge na main. RTK fica na máquina de build e não no produto. Hardware real não é acionado.

## Limites

Build exige Windows x64 e Git; o primeiro uso baixa ferramentas, Python e dependências. Repetir o processo com versões fixadas não garante hashes idênticos por causa dos metadados do empacotamento. Código sem commit é permitido para investigação e registrado no relatório; reproduzir um release exige uma cópia limpa do commit publicado.
