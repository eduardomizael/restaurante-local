# ADR-0025 — Atualização confirmada pelo inicializador

Status: aceita. Data: 04/10/2026. Complementa ADR-0012 e ADR-0024.

## Contexto e decisão

O usuário solicitou que `Iniciar.bat` ofereça atualizar o banco sem exigir fechar o inicializador, abrir `Atualizar.bat` e iniciar novamente. A confirmação na janela substitui essa sequência manual; migrations continuam sendo uma etapa explícita com backup, nunca silenciosa.

`run_local` retorna código 3 exclusivamente para instalação ausente, banco ausente ou migrations pendentes. `InstallationUpdateRequired` mantém o contrato de RuntimeError da validação de schema. O código 3 chega ao script somente depois do encerramento dos componentes e liberação do mutex. Outras falhas conservam seus códigos e não oferecem atualização.

Ao receber 3, `Iniciar.bat` pergunta **Executar a atualização com backup e depois iniciar? [S/N]**. Somente S chama `initialize_local` no Python da mesma instalação, com `.env`, backup e mutex já existentes. Não repassar argumentos de `run_local` ao atualizador. Se a atualização terminar com sucesso, executar novamente `run_local` com todos os argumentos originais, na mesma janela. Não repetir a oferta depois de uma atualização no mesmo fluxo. Recusa não executa o atualizador; falha impede a abertura e permanece visível.

O atualizador continua recusando o banco em uso. Se outro processo iniciar entre a detecção e a confirmação, a aquisição exclusiva evita atualização concorrente. `Atualizar.bat` permanece disponível para execução direta e opções próprias, como `--port`.

## Validação e limites

Testes verificam o código específico, encerramento do runtime, recusa sem banco criado, confirmação com backup e migration, nova tentativa de abertura e falha do atualizador sem reinício. Testes Windows executam o `.bat` real com dados temporários, entrada explícita S/N e flags de simulação. Na validação da confirmação, uma porta temporária ocupada interrompe o servidor antes dos workers. Não usar dados operacionais, abrir hardware, enviar impressão ou iniciar automaticamente a instalação real.

A distribuição sem console com runtime incluído permanece pendente; o prompt atual pertence ao inicializador de desenvolvimento no Windows.
