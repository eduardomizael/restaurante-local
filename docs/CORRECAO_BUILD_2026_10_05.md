# Correção da validação do build Windows — 05/10/2026

Execução analisada: [Actions 37378979126](https://github.com/eduardomizael/restaurante-local/actions/runs/37378979126), revisão `25537d164ce762ed40d7eb0d81708344903ac750`.

Os jobs x86 e x64 pararam na suíte de 199 testes, com as mesmas cinco falhas, antes de PyInstaller. Release e deploy foram ignorados pelo workflow.

- Três testes do inicializador: `Iniciar.bat` exigia `.venv/Scripts/python.exe`, mas o build prepara `.venv-build-x86` ou `.venv-build-x64`. O script passa a respeitar `UV_PROJECT_ENVIRONMENT`; os testes indicam explicitamente o ambiente do Python em execução, mantendo `.venv` como padrão de desenvolvimento.
- Um teste do relatório de desinstalação: o diretório temporário do runner usa `RUNNER~1`, enquanto a enumeração do PowerShell informa `runneradmin`. A fixture resolve o caminho completo antes de registrar e comparar os arquivos.
- Um teste de remoção de atalho: a comparação textual falhava quando o argumento do atalho continha um caminho abreviado e a instalação tinha caminho completo. A desinstalação normaliza caminhos existentes pelo filesystem e compara o argumento `-File` completo. Os testes cobrem atalho próprio com caminho retornado por `GetShortPathNameW` e preservação de atalho de outra instalação.

Não desativar testes nem usar `SkipTests` para contornar a falha. Nenhuma alteração em dependências, hardware, dados operacionais ou publicação. Uma nova execução do workflow com a correção ainda é necessária para confirmar os dois pacotes no GitHub.

Validação local: suíte completa com **200 testes aprovados** em Windows, usando `rtk proxy uv run --offline --no-sync --cache-dir .uv-cache python manage.py test --settings=config.test_settings`. Os testes Windows precisaram executar fora do sandbox devido a bloqueios de acesso às pastas temporárias. Diff sem erros de whitespace. O build completo x86/x64 e o deploy no GitHub não foram reexecutados nesta verificação.
