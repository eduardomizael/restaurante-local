# Separação dos projetos

Data: 03/10/2026. Solicitada pelo usuário: criar D:\restaurante-local e transferir o material da aplicação autônoma.

Transferidos do projeto anterior: plano da aplicação local, estrutura técnica e ADR-0012. Removida a entrada dessa ADR do índice anterior. Documentos ajustados para usar referências locais; identificador da decisão preservado.

Preservados aqui: fotografia da comanda e consolidação das evidências de balança/impressora, com origem histórica e pendências explícitas. Criados README, AGENTS.md, .gitignore e índice de ADRs próprios.

O projeto anterior preserva integralmente seu código, agente, contratos de integração, ADRs anteriores, dependências e dados. Nenhum arquivo sensível, banco, .env, log, ambiente ou configuração de produção foi transferido. Não há importação de código do agente anterior.

Neste momento não existe código implementado do aplicativo novo para mover: o conteúdo transferido é a especificação aprovada. Django, models, migrations, assets e inicializador serão implementados na nova raiz com ambiente próprio.

O repositório novo é independente; nenhuma relação de submódulo, junction, symlink ou dependência de caminho com D:\restaurante. Não houve commit, push, instalação de dependências, execução de servidor, migrations ou equipamento físico nesta separação.