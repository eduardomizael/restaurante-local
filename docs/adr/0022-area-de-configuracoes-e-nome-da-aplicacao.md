# ADR-0022 — Área de configurações e nome da aplicação

Status: aceita. Data: 03/10/2026. Complementa ADR-0012.

## Contexto e decisão

O usuário solicitou navegação superior reservada às áreas principais, reunindo numeração, documento e equipamentos em uma área de configurações, além de editar o nome mostrado na barra superior. Determinou remover o indicador de transportes reais/simulados da barra e o rodapé técnico global.

Adicionar a entrada **Configurações** com submenus **Geral**, **Numeração**, **Documento** e **Equipamentos**. Todas as páginas compartilham o mesmo template de seção e destacam o submenu atual. Manter as URLs dos formulários existentes para preservar links e fluxos de edição. A navegação principal mantém Atendimento, Produtos, Histórico, Configurações e Status.

Persistir o nome em `ApplicationConfiguration`, singleton independente das configurações de equipamentos e documentos, com default **Restaurante Local**, limite de 80 caracteres e revisão para rejeitar edições obsoletas. Forms fazem parsing, selectors fazem leitura sem criar registros, services validam e salvam em transação SQLite IMMEDIATE com evento de histórico. POST exige CSRF e runtime ativo. Templates escapam o nome e o usam na marca e no título das páginas.

O nome da interface não altera o cabeçalho de impressão nem documentos congelados. Detalhes dos transportes permanecem no diagnóstico Status e nas confirmações de impressão em que explicam a ação. Remover os textos globais solicitados não modifica captura, fila, impressão ou estados do spooler. Submenus têm alvos de pelo menos 48 px, foco visível e quebra de linha em telas menores.

## Atualização e validação

Migration `configuration/0002_applicationconfiguration.py` gerada pelo Django e revisada. Com o aplicativo fechado, executar `Atualizar.bat` para backup e atualização explícita antes de abrir o novo código; não migrar automaticamente na abertura.

Testes cobrem navegação, default sem escrita no GET, persistência e propagação do nome, validação, revisão obsoleta, escape HTML, métodos HTTP, CSRF e runtime ausente. Validação visual em instalação temporária com balança e impressão simuladas percorreu os quatro submenus e salvou o nome, confirmando a mudança da barra e título. Banco operacional e equipamentos reais não foram usados.
