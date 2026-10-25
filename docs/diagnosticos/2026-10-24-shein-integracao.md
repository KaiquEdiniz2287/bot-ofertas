# SHEIN — validação da integração

Data: 24/10/2026. Nenhuma publicação foi enviada durante estes testes.

## Fluxo confirmado

- Página oficial: `https://m.shein.com/br/affiliate/convert-link`.
- O botão Confirmar gera uma chamada a `/br/affiliate/api/share/link/from/url`; a resposta de sucesso contém `info.oneLink`.
- O próprio painel consulta `/br/affiliate/api/goods/recommend/detailNew`, que fornece nome, preços, imagem original, avaliação e vendas. O módulo observa essas respostas produzidas pelo formulário, sem reproduzir chamadas autenticadas fora do navegador.
- Coleta: `https://br.shein.com/super-deals`; pesquisa: `/pdsearch/{termo}/`.
- Identificados dois modelos de cartões: `.product-card` e `.bs-product-card`.

## Evidência real

1. Sem sessão, HTTP, Chrome oculto e CloakBrowser encontraram verificação da SHEIN.
2. O usuário preparou manualmente o login em `data/shein_profile`, separado do ML e do Chrome pessoal.
3. Com o perfil salvo, o módulo coletou dez ofertas sem janela, usando CloakBrowser após o bloqueio do Chrome.
4. A pesquisa “camiseta masculina” retornou cinco produtos com nome, preço e imagem, também pelo CloakBrowser.
5. O conversor, pelo Chrome oculto, gerou um link real para o produto SHEGLAM de ID público 11139230, com preço de R$ 21,95, preço anterior de R$ 31,95, imagem, avaliação 4,89 e 1,4 mil+ vendas informadas pelo painel.
6. A busca manual completa retornou três camisetas com links afiliados reais e texto formatado, sem publicar ou registrar no histórico.
7. Uma coleta posterior encontrou nova verificação nos dois navegadores e foi encerrada com orientação de login. Os sucessos não comprovam disponibilidade permanente.

## Isolamento e limites

- Nenhum código dos provedores Mercado Livre, Amazon, Shopee ou AliExpress foi alterado nesta integração.
- O novo provedor usa perfil e bloqueio próprios. A sessão passada ao CloakBrowser fica apenas em memória.
- Não há resolução automática de CAPTCHA, abertura visível durante consultas nem download do CloakBrowser dentro do ciclo.
- A fonte começa desativada. Categorias e filtros gerais continuam válidos; até dois termos são consultados por ciclo, em rodízio.
- A conversão não permite assumir comissão de produto inelegível: só usa link retornado com sucesso pelo conversor oficial.
- O preço estimado da vitrine pode diferir do preço fornecido pelo conversor. Os valores retornados na conversão substituem os valores antigos ao preparar o post.
- O funcionamento autenticado foi testado com a conta do usuário e pode exigir renovação manual quando a SHEIN invalidar a sessão.

## Revisão posterior — indicadores, seleção de fontes e histórico

- O backend já informava `sheinSessionDetected`, mas o botão de login não aplicava `completed`, o selo de pronto ou o visto verde. Essa apresentação foi corrigida na versão 0.21.0; o selo indica perfil local salvo, não uma sessão permanentemente válida.
- O diretório de logs estava vazio e não havia processo do aplicativo em execução no momento da revisão. Portanto, não foi possível recuperar o Console anterior nem afirmar que todas as consultas ocorreram sem bloqueios.
- Inspeção somente leitura de `data/ofertas.db`: uma publicação da SHEIN registrada em 24/10/2026 às 17:32:34, com a respectiva entrega de WhatsApp marcada como `sent` e sem erro.
- As 18 entregas mais recentes inspecionadas estavam marcadas como `sent`, com `ultimo_erro` vazio. Os últimos três registros eram Mercado Livre, AliExpress e Shopee, na faixa de 21:11 a 21:18.
- Os horários acima são os gravados pelo aplicativo no banco local. O histórico comprova o estado registrado das publicações e entregas, não substitui os logs completos de coleta.

## Correção 0.21.1 — CloakBrowser primeiro e espera por dados completos

### Reprodução

O erro de dados ausentes foi reproduzido com a sessão salva do usuário, copiada para um diretório temporário para não concorrer com o aplicativo aberto. A SHEIN retornou HTTP 200 e mostrou inicialmente 12 cartões de vitrine, com nome e preço, mas links `javascript:void(0)`. O coletor antigo esperava apenas pela classe `.product-card` e encerrava a leitura nesse ponto.

No teste comparativo, o contexto efêmero do CloakBrowser continuou sem ofertas utilizáveis durante as quatro leituras iniciais (aproximadamente 4,5 segundos). No contexto persistente, a página completou o carregamento e mostrou 42 produtos válidos. Ao fechar e reabrir o mesmo perfil, retornou 48 produtos válidos. Isso confirma o erro da leitura prematura; não demonstra que todo bloqueio era causado pelo modo efêmero.

### Alteração restrita à SHEIN

- Coleta e pesquisa: CloakBrowser persistente primeiro, Chrome oculto como alternativa.
- Conversão: Chrome oculto primeiro, preservando o fluxo que funcionou; CloakBrowser persistente como alternativa.
- Novo perfil exclusivo: `data/shein_coleta_profile`. A versão validada do navegador continua `146.0.7680.177.5`; nenhum binário ou dependência foi atualizado.
- A sessão da SHEIN é importada na primeira preparação, sem consultar o site pelo Chrome, e renovada após o login manual. A marcação local `.bot-login` permite sincronizar a conta sem sobrescrever os dados do CloakBrowser em todas as consultas.
- Espera limitada por produtos com nome, preço e link válidos, até 20 segundos, em vez de apenas esperar o esqueleto do cartão. O intervalo consulta o DOM local, sem recarregar a página repetidamente.
- Verificações reais continuam sendo identificadas. Não há resolução de CAPTCHA, abertura visível durante coleta ou garantia de ausência de bloqueios futuros.

### Resultado real da correção

Todos os testes abaixo usaram cópia isolada do perfil da SHEIN, sem interferir no app aberto e sem publicar ou registrar ofertas no histórico:

| Teste | Resultado | Duração aproximada |
|---|---|---|
| Primeira coleta | 10 ofertas com preço e imagem | 16,9 s |
| Reabrir o perfil e coletar novamente | 10 ofertas com preço e imagem | 7,8 s |
| Pesquisa “camiseta masculina” com conversão | 3 produtos com imagem e links afiliados reais | 24,5 s |
| Conversão avulsa de SHEGLAM | Link afiliado, título, imagem e preços de R$ 21,95 / R$ 31,95 | 7,7 s |

A persistência usa a API documentada do navegador: [CloakBrowser](https://github.com/CloakHQ/CloakBrowser). Os resultados acima são evidência local desta execução, não uma garantia do fornecedor.

### Regressão e empacotamento

- 148 testes Python e 30 testes da interface aprovados.
- Verificações de navegador local aprovadas para configurações/SHEIN, conversor e histórico/pesquisa/exportação SendAi, com UTF-8 e responsividade.
- Backend 0.21.1 empacotado em diretório temporário; protocolo, carregamento do módulo, validação de perfil ausente e encerramento aprovados.
- A checagem nativa em debug encontrou um executável em uso pelo aplicativo (Windows, erro 32). A checagem alternativa `cargo check --release` passou, sem encerrar o aplicativo.
- Nenhum instalador, release remoto ou publicação de oferta foi gerado nesta correção.
