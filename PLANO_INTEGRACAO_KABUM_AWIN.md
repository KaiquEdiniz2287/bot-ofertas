# Planejamento futuro: KaBuM! / Awin

Estado: **adiado a pedido do usuário**. Este documento registra dúvidas e verificações; não autoriza implementar ou alterar a conta Awin agora.

## Objetivo

Adicionar KaBuM! como fonte independente de produtos afiliados no Bot de Ofertas, preservando as fontes, o garimpo e os envios existentes.

## O que já sabemos

- O programa de afiliados do KaBuM! usa a Awin.
- A tela **Create-a-Feed** foi localizada e gera uma URL de download com seleção de colunas.
- Um feed é o candidato principal para descobrir produtos, preços e imagens. O Link Builder serve para criar links de rastreamento a partir de URLs de produtos, caso o feed não forneça um link afiliado utilizável.
- A captura enviada estava reduzida; não foi possível confirmar nela se **KaBuM!** é o anunciante selecionado, se o formato é **Legacy** ou **Enhanced**, nem quais campos têm dados reais.
- A URL completa do feed pode conter uma chave de acesso e não deve ser colada em conversas, issues ou logs.

## Dúvidas a resolver antes de implementar

1. A participação na campanha KaBuM! aparece como aprovada na conta Awin usada?
2. KaBuM! aparece no seletor **Toolbox → Create-a-Feed**? Qual é o nome, idioma e formato do feed: Legacy ou Enhanced?
3. O arquivo baixado tem produtos reais e atuais? Qual a frequência de atualização e o tamanho aproximado?
4. Quais colunas estão efetivamente preenchidas: ID do produto, nome, descrição, categoria, preço atual, preço anterior/desconto, moeda, estoque, imagem principal e link?
5. O feed Legacy oferece `aw_deep_link` válido para esta conta? Se for Enhanced, existe campo afiliado próprio? O campo `link` do formato Google é uma URL de produto **sem rastreamento** e não pode ser publicado como afiliado sem conversão.
6. Se precisarmos do Link Builder, o programa KaBuM! permite gerar deeplinks por API para os produtos? Há necessidade de token da Partner API, distinto da chave do feed?
7. As regras vigentes do programa permitem os canais de divulgação pretendidos, incluindo Telegram e WhatsApp?
8. Os dados de preço, estoque e imagem estão confiáveis o suficiente para publicar automaticamente? Como lidar com ofertas desatualizadas ou produtos ausentes do feed?

## Caminho técnico provável, sujeito às respostas

1. Criar uma fonte KaBuM!/Awin isolada, sem tocar nas integrações existentes.
2. Baixar/atualizar o feed somente quando houver nova versão e manter cache local para buscas e ciclos.
3. Filtrar produto disponível, moeda/preço válido, categoria e imagem; nunca inventar desconto ou avaliação ausente.
4. Usar somente link afiliado confirmado; se necessário, converter a URL do produto pelo Link Builder e validar o resultado antes da publicação.
5. Testar garimpo, busca manual, formatação e rastreamento em ambiente controlado antes de habilitar publicações.

## Próxima evidência necessária

Captura ampliada do **anunciante selecionado e formato do feed**, mais cabeçalho e duas linhas de exemplo do arquivo, com URL de download, chaves, tokens e links pessoais ocultos.

Documentação: [KaBuM! afiliados](https://www.kabum.com.br/hotsite/afiliados/), [Awin Create-a-Feed](https://help.awin.com/developers/docs/downloading-feeds-using-create-a-feed), [Awin Product Feed](https://help.awin.com/developers/docs/product-feed-publisher-guide-intro), [Awin Link Builder](https://help.awin.com/apidocs/generatelink).
