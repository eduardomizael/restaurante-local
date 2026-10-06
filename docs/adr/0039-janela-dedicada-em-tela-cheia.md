# ADR-0039 — Janela dedicada em tela cheia

Data: 06/10/2026. Status: aceita por solicitação do usuário.

## Contexto

O usuário pediu abertura maximizada ou em tela cheia e fechamento da janela pela interface. A abertura pelo navegador padrão não controla tamanho ou posse da janela. A ADR-0028 já coordena o encerramento pela interface, mas deixava a janela aberta. WebView2 permanece adiado.

## Decisão

No Windows, abrir uma janela dedicada em tela cheia: usar Edge instalado, com fallback para Chrome. O inicializador passa o modo kiosk e um perfil exclusivo por sessão em `dados/browser/<instance_id>`, sem reutilizar o perfil pessoal. Não instalar navegador ou configurar quiosque do Windows. Abertura ocorre somente após confirmar prontidão HTTP, sem acesso ao hardware durante imports ou views.

O padrão é `fullscreen`. Para suporte, `run_local --browser-mode maximized` abre uma janela dedicada maximizada; `browser_mode` em `installation.json` permite persistir essa opção e aceita somente `fullscreen` ou `maximized`. Instalações existentes assumem fullscreen sem alterar banco ou exigir migration. `--no-browser` permanece disponível. Fora do Windows, conservar navegador padrão sem prometer fechamento automático.

**Status → Encerrar aplicação → Sim, encerrar aplicação** mantém POST, CSRF e confirmação. Após entregar a página final e parar os componentes, o runtime solicita fechamento das janelas de seus processos com `WM_CLOSE`. Há prazo e fallback por handle do processo iniciado com perfil exclusivo. Não encerrar processos por nome, usar taskkill ou fechar janelas de outros perfis. **Sair** na bandeja usa a mesma parada. **Continuar usando** não encerra nada. Fechar a janela manualmente continua sem interromper captura ou impressão; o atalho pode reabri-la.

O atalho duplicado pede ao runtime ativo que abra a janela. Uma rota POST local exige CSRF e uma capability aleatória armazenada apenas em `instance.json` e no estado privado do runtime. Ela não aparece em health, snapshots ou templates. Assim o processo dono conserva os handles também quando a janela foi fechada manualmente e reaberta por outro launcher. Não duplicar servidor, trabalhadores ou acesso ao hardware. Runtimes antigos ou iniciados com `--no-browser` conservam abertura no navegador padrão.

O perfil de sessão é removido após os processos encerrarem, somente dentro da pasta de sessões e com identidade validada. Falha de limpeza é registrada; perfis de sessões interrompidas podem permanecer. Dados comerciais, configuração e backups ficam separados desse perfil. Navegação manual no navegador pessoal não permite fechamento automático dessa janela.

## Consequências e alternativas

Edge ou Chrome precisam estar instalados em caminho padrão do Windows. Ausência gera orientação explícita. Uma página web comum não garante maximização ou fechamento de uma janela aberta pelo navegador; um navegador embutido adicionaria runtime próprio. A janela dedicada permite o comportamento solicitado com navegador instalado.

## Validação

Testes verificam flags, perfil exclusivo, descoberta/fallback, fechamento por posse, prazo, bloqueio de abertura após parada, controle por POST/CSRF/capability e reabertura pelo processo dono. Ensaio nativo opt-in com Edge em Windows x64, banco temporário e transportes simulados confirmou janela cobrindo monitor, encerramento pelo POST da interface, saída normal do runtime e preservação de uma segunda janela isolada. Não usa perfil pessoal, COM ou spooler. Chrome e Windows x86 final permanecem para conferência nativa própria; testes de construção do comando não equivalem a homologação nesses ambientes.

Este incremento complementa a ADR-0028. Fonte do modo Edge: [Configurar modo kiosk](https://learn.microsoft.com/en-us/deployedge/microsoft-edge-configure-kiosk-mode).

Resultado local: suíte de 230 testes aprovada, com 229 executados e o ensaio nativo opt-in ignorado na execução padrão. O ensaio nativo foi executado separadamente e passou, incluindo fechar manualmente, reabrir por um segundo launcher, conferir tela cheia e sair pela interface mantendo a outra janela de teste. `check` sem problemas e `makemigrations --check --dry-run` sem alterações. Publicação autorizada na main fornece a mudança ao canal por código; pacotes executáveis continuam dependendo de promoção para release.
