# ADR-0045 — Histórico versionado e confirmação local

Status: aceita. Data: 12/10/2026.

## Decisão

Manter o histórico cumulativo em `resources/change-history.json`, versionado e incluído nos pacotes executáveis. Cada grupo tem data ISO (`date`), versão única (`version`) e lista de mudanças (`changes`), com resumo (`summary`) e explicação breve (`description`). O título do grupo mostra versão e data, seguido dos tópicos detalhados. Exibir grupos por data decrescente e, na mesma data, versão numérica decrescente. Manter a ordem dos tópicos de cada grupo e preservar as versões anteriores.

A versão da aplicação é definida em `[project].version` no `pyproject.toml`, com `uv.lock` sincronizado. O primeiro grupo publicado no histórico deve ter a mesma versão. Este incremento passa de `0.1.0` para `0.2.0` por acrescentar funcionalidades.

Na abertura de uma página completa, consultar o histórico e abrir um diálogo quando seu SHA-256 diferir da confirmação local. O hash considera o conteúdo JSON, sem depender do Git ou de alterações de código sem novidades registradas. Atualizações futuras precisam acrescentar suas entradas ao arquivo.

O botão “Entendi, fechar” e Escape confirmam a leitura por POST com CSRF. A confirmação só encerra o diálogo após gravação atômica de `change-history-state.json` na pasta de dados da instalação (`DATA_DIR`). A confirmação vale para a instalação, compartilhada entre seus navegadores; não é individual por usuário. Ausência ou corrupção do arquivo faz o aviso reaparecer. Falha de gravação mantém o diálogo aberto para nova tentativa. Uma confirmação com hash antigo é recusada.

A tela de Status permite reabrir todo o histórico a qualquer momento. O corpo do diálogo rola independentemente do botão de fechar. Sem JavaScript, o botão abre uma página com formulário normal. Uma falha no arquivo do histórico não impede o atendimento de abrir.

## Consequências

Não há tabela nem migration para esse recurso. O arquivo de confirmação fica separado do programa e sobrevive às atualizações dos canais por código e executável. O diálogo pausa apenas o polling visual, conforme os demais diálogos, sem interromper a captura em segundo plano. Esta alteração não publica novos pacotes nem homologa arquiteturas Windows.
