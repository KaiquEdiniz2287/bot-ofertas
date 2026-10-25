# SHEIN — bloqueio da loja e consulta pelo painel de afiliados

Data: 25/10/2026. Correção: 0.21.2. Nenhuma oferta foi publicada durante os testes.

## Diagnóstico confirmado

O histórico e o Console do aplicativo 0.21.1 confirmaram coleta de 12 ofertas às 09:29 e publicação de um casaco da SHEIN às 09:37, no Telegram e no grupo do WhatsApp. Nos quatro ciclos seguintes, a busca foi redirecionada para verificação nos dois navegadores. As categorias selecionadas eram Moda e Esporte; elas ativam consultas por termos, em vez da página de ofertas gerais.

Com o aplicativo encerrado, foram copiadas somente as duas pastas de perfil da SHEIN para um diretório temporário. As sessões originais, as configurações, o histórico e as conexões dos canais não foram modificados. Nenhum CAPTCHA foi resolvido automaticamente.

| Consulta anterior | CloakBrowser persistente | Chrome oculto |
|---|---|---|
| `/super-deals` | 12 produtos | `/risk/action/limit` |
| `/pdsearch/camiseta/` | `/risk/challenge` | `/risk/challenge` |
| Conversor de afiliados | Formulário acessível | Formulário acessível |

Portanto, o problema observado foi o acesso à busca pública, não uma conta inteiramente desconectada. Trocar apenas o navegador não eliminou a verificação.

## Alternativa validada e implementada

A [documentação brasileira da SHEIN](https://br.shein.com/campus--a-1500.html) descreve a recomendação de produtos no centro de afiliados. Não foi encontrada documentação pública de uma API de catálogo para a conta desse programa brasileiro. A documentação genérica de feeds de redes como a [Awin](https://help.awin.com/developers/docs/product-feed-publisher-guide-intro) não comprova disponibilidade de um feed SHEIN Brasil para esta conta.

O painel autenticado `https://m.shein.com/br/affiliate` abriu normalmente com o Chrome oculto. Seu formulário “Pesquisar produtos” navega para `/br/affiliate/search11` e devolve produtos com preços em reais, imagens, avaliação, vendas e endereço de produto. O CloakBrowser também passou no teste desse formulário.

O provedor agora observa somente as respostas normais produzidas pelo próprio painel:

- Recomendações: `/br/affiliate/api/goods/recommend/recommendNew`.
- Pesquisa pelo formulário: `/br/affiliate/api/search/keywordsNew`.
- Conversão: preservado o formulário oficial já existente.

Não há chamadas diretas a esses endpoints, cópia de credenciais para serviços externos, alteração de IP ou atualização do binário do navegador. Chrome oculto é a primeira opção e CloakBrowser persistente é a alternativa. O login solicitado pelo usuário passa a abrir o catálogo junto do conversor.

O coletor confere origem da resposta, termo enviado, moeda, formato dos dados, ID e URL do produto, preço válido e duplicatas. Bônus e comissões são ignorados no cálculo do preço e do desconto. O painel também retorna recomendações para termos sem correspondência; produtos cujo título não contém nenhum termo significativo da pesquisa são descartados. Essa verificação é textual, não semântica.

São aproveitadas até duas páginas por consulta, com espera máxima de 20 segundos após o acionamento do formulário. A primeira resposta pode ter poucos produtos ou nenhum; a segunda página também é observada. Respostas de pesquisas anteriores e de outras seções do painel não são misturadas. Os tempos de navegação e de carregamento do formulário têm limites próprios. As categorias e o rodízio de até dois termos por ciclo foram preservados.

## Testes reais da implementação

Todas as consultas abaixo usaram perfis temporários e nenhum envio a canais.

| Teste | Resultado | Tempo aproximado |
|---|---|---|
| Ciclo com “tênis” e “camiseta” | 8 produtos; nenhum com desconto mínimo de 25% | 17,1 s |
| Ciclo com “legging” e “roupa fitness” | 30 produtos; 3 com desconto de pelo menos 25% | 13,3 s |
| Recomendações gerais | 3 produtos válidos | 8,4 s |
| Busca manual “camiseta masculina” | 3 produtos com imagem e links afiliados reais | 22,0 s |
| Termo inexistente `zzzxqv987654321` | 0 produtos após descartar recomendações sem correspondência | 8,3 s |
| Termos efetivos de Esporte: “suplemento” e “roupa academia” | 4 produtos; 1 com desconto de pelo menos 25% | 12,6 s |
| Rodízio seguinte: “garrafa térmica” e “tênis” | 3 produtos | 12,9 s |
| Conversão da oferta esportiva escolhida | Link afiliado; de R$ 137,09 por R$ 63,06, desconto de 54% confirmado | 8,8 s |
| Pesquisa do painel pelo CloakBrowser | 8 produtos | 10,3 s |
| Reabertura do Chrome e repetição da pesquisa | 8 produtos | 9,0 s |

As quantidades são uma fotografia destes testes. O catálogo do afiliado pode ter menos produtos que a loja pública. “Tênis” e “suplemento” não tiveram produtos válidos nas páginas examinadas, sem erro de acesso. Encontrar produtos não garante publicação: desconto mínimo, repetição, limite por ciclo e seleção entre marketplaces continuam aplicados.

## Regressão e limites

- 156 testes Python aprovados, incluindo 33 do módulo SHEIN.
- 30 testes da interface aprovados.
- Fluxo visual local da SHEIN aprovado: configuração, rascunho, salvamento, operações, conversor e responsividade.
- `cargo check` aprovado após sincronizar a versão 0.21.2; `git diff --check` sem erros.
- Testes cobrem respostas vazias, erro de autenticação, moeda errada, URLs inválidas, preço inválido, duplicação, respostas atrasadas de outro termo, duas páginas, limite de espera e liberação do observador.
- Os provedores dos outros marketplaces, as pausas e a publicação em Telegram/WhatsApp não foram alterados nesta correção.
- Nenhum navegador garante ausência permanente de verificações. O painel ainda depende da conta autenticada e pode mudar de estrutura ou restringir o acesso. Falhas continuam sendo informadas e isoladas da coleta das outras fontes.
- Não foi adicionada uma reserva de ofertas: os produtos continuam sendo coletados por ciclo. Essa mudança de estratégia é separada desta correção.
- Nenhum instalador, release remoto, commit ou push foi gerado.
