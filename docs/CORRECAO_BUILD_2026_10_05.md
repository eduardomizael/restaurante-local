# Correção da validação do build Windows — 05/10/2026

Execução analisada: [Actions 37378979126](https://github.com/eduardomizael/restaurante-local/actions/runs/37378979126), revisão `25537d164ce762ed40d7eb0d81708344903ac750`.

Os jobs x86 e x64 pararam na suíte de 199 testes, com as mesmas cinco falhas, antes de PyInstaller. Release e deploy foram ignorados pelo workflow.

- Três testes do inicializador: `Iniciar.bat` exigia `.venv/Scripts/python.exe`, mas o build prepara `.venv-build-x86` ou `.venv-build-x64`. O script passa a respeitar `UV_PROJECT_ENVIRONMENT`; os testes indicam explicitamente o ambiente do Python em execução, mantendo `.venv` como padrão de desenvolvimento.
- Um teste do relatório de desinstalação: o diretório temporário do runner usa `RUNNER~1`, enquanto a enumeração do PowerShell informa `runneradmin`. A fixture resolve o caminho completo antes de registrar e comparar os arquivos.
- Um teste de remoção de atalho: a comparação textual falhava quando o argumento do atalho continha um caminho abreviado e a instalação tinha caminho completo. A desinstalação normaliza caminhos existentes pelo filesystem e compara o argumento `-File` completo. Os testes cobrem atalho próprio com caminho retornado por `GetShortPathNameW` e preservação de atalho de outra instalação.

Não desativar testes nem usar `SkipTests` para contornar a falha. Nenhuma alteração em dependências, hardware, dados operacionais ou publicação. Uma nova execução do workflow com a correção ainda é necessária para confirmar os dois pacotes no GitHub.

Validação local: suíte completa com **200 testes aprovados** em Windows, usando `rtk proxy uv run --offline --no-sync --cache-dir .uv-cache python manage.py test --settings=config.test_settings`. Os testes Windows precisaram executar fora do sandbox devido a bloqueios de acesso às pastas temporárias. Diff sem erros de whitespace. O build completo x86/x64 e o deploy no GitHub não foram reexecutados nesta verificação.

## Segunda execução

A [execução 37381661958](https://github.com/eduardomizael/restaurante-local/actions/runs/37381661958), revisão `4eb7b0ff8a248e3d8cd565407e3d2825d7939201`, passou nos 200 testes e gerou os ZIPs x86/x64. Os dois jobs falharam posteriormente na linha 219 de `packaging/smoke.py`: a verificação dos dados registrados comparava strings de caminho, novamente distinguindo `RUNNER~1` de `runneradmin`. Release e deploy não ocorreram.

O teste do pacote passa a resolver a raiz temporária antes de derivar programa/dados e a comparar caminhos resolvidos no registro de desinstalação. A assertiva continua exigindo a mesma pasta, com diagnóstico dos caminhos em caso de falha. Não altera o aplicativo distribuído nem desativa a validação de instalação e desinstalação.

Validação desta correção: comando completo `rtk proxy powershell.exe -NoProfile -ExecutionPolicy Bypass -File packaging/Build-Windows.ps1 -Architecture all` concluído com código zero, sem `SkipTests`. **200 testes aprovados em cada arquitetura**, checks Django e migrations sem pendências; ZIPs x86/x64 gerados e testes dos dois pacotes instalados aprovados (instalação, HTTP, abertura offline, integridade, exclusão de instância ativa, atualização web, encerramento e desinstalação completa). Foram usados apenas instalações temporárias e simuladores, fora do sandbox. Relatório local em `dist/build-report.json` e transcript em `build/logs/build-20261005-222641.log`, fora do Git. A confirmação no runner do GitHub permanece pendente de publicação da correção.
