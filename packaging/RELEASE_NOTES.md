Pacotes Windows x86 e x64 completos, com executáveis, Python, dependências e assets incluídos.

1. Para **Windows de 32 bits**, baixe **RestauranteLocal-windows-x86.zip**; para **Windows de 64 bits**, baixe **RestauranteLocal-windows-x64.zip**. Escolha pelo Windows instalado, mesmo que o processador seja x64.
2. Extraia todo o ZIP em uma pasta e execute **Instalar.bat**.
3. Abra **Restaurante Local** pelo atalho da área de trabalho.

Não é necessário instalar Python, Git, uv ou rtk. A instalação prepara os dados e cria o atalho, sem configurar início automático.

O atalho verifica a versão publicada da release antes de abrir, baixa atualizações da mesma arquitetura com backup e preserva os dados. Sem internet, abre a versão instalada. Se o aplicativo já estiver em execução, apenas reabre a interface. Para atualizar manualmente, use **Encerrar aplicação** no menu superior, confirme e execute **Atualizar.bat** na pasta instalada. A bandeja também permite encerrar. Instalações por código com Git/uv usam a main, conforme o manual próprio.

Programa: `%LOCALAPPDATA%\Programs\RestauranteLocal`. Dados e backups: `%LOCALAPPDATA%\RestauranteLocal`.

[Página de distribuição e atualização](https://eduardomizael.github.io/restaurante-local/) · [Manual](https://github.com/eduardomizael/restaurante-local/blob/main/docs/DISTRIBUICAO_WINDOWS.md)
