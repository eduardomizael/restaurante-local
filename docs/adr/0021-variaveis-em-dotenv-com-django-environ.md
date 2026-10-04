# ADR-0021 — Variáveis em .env com django-environ

Status: aceita. Data: 03/10/2026. Complementa ADR-0012.

## Contexto

O usuário determinou o uso de `.env` na raiz do projeto e da biblioteca `django-environ` com defaults. A aplicação usava acesso direto ao ambiente para escolher o diretório de dados e valores fixos nas configurações Django.

## Decisão

Centralizar o carregamento em `config/environment.py`, com caminho absoluto derivado do próprio módulo, antes de resolver a instalação. Usar `django-environ==0.14.0`, fixado por uv no ambiente e lockfile próprios. Ler o arquivo em UTF-8 quando presente, sem sobrescrever variáveis do processo. A ausência do arquivo mantém os defaults e não cria dados, migrations ou workers.

Expor `DEBUG` (booleano, default falso), `TIME_ZONE` (default America/Sao_Paulo), `LOCAL_WEIGHING_DATA_DIR` (default diretório de dados do usuário) e `SECRET_KEY` (default chave gerada na instalação). O default de armazenamento continua usando `LOCALAPPDATA` do Windows, ou o fallback histórico de diretório do usuário. A inicialização respeita o mesmo override de chave das settings. Não fornecer segredo fixo compartilhado.

Manter `.env` fora do Git e versionar apenas `.env.example`. As variáveis do processo têm prioridade para preservar instalações temporárias de validação. Banco, logs, backups e configuração operacional permanecem fora da raiz. Porta HTTP e equipamentos continuam nas configurações existentes; abrir a aplicação continua sem aplicar migrations.

## Consequências e validação

Comandos técnicos e arquivos de abertura usam a mesma leitura, sem depender de uv para interpretar `.env`. O operador precisa reiniciar após editar o arquivo. Trocar o diretório seleciona outra instalação, sem transferir dados automaticamente. O runtime distribuído deverá incluir a dependência e posicionar o arquivo de configuração conforme a raiz do programa; o empacotamento continua pendente.

Validar arquivo ausente, parsing booleano, caminhos com espaços e UTF-8, precedência do processo, fallback da chave e diretório padrão. Rodar checks e suíte com settings isoladas, sem hardware real ou alteração do banco operacional.
