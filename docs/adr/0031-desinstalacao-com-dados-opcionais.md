# ADR-0031 — Desinstalação com dados opcionais

Status: aceita. Data: 05/10/2026.

## Contexto

A instalação por usuário possui versões, arquivos temporários, dados e backups em pastas distintas. O operador precisa removê-los sem ferramentas de desenvolvimento, escolhendo explicitamente se apaga os dados.

## Decisão

Distribuir `Desinstalar.bat` e `Uninstall.ps1`, também instalados na raiz do programa. O BAT encerra seu terminal após a pausa para permitir remover o próprio arquivo. O PowerShell mostra os caminhos, oferece preservar dados por padrão e exige confirmação; apagar banco e todos os backups exige digitar `APAGAR`.

O instalador registra raízes de dados, mutexes e origens manuais em `uninstall-info.json`. Instalações anteriores identificam dados pelo executável de manutenção. Uma atualização pelo atualizador antigo inclui os scripts no payload; o novo atualizador recupera esses arquivos na raiz na próxima abertura.

A remoção adquire o lock do atualizador e reserva os mutexes do runtime. Aplicação aberta ou atualização ativa bloqueiam a operação. Raízes protegidas, diretórios de desenvolvimento, sobreposição programa/dados e raízes com junções são rejeitados. Junções internas são apagadas sem seguir seu destino.

Todas as versões, staging, arquivos auxiliares e o atalho pertencente à instalação são removidos. Preservar dados guarda também `.env` e `update-url.txt` existentes em `preserved-installation` nos dados atuais; reinstalar não restaura esses arquivos automaticamente. Apagar dados remove todas as raízes registradas, incluindo backups, logs e configurações.

Falhas mantêm os scripts e o registro de recuperação, listam resíduos e geram um relatório identificado em `%TEMP%`. O operador pode liberar arquivos e repetir a remoção.

## Alternativas e consequências

MSI não foi adotado neste incremento. Não existem serviço, início automático ou registro de instalação a remover. ZIPs do navegador, pacotes manuais e atalhos de terceiros não têm posse segura para exclusão automática: origens registradas são informadas e o aviso final orienta conferir Downloads e cópias. Dados preservados e relatórios de falha são informados com seus caminhos.

Validação usa pastas temporárias, executáveis empacotados e simuladores, sem desinstalar a aplicação operacional ou acessar hardware real.
