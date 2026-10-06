# ADR-0037 — Promoção do atendimento compacto

Status: aceita; homologação física pendente.

Data: 05/10/2026.

## Contexto e decisão

Após avaliar e ajustar a versão alternativa, o usuário escolheu torná-la principal e manter a anterior como alternativa.

O endereço `/` e a navegação Atendimento apresentam o layout compacto: peso à esquerda, pesagens ao lado, comandas de 248 pixels, itens e produtos rápidos na proporção 1 : 0,8, catálogo em diálogo e prévia de impressão em diálogo. A página de prévia existente continua acessível pelo ícone.

`/attendance/alternative/` passa a apresentar a versão anterior, com catálogo permanente. Status oferece Atendimento principal e Versão alternativa. A navegação Atendimento sempre abre a principal. Ações e retornos da versão anterior transportam `layout=alternative`; as ações sem esse parâmetro usam a principal. O layout não altera dados ou regras comerciais.

## Consequências e validação

Revisa o papel das versões descritas nas ADRs 0034–0036; os nomes internos dos templates e classes CSS podem preservar sua origem histórica. Nenhuma migration. A mudança é local e não implica commit, push ou publicação.

Testes verificam a principal na raiz, a anterior na rota alternativa e a preservação de destinos em criação, seleção, inclusão, atualização HTMX e impressão. A validação no navegador usa dados fictícios e modo de prévia, sem impressão física.
