# ADR-0029 — Distribuição Windows x86 e x64

Data: 05/10/2026. Status: aceita conforme identificação da máquina final pelo usuário.

## Contexto

O computador do restaurante tem Windows 10 Home de 32 bits e processador x64. O pacote anterior era somente x64 e não executa nesse Windows. A arquitetura do sistema operacional define o pacote necessário.

## Decisão

Compilar Python 3.13 e as dependências fixadas em ambientes Windows separados x86/x64. PyInstaller herda a arquitetura do interpretador; não converter executáveis existentes. Produzir ZIP e checksum por arquitetura, mantendo os mesmos dados e regras de instalação.

Incluir `architecture` em `version.json`, `current.json` e manifestos web. O atualizador verifica os cabeçalhos PE de ambos os EXEs e rejeita x64 em Windows de 32 bits antes de preparar o banco. Instalações e pacotes antigos sem o campo representam x64. Atualizações automáticas preservam a arquitetura instalada e rejeitam manifestos/pacotes de outra arquitetura.

Publicar canais `x86/latest.json` e `x64/latest.json`. Preservar `latest.json` e o pacote x64 na raiz para inicializadores antigos. O CI usa matriz x86/x64, ensaia cada pacote, cria uma única Release com os dois ZIPs e só então publica o site com ambos os canais. A página orienta a escolha pelo tipo do Windows.

## Limites e validação

Windows 10/11 continua sendo o escopo. O ensaio x86 em Windows x64 comprova execução em processo de 32 bits, instalação, migrations, encerramento e atualização com dados isolados; não substitui validação no Windows 10 de 32 bits final. Testar arquitetura declarada adulterada e manifesto de outra arquitetura, preservando o apontador e os dados. Não trocar Windows, instalar drivers ou acessar hardware real como efeito deste trabalho.
