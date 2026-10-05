# ADR-0027 — Executáveis Windows e atualização web da main

Status: aceita para implementação conforme solicitação do usuário em 05/10/2026.

## Contexto

O usuário solicitou executáveis prontos para a máquina final e atualização baixada por script, considerando balança e impressão funcionais. Esclareceu que a main é a versão atual e o próprio inicializador deve verificar, baixar e atualizar ao abrir. Ajustes posteriores e nova homologação física não condicionam esta entrega.

## Decisão

Distribuir ZIP Windows x64 com PyInstaller em modo pasta, executável sem console `RestauranteLocal.exe` e executável console `Manutencao.exe`. Incluir runtime, dependências fixadas, assets e licenças. Build usa coleta explícita dos apps, migrations e comandos Django. Configuração opcional vem da pasta do executável; assets continuam no bundle.

Instalar por usuário em LocalAppData/Programs, com versões identificadas por hash e apontador `current.json` trocado atomicamente. Atalho estável abre a versão ativa. Dados comerciais ficam separados em LocalAppData/RestauranteLocal. Não copiar configuração ou dados de desenvolvimento.

Atualização via PowerShell consulta manifesto HTTPS do deploy da main, compara SHA do commit, confere SHA-256 do ZIP, valida caminhos, instala nova pasta, executa initialize_local com backup e ativa somente após sucesso. O atalho executa essa etapa antes de abrir o runtime, por autorização explícita atual do usuário, substituindo a exigência anterior de confirmação S/N no inicializador distribuído. `run_local` continua sem migrar. Mutex do runtime impede migrations enquanto o programa estiver aberto; lock do atualizador serializa instalações. Instância ativa somente reabre a interface. Runtime não exige internet; download exige. Falha de rede abre a versão instalada; falha de preparação do banco bloqueia abertura.

CI Windows testa, compila e ensaia o pacote. Push/merge na main publica manifesto e pacote no GitHub Pages, usando workflow próprio e ativação prévia do Pages. Também cria automaticamente Release `windows-<SHA>` com ZIP e checksum para download na página do repositório; não substituir arquivos de Releases anteriores. Pull requests não publicam. Outro servidor HTTPS pode hospedar os mesmos arquivos. Não criar commit, push ou deploy implicitamente. Não embutir credenciais no pacote.

## Limites

Falha de migration não garante rollback integral do schema; backup e intervenção continuam necessários. Não trocar automaticamente para executável antigo após migration. Não remover versões automaticamente. SHA-256 é integridade de download, sem assinatura Authenticode. Não instalar serviço nem início automático. Ensaios usam instalação temporária e simuladores, sem hardware operacional.
