# Restaurante Local

Aplicação autônoma de pesagem, pré-inserção de itens e impressão de comandas para um PC Windows 10/11, com interface touch em Django e operação offline.

Raiz: `D:\restaurante-local`. Projeto independente de `D:\restaurante`; não compartilha ambiente, imports, banco, configuração ou agentes com ele.

## Estado atual

Fundação Django e primeiro recorte do inicializador implementados: Waitress em loopback, mutex por diretório de dados, diagnóstico touch, HTMX local, leitura simulada, pausa/retomada, bandeja e encerramento coordenado. Dependências próprias fixadas em `pyproject.toml` e `uv.lock`. Histórico organizado em commits semânticos em português; novos commits exigem pedido explícito.

Backend comercial implementado: products, measurements e orders, snapshots em centavos/gramas, captura persistente explícita, múltiplos rascunhos, inclusão/remoção, consumo único, descarte manual e cancelamento isolado. Commits deste recorte autorizados expressamente pelo usuário. Consulte [entrega do domínio](docs/IMPLEMENTACAO_DOMINIO.md).

Ainda pendentes: telas comerciais e configuração, captura automática persistente pelo worker, fila/preview de impressão, adaptadores reais e distribuição. `--preview-print` bloqueia qualquer futura impressão física neste modo; não significa que o preview documental já exista. A etapa 1 do plano permanece parcialmente concluída.

## Desenvolvimento e execução

Requer Python 3.13 e uv para desenvolvimento. Os comandos são executados nesta raiz:

```powershell
rtk proxy uv sync --frozen --cache-dir .uv-cache
rtk proxy uv run --offline --no-sync python manage.py initialize_local
rtk proxy uv run --offline --no-sync python manage.py run_local --simulate --preview-print
```

`initialize_local` é a etapa explícita de instalação/atualização: gera segredo local e aplica migrations; em dados existentes, salva backup consistente de SQLite e configuração antes de atualizar. Exige o programa fechado. O início normal nunca migra o banco. Inclui as migrations nativas de `contenttypes` e as migrations geradas dos apps core, products, measurements e orders.

Dados padrão: `%LOCALAPPDATA%\RestauranteLocal`, fora dos arquivos do programa. Para testes ou outra instalação, definir `LOCAL_WEIGHING_DATA_DIR` antes de executar os comandos. Nunca apontar para os dados do Restaurante anterior. Porta padrão `8765`; alterar com `initialize_local --port 8766`, com programa fechado.

Para executar sem bandeja/navegador:

```powershell
rtk proxy uv run --offline --no-sync python manage.py run_local --simulate --preview-print --no-tray --no-browser
```

Abrir `http://127.0.0.1:8765/` após a mensagem de prontidão. Encerrar com **Sair** na bandeja ou Ctrl+C sem bandeja. Fechar o navegador não encerra o processo. Segunda execução confirma a identidade HTTP da instância existente antes de abrir sua interface e não duplica leitor/servidor. A abertura atual usa o navegador padrão; perfil próprio e kiosk ficam para distribuição.

## Validação

```powershell
rtk proxy uv run --offline --no-sync python manage.py check --settings=config.test_settings
rtk proxy uv run --offline --no-sync python manage.py test --settings=config.test_settings
rtk proxy uv run --offline --no-sync python manage.py makemigrations --check --dry-run --settings=config.test_settings
```

45 testes isolados usam diretórios/banco temporários, simulador e backend falso de bandeja; não abrem navegador, COM ou spooler. Cobrem Waitress real em loopback, backup, processos distintos, porta ocupada, falha parcial, CSRF, encerramento, invariantes comerciais e concorrência SQLite em arquivo com conexões distintas. Consulte os registros da [fundação](docs/IMPLEMENTACAO_FUNDACAO.md) e do [domínio](docs/IMPLEMENTACAO_DOMINIO.md) para evidências e limitações.

## Documentação

- [Plano e requisitos de produto](docs/PLANO_APLICACAO_LOCAL_PESAGEM.md).
- [Estrutura técnica e inicializador](docs/ESTRUTURA_TECNICA_APLICACAO_LOCAL.md).
- [Decisão Django e interface touch](docs/adr/0012-aplicacao-autonoma-django-touch.md).
- [Referência de balança e impressora](docs/REFERENCIA_HARDWARE.md).
- [Modelo visual da comanda](docs/references/order-slip-reference.png).
- [Registro da separação](docs/SEPARACAO_PROJETOS.md).

## Escopo

Várias comandas abertas, pesagens compartilhadas, produtos rápidos, peso manual, numeração sequencial, configurações e impressão em bobina contínua de 80 mm. Descarte de medições somente manual. Sem estoque, caixa, pagamento ou emissão fiscal.

Equipamentos previstos: COM3 e fila Windows `balanca`, futuramente editáveis pela tela de configuração. Backend Django/SQLite, Templates/HTMX e assets locais; entrada técnica `manage.py run_local`.

Não instalar, migrar ou iniciar o sistema antigo para desenvolver este projeto. Nenhum hardware físico foi homologado pela implementação atual.
