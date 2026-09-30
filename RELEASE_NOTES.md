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
