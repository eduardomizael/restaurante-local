# Produtos, medições e comandas — recorte de backend

Data: 03/10/2026. Implementado diretamente após os quatro commits autorizados da fundação. Commits deste recorte autorizados expressamente pelo usuário, separados por responsabilidade; não houve push, acesso ao projeto anterior ou hardware real. Novos commits continuam exigindo ordem expressa.

## Entrega

- Product: catálogo UN/KG, preço em centavos, ativo, acesso rápido, Aparece na comanda, ordenação e revisão para rejeitar edição desatualizada. Troca atômica do único produto ativo em KG da balança.
- Measurement: identificadores UUID/número interno, captura sem comanda, peso líquido e tara em gramas, dispositivo, parâmetros técnicos, snapshots comerciais e estados AVAILABLE/USED/DISCARDED.
- Order/OrderSequence: vários rascunhos, numeração sequencial atômica, ajuste explícito do próximo número sem renumerar histórico e idempotência de abertura.
- OrderItem: inclusão manual UN/KG ou consumo explícito de medição, destino fixado pela ação, snapshots, remoção sem exclusão e índice único para vínculo ativo. Repetir a ação original não duplica item nem reativa vínculo removido.
- Cancelamento somente da selecionada, devolvendo medições de seus vínculos; medições já disponíveis e outras comandas permanecem intactas. Descarte manual apenas da medição disponível selecionada.
- Selectors de catálogo ativo/rápido, produto da balança, medições compartilhadas, rascunhos, itens ativos e subtotal em centavos.
- Forms para parsing de preço, quantidade e peso; texto decimal sem milhares/expoentes, conversão para centavos/gramas sem float.
- DomainEvent: eventos de catálogo, captura, vínculo, remoção, descarte, numeração e cancelamento dentro da transação correspondente.

Contrato detalhado e limites técnicos: [ADR-0013](adr/0013-dominio-comercial-e-concorrencia-sqlite.md).

## Banco e migrations

Models foram revisados antes de executar `makemigrations core products measurements orders --settings=config.test_settings`. Quatro migrations iniciais foram geradas pelo Django e revisadas: dependências, FKs PROTECT, checks de unidade/quantidade/status, singleton, UUIDs, preços, números e unicidade parcial do vínculo ativo/produto da balança.

Aplicação das migrations ocorreu somente em bancos temporários de testes, incluindo testes de instalação em subprocesso. Não foi criado ou migrado banco operacional. O comando `initialize_local` continua sendo a instalação/atualização explícita, com backup; `run_local` recusa schema desatualizado.

## Validação

45 testes passaram: 19 da fundação e 26 novos do domínio. `check` sem problemas e `makemigrations --check --dry-run` sem alterações.

Oito testes concorrentes usam SQLite em arquivo com conexões distintas: duas comandas disputando captura, retry concorrente de inclusão, oito alocações de número, abertura repetida, descarte versus consumo, remoção repetida, cancelamento versus inclusão e timeout de banco ocupado. Os resultados não dependem de mock nem de `select_for_update()`.

As demais evidências cobrem arredondamento de meio centavo, parsing pt-BR, rejeição de float nos services comerciais, ausência de produto da balança, edição desatualizada, preço histórico após alteração, várias comandas, lançamento manual sem consumir captura, destino explícito, rollback de consumo se a criação de item falhar, liberação sem apagar histórico, descarte isolado, numeração sem colisão e restrições diretas de banco.

Recuperação em processo independente verifica duas comandas, itens, captura disponível com preço anterior, medição usada, descarte, inclusão após reabertura e cancelamento isolado.

## Limites da entrega e próximo recorte

Este é o backend do domínio. A tela ainda mostra diagnóstico e peso demonstrativo: cadastro e atendimento comerciais não foram ligados ao HTTP, não há teclado numérico novo nem ações comerciais disponíveis pela interface. O worker continua sem gravar automaticamente medições; `capture_measurement` exige captura explicitamente estável de seu chamador, e a máquina física será implementada no próximo recorte de captura.

FINALIZED é previsto no model e os services bloqueiam alterações de comanda nesse estado; a transição de finalização ainda não é oferecida. Ela será feita junto do snapshot documental e fila de impressão, em uma transação. Não há emissão de documento, spooler, reimpressão ou homologação física nesta entrega.

Próximo recorte: integrar cadastro, montagem das comandas e teclado numérico à interface touch; implementar o ciclo simulado de estabilidade/retirada com persistência através do service; manter COM e impressão reais desabilitadas até seus incrementos e autorização de ensaio.
