# ADR-0012 — Aplicação autônoma de pesagem com Django e interface touch

- Status: Aceito
- Data: 2026-10-03
- Escopo: nova aplicação local; não substitui a ADR-0010 nem altera o Restaurante existente.

## Contexto

O usuário definiu um programa independente para Windows 10/11, um PC, balança COM3 e impressora balanca. A operação envolve várias comandas abertas, medições compartilhadas, cadastro simples e impressão interna em papel contínuo. Não há caixa, fiscal ou dependência do Restaurante.

A interface será usada por toque. Em 03/10/2026 o usuário escolheu Django com as recomendações da conversa **Detalhar estrutura técnica** e solicitou inicializador para servidor e agente, com ícone na bandeja. A proposta anterior de interface Tkinter do plano desta aplicação é substituída.

## Alternativas consideradas

- Tkinter: adequado a utilitários desktop, mas menos conveniente para o terminal touch e composição visual desejados.
- Flask/FastAPI: viáveis, porém exigiriam escolher e integrar persistência, migrations e formulários adicionais.
- Django com Templates/HTMX: aproveita ORM, migrations, forms e convenções já conhecidas, mantendo o frontend simples e local.
- Processos independentes para cada periférico: isolamento maior, com custo de supervisão e comunicação desnecessário no escopo inicial de um PC.

## Decisão

1. Usar projeto Django próprio, banco SQLite próprio, Templates/HTMX e CSS/JS local. Não importar apps, settings ou runtime do Restaurante.
2. Projetar telas para toque: alvos mínimos de 48 px, ícones e rótulos, teclado numérico e feedback sem depender de mouse/hover.
3. Executar servidor WSGI Waitress somente em loopback. Navegador Edge/Chrome apresenta a interface; o Python controla balança e impressora.
4. Criar comando `manage.py run_local` no novo projeto. O comando compõe bandeja, servidor e workers de serial/impressão em um processo, com threads dedicadas. Um launcher sem console chama a mesma composição.
5. Inicializar workers exclusivamente no runtime explícito, nunca em imports, `AppConfig.ready()`, views ou autoreloader. Usar mutex de instância e encerramento coordenado.
6. Manter regras em services, consultas em selectors, parsing em forms, HTTP em views e persistência/restrições em models. Adaptadores físicos e simuladores têm contratos equivalentes.
7. Serial e spooler não executam em transações abertas nem nas threads que atendem pedidos de tela. Trabalhos de impressão são persistidos e o resultado incerto exige ação explícita.
8. Separar settings mínimos de instalação das configurações operacionais no banco. Assets e runtime necessários são distribuídos localmente; operação não exige internet.

## Consequências e validação

Há um servidor web embutido no programa, mas nenhum servidor externo necessário. Fechar o navegador não encerra leitura; **Sair** na bandeja encerra o runtime e libera COM e porta HTTP. Queda do processo exige novo início; SQLite preserva rascunhos e trabalhos confirmados.

SQLite não oferece bloqueio de linha por `select_for_update()`: os services precisam de transações curtas, escrita condicional e restrições únicas, com testes concorrentes reais. A implementação não pode copiar garantias de PostgreSQL do projeto de referência.

Validar dupla inicialização, falha da COM, porta HTTP ocupada, desligamento durante impressão, navegação touch, recuperação de rascunhos e funcionamento offline. Dependências e versões serão avaliadas e fixadas quando o projeto próprio for criado. Esta ADR não declara o inicializador implementado ou hardware homologado.

Detalhamento: [Estrutura técnica](../ESTRUTURA_TECNICA_APLICACAO_LOCAL.md) e [Plano](../PLANO_APLICACAO_LOCAL_PESAGEM.md).
