# ADR-0036 — Prévia em diálogo na alternativa

Status: aceita para avaliação; homologação física pendente.

Data: 05/10/2026.

## Contexto e decisão

O usuário pediu que Prévia e impressão abra um diálogo na versão alternativa, com a comanda e as ações Imprimir e Imprimir e fechar. A página existente permanece disponível até uma decisão posterior, por um terceiro botão com ícone ao lado de Cancelar comanda.

O diálogo reutiliza a geração do documento, a prévia congelada, a revisão por fingerprint, o modo de impressão e a configuração da impressora. O conteúdo possui rolagem e os dois botões permanecem fora da área rolável. Em simulação, o diálogo identifica que não há impressão em papel. O atalho para a página mantém um alvo de 48 × 48 pixels e rótulo acessível.

As ações continuam nos serviços existentes: Imprimir preserva a comanda aberta; Imprimir e fechar encerra apenas a selecionada. Após aceitar a solicitação, retornar ao atendimento alternativo. Falhas de revisão mantêm o diálogo e apresentam a prévia atual para nova conferência, sem criar impressão. Sem JavaScript, o botão principal acessa a página existente.

## Consequências

A tela padrão e a página de prévia não são substituídas. Nenhuma migration ou alteração de hardware. O diálogo cria solicitações de impressão; a entrega continua sob responsabilidade do worker e aparece no histórico/página existente.

## Validação

Testes Django verificam diálogo versus página, impressão sem encerrar, encerramento da selecionada com preservação das outras e rejeição de conteúdo modificado após a revisão. Chrome com dados fictícios verificou abertura, rolagem, botões visíveis em 1280 × 673, atalho para a página e os dois fluxos em modo de prévia. Nenhuma impressão física executada.
