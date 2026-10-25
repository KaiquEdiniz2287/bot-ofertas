# 0.21.2 — Consulta da SHEIN pelo catálogo de afiliados

- A coleta automática e a pesquisa da SHEIN passam a usar o catálogo do painel de afiliados, cujo acesso funcionou nos testes em que a busca pública exigia verificação.
- Reutilizado o perfil salvo do Chrome em segundo plano, com CloakBrowser persistente como alternativa; nenhum navegador novo precisa ser instalado.
- Preservados os termos das categorias, o rodízio e os filtros existentes. Cada consulta aproveita até duas páginas do painel, com espera limitada e identificação do termo no Console.
- Preços, imagens, avaliações e vendas são lidos dos produtos do catálogo. Comissão e bônus não são confundidos com preço ou desconto; recomendações sem correspondência com a pesquisa são descartadas.
- A geração de links continua pelo conversor oficial, e o login passa a abrir também o catálogo usado na coleta.
- Validadas consultas reais com os dois navegadores, reabertura do perfil, categorias, resultados vazios e quatro links afiliados, sem publicar ofertas.

## Versionamento

Versão: 0.21.1 → 0.21.2
Tipo: PATCH
Motivo: correção compatível da consulta da SHEIN, mantendo os demais marketplaces e o fluxo de publicação.

---

# 0.21.1 — Coleta estável da SHEIN em segundo plano

- A coleta e a pesquisa da SHEIN passam a começar pelo CloakBrowser sem janela, com perfil persistente próprio; o Chrome oculto permanece como alternativa.
- Corrigida a leitura prematura da vitrine: cartões iniciais sem link não encerram mais a consulta antes de os produtos completos carregarem. A espera é limitada a 20 segundos, sem novas requisições de página durante a leitura.
- O perfil do CloakBrowser preserva os dados entre consultas e sincroniza a sessão da SHEIN após um novo login, em vez de descartá-la a cada tentativa.
- Mantida a conversão de links pelo Chrome sem janela como primeira opção, com recuperação pelo CloakBrowser persistente.
- Melhoradas as mensagens para distinguir carregamento incompleto, verificação da SHEIN e falha do navegador; removido o texto de navegação do rótulo usado como título em alguns cartões.
- Validados dois acessos consecutivos às ofertas, busca com três links afiliados reais e conversão avulsa, em perfil isolado e sem publicar mensagens.

## Versionamento

Versão: 0.21.0 → 0.21.1
Tipo: PATCH
Motivo: correção compatível da sessão e do carregamento de dados da SHEIN.

---

# 0.21.0 — Seleção de marketplaces e configurações organizadas

- Mercado Livre, Amazon, Shopee e AliExpress ganharam subblocos próprios no bloco 02 das configurações, com credenciais e interruptores de ativação.
- A seleção é salva para o ciclo automático e a busca manual, preservando chaves, sessões, categorias e demais parâmetros; a SHEIN continua em seu bloco separado.
- Rascunhos dos interruptores são preservados durante atualizações do app e ao executar ações de preparação.
- Corrigido o visto verde de perfil salvo no login da SHEIN em Operação e Configurações, mantendo a distinção entre perfil local e acesso validado por teste.
- Consultas bem-sucedidas de mensagens do Telegram passaram a usar uma descrição familiar no Console. Falhas e outras requisições continuam visíveis.
- Reativar uma fonte após iniciar o bot com todas desligadas agenda o primeiro ciclo sem alterar pausas existentes nem criar ciclos concorrentes.

## Versionamento

Versão: 0.20.0 → 0.21.0
Tipo: MINOR
Motivo: adição compatível de controles individuais de ativação de marketplaces na interface.

---

# 0.20.0 — Integração de afiliados da SHEIN

- Adicionado módulo independente para coleta de Super Ofertas, pesquisa por produto e conversão de links da SHEIN.
- Login local exclusivo em Operação, com sessão separada do Mercado Livre; não exige App Key nem cópia manual de cookies.
- Consultas e conversões tentam Chrome sem janela e usam CloakBrowser como alternativa. Somente a preparação de login solicitada pelo usuário abre janela.
- Nova opção nas configurações inclui a SHEIN no ciclo e na busca manual; permanece desativada até ser habilitada pelo usuário.
- Categorias e filtros existentes também se aplicam à SHEIN. Links são gerados apenas para as ofertas escolhidas ou os melhores resultados da busca.
- A conversão usa o retorno oficial para obter link afiliado, nome, imagem, preços, avaliação e vendas disponíveis.
- Bloqueios e sessões expiradas geram orientação no Console; falhas da SHEIN não interrompem as demais plataformas.
- Adicionados teste isolado, identificação visual, suporte no conversor do aplicativo e nos comandos de terminal.

## Versionamento

Versão: 0.19.1 → 0.20.0
Tipo: MINOR
Motivo: adição compatível de uma nova plataforma de afiliados.

---

# 0.19.1 — Dados do produto do Mercado Livre no conversor

- Quando o acesso simples não retorna nome, preço ou imagem, o conversor consulta o produto com CloakBrowser sem abrir janela.
- Páginas de verificação deixam de ser tratadas como páginas de produto; links compartilhados com redirecionamento tardio recebem uma tentativa limitada de recuperação da leitura.
- Preservados os centavos dos preços atual e anterior na extração dos valores visíveis.
- Se os dados continuarem indisponíveis, o link afiliado permanece disponível e os avisos também aparecem no Console.
- Linkbuilder, coleta automática, pesquisa e demais plataformas mantêm seus fluxos existentes.
- Validada a leitura real do produto informado e a montagem do texto em perfil temporário, sem publicar ou acessar a sessão ativa do Linkbuilder.

## Versionamento

Versão: 0.19.0 → 0.19.1
Tipo: PATCH
Motivo: correção compatível da coleta de dados na conversão de links do Mercado Livre.

---

# 0.19.0 — Conversor de links no aplicativo

- Nova aba Converter link para Mercado Livre, Shopee, Amazon e AliExpress, com identificação automática da plataforma.
- Usa as credenciais de afiliado já salvas e oferece cópia do link e da oferta formatada quando os detalhes estão disponíveis.
- Conversões avulsas funcionam com o bot ativo, sem publicar mensagens nem registrar ofertas no histórico.
- Acesso ao perfil do Mercado Livre coordenado com o Linkbuilder; conversões duplicadas são bloqueadas enquanto uma está em andamento.
- Mensagens claras para links inválidos, configuração incompleta, falhas e detalhes indisponíveis.
- O campo preserva texto e foco durante atualizações do aplicativo; a tela se adapta às larguras menores.

## Versionamento

Versão: 0.18.6 → 0.19.0
Tipo: MINOR
Motivo: adição compatível de uma nova aba de conversão avulsa.

---

# 0.18.6 — CloakBrowser exclusivo para coleta de ofertas do Mercado Livre

- Após a tentativa de acesso público, a coleta usa o CloakBrowser sem janela, com perfil separado do login e do Linkbuilder.
- O botão Instalar navegador prepara Chromium e CloakBrowser; o download do novo navegador ocorre diretamente do fornecedor, fora do instalador e do ciclo de ofertas.
- Se a coleta pelo CloakBrowser falhar ou ele ainda não estiver instalado, permanece a recuperação pelo navegador padrão.
- A pesquisa manual, a geração de links afiliados e as demais plataformas mantêm o comportamento anterior.
- Adicionados testes de isolamento, parâmetros de categoria e paginação, encerramento do navegador, instalação e recuperação de falhas.

## Versionamento

Versão: 0.18.5 → 0.18.6
Tipo: PATCH
Motivo: melhoria compatível no navegador usado internamente pela coleta existente.

---

# 0.18.5 — Coleta do Mercado Livre tenta primeiro em segundo plano

- A coleta de ofertas volta a tentar o Chrome sem janela com o perfil salvo, depois da tentativa pública já existente.
- Se o acesso em segundo plano for bloqueado ou redirecionado à verificação da conta, o contexto é fechado antes de uma única tentativa com Chrome visível.
- Se a coleta oculta funcionar, nenhuma janela é aberta. Timeout e indisponibilidade do servidor não acionam a tentativa visível.
- O console informa quando há necessidade de abrir a janela. A geração de links permanece escondida e a pesquisa manual mantém seu comportamento anterior.
- Testes cobrem sucesso oculto, bloqueio com alternativa visível, encerramento dos contextos e falha nos dois modos sem repetição ilimitada.

## Versionamento

Versão: 0.18.4 → 0.18.5
Tipo: PATCH
Motivo: ajuste compatível para abrir a janela da coleta somente quando houver bloqueio no modo oculto.

---

# 0.18.4 — Linkbuilder do Mercado Livre em segundo plano

- A geração de links afiliados do Mercado Livre volta a funcionar sem janela visível, usando o perfil já salvo.
- Os links continuam sendo gerados em lotes, no mesmo contexto, sem abrir um navegador para cada postagem.
- A coleta de ofertas e a pesquisa de produtos mantêm o Chrome visível, preservando o modo que funcionou na validação local.
- Ajustado o teste de regressão para conferir três links em um único contexto sem janela.

## Versionamento

Versão: 0.18.3 → 0.18.4
Tipo: PATCH
Motivo: correção compatível para limitar as janelas visíveis às consultas de produtos do Mercado Livre.

---

# 0.18.3 — Acesso do Mercado Livre pelo Chrome visível

- A coleta de ofertas, a pesquisa manual e a geração de links do Mercado Livre passam a usar o Chrome visível com o perfil salvo. Na verificação local, o modo sem janela recebia `/captcha/wall/logged`, enquanto o modo visível retornava 48 produtos com o mesmo perfil.
- A janela do navegador abre durante a operação e fecha ao concluir; o console informa esse comportamento.
- O login abre o Linkbuilder e a página de ofertas para conferência manual. Ao fechar, a mensagem informa que o perfil foi salvo e orienta executar o teste, sem afirmar que o acesso já foi validado.
- Validação real: 48 ofertas coletadas e um link de afiliado gerado pelo Linkbuilder. Novas verificações exigidas pelo site continuam dependendo da conclusão manual pelo usuário.
- As integrações Amazon, Shopee, AliExpress, Telegram e WhatsApp permanecem inalteradas.

## Versionamento

Versão: 0.18.2 → 0.18.3
Tipo: PATCH
Motivo: correção compatível do modo de acesso ao Mercado Livre usando o perfil existente.

---

# 0.18.2 — Correção do empacotamento de release

- Restauradas as versões corretas de `gobject-sys`, `gdk-pixbuf-sys` e `pango-sys` no Cargo.lock. Essas dependências haviam sido alteradas indevidamente junto da versão do aplicativo, impedindo a resolução pelo Cargo.
- O build para imediatamente quando testes Python, da interface ou Rust falham, informando a etapa e o código de erro original.
- Falhas de preparação ou empacotamento do backend interrompem o processo antes de reutilizar um executável antigo.
- Os testes Rust e o build Tauri usam `--locked`, preservando as versões de dependências registradas no projeto.
- Os scripts PowerShell alterados usam UTF-8 com BOM e executam o Python em UTF-8 para preservar os diagnósticos com acentos.

## Versionamento

Versão: 0.18.1 → 0.18.2
Tipo: PATCH
Motivo: correção compatível das dependências e da interrupção de falhas no release.

---

# 0.18.1 — Consulta e diagnóstico da Creators API da Amazon

- Corrigido o retorno imediato de zero ofertas ao usar credenciais da Amazon sem categorias ou termos configurados. Esse modo agora executa uma busca geral por ofertas em todas as categorias.
- Configurações existentes de categorias, termos e desconto permanecem respeitadas; o número de páginas da API fica entre 1 e 10.
- Recusas do catálogo, incluindo `AssociateNotEligible`, são identificadas pelo motivo retornado pela Amazon; o console explica a restrição e a tentativa alternativa pelo site.
- Erros declarados pela API em respostas HTTP 200 deixam de aparecer como simples ausência de produtos.
- Verificação real: autenticação aceita (HTTP 200), catálogo recusado por elegibilidade (HTTP 403) e 48 ofertas obtidas pela busca alternativa no site. Credenciais e dados da instalação não foram alterados.

## Versionamento

Versão: 0.18.0 → 0.18.1
Tipo: PATCH
Motivo: correção compatível da consulta geral e dos diagnósticos da Amazon.

---

# 0.18.0 — Exportação de ofertas para o SendAiPlus

- Adicionado o botão **Exportar SendAi** em cada oferta do Histórico e em cada resultado da busca de produtos.
- O botão fica disponível quando o SendAiPlus atualizado está aberto no mesmo computador e usuário, inclusive na bandeja.
- A oferta cria um post ativo **Texto com link**, com o nome do produto, sem título opcional e com o texto formatado completo, preservando links, acentos e emojis.
- O sucesso só é informado após a confirmação de salvamento. Cliques repetidos e novas tentativas na mesma sessão não duplicam o post.
- A integração não publica mensagens, não seleciona posts no respondedor e não altera pesquisa, ciclos ou envios existentes.
- Requer SendAiPlus 0.12.0 ou superior.

## Versionamento

Versão: 0.17.2 → 0.18.0
Tipo: MINOR
Motivo: nova integração local e compatível para exportar ofertas.

---

# 0.17.2 — Diagnósticos reais na busca de produtos

- A busca manual identifica o bloqueio `/captcha/wall/logged` do Mercado Livre e orienta a concluir a verificação no navegador, sem confundi-lo com ausência de produtos.
- O bloqueio temporário da Amazon agora aparece como tal na busca manual, mesmo quando o site responde HTTP 200; o ciclo automático mantém o comportamento anterior.
- Uma falha transitória de rede ou DNS no AliExpress recebe uma nova tentativa antes de exibir uma mensagem clara. A consulta de teste com `fone blue` retornou produtos após a rede voltar.
- Nenhuma verificação de segurança é contornada automaticamente; pesquisas e publicações das demais plataformas permanecem inalteradas.

## Versionamento

Versão: 0.17.1 → 0.17.2
Tipo: PATCH
Motivo: correção compatível dos diagnósticos e de falhas transitórias na busca manual.

---

# 0.17.1 — Busca manual de produtos mais confiável

- Buscas longas que não retornam itens tentam novamente com as palavras principais em Mercado Livre, Shopee, Amazon e AliExpress.
- A resposta de resultado vazio do AliExpress deixa de impedir essa segunda tentativa; erros reais de API continuam visíveis.
- A busca do Mercado Livre usa a URL de pesquisa adequada e distingue bloqueio, falha de carregamento e página sem produtos de uma busca válida.
- Se o AliExpress não conseguir encurtar um link, a busca preserva o link afiliado já fornecido pela API.
- O ciclo automático, as publicações e as demais integrações permanecem inalterados.

## Versionamento

Versão: 0.17.0 → 0.17.1
Tipo: PATCH
Motivo: correção compatível da busca manual e de seus diagnósticos.

---

# 0.17.0 — Histórico com cópia e atualização automática

- Cada produto do Histórico agora tem um botão **Copiar** para compartilhar o texto da oferta.
- Novas publicações guardam o texto completo, com preço, desconto, plataforma e link afiliado.
- Registros antigos usam os dados completos ainda disponíveis; quando o link não foi armazenado, o texto copiado contém apenas os dados preservados, sem criar um link incorreto.
- Enquanto a aba Histórico está aberta, a lista consulta novas publicações automaticamente a cada três segundos, sem recarregar a página.
- Busca, publicação, Telegram e WhatsApp não foram alterados.

## Versionamento

Versão: 0.16.2 → 0.17.0
Tipo: MINOR
Motivo: adição compatível de cópia e atualização automática ao Histórico.

---

# 0.16.2 — Reenvio correto de ofertas antigas ao WhatsApp

- Corrigido o bloqueio de ofertas republicadas: o WhatsApp considerava uma entrega antiga como definitiva, mesmo após o prazo de repetição configurado para o Telegram.
- Após esse prazo, um novo ciclo pode enviar novamente a oferta ao grupo e ao Canal ativos, mantendo o intervalo entre os dois destinos.
- Entregas recentes continuam protegidas contra duplicatas; falhas pendentes continuam sem reenvio automático.

## Versionamento

Versão: 0.16.1 → 0.16.2
Tipo: PATCH
Motivo: correção compatível da deduplicação de entregas do WhatsApp.

---

# 0.16.1 — Reconexão do WhatsApp após falha de rede

- Corrigido o caso em que uma queda de DNS esgotava as cinco tentativas de reconexão antes de a internet voltar, deixando o WhatsApp permanentemente à espera de um clique manual.
- Erros de rede ou DNS agora colocam a conexão em espera, com verificação a cada 30 segundos; essas verificações não consomem as cinco tentativas.
- A tela do WhatsApp e o Console distinguem “aguardando rede” de uma tentativa de reconexão; avisos idênticos não são repetidos a cada verificação.
- Sessão realmente removida continua exigindo novo QR Code. Envios pendentes continuam exclusivamente manuais, sem reenvio automático.
- Os fluxos de Telegram, Amazon e Mercado Livre não foram alterados.

## Versionamento

Versão: 0.16.0 → 0.16.1
Tipo: PATCH
Motivo: correção compatível da reconexão após indisponibilidade temporária de rede.

---

# 0.16.0 — Pausas variáveis entre ofertas e ciclos

- Cada pausa entre ofertas de um mesmo ciclo agora é sorteada independentemente entre 2 e 5 minutos, com precisão de segundos.
- Ao terminar um ciclo automático, o próximo é agendado após uma pausa sorteada entre 40 e 60 minutos, também com precisão de segundos.
- A Visão geral e o Console mostram as faixas, o tempo efetivamente sorteado e a contagem regressiva.
- O primeiro ciclo após iniciar o bot, o ciclo manual e o intervalo de cinco segundos entre grupo e Canal permanecem como antes.
- Configurações antigas continuam compatíveis; valores zero nas opções legadas continuam desativando o ciclo automático ou a pausa entre ofertas.

## Versionamento

Versão: 0.15.1 → 0.16.0
Tipo: MINOR
Motivo: nova política de agendamento compatível, com visibilidade dos tempos no aplicativo.

---

# 0.15.1 — Prévia estável no Canal do WhatsApp

- A miniatura incorporada nas prévias do Canal passou de 300 px com JPEG de qualidade 65 para até 512 px com qualidade 85, sem ampliar artificialmente imagens menores.
- O Canal não anexa mais a mídia HD ao cartão: dois testes reais confirmaram que ela ficava borrada ou preta no WhatsApp móvel, inclusive com o caminho de upload específico dos Canais.
- A imagem do produto permanece incorporada em JPEG no próprio cartão, com título, descrição e link; sua resolução foi aumentada para reduzir a perda de nitidez.
- O envio ao grupo e o modo de foto completa com legenda permanecem inalterados.
- O terceiro teste confirmou a foto visível em um cartão compacto no computador e no celular. O tamanho do cartão ainda é controlado pelo cliente WhatsApp, não pelo aplicativo.

## Versionamento

Versão: 0.15.0 → 0.15.1
Tipo: PATCH
Motivo: correção compatível da imagem preta no WhatsApp móvel, preservando um cartão de prévia legível no Canal.

---

# 0.15.0 — Operação organizada e testes em sequência

- A tela Operação separa os testes das quatro plataformas das ferramentas de preparação do ambiente.
- O botão **Testar todas em sequência** executa Mercado Livre, Shopee, Amazon e AliExpress, aguardando cada teste terminar antes do próximo.
- Uma falha individual não impede os testes seguintes; o resumo final mostra quais plataformas falharam.
- Login do Mercado Livre e instalação do navegador continuam disponíveis em um bloco próprio, fora da sequência automática.
- Os comandos de teste, os indicadores da sessão e os fluxos de publicação permanecem inalterados.

## Versionamento

Versão: 0.14.1 → 0.15.0
Tipo: MINOR
Motivo: adição compatível de uma ação sequencial de teste e reorganização visual da tela Operação.

---

# 0.14.1 — Acesso às ofertas do Mercado Livre

- Corrigido o falso resultado de zero ofertas quando o Mercado Livre redireciona a busca para verificação de conta.
- Se o acesso público falhar ou expirar, a busca tenta a sessão do Mercado Livre já salva no navegador do aplicativo.
- Caso o site também bloqueie essa sessão, o teste informa que é preciso revalidar a conta, sem esconder a falha como ausência de produtos.
- Timeouts da página passam a gerar uma mensagem clara, sem traceback no console do aplicativo.
- As demais fontes e a geração dos links de afiliado não foram alteradas.

## Versionamento

Versão: 0.14.0 → 0.14.1
Tipo: PATCH
Motivo: correção compatível da coleta e do diagnóstico de acesso às ofertas do Mercado Livre.

---

# 0.14.0 — Aplicativo dedicado às ofertas

- Removidos a aba e os comandos do respondedor automático de mensagens em grupos.
- Retirados o recebimento de mensagens para respostas, a fila, as regras e a inicialização automática do respondedor.
- O WhatsApp continua conectado para publicar ofertas no grupo e no Canal, testar destinos e administrar pendências; Telegram, busca e demais marketplaces não foram alterados.
- Cadastros e mídias antigos do respondedor permanecem nos dados locais, sem serem carregados ou executados pelo aplicativo. Nenhum dado pessoal foi apagado.

## Versionamento

Versão: 0.13.2 → 0.14.0
Tipo: MINOR (série 0.x)
Motivo: mudança de escopo do produto solicitada pelo usuário, mantendo o fluxo de ofertas e sinalizando a remoção da funcionalidade experimental.

---

# 0.13.2 — Diagnóstico claro das respostas automáticas

- O Resumo do respondedor agora mostra os pré-requisitos para responder: WhatsApp conectado, post/campanha/grupo ativos, respondedor iniciado e simulação desligada para envio real.
- O botão distingue claramente **Iniciar simulação** de **Iniciar respostas**; há acesso direto às configurações para desativar a simulação quando desejado.
- O console informa quantas automações iniciaram e quando novas mensagens de grupos entram para avaliação, sem registrar o conteúdo das conversas.
- Validado em teste isolado o fluxo de uma mensagem recebida até o transporte compartilhado e o backend Windows empacotado, incluindo texto com acentos e emoji; o envio real ainda depende de teste em grupo.
- As preferências existentes foram preservadas: nenhuma resposta em massa foi ativada automaticamente.

## Versionamento

Versão: 0.13.1 → 0.13.2
Tipo: PATCH
Motivo: melhoria compatível de diagnóstico e operação do respondedor.

---

# 0.13.1 — Respondedor mais simples e modo geral corrigido

- Corrigido o erro ao salvar **Todos os grupos** quando a interface era iniciada com componentes Python/WhatsApp de um build anterior.
- `npm start` e `npm run dev` agora atualizam os componentes locais quando o código deles muda, evitando versões incompatíveis durante o desenvolvimento.
- O formulário separa destino, proteção contra excesso e opções avançadas. Campos de regra, atraso e mídia só aparecem quando a opção correspondente está ativa.
- Valores de opções desativadas não interferem no salvamento; quando falta um post ou campanha ativa, a tela informa exatamente o que fazer e permite salvar um rascunho desativado.
- Novas automações usam por padrão intervalo de 10 minutos e limite de 10 respostas por grupo ao dia; os limites globais continuam independentes.
- O modo **Todos os grupos** aplica uma campanha sem cadastrar cada grupo. Conversas privadas e Canais continuam fora, e regras específicas ativas têm prioridade.
- Os ícones **?** explicam cada configuração ao passar o mouse ou focar pelo teclado.

## Versionamento

Versão: 0.13.0 → 0.13.1
Tipo: PATCH
Motivo: correção compatível do empacotamento local e simplificação segura das configurações do respondedor.

---

# 0.13.0 — Respostas automáticas em grupos do WhatsApp

- Nova área independente para cadastrar posts, campanhas, grupos e regras de resposta, usando a conexão WhatsApp já existente.
- Mensagens novas em grupos habilitados podem acionar respostas prontas citando a mensagem original; mensagens próprias, antigas, duplicadas e eventos de sistema são ignorados.
- Regras de intervalo, execução, dia, período, quantidade de mensagens, probabilidade, horários e atrasos; reservas e limites persistidos em um banco SQLite próprio.
- Fila e histórico mostram respostas enviadas, simuladas, ignoradas, canceladas ou com confirmação incerta. O simulador nunca envia mensagens.
- Por padrão, o respondedor inicia desligado, sem grupos ativos, em modo de simulação e sem inicialização automática.
- Configuração pode ser exportada/importada em JSON; há backup e restauração do banco com desativação preventiva dos grupos após restaurar.
- O console ganhou filtros por Ofertas, Respostas e Conexão. Uma queda de conexão cancela respostas aguardando, sem reenviá-las automaticamente.
- Corrigida a leitura UTF-8 do protocolo no backend empacotado para preservar acentos, pontuação e emojis nos cadastros e nas respostas no Windows.
- O envio de ofertas conserva prioridade no transporte compartilhado; o fluxo existente do Telegram, marketplaces, grupo e Canal não foi alterado.

## Versionamento

Versão: 0.12.1 → 0.13.0
Tipo: MINOR
Motivo: adição compatível de uma nova automação de respostas prontas em grupos.

---

# 0.12.1 — Reconexão preservada após falha de envio

- Corrigida a falha que encerrava o componente do WhatsApp quando a conexão caía antes de terminar um envio, impedindo as tentativas de reconexão automática.
- O envio e a confirmação do WhatsApp agora são acompanhados simultaneamente, tratando também recusas antecipadas e tempo de confirmação esgotado.
- O fallback de prévia só repete um envio após recusa explícita e com a conexão ainda ativa; quedas e confirmações incertas deixam a oferta pendente para ação manual.
- Testes de marketplace sem resultados deixam de informar sucesso indevidamente. O aviso de indisponibilidade da Amazon esclarece que as demais plataformas continuam funcionando.
- Tratado o falso aviso do ApplicationBuilder do Telegram causado pela comparação de caminhos no executável empacotado, preservando os demais avisos.
- Incluídos testes de queda durante o envio para grupo e Canal e autoteste de desconexão no componente empacotado.

## Versionamento

Versão: 0.12.0 → 0.12.1
Tipo: PATCH
Motivo: correção compatível do tratamento de falhas de envio e da clareza dos diagnósticos.

---

# 0.12.0 — Mais resultados e conexão automática do WhatsApp

- O garimpador manual agora retorna até três dos melhores produtos de cada marketplace ativo.
- Os resultados são ordenados por relevância, desconto e disponibilidade do link afiliado, sem repetir o mesmo produto.
- Cada resultado continua trazendo imagem, preço, avaliação, texto formatado e botões individuais para copiar ou abrir a oferta.
- A pesquisa permanece independente do ciclo automático e pode chegar a doze resultados quando as quatro plataformas responderem.
- Quando a integração estiver ativa, o aplicativo tenta restaurar a conexão do WhatsApp automaticamente ao abrir.
- A conexão automática não liga o bot, não publica ofertas e não reenvia pendências.
- Se a sessão tiver sido removida, o aplicativo exibe o QR Code; se a tentativa falhar, o botão manual continua disponível.
- O comando `npm run release` agora prepara automaticamente um rascunho da GitHub Release, com tag e título correspondentes à versão atual.
- A descrição do rascunho é gerada em UTF-8 com as alterações registradas desde a última execução, considerando releases publicadas e rascunhos anteriores.
- O instalador, a assinatura e o `latest.json` continuam sendo gerados localmente para que sejam anexados e publicados manualmente.
- O rascunho pode ser preparado antes do commit; o código correspondente precisa ser commitado e enviado somente antes da publicação definitiva.

## Versionamento

Versão: 0.11.1 → 0.12.0
Tipo: MINOR
Motivo: ampliação funcional do buscador e conexão automática do WhatsApp na abertura do aplicativo.

---

# 0.11.1 — Entrega sincronizada entre grupo e Canal

- Corrigido o caso em que uma oferta antiga, já registrada no grupo, era publicada somente no Canal recém-ativado.
- As entregas do WhatsApp agora são preparadas de forma atômica para todos os destinos ativos.
- Uma oferta nova continua sendo enviada primeiro ao grupo e, após cinco segundos, ao Canal.
- Ofertas já conhecidas não geram publicações retroativas isoladas em apenas um destino.
- O envio manual das pendências existentes e as demais integrações permanecem inalterados.

## Versionamento

Versão: 0.11.0 → 0.11.1
Tipo: PATCH
Motivo: correção compatível da sincronização das entregas entre grupo e Canal do WhatsApp.

---

# 0.11.0 — Publicação em Canais do WhatsApp

- Adicionado suporte a Canais do WhatsApp nos quais o número conectado seja administrador ou proprietário.
- Grupo e Canal podem receber a mesma oferta no mesmo ciclo, com texto e prévia idênticos.
- Quando os dois destinos estão ativos, o Canal aguarda cinco segundos após o envio ao grupo.
- O Canal pode ser configurado pelo link público ou pelo identificador `@newsletter` e precisa ser validado antes de salvar.
- Entregas, confirmações e pendências são controladas separadamente para grupo e Canal.
- Nomes de grupos e Canais passam por normalização Unicode, preservando emojis, acentos e caracteres especiais.
- O fluxo já existente do grupo, incluindo prévias, confirmação de entrega e reenvio manual, permanece compatível.

## Versionamento

Versão: 0.10.4 → 0.11.0
Tipo: MINOR
Motivo: adição compatível de um novo destino de publicação no WhatsApp.

---

# 0.10.4 — Foto principal nas prévias da Amazon

- Corrigida a prévia da Amazon que podia exibir apenas a logomarca da plataforma.
- Ofertas da Amazon agora usam diretamente a imagem principal do produto ao montar a prévia do WhatsApp.
- A prévia mantém o título, o texto completo e o link afiliado da oferta.
- Mercado Livre, Shopee e AliExpress continuam usando o fluxo de prévia já existente.

## Versionamento

Versão: 0.10.3 → 0.10.4
Tipo: PATCH
Motivo: correção compatível da imagem selecionada para as prévias da Amazon.

---

# 0.10.3 — Organização dos cartões da Visão geral

- Os três indicadores principais agora ocupam a largura disponível em colunas iguais.
- O diretório de dados passou a ocupar uma linha completa, eliminando o espaço vazio à direita.
- A barra compacta de tempos foi alinhada em três colunas uniformes.
- O layout continua se reorganizando em duas colunas e depois em uma coluna em janelas menores.

## Versionamento

Versão: 0.10.2 → 0.10.3
Tipo: PATCH
Motivo: correção visual compatível da distribuição dos blocos na Visão geral.

---

# 0.10.2 — Visão geral sem indicadores repetidos

- Removidos da barra da Visão geral os indicadores repetidos de próximo ciclo e conexão do WhatsApp.
- Removido o cartão repetido do WhatsApp na mesma tela.
- O próximo ciclo continua visível no cartão principal, e o status do WhatsApp permanece no painel superior.
- A barra completa de temporizadores do Console permanece inalterada.

## Versionamento

Versão: 0.10.1 → 0.10.2
Tipo: PATCH
Motivo: pequeno ajuste visual compatível na organização da Visão geral.

---

# 0.10.1 — Imagem correta nas ofertas da Amazon

- Corrigida a prévia branca exibida nas ofertas da Amazon no WhatsApp.
- Pixels de rastreamento informados pela página da Amazon deixam de ser aceitos como imagem do produto.
- Quando a prévia da Amazon fornece uma imagem inválida, o aplicativo usa automaticamente a foto principal real da oferta.
- O envio das demais plataformas e o modo tradicional com imagem permanecem inalterados.

## Versionamento

Versão: 0.10.0 → 0.10.1
Tipo: PATCH
Motivo: correção compatível da imagem usada na prévia das ofertas da Amazon.

---

# 0.10.0 — Seleção de categorias no aplicativo

- Restaurado o seletor de categorias na tela de Configurações do aplicativo desktop.
- Mantido o catálogo já existente: tecnologia, celulares, games, casa, eletrodomésticos, moda, beleza, esporte, saúde, brinquedos e bebês, pet, automotivo e livros.
- É possível selecionar vários nichos; deixar todos desmarcados mantém a pesquisa em todas as categorias.
- A seleção é salva localmente e passa a valer no próximo ciclo, sem interromper o bot.
- O fluxo existente de pesquisa e publicação de cada marketplace permanece inalterado.

## Versionamento

Versão: 0.9.3 → 0.10.0
Tipo: MINOR
Motivo: restauração de uma funcionalidade de seleção no aplicativo desktop.

---

# 0.9.3 — Imagens WebP nas prévias do WhatsApp

- Corrigido o envio de prévias de ofertas do Mercado Livre e do AliExpress, cujas imagens são fornecidas em WebP.
- O componente do WhatsApp agora converte JPEG, PNG, WebP e AVIF para JPEG antes de montar a prévia.
- A validação foi realizada com dez imagens reais de cada marketplace: Shopee, AliExpress, Amazon e Mercado Livre.
- O modo tradicional de envio com imagem e legenda permanece inalterado.

## Versionamento

Versão: 0.9.2 → 0.9.3
Tipo: PATCH
Motivo: correção compatível do processamento de imagens nas prévias do WhatsApp.

---

# 0.9.2 — Logs seguros na conexão do WhatsApp

- Corrigido o excesso de avisos exibido ao conectar uma sessão existente do WhatsApp.
- O bridge deixa de imprimir os detalhes internos das sessões criptográficas renovadas pelo `libsignal`.
- Adicionada uma segunda barreira no backend para impedir que chaves temporárias e blocos de sessão cheguem ao console ou ao arquivo de log.
- A renovação normal de uma sessão antiga passa a ser registrada uma única vez como informação, sem indicar uma falha inexistente.
- Erros operacionais reais continuam visíveis e não são ocultados pelo novo filtro.

## Versionamento

Versão: 0.9.1 → 0.9.2
Tipo: PATCH
Motivo: correção compatível de segurança e clareza nos logs da conexão do WhatsApp.

---

# 0.9.1 — Entrega confirmada e prévia resiliente no WhatsApp

- O aplicativo agora só registra uma oferta como enviada depois que o protocolo do WhatsApp confirma o recebimento.
- Corrigidos os falsos sucessos em que o bridge retornava um identificador, mas a mensagem era recusada logo depois.
- Com a foto completa desativada, o aplicativo tenta primeiro a prévia fornecida pelo link da oferta.
- Se a prévia do link falhar, o aplicativo monta um cartão expandido usando o título e a imagem principal do produto em alta qualidade.
- Uma oferta sem confirmação fica pendente para envio manual, em vez de ser marcada incorretamente como entregue.
- Avisos repetitivos de sessões criptográficas antigas deixam de poluir o console durante a conexão.
- O modo tradicional com imagem completa e legenda permanece inalterado.

## Versionamento

Versão: 0.9.0 → 0.9.1
Tipo: PATCH
Motivo: correção compatível da confirmação de entrega e da montagem de prévias do WhatsApp.

---

# 0.9.0 — Prévia de produtos no WhatsApp

- Adicionado um controle para escolher entre foto completa e prévia compacta nas ofertas do WhatsApp.
- Quando a foto completa está desligada, o WhatsApp usa o título, a descrição e a imagem fornecidos pela prévia do próprio link afiliado.
- A opção permanece ligada por padrão, preservando o comportamento das instalações atuais.
- Ofertas sem imagem continuam sendo enviadas somente como texto, sem interromper o ciclo.

## Versionamento

Versão: 0.8.5 → 0.9.0
Tipo: MINOR
Motivo: adição compatível de uma nova opção de apresentação das ofertas no WhatsApp.

---

# 0.8.5 — Ciclos resilientes e início correto com o Windows

- Ciclos automáticos que começarem alguns segundos atrasados deixam de ser descartados pelo agendador.
- Após suspensão ou atraso do computador, somente um ciclo pendente é executado, sem acumular várias publicações.
- O painel agora diferencia claramente **Bot aguardando próximo ciclo** de **Ciclo em execução**.
- O próximo horário exibido acompanha o agendamento real, evitando que o contador fique preso em **Agora**.
- Corrigida a entrada de inicialização do Windows para caminhos que contêm espaços.
- Entradas antigas sem aspas são reparadas automaticamente quando o aplicativo é aberto.

## Versionamento

Versão: 0.8.4 → 0.8.5
Tipo: PATCH
Motivo: correções compatíveis no agendamento automático e na inicialização com o Windows.

---

# 0.8.4 — Links válidos na busca do Mercado Livre

- Corrigida a pesquisa manual quando o Mercado Livre retorna um link intermediário de anúncio.
- O endereço real do produto agora é extraído antes de solicitar o link de afiliado ao Linkbuilder.
- Redirecionadores sem um destino válido são ignorados, evitando o erro `URL Invalid`.
- Amazon e as demais plataformas não foram alteradas.

## Versionamento

Versão: 0.8.3 → 0.8.4
Tipo: PATCH
Motivo: correção compatível na normalização dos links encontrados no Mercado Livre.

---

# 0.8.3 — Release sem confirmação de senha vazia

- O comando `npm run release` agora informa explicitamente ao Tauri que a chave local utiliza senha vazia.
- A assinatura do updater deixa de interromper o build pedindo que o usuário pressione Enter.
- Uma senha real fornecida por variável de ambiente continua sendo respeitada.
- A geração do instalador, da assinatura `.sig` e do `latest.json` permanece inalterada.

## Versionamento

Versão: 0.8.2 → 0.8.3
Tipo: PATCH
Motivo: correção compatível da execução não interativa do script de release.

---

# 0.8.2 — Pesquisa de produtos liberada no aplicativo

- Corrigido o bloqueio **Operação não permitida** ao pesquisar produtos pela interface desktop.
- O comando de pesquisa agora está autorizado tanto no Tauri quanto no protocolo do backend Python.
- Pesquisas demoradas passam a usar o limite estendido de operação, evitando interrupção após 60 segundos.
- Adicionado teste de regressão para manter a autorização e o tempo estendido sincronizados.

## Versionamento

Versão: 0.8.1 → 0.8.2
Tipo: PATCH
Motivo: correção compatível da autorização do comando já disponível na interface.

---

# 0.8.1 — Links curtos oficiais do AliExpress

- As ofertas escolhidas do AliExpress agora recebem um link curto oficial `s.click.aliexpress.com/e/_...` antes da publicação.
- O encurtamento usa `aliexpress.affiliate.link.generate` com o Tracking ID configurado, preservando a atribuição da comissão.
- A busca manual e a conversão de links também passam a entregar o formato curto.
- Se o AliExpress não devolver o link curto, o link afiliado anterior é preservado para não interromper a publicação.
- As demais plataformas e o ciclo de seleção das ofertas não foram alterados.

## Versionamento

Versão: 0.8.0 → 0.8.1
Tipo: PATCH
Motivo: correção compatível do formato dos links afiliados já publicados pelo AliExpress.

---

# 0.8.0 — Busca avulsa de produtos no aplicativo

- Adicionada a aba **Buscar produtos**, com pesquisa simultânea nas plataformas ativas.
- A tela retorna o melhor resultado disponível de Mercado Livre, Shopee, Amazon e AliExpress, cada um identificado pela logomarca da plataforma.
- Cada oferta exibe imagem, título, preço anterior, preço atual, desconto, avaliação e vendas quando esses dados estão disponíveis.
- O botão **Copiar oferta completa** usa o mesmo modelo formatado das publicações atuais e inclui o link de afiliado.
- A pesquisa é independente do ciclo automático: não pausa o bot, não publica mensagens, não altera a fila e não grava resultados no histórico.
- Falhas são isoladas por marketplace; uma plataforma indisponível não impede as demais de retornarem resultados.
- O acesso ao perfil do Mercado Livre agora é serializado para impedir conflito entre a pesquisa manual e a geração automática de links.

## Versionamento

Versão: 0.7.1 → 0.8.0
Tipo: MINOR
Motivo: adição compatível de uma nova tela e de um fluxo independente de busca manual.

---

# 0.7.1 — Compatibilidade com a API básica do AliExpress

- Corrigido o erro `isv.appkey-not-exists` ao usar App Keys atuais do AliExpress Open Platform.
- A integração agora usa o gateway atual, assinatura HMAC-SHA256 e timestamp em milissegundos.
- A busca geral deixou de exigir `hotproduct.query`, indisponível na API básica, e usa `product.query` ordenado por volume.
- Validada uma consulta real: ofertas em BRL e links de afiliado foram retornados corretamente.

## Versionamento

Versão: 0.7.0 → 0.7.1
Tipo: PATCH
Motivo: correção compatível do gateway e do método de busca para App Keys atuais e acesso básico.

---

# 0.7.0 — Integração de afiliados do AliExpress

- Adicionada busca automática de ofertas do AliExpress por nicho e de produtos em alta pela Affiliate API oficial.
- As consultas usam português, preços em reais e entrega para o Brasil.
- Links de produtos colados no bot agora podem ser convertidos em links de afiliado do AliExpress.
- App Key, Key Secret e Tracking ID podem ser salvos com segurança nas configurações do aplicativo.
- A área Operação ganhou teste isolado do AliExpress, com logomarca e mensagens claras de permissão ou configuração.
- Falhas do AliExpress são isoladas e não interrompem Mercado Livre, Shopee, Amazon, Telegram ou WhatsApp.
- O painel web legado e os comandos de terminal também reconhecem a nova fonte.

## Versionamento

Versão: 0.6.0 → 0.7.0
Tipo: MINOR
Motivo: nova integração compatível de marketplace e geração de links de afiliado.

---

# 0.6.0 — Central de operação e tempos reorganizada

- O botão **Executar ciclo agora** foi movido para a Visão geral, junto dos estados do Telegram e WhatsApp.
- O Console ganhou uma faixa fixa de tempos com pausa atual, próximo ciclo, intervalo entre ciclos, espaço entre publicações e reconexão do WhatsApp.
- A área Operação agora explica com clareza o que está em andamento, o que terminou com sucesso e o que falhou.
- Testes concluídos recebem um visto verde durante a sessão atual do aplicativo.
- A instalação do Chromium e a presença do perfil local do Mercado Livre são verificadas no computador e exibidas como prontas de forma permanente.
- Logomarcas locais identificam Mercado Livre, Shopee, Amazon, Telegram, WhatsApp e Chromium sem depender da internet.
- Mensagens do backend deixaram de registrar uma operação com falha como se ela tivesse sido concluída com sucesso.
- O layout responsivo foi revisado para manter controles, indicadores e textos legíveis em janelas estreitas.

## Versionamento

Versão: 0.5.3 → 0.6.0
Tipo: MINOR
Motivo: adição compatível de uma central de tempos, acompanhamento de operações por sessão e indicadores permanentes de preparo.

---

# 0.5.3 — Diagnóstico estável do WhatsApp

- Centenas de linhas repetidas do libsignal agora são condensadas em um único aviso claro sobre a sessão criptográfica recebida.
- Nenhuma mensagem, recibo de entrega ou pedido de retransmissão é bloqueado; conexão, autenticação, grupos e envios permanecem inalterados.
- Outros erros do componente WhatsApp continuam aparecendo normalmente no console.
- Adicionado teste de regressão para reconhecer somente o diagnóstico repetitivo conhecido.

## Versionamento

Versão: 0.5.2 → 0.5.3
Tipo: PATCH
Motivo: correção compatível do excesso de avisos de sessão Signal, sem alterar o protocolo do WhatsApp.

---

# 0.5.2 — Correção da instalação de atualizações

- O backend agora é encerrado e aguardado antes de o instalador substituir os arquivos do aplicativo.
- Corrigido o erro do Windows ao tentar gravar `bot-ofertas-backend.exe` durante uma atualização.
- O próprio instalador encerra componentes antigos que tenham ficado órfãos, permitindo atualizar diretamente a partir da versão afetada.
- Se o download ou a abertura do instalador falhar, o aplicativo restaura o backend e o estado anterior do bot.

## Versionamento

Versão: 0.5.1 → 0.5.2
Tipo: PATCH
Motivo: correção compatível do ciclo de atualização no Windows, sem alterar as funcionalidades existentes.

---

# 0.5.1 — Reconexão automática do WhatsApp

- Corrigida a desconexão definitiva após quedas transitórias do WhatsApp.
- O aplicativo agora tenta reconectar automaticamente até cinco vezes, com pausas progressivas de 2, 5, 10, 20 e 30 segundos.
- Sessões realmente removidas da conta não entram em repetição: o aplicativo solicita uma nova conexão manual.
- O console passa a informar o código da desconexão, a tentativa atual, o limite e o tempo até a próxima tentativa.
- Após cinco falhas, a reconexão automática é encerrada e o botão manual volta a ser habilitado.

## Versionamento

Versão: 0.5.0 → 0.5.1
Tipo: PATCH
Motivo: correção compatível da permanência e recuperação da conexão existente com o WhatsApp.

---

# 0.5.0 — Integração opcional com WhatsApp

- Adicionada integração local com WhatsApp Business por QR Code, usando uma ponte Baileys empacotada para Windows x64.
- A mesma seleção de ofertas do Telegram pode ser enviada a um grupo do WhatsApp, sem duplicar coleta ou geração de links.
- Telegram e WhatsApp possuem entregas independentes: falhas do WhatsApp não interrompem o canal já existente.
- Ofertas não entregues ficam pendentes por seis horas e somente são reenviadas por ação manual individual, com limite de cinco tentativas manuais.
- Nova área do WhatsApp com estado da conexão, QR Code, conta mascarada, carregamento de grupos, teste e remoção da sessão.
- Visão geral mostra conexão, pendências, próxima execução e contagem regressiva das pausas.
- Console agora informa duração das pausas, horário previsto de retomada, resultado por canal e pendências sem repetir envios automaticamente.
- Adicionados comandos `npm run whatsapp:test` e `npm run whatsapp:build`.
- Instalador inclui os backends Python e WhatsApp, sem exigir Node.js na máquina de destino.

## Versionamento

Versão: 0.4.2 → 0.5.0
Tipo: MINOR
Motivo: nova integração opcional com WhatsApp, fila manual e controles de interface, mantendo compatibilidade com o Telegram.

---

# 0.4.2 — Operação estável e interface reorganizada

- Ações manuais agora retornam corretamente ao estado disponível, inclusive quando ocorre uma falha.
- O console ao vivo preserva a posição de leitura e acompanha novas mensagens somente quando já está no final.
- Mensagens de log idênticas e consecutivas são agrupadas para evitar uma enxurrada visual de erros repetidos.
- A desconexão do backend libera imediatamente as operações pendentes e atualiza o estado do aplicativo.
- Interface reorganizada com hierarquia visual mais clara, navegação consistente, cartões de operação e configurações responsivas.
- Adicionados testes de regressão para o estado das ações e o agrupamento dos logs.

## Versionamento

Versão: 0.4.1 → 0.4.2
Tipo: PATCH
Motivo: correções de estabilidade e melhorias visuais compatíveis, sem remover funcionalidades.

---

# 0.4.1 — Inicialização opcional e ícone da bandeja

- Salvar configurações não tenta mais desativar a inicialização com o Windows quando ela já está desativada.
- O aviso sobre inicialização só aparece quando uma alteração realmente solicitada falha.
- O ícone do aplicativo agora é definido explicitamente na bandeja do Windows.
- Os recursos de ícone foram declarados no pacote desktop.

## Versionamento

Versão: 0.4.0 → 0.4.1
Tipo: PATCH
Motivo: correções do salvamento opcional e da apresentação do ícone na bandeja.

---

# 0.4.0 — Salvamento confiável e atualização sob controle

- O salvamento das credenciais continua mesmo se o Windows recusar a alteração da inicialização automática.
- O botão de salvar informa quando está processando e sempre apresenta o resultado.
- A versão instalada agora aparece no rodapé da barra lateral.
- Novas atualizações perguntam antes de baixar: “Atualizar agora” ou “Deixar para depois”.
- Atualizações adiadas permanecem visíveis no rodapé e podem ser retomadas quando o usuário quiser.
- O bot só é interrompido depois que o usuário escolhe instalar a atualização.

## Versionamento

Versão: 0.3.2 → 0.4.0
Tipo: MINOR
Motivo: correção do fluxo de persistência e inclusão de controles visíveis para versão e atualização.

---

# 0.3.2 — Correção do salvamento das configurações

- Corrigido o salvamento da primeira configuração quando ainda não existe `config.yaml`.
- Adicionados os campos Credential ID e Credential Secret da Amazon ao aplicativo desktop.
- Adicionado teste de regressão para garantir a persistência das credenciais.

## Versionamento

Versão: 0.3.1 → 0.3.2
Tipo: PATCH
Motivo: correção de persistência e inclusão de campos já suportados pelo backend.

---

# 0.3.1 — Correções de interface

- Caminhos e textos longos agora quebram corretamente sem ultrapassar os cartões ou a janela.
- Navegação lateral e superior permanece legível em janelas compactas.
- Formulários, botões, caixas de seleção, histórico e console foram ajustados para diferentes larguras.
- Preços e datas do histórico usam formatação local em português do Brasil.
- Ações em andamento ficam bloqueadas para evitar comandos duplicados.
- Testes de regressão adicionados para os principais problemas de layout.

## Versionamento

Versão: 0.3.0 → 0.3.1
Tipo: PATCH
Motivo: correções visuais e responsivas sem quebra das funcionalidades existentes.

---

# 0.3.0 — Atualizações automáticas

- Atualização automática assinada pelo GitHub Releases.
- Progresso de download e reinício controlado pela interface.
- Backend encerrado com segurança antes de aplicar a atualização.
- Comandos `npm start`, `npm test`, `npm run build`, `npm run release` e `npm run set-version` disponíveis na raiz.
- Geração automática de instalador, assinatura `.sig` e manifesto `latest.json` para publicação.

## Versionamento

Versão: 0.2.0 → 0.3.0
Tipo: MINOR
Motivo: adição do sistema de atualização automática e do fluxo de release assinado, sem quebra das funcionalidades existentes.

---

# 0.2.0 — Aplicativo desktop

- Aplicativo Tauri para Windows x64 com instalador NSIS.
- Console operacional e logs ao vivo dentro do aplicativo.
- Bandeja, inicialização com o Windows e início automático do bot configuráveis.
- Migração segura de configurações, histórico e sessão do Mercado Livre.
- Backend Python e CLI existentes preservados.
- Configurações e dados privados armazenados fora da pasta de instalação.

## Versionamento

Versão: 0.1.0 → 0.2.0  
Tipo: MINOR  
Motivo: adição do aplicativo desktop, instalador e gerenciamento operacional sem remoção intencional das funcionalidades existentes.
