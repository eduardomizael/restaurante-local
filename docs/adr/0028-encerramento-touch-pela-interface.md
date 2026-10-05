# ADR-0028 — Encerramento pela interface touch

Data: 05/10/2026. Status: aceita por solicitação do usuário.

## Contexto

O menu nativo da bandeja é pequeno para os dedos. O usuário solicitou encerramento pela interface e adiou WebView2.

## Decisão

Adicionar **Encerrar aplicação** na navegação superior, com alvo mínimo de 56 px. GET abre confirmação sem efeitos; POST exige CSRF e confirmação explícita. **Continuar usando** preserva o atendimento.

O runtime registra seu próprio sinal de parada somente durante a inicialização explícita. A confirmação bloqueia novas mutações e devolve uma página final sem dependências externas. O sinal é enviado uma única vez no fechamento da resposta WSGI, após sua entrega, para evitar desligar HTTP antes da resposta. A thread de setup da bandeja observa o evento do runtime e encerra o loop nativo. O mesmo evento atende o modo sem bandeja. O encerramento existente fecha os componentes e libera a instalação.

Não encerrar ou finalizar comandas, descartar medições nem apagar fila. Impressões interrompidas permanecem sujeitas à recuperação existente, sem prometer conclusão física. Fechar o navegador continua sem parar o runtime. Nenhuma dependência de navegador embutido é adicionada.

## Validação

Atualização em 05/10/2026, por solicitação do usuário: **Encerrar aplicação** fica dentro da tela **Status**, na seção **Como encerrar**, com alvo mínimo de 56 px. O menu superior compartilhado mantém somente Atendimento, Produtos, Histórico, Configurações e Status. A confirmação de encerramento também destaca Status como área ativa. Esta posição substitui a decisão anterior de colocar o botão diretamente na navbar; o fluxo de confirmação e parada permanece igual.

Testar confirmação/cancelamento, CSRF, POST, indisponibilidade, pedidos repetidos, sinal após entrega da resposta, bandeja com substituto e runtime HTTP real com transportes simulados. O ensaio do pacote verifica saída normal pelo POST e remoção do registro de instância. Uso físico por toque permanece para conferência na máquina final.
