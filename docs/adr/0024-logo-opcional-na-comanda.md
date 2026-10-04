# ADR-0024 — Logo opcional na comanda

Status: aceita. Data: 04/10/2026. Complementa ADR-0023.

## Contexto e decisão

O usuário solicitou upload de logo em Configurações → Documento, centralizada acima do cabeçalho. Sem logo, não renderizar imagem, linha vazia ou espaço reservado. Permitir substituição e remoção explícita; salvar apenas textos preserva a imagem atual.

Aceitar PNG/JPEG de até 2 MB e 4 milhões de pixels, decodificados pelo Pillow já presente no ambiente. Remover metadados, aplicar orientação EXIF, compor transparência sobre branco e converter para preto e branco. Redimensionar proporcionalmente para no máximo 384 × 192 pontos, sem ampliar imagens pequenas. Guardar PNG normalizado e raster binário em base64 no JSON `DocumentConfiguration.logo`, dentro do SQLite externo ao executável. Não expor caminhos de upload nem depender de arquivos de mídia para reimpressão.

Novos documentos usam versão 7 e congelam uma cópia da logo junto dos valores comerciais. Mudança de logo altera revisão e fingerprint; documento salvo e segunda via conservam a imagem original. Versões 1–6 mantêm suas apresentações. O texto continua sem comandos de transporte e sem linhas artificiais para a imagem.

Prévia HTML usa o PNG monocromático centralizado. RAW envia raster `GS v 0` em tamanho normal antes do cabeçalho, com alinhamento central ativado e depois restaurado à esquerda. Conferir dimensões e quantidade de bytes antes de abrir o spooler. Esta escolha atende o perfil POS-80 atual; o comando é legado e seu suporte na impressora instalada ainda precisa de ensaio físico. Fonte do contrato: [referência oficial Epson GS v 0](https://download4.epson.biz/sec_pubs/pos/reference_en/escpos/gs_lv_0.html). Na prévia, a escala assume 8 pontos/mm (máximo 48 × 24 mm); a densidade física efetiva permanece a confirmar.

## Atualização e validação

Migration `printing.0004_documentconfiguration_logo` gerada com Django, adicionando JSON vazio sem alterar cabeçalho, rodapé, revisão ou documentos anteriores. Executar `Atualizar.bat` com a aplicação fechada, na etapa explícita de atualização com backup. Não aplicar migration automaticamente ao iniciar.

Testes cobrem parsing multipart, arquivos inválidos e limites, PNG/JPEG, transparência, proporções, bits pretos e padding branco, presença/ausência na prévia, troca/remoção, revisão obsoleta, fingerprint, documento congelado e transporte RAW falso com alinhamento restaurado. Nenhum envio físico é executado na validação.

Alternativa rejeitada: guardar apenas caminho de arquivo no documento, pois remover ou substituir o arquivo mudaria as segundas vias. O custo do snapshot embutido é maior tamanho do banco, limitado pelo raster normalizado a 9.216 bytes e seu PNG compacto por documento.
