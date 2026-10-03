# Restaurante Local — instruções de desenvolvimento

## Escopo e fontes de verdade

Este é um projeto independente, na raiz `D:\restaurante-local`. Não importar módulos, settings, banco ou configuração de `D:\restaurante`. Os documentos locais são suficientes para trabalhar; o projeto anterior é apenas origem histórica das evidências de hardware.

Consultar `docs/PLANO_APLICACAO_LOCAL_PESAGEM.md`, `docs/ESTRUTURA_TECNICA_APLICACAO_LOCAL.md`, `docs/REFERENCIA_HARDWARE.md` e `docs/adr/`. Precedência: instruções explícitas atuais do usuário, ADR aceita, contrato técnico específico e plano. Separar fatos confirmados, propostas e homologação pendente.

## Fluxo

- Codex implementa, valida e revisa diretamente. Não criar ou executar harness, tasks externas ou agentes executores externos. Não usar subagentes como padrão.
- Declarar tipo de trabalho e fluxo antes de editar; inspecionar Git e preservar alterações não relacionadas.
- Não criar commit nem push sem pedido explícito. Quando autorizado, commits semânticos, atômicos e em pt-BR, com revisão do staged.
- Prefixar comandos shell com `rtk`; usar `rtk proxy` quando necessário.

## Arquitetura e produto

- Django próprio, SQLite, Templates/HTMX, CSS/JS locais, Waitress loopback e inicializador com bandeja. Sem DRF, Redis, Celery, SPA ou CDN no MVP.
- Models para estrutura/restrições; selectors para consultas; services para regras, transações e escrita; forms para parsing; views para HTTP; templates somente apresentação.
- Hardware e workers independentes das telas. Nunca abrir COM, spooler ou iniciar threads em imports, views ou AppConfig.ready().
- Várias comandas abertas; medições compartilhadas utilizáveis uma única vez. Fechamento não descarta disponíveis; descarte manual. Impressão encerra somente a selecionada.
- Valores históricos e documento impresso congelados. Peso em gramas, dinheiro em centavos e Decimal para parsing/cálculo; sem float comercial. SQLite não garante bloqueio com select_for_update().
- Interface touch: alvos mínimos 48 x 48 px, ícones com rótulos relevantes, teclado numérico, contraste/foco e nenhuma ação dependente de hover. Assets próprios e locais.

## Ferramentas, validação e operação

- uv para Python/dependências; ambiente e lockfile próprios. Não usar pip manual ou dependências do projeto anterior.
- npm somente para assets se necessário; versões fixadas e lockfile. Distribuição funciona sem uv/npm/internet.
- Código e nomes técnicos em inglês; UI e documentação em pt-BR; docstrings no padrão Google.
- Migrations nunca são escritas manualmente: Codex revisa models, gera com makemigrations e revisa arquivos gerados. Não aplicar migrations automaticamente na abertura; instalação/atualização tem etapa própria e backup.
- Não copiar .env, segredos, bancos, filas, logs ou configuração de produção. Dados locais ficam fora do Git e separados do executável.
- Não executar hardware real, impressão, instalar serviço Windows, configurar início automático ou fazer deploy como efeito implícito de validação. Usar simuladores até autorização correspondente.
- Validar invariantes, concorrência SQLite, dupla inicialização, encerramento, falhas de impressão, recuperação e fluxo touch conforme o escopo. Documentar limitações; não declarar homologação física sem evidência.
- Registrar mudanças arquiteturais em ADR e atualizar documentos junto da implementação.