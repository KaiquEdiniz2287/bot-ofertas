# Plano de Implementação — Integração com WhatsApp

> **Estado:** v0.5 implementada, empacotada e validada automaticamente; aguardando validação real por QR Code no grupo de teste.  
> **Regra:** este documento continuará sendo atualizado quando decisões ou limites forem refinados durante a implementação.  
> **Projeto:** Bot de Ofertas Desktop — Tauri 2, backend Python e Windows x64.  
> **Versão implementada:** 0.5.0 (MINOR), conforme `.skills/semver-versioning`.  

## 1. Objetivo

Usar a mesma coleta, filtros, seleção e links de afiliado já empregados no Telegram para também publicar as ofertas em um grupo próprio do WhatsApp, sem remover nem enfraquecer o fluxo atual.

O aplicativo continuará local e deverá controlar, na mesma interface:

- Telegram e WhatsApp de forma independente;
- conexão do WhatsApp por QR Code;
- seleção segura do grupo de destino;
- fila, tentativas e resultado de cada entrega;
- logs e diagnóstico sem expor tokens, QR Code ou sessão.

### Decisões confirmadas na conversa

- Será usado um número dedicado com WhatsApp Business.
- O grupo de teste já existe.
- O primeiro lançamento publicará em somente um grupo.
- A estrutura de dados poderá receber vários grupos futuramente, sem levar esse gerenciamento extra para a primeira interface.
- O WhatsApp receberá a mesma seleção de ofertas feita para o Telegram.
- O aviso sobre links de afiliado ficará na descrição do grupo, não será repetido em cada mensagem.
- Entregas pendentes não serão disparadas automaticamente ao reconectar. O aplicativo apenas avisará; o proprietário escolherá quando reenviar cada uma.
- Ofertas pendentes expiram após seis horas e terão no máximo cinco tentativas manuais.
- O console usará mensagens operacionais claras e informará a duração e o horário final de cada pausa antes do próximo envio.
- O Telegram já está operacional e terá proteção explícita contra regressões: a nova integração não poderá mudar seu resultado, formato ou disponibilidade quando o WhatsApp estiver desativado ou indisponível.

## 2. Decisão técnica provisória

### Recomendação: Baileys em um sidecar Node.js local

O Baileys é a opção provisoriamente recomendada porque:

- suporta grupos e IDs de grupo (`...@g.us`);
- conecta a conta como um dispositivo vinculado por QR Code ou código de pareamento;
- usa WebSocket e não precisa abrir Chrome, Edge, Selenium ou Puppeteer;
- consegue enviar texto e mídia e restaurar a sessão localmente.

O Baileys é **não oficial** e não é afiliado ao WhatsApp. Mudanças no WhatsApp Web podem quebrar a integração e existe risco de desconexão ou restrição da conta. Não serão implementadas técnicas de evasão, stealth, bypass, spam ou automação de participantes.

### Alternativas avaliadas

| Opção | Vantagem | Limitação | Decisão atual |
|---|---|---|---|
| Baileys | Leve, sem navegador e com suporte a grupos | Não oficial; pode quebrar ou causar restrição da conta | Recomendada para o protótipo |
| WhatsApp Cloud API da Meta | Oficial, documentada e mais estável | A API de mensagens documenta destinatários individuais, não resolve o grupo desejado | Não atende ao requisito atual |
| `whatsapp-web.js` | Integração conhecida e já usada em outro aplicativo local | Exige Chrome/Edge e consome mais memória | Plano de contingência |

Fontes consultadas:

- [Documentação do Baileys](https://github.com/WhiskeySockets/docs/blob/main/quickstart.mdx)
- [Repositório oficial do Baileys](https://github.com/WhiskeySockets/Baileys)
- [Coleção oficial da WhatsApp Cloud API](https://www.postman.com/meta/whatsapp-business-platform/documentation/wlk6lh4/whatsapp-cloud-api)
- [Política de Mensagens do WhatsApp Business](https://business.whatsapp.com/policy/preview?lang=pt_BR)

## 3. Escopo inicial recomendado

### Incluído

- Uma conta de WhatsApp conectada por vez.
- Um grupo de destino inicialmente, preservando no banco a identificação do destino para permitir vários grupos no futuro.
- Conta e grupo escolhidos pelo proprietário do aplicativo.
- Listagem dos grupos acessíveis após a conexão.
- Seleção do grupo pela interface, sem digitação manual de JID.
- Envio da mesma seleção de ofertas para Telegram e WhatsApp, sem repetir coleta, filtros ou geração de links.
- Imagem, texto formatado, preço, desconto, plataforma e link afiliado.
- Telegram e WhatsApp ativáveis separadamente.
- Fila de entrega por destino para evitar que uma falha no WhatsApp bloqueie o Telegram.
- Reconexão limitada e recuperação da sessão após reiniciar o aplicativo.
- Estado do WhatsApp, erros e entregas no console e no histórico.
- Desconectar a sessão e trocar de conta mediante confirmação.
- Empacotamento no instalador e atualização pelo mecanismo já existente.

### Fora do escopo inicial

- Criar grupos ou adicionar/remover participantes.
- Ler conversas ou responder automaticamente aos membros.
- Enviar mensagens privadas em massa.
- Gerenciar vários números de WhatsApp.
- Gerenciar vários grupos simultaneamente.
- WhatsApp Communities, Status ou Canais.
- Serviço em nuvem, servidor remoto ou webhook público.
- Técnicas para contornar bloqueios ou limites do WhatsApp.

## 4. Arquitetura proposta

```text
Mercado Livre ─┐
Shopee ────────┼─> coleta e filtros Python ─> seleção única de ofertas
Amazon ────────┘                              │
                                               v
                                      fila persistente de entregas
                                      ├─> publicador Telegram
                                      └─> bridge Baileys ─> grupo WhatsApp

Tauri/UI <─NDJSON─> backend Python <─NDJSON─> sidecar Node/Baileys
```

### 4.1 Backend Python continua como orquestrador

O Python continuará sendo responsável por:

- coletar, filtrar e escolher ofertas uma única vez;
- formatar o conteúdo de cada canal;
- criar e acompanhar entregas independentes;
- decidir tentativas e intervalos;
- emitir estados e logs para a interface;
- iniciar e encerrar o bridge do WhatsApp sem deixar processos órfãos.

Não será duplicada no Node nenhuma regra de coleta, preço, desconto, afiliado ou seleção.

O fluxo escolherá a oferta uma única vez e criará uma entrega para cada canal habilitado. “Mesma oferta” significa mesma seleção, preço, imagem e link afiliado; o horário de chegada pode variar se um canal estiver temporariamente desconectado.

### 4.2 Bridge Node.js/Baileys

Será criado um diretório isolado, por exemplo `whatsapp-bridge/`, com protocolo NDJSON por entrada e saída padrão.

Comandos mínimos previstos:

- `connect`;
- `get_status`;
- `list_groups`;
- `send_offer`;
- `logout`;
- `shutdown`.

Eventos mínimos previstos:

- `bridge_ready`;
- `qr`;
- `connection_state`;
- `groups`;
- `message_sent`;
- `error`.

O bridge receberá somente o grupo escolhido e o conteúdo pronto para envio. Ele não terá acesso ao banco de ofertas, tokens de marketplaces ou credenciais do Telegram.

### 4.3 Empacotamento do bridge

A primeira tarefa técnica será um protótipo de empacotamento. Ordem de preferência:

1. Executável Windows x64 autocontido com `@yao-pkg/pkg`, se Baileys e suas dependências funcionarem corretamente.
2. Como contingência, runtime Node portátil e bridge empacotado como recursos privados do aplicativo.
3. `whatsapp-web.js` apenas se o Baileys não puder ser estabilizado ou empacotado.

O caminho escolhido deverá funcionar em máquina limpa sem exigir que amigos e familiares instalem Node.js.

## 5. Sessão e dados locais

A sessão será armazenada fora do instalador, em caminho equivalente a:

```text
%LOCALAPPDATA%\br.com.kaiodiniz.botofertas\data\whatsapp-session\
```

Regras:

- persistir entre reinicializações e atualizações;
- nunca entrar no Git, instalador, release, logs ou diagnóstico exportado;
- não entrar em backup comum sem uma decisão específica sobre criptografia;
- permitir exclusão apenas pela ação explícita “Desconectar e apagar sessão”;
- gravar credenciais e chaves de sessão de forma atômica quando possível;
- QR Codes não serão persistidos nem registrados no console.

## 6. Publicação e prevenção de duplicidade

O registro atual `postadas` não é suficiente para dois destinos: se o Telegram funcionar e o WhatsApp falhar, um único marcador não consegue distinguir os resultados.

Será adicionada uma fila persistente com duas entidades conceituais:

- **publicação:** fotografia da oferta selecionada, incluindo título, preços, imagem, plataforma e URL afiliada;
- **entrega:** resultado daquela publicação em um destino, como `telegram` ou `whatsapp`.

Estados de entrega:

```text
pendente → enviando → enviada
                    ↘ falhou → aguardando nova tentativa
                              → bloqueada após o limite
```

Regras propostas:

- cada destino possui estado próprio;
- sucesso no Telegram nunca é repetido só porque o WhatsApp falhou;
- sucesso no WhatsApp nunca é repetido só porque o Telegram falhou;
- falhas aguardam nova tentativa manual sem refazer a coleta;
- reconectar apenas informa a quantidade pendente, sem iniciar disparos;
- cada entrega aceita no máximo cinco tentativas manuais;
- ofertas com mais de seis horas expiram e não podem ser enviadas por engano;
- depois do limite, a entrega fica bloqueada;
- reconexão também terá espera progressiva e limite, evitando `ERROR` infinito;
- registros existentes serão preservados como histórico legado e não serão reenviados ao WhatsApp automaticamente.
- o identificador do destino fará parte da entrega, preparando o banco para vários grupos sem implementar essa interface agora.

Observação técnica: a entrega será “pelo menos uma vez”. Uma queda exatamente depois do WhatsApp aceitar a mensagem e antes de o banco registrar o sucesso ainda pode gerar uma duplicata rara. O plano não tentará prometer garantia impossível de “exatamente uma vez”.

## 7. Formatação das mensagens

Será criada uma representação neutra da oferta e dois formatadores:

- Telegram: HTML e botão “Pegar oferta”, mantendo o comportamento atual;
- WhatsApp: texto simples compatível com WhatsApp, imagem e URL afiliada visível.

Formato inicial recomendado no WhatsApp:

```text
🔥 Nome da oferta

❌ De: R$ 999,90
✅ Por: R$ 699,90  🔻 -30%

📦 Plataforma
🛒 Link da oferta: https://...
```

A divulgação de afiliado ficará na descrição do grupo e não será repetida em cada oferta. Antes da validação real, o plano verificará se a descrição está visível e informa claramente a presença de links afiliados.

## 8. Interface e experiência

### Nova área “WhatsApp” em Configurações

- Chave “Publicar também no WhatsApp”, desativada por padrão.
- Estado: desconectado, aguardando QR, conectando, conectado, reconectando ou erro.
- Botão “Conectar WhatsApp”.
- QR Code dentro do aplicativo.
- Instrução: “WhatsApp no celular → Aparelhos conectados → Conectar aparelho”.
- Nome e número mascarado da conta conectada.
- Botão “Carregar grupos”.
- Seletor com os grupos encontrados.
- Botão “Enviar mensagem de teste”, com confirmação explícita.
- Botão “Desconectar dispositivo”.

### Visão geral

- Estado separado de Telegram e WhatsApp.
- Grupo selecionado.
- Entregas pendentes ou bloqueadas.
- Último envio bem-sucedido por destino.

### Operação

- Testar conexão do WhatsApp.
- Atualizar lista de grupos.
- Tentar novamente entregas falhas.
- Executar ciclo continua sendo uma única ação e mostra o resultado por destino.

### Histórico

- Colunas ou indicadores separados para Telegram e WhatsApp.
- Estado, horário e último erro de cada entrega.
- Ação manual de nova tentativa somente para destinos ainda não enviados.

## 9. Configurações previstas

Configurações não secretas:

```text
whatsapp.enabled = false
whatsapp.groupJid = ""
whatsapp.groupName = ""
whatsapp.maxRetries = 5
```

O número conectado e a sessão serão descobertos pelo bridge, não digitados no `.env`. O JID do grupo será escolhido pela lista retornada pelo WhatsApp e persistido com validação.

Telegram e WhatsApp terão chaves independentes. Por padrão:

- Telegram mantém o comportamento atual;
- WhatsApp começa desativado;
- ativar WhatsApp exige sessão conectada e grupo selecionado;
- falha de um canal não interrompe o outro.

Embora a primeira versão tenha somente `groupJid` e `groupName`, cada entrega persistirá também o ID do destino. Uma futura versão poderá trocar a configuração única por uma lista de grupos sem reestruturar o histórico.

## 10. Segurança, política e uso responsável

- Usar o número dedicado definido para esta integração.
- Usar apenas em grupo próprio e com participantes que escolheram entrar.
- Informar claramente que o grupo envia ofertas e contém links de afiliado.
- Oferecer forma simples de sair do grupo.
- Não coletar contatos nem enviar mensagens privadas automaticamente.
- Não registrar QR, chaves de sessão, tokens, conteúdo privado ou lista completa de participantes.
- Fixar a versão do Baileys; atualizações serão avaliadas e testadas antes de entrar em release.
- Mostrar na interface que a integração é não oficial e pode precisar de nova vinculação.
- Se a conta for desconectada pelo WhatsApp, interromper envios e pedir nova autenticação; nunca entrar em loop infinito.

## 11. O que será necessário do proprietário

Antes do teste real:

1. O número dedicado definido para esta integração.
2. WhatsApp Business ativo no celular.
3. O grupo de teste já criado.
4. A conta conectada como membro; se apenas administradores puderem enviar, ela deve ser administradora.
5. Celular disponível para escanear o QR Code no primeiro vínculo.
6. Participantes cientes de que receberão ofertas e links de afiliado.
7. Autorização explícita antes de qualquer mensagem real de teste.

Não será necessário, usando Baileys:

- conta de desenvolvedor Meta;
- token da WhatsApp Cloud API;
- servidor público;
- domínio, SSL ou webhook;
- instalar Node.js na máquina do usuário final.

## 12. Fases de implementação propostas

### Fase 0 — Prova de viabilidade isolada

- Criar bridge mínimo fora do fluxo principal.
- Fixar versões compatíveis de Node e Baileys.
- Gerar QR no aplicativo ou em harness local.
- Conectar uma conta de teste.
- Listar grupos.
- Enviar texto e imagem para um grupo de teste autorizado.
- Reiniciar e confirmar restauração da sessão.
- Empacotar para Windows x64 e testar sem Node instalado globalmente.
- Encerrar e confirmar ausência de processo órfão.

**Saída:** decisão definitiva entre Baileys, runtime portátil ou contingência `whatsapp-web.js`.

### Fase 1 — Modelo de publicação e entregas

- Adicionar migração SQLite compatível com os dados atuais.
- Persistir fotografia da oferta e entregas por destino.
- Extrair publicador Telegram sem mudar seu comportamento.
- Implementar estado, tentativas limitadas e retomada.
- Cobrir falhas parciais sem duplicar no destino que já recebeu.

### Fase 2 — Bridge WhatsApp integrado

- Implementar protocolo NDJSON estrito.
- Supervisão pelo backend Python.
- QR, restauração, listagem de grupos e envio.
- Sanitização de logs.
- Encerramento gracioso e forçado com timeout.

### Fase 3 — Interface

- Configuração, QR e seletor de grupo.
- Estados por canal na visão geral.
- Ações operacionais e envio de teste confirmado.
- Histórico por destino e repetição manual.
- Mensagens de erro compreensíveis.

### Fase 4 — Pipeline e resiliência

- Publicar a mesma seleção nos destinos habilitados.
- Continuar Telegram quando WhatsApp estiver indisponível.
- Informar a fila pendente após reconexão, sem enviar automaticamente.
- Aplicar limites de tentativas e reconexão.
- Tratar sessão revogada, internet ausente, grupo removido e bridge encerrado.

### Fase 5 — Empacotamento, testes e documentação

- Integrar build do bridge a `npm start`, `npm run build` e `npm run release`.
- Incluir apenas binários e arquivos públicos no instalador.
- Confirmar ausência da sessão no bundle.
- Atualizar README e notas da versão.
- Aplicar SemVer uma única vez após validação.
- Gerar instalador e, somente quando solicitado, artefatos assinados do updater.

## 13. Testes e cenários obrigatórios

### Automatizados

- Formatação Telegram e WhatsApp com acentos, emojis e caracteres especiais.
- Migração do banco existente.
- Duas entregas independentes para a mesma oferta.
- Modo somente Telegram produz o mesmo conteúdo e comportamento da versão anterior.
- WhatsApp desativado não inicia o bridge nem altera o ciclo do Telegram.
- Telegram com sucesso e WhatsApp com falha.
- WhatsApp com sucesso e Telegram com falha.
- Limite de tentativas e ausência de loop infinito.
- Retomada após reiniciar o aplicativo.
- Protocolo rejeita comando ou payload inválido.
- Logs removem QR e dados de sessão.
- Encerramento mata o bridge.

### Reais em Windows x64

- Máquina sem Node.js global.
- QR Code e sessão restaurada após reinício.
- Lista mostra somente grupos acessíveis.
- Texto, acentos, imagem e link chegam corretamente.
- Conta sem permissão de publicar recebe erro claro.
- Internet interrompida não duplica mensagem já confirmada.
- Logout pelo celular atualiza a interface.
- Fechar na bandeja mantém o bridge quando necessário.
- “Sair completamente” não deixa processos órfãos.
- Atualização do aplicativo preserva a sessão local.

Publicações reais dependerão de autorização explícita e serão feitas primeiro em grupo de teste.

## 14. Critérios de aceite

A implementação será considerada pronta quando:

1. Telegram continuar funcionando como antes.
2. WhatsApp puder ser ativado e desativado independentemente.
3. QR Code, restauração de sessão e seleção de grupo funcionarem no app instalado.
4. A mesma seleção de ofertas chegar aos dois destinos habilitados.
5. Falha em um destino não duplicar nem impedir o outro.
6. Não houver tentativa ou reconexão infinita.
7. Sessão e QR nunca aparecerem nos logs ou instalador.
8. O instalador funcionar sem Node.js global.
9. Encerramento e atualização não deixarem sidecar órfão.
10. Testes, lint, build, instalador e validação real aplicável passarem.

## 15. Decisões pendentes para a conversa

- [x] Usar um número dedicado ou o número pessoal principal? **Número dedicado.**
- [x] WhatsApp receberá sempre exatamente as mesmas ofertas do Telegram? **Sim, a mesma seleção, com entregas independentes.**
- [x] Entregas pendentes devem ser reenviadas automaticamente ao reconectar? **Não. Apenas avisar; reenvio individual e manual, dentro de seis horas e com até cinco tentativas.**
- [x] O aviso de link afiliado ficará em cada mensagem ou apenas na descrição do grupo? **Somente na descrição.**
- [x] O primeiro lançamento suportará apenas um grupo, como recomendado? **Sim; vários grupos ficam previstos para uma evolução posterior.**
- [x] A conta será WhatsApp comum ou WhatsApp Business? **WhatsApp Business.**
- [x] O grupo de teste já existe ou será criado antes da validação? **Já existe.**

## 16. Histórico deste plano

- **v0.1 — 25/09/2026:** criação do rascunho inicial, recomendação provisória de Baileys, arquitetura com bridge local, entregas independentes e lista de decisões pendentes.
- **v0.2 — 25/09/2026:** confirmados número dedicado com WhatsApp Business, mesma seleção do Telegram, aviso afiliado somente na descrição, um grupo inicial com expansão futura e grupo de teste existente; reforçada a não regressão do Telegram.
- **v0.3 — 25/09/2026:** plano aprovado para implementação; pendências passam a exigir reenvio manual individual, expiram em seis horas e o console deverá explicar pausas e retomadas com clareza.
- **v0.4 — 25/09/2026:** bridge Baileys empacotado, fila SQLite, integração Python/Tauri, QR e grupos na interface, reenvio exclusivamente manual, contadores de pausa, testes automatizados e build Windows implementados; vínculo e envio reais permanecem para validação assistida no grupo de teste.
- **v0.5 — 25/09/2026:** versão 0.5.0 sincronizada, 22 testes Python, 9 testes de interface, protocolo Node, auto-testes dos executáveis e testes Rust aprovados; instalador Windows x64 gerado sem depender de Node.js global. O build comum não exige mais a chave do updater; assinatura e `latest.json` permanecem exclusivas de `npm run release`.
