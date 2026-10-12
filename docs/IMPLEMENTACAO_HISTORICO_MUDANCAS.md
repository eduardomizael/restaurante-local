# Histórico de mudanças

Implementado em 12/10/2026, conforme [ADR-0045](adr/0045-historico-versionado-e-confirmacao-local.md).

## Como registrar uma atualização

Definir a versão da aplicação em `[project].version` no `pyproject.toml` e atualizar `uv.lock` com `uv lock`. Usar o formato `maior.menor.correção`: aumentar a menor para funcionalidades e a correção para ajustes. A versão deste incremento é `0.2.0`.

Acrescentar um grupo no topo de `resources/change-history.json`, com `date` no formato `AAAA-MM-DD`, `version` e `changes`, uma lista de objetos com `summary` e `description`. A versão mais recente deve coincidir com o `pyproject.toml`; um teste verifica essa consistência. Manter os grupos anteriores, sem repetir versões. O diálogo exibe um título com versão e data, seguido dos tópicos detalhados. Ordenar por data decrescente e, na mesma data, pela versão numérica decrescente; preservar a ordem dos tópicos de cada grupo.

Exemplo:

```json
[
  {
    "date": "2026-10-12",
    "version": "0.2.0",
    "changes": [
      {"summary": "Resumo da novidade", "description": "Como usar e o que muda para o usuário."}
    ]
  }
]
```

O SHA-256 do conteúdo identifica novidades. Alterações de código sem mudança nesse arquivo não abrem o aviso. A confirmação local fica em `DATA_DIR/change-history-state.json`, compartilhada na instalação, sem persistência no banco. Uma atualização que preserve a pasta de dados preserva essa confirmação. O spec do PyInstaller inclui os recursos no pacote; não foi gerado nem publicado um novo executável nesta implementação.

## Validação

- Suíte Django: 293 testes executados, 1 ignorado, sem falhas. Após ajuste final no formulário, os 7 testes específicos do histórico passaram novamente.
- Testes específicos verificam confirmação persistente, mudança de conteúdo, hash antigo, CSRF, estado corrompido, GET sem escrita e preservação do arquivo anterior quando a gravação atômica falha.
- Chrome instalado, servidor de teste local, banco em memória, pasta de dados temporária e equipamentos simulados: abertura automática, fechamento e recarga, acesso pelo Status, Escape e atendimento alternativo.
- Rolagem interna e botão de confirmação visível, com alvo mínimo de 48 px, em 1024×600, 800×600, 390×650 e 1280×673.
- Nenhuma migration operacional, impressão física, commit, push ou publicação realizados.

Agrupamento por versão/data: 8 testes específicos aprovados, incluindo ordenação numérica das versões, rejeição de grupos inválidos e consistência com o `pyproject.toml`. No Chrome, confirmado o título “Versão 0.2.0 — 12/10/2026” com seis tópicos, mantendo abertura automática, confirmação, Escape, consulta pelo Status e rolagem nas quatro dimensões acima.
