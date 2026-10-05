# Integração do SendAiPlus ao Bot de Ofertas

Data: 04/10/2026
Estado: primeira implementação funcional concluída na versão 0.13.0; modo geral e simplificação das configurações corrigidos na 0.13.1. Validação ao vivo em grupo de teste ainda pendente.

Na 0.13.1, **Todos os grupos** usa uma única automação, sem cadastrar cada JID. Apenas mensagens novas de grupos são aceitas; grupo com regra específica ativa prevalece. O formulário mostra parâmetros de regra, atraso e mídia somente quando fazem sentido, preservando sempre visíveis os limites contra excesso. Uma campanha/post ativo é pré-requisito para habilitar respostas; antes disso, a automação pode ser salva desativada. O modo de desenvolvimento recompila os componentes locais desatualizados antes de iniciar, evitando interface e backend de versões diferentes.
Base analisada: Bot de Ofertas 0.12.1 e SendAiPlus 0.5.1.

## 1. Objetivo e conclusão

É tecnicamente possível acrescentar respostas automáticas ao Bot de Ofertas usando a mesma conta, sessão e conexão Baileys já existentes.

A implementação deve adaptar o domínio do SendAiPlus às tecnologias atuais: Tauri 2, backend Python, SQLite, interface HTML/CSS/JavaScript e bridge Node/Baileys. Não é necessário embutir outro aplicativo, adotar React ou iniciar uma segunda conexão.

O SendAiPlus permanece intacto como referência. Sua sessão whatsapp-web.js não deve ser copiada para o Baileys: são formatos diferentes. A conexão reutilizada será a que já funciona no Bot de Ofertas.

## 2. O que foi analisado

- Pedido original e mensagens posteriores da conversa local disponível do SendAiPlus, até a correção da versão 0.5.1.
- README, arquitetura, banco, regras e documentação do provedor WhatsApp.
- Modelos de domínio, RuleEngine, BotManager, RuntimeSessionManager, PostSelector e ResponseQueue.
- AppRuntime, persistência, importação/exportação e estado da interface.
- Cadastro de posts, configuração de grupos, campanhas e configurações gerais.
- Bridge whatsapp-web.js e seu adaptador Tauri.
- Testes existentes dos motores de regras, fila, seleção, sessão e preservação de grupos.
- No Bot de Ofertas: bridge Baileys, cliente Python, serviço desktop, protocolo autorizado, banco de ofertas, integração Rust e organização da interface.

A conversa original solicita expressamente ausência de IA. A mensagem recebida é apenas um gatilho; o post enviado pode não ter relação com seu conteúdo. Em 04/10/2026, o usuário confirmou: **“Respostas prontas e regras primeiro”**. Esse é o escopo inicial definido. Conversas com IA ou fluxos de atendimento privado não estão implementados no SendAiPlus analisado.

## 3. Separação funcional

| Área | Responsabilidade | Compartilha com as demais |
| --- | --- | --- |
| Bot de Ofertas | Pesquisa, afiliados, filtros, ciclos, publicações no Telegram, grupo e Canal | Transporte WhatsApp |
| Respostas em grupos | Mensagem recebida como gatilho, campanhas, posts, timing, resposta citada | Transporte WhatsApp |
| Chatbot/atendimento | Futura interação por regras, palavras-chave ou fluxos a definir | Transporte WhatsApp; não confundir com o respondedor por gatilho |
| Conexão WhatsApp | QR Code, sessão, reconexão e estado da conta | Uma única conexão para todos |

Cada automação tem seu próprio estado de execução. Parar as respostas não para o garimpo; parar as ofertas não para as respostas. Desconectar a conta compartilhada afeta todos os envios de WhatsApp e deve estar claro na interface. O Telegram continua independente.

Preservar o significado das preferências atuais do bot de ofertas. Novas preferências do respondedor não devem reutilizar `autoStartBot`, a seleção de categorias ou o destino de ofertas para outra finalidade.

## 4. Recursos a adaptar do SendAiPlus

### Grupos, posts e campanhas

- Listar os grupos pela conexão existente; seleção independente dos destinos de ofertas.
- Identificação pelo JID do WhatsApp, nunca pelo nome. Preservar nomes, emojis e acentos em UTF-8/NFC.
- Ativar/desativar individualmente e associar uma campanha por grupo.
- Biblioteca com texto, texto com link, imagem + legenda e vídeo + legenda.
- Nome interno do post não participa da mensagem enviada.
- Campanhas com posts ativos e sorteio local sem repetir os últimos N posts, adaptando N à quantidade disponível.
- Revalidar post, campanha, grupo, arquivo de mídia e regras antes do envio.
- Copiar mídias selecionadas para a pasta de dados do módulo, para não depender de um arquivo temporário ou movido pelo usuário.

### Regras de tempo

- Sempre, respeitando os limites configurados.
- Cooldown por grupo.
- Uma vez por execução do respondedor.
- Uma vez por dia no fuso configurado.
- Limite de respostas por período.
- A cada X mensagens válidas.
- Probabilidade configurável.
- Delay fixo ou aleatório, somado ao atraso global opcional.
- Limites por grupo, por hora e por dia.
- Dias e múltiplas janelas de horário, inclusive atravessando meia-noite.

Reservar a autorização ao criar um job, em transação, para que várias mensagens simultâneas não passem pelo mesmo cooldown. Contabilizar envios confirmados e reservas separadamente; liberar reservas quando a tarefa for cancelada ou falhar antes do envio. Uma entrega incerta exige tratamento próprio e não pode disparar repetição automática.

O cooldown de um grupo não pausa a coleta de ofertas nem os outros grupos. Uma vez por execução reinicia somente ao parar/iniciar o respondedor; reconectar o WhatsApp não cria outra execução.

### Operação e diagnóstico

- Fila com motivo de espera, horário previsto, contagem regressiva e cancelamento.
- Histórico independente: enviado, ignorado, falhou, cancelado, simulado e confirmação incerta.
- Dashboard com status, próximos envios, grupos em cooldown e contadores.
- Simulador usando o mesmo motor, sempre sem envio externo.
- Dry Run para mensagens reais: avalia e registra, mas não envia.
- Importação/exportação de configuração e backup do banco do módulo.
- Configuração inicial: módulo desligado, grupos desativados, simulação ligada e início automático desligado.

## 5. Uma conexão, módulos independentes

```text
WhatsApp/Baileys já conectado
  ├─ envio de ofertas existente ───────────────────────────┐
  └─ novas mensagens → filtro → fila de entrada            │
                                  ↓                       │
                           regras em Python               │
                                  ↓                       │
                       seleção do post + reserva          │
                                  ↓                       │
                       fila de respostas + delay          │
                                  ↓                       │
                            revalidação                   │
                                  └── coordenação de envio┘
                                              ↓
                            mesmo socket + confirmação
```

Baileys fornece `messages.upsert` e envio com `quoted`. A versão instalada também expõe esses contratos. A resposta deve citar a mensagem original, preservando chave, grupo e participante; texto e mídias saem pelo mesmo socket.

O listener deve somente filtrar e enfileirar. Nunca deve aguardar um envio dentro do leitor de respostas JSON do bridge Python: isso pode impedir o processamento da confirmação que o próprio envio espera.

Regras, consultas SQLite e delays ficam fora do listener e não bloqueiam o ciclo automático. Todos os novos comandos precisam entrar nas listas permitidas do Python e do Rust.

### Coordenação de envios

- Um envio físico por vez na conexão compartilhada, com fila limitada e tratamento explícito de congestionamento.
- Delays e cooldowns do respondedor aguardam fora do bloqueio do transporte.
- Ofertas prontas têm prioridade sobre respostas ainda não iniciadas; não interromper uma mensagem já em envio.
- Preservar o fluxo grupo → intervalo mínimo de cinco segundos → Canal.
- Com o respondedor desativado, manter o comportamento atual das ofertas.
- Quando os dois módulos estiverem ativos, uma transmissão já iniciada pode acrescentar uma espera curta ao outro. Independência de regras não significa simultaneidade irrestrita na mesma conta.
- Limites de respostas pertencem ao respondedor. O espaçamento físico entre envios pertence à conexão e não deve ser confundido com os timers do ciclo de ofertas.
- A recuperação de conexão já existente permanece única. Não criar outro mecanismo concorrente de cinco tentativas.

## 6. Recebimento, duplicidade e falhas

1. Processar todos os itens de um lote `messages.upsert`, não somente o primeiro.
2. Não tratar sincronização histórica como gatilho. Validar tipo do evento e data da mensagem em relação à ativação do módulo; `notify` sozinho não basta para provar que uma mensagem é nova.
3. Deduplicar por conta, chat e chave externa de mensagem com restrição única no banco.
4. Ignorar mensagens próprias, inclusive ofertas, respostas, testes e mensagens da conta enviadas pelo celular.
5. Ignorar eventos de sistema, reações, recibos, edições e exclusões como novos gatilhos. Não responder em Canais ou status.
6. Validar que o grupo está habilitado e acessível no momento do envio.
7. Guardar apenas o contexto necessário para citar a mensagem original, com limites de armazenamento e expiração. Se esse contexto não estiver mais disponível, registrar a impossibilidade em vez de publicar uma resposta solta.
8. Não reprocessar automaticamente um acúmulo de mensagens ao reconectar.
9. Reaproveitar a confirmação de envio corrigida na 0.12.1. Aceitação pelo servidor não prova leitura pelos participantes.
10. Não repetir automaticamente após timeout ou queda com entrega incerta; preservar no histórico para análise manual.
11. Parar o respondedor cancela tarefas aguardando. Um envio já entregue ao transporte não pode ser desfeito; registrar seu resultado e bloquear os próximos.
12. Falhas do consumidor de mensagens devem ser capturadas e registradas sem interromper o leitor do bridge.

Mensagens que não puderam ser descriptografadas não são gatilhos utilizáveis. A mensagem de diagnóstico atual sobre renovação de sessão precisa diferenciar falha de recebimento de mensagem e simples renovação; não deve prometer que o recebimento funciona quando isso não foi observado.

## 7. Organização técnica proposta

```text
ofertas/autoresponder/
  models.py          # contratos, enums e validação
  rules.py           # regras e cálculo de horários
  selector.py        # seleção de posts sem repetição
  repository.py      # SQLite próprio, migrations e reservas atômicas
  runtime.py         # sessão, fila e cancelamento
  service.py         # operações expostas à interface
desktop/ui/autoresponder/
  app.js             # páginas e eventos do novo módulo
  styles.css         # estilos com escopo próprio
whatsapp-bridge/
  incoming.cjs       # normalização e contexto de mensagens recebidas
```

Integrações pontuais necessárias nos arquivos existentes: registro do serviço desktop, autorização dos comandos, navegação, callback de eventos e comando de resposta no bridge. Preservar coleta, conversores de afiliado, formatação de ofertas, histórico de publicações, instalador e updater.

Dados novos em `data/autoresponder.db`, mídias em `data/autoresponder-media/`, sem modificar `ofertas.db`. Tabelas normalizadas para configurações, grupos, regras, horários, posts, campanhas, vínculos, mensagens deduplicadas, jobs, histórico e sessões. Índices para jobs agendados e contadores por grupo/período; consultas paginadas e contadores independentes da página visível do histórico.

Datas persistidas em UTC, regras avaliadas no fuso IANA configurado. Ao implementar em Python/Windows, verificar disponibilidade da base de fusos e seu empacotamento; incluir `tzdata` somente se necessário.

Não importar inicialização automática, credenciais, sessão WhatsApp ou comportamento de fechamento do SendAiPlus. Aproveitar o tray e a configuração de Windows existentes.

## 8. Organização visual

- **Ofertas:** Visão geral, Buscar produtos, Operação e Histórico atual.
- **Respostas automáticas:** Resumo, Grupos e regras, Posts, Campanhas, Fila e histórico, Simulador.
- **Compartilhado:** WhatsApp, Configurações gerais e Console.

Preferir uma entrada lateral “Respostas automáticas” com navegação interna para suas telas, evitando duplicar todos os itens na barra lateral. Estado e controle no topo devem identificar qual automação está sendo iniciada/parada.

Na área de respostas, mostrar no mesmo contexto o timer, o grupo, a campanha, a mensagem citada e o motivo de espera. Filtros do console por origem: Ofertas, Respostas e Conexão.

## 9. Achados que não devem ser copiados sem ajuste

| Achado no SendAiPlus | Evidência no código atual | Tratamento na adaptação |
| --- | --- | --- |
| Persistência principal é um snapshot de UI | `PersistenceService` grava `app_state`; tabelas normalizadas existem, mas não sustentam as consultas do runtime | Repositories SQLite reais para eventos, jobs e limites |
| Histórico em memória é limitado a 500 registros | `appStore.addHistory`; `AppRuntime` calcula limites a partir dessa lista | Limites por consultas persistentes, sem depender do recorte da interface |
| Repetição zero ainda exclui posts antigos | `recentPostIds.slice(-0)` equivale a `slice(0)` | Tratar N=0 explicitamente; reproduzido nesta análise |
| Janela cruzando meia-noite ignora o dia anterior | `isInsideSchedule` filtra apenas o dia atual | Considerar a janela iniciada no dia anterior; reproduzido nesta análise |
| Não há deduplicação persistente efetiva no fluxo de eventos | Listener → BotManager → snapshot | Chave única e reserva transacional antes de enfileirar |
| Simulações participam dos contadores usados para envios reais | `getRecent*Responses` inclui `WOULD_SEND` | Separar estado simulado e real |
| Fila tenta novamente erros genéricos | `ResponseQueue` usa até três tentativas | Distinguir falha antes do envio e confirmação incerta |
| Revalidação antes do envio é parcial | `AppRuntime.execute` revalida grupo/campanha e cooldown global | Revalidar horários, limites, post e vínculo atual também |
| Importação valida mais a estrutura externa que o conteúdo | Arrays de `unknown` e casts em `BackupService`/`SettingsPage` | Validar campos, números finitos, IDs, relacionamentos e arquivos |

Os 15 testes existentes do SendAiPlus passaram nesta análise. Os dois casos adicionais acima reproduziram problemas que a suíte atual não cobre. Isso fundamenta usar o projeto como referência de requisitos, sem copiar integralmente sua implementação.

## 10. Sequência de implementação e aceite

1. Criar domínio, banco separado e motor de regras com relógio e sorteio controláveis nos testes.
2. Implementar CRUD de grupos, posts e campanhas, filas, simulação e histórico; ainda sem enviar externamente.
3. Integrar recebimento Baileys com filtros, deduplicação, fila limitada e contexto da mensagem original.
4. Integrar resposta citada e coordenação do transporte com confirmação de envio e cancelamento.
5. Implementar interface independente, importação validada do JSON do SendAiPlus e cópia das mídias disponíveis.
6. Validar regressões de ofertas, grupo/Canal, Telegram, temporizadores, shutdown e updater.
7. Validar em grupo de teste explicitamente escolhido antes da ativação nos demais grupos.

Critérios obrigatórios:

- Todos os sete modos de resposta e suas combinações passam nos testes.
- Uma mensagem repetida não cria duas respostas, inclusive após reconexão.
- Publicações do próprio bot nunca viram gatilhos.
- Desativar post, grupo, campanha ou módulo durante o delay bloqueia o envio pendente.
- Horários noturnos e virada diária funcionam em America/Manaus e no fuso escolhido.
- Falha de envio não trava fila nem interrompe o bot de ofertas.
- Grupo e Canal continuam recebendo ofertas com seus controles atuais.
- Dry Run e simulador não acionam o transporte real.
- A atualização de uma instalação existente não ativa nenhuma nova automação.
- Acentos, emojis, nomes de grupos e caminhos com espaços funcionam em cadastro, persistência, exportação e envio.
- Falta de contexto para citar a mensagem e confirmação incerta são explicadas no histórico.
- Limites continuam corretos depois de reiniciar o app e após milhares de registros.

## 11. Decisões ainda abertas

- Confirmado: respostas prontas e regras primeiro; nenhuma integração de IA nesta etapa.
- Se houver atendimento privado, definir gatilhos, mensagens, menus/fluxos, quando passar a resposta para uma pessoa e quais conversas habilitar. Esse comportamento não existe pronto na base analisada.
- Importação de dados reais: oferecer arquivo exportado pelo SendAiPlus com prévia e validação. Não importar automaticamente bancos ou sessões de uma instalação em uso.

## 12. Estado desta entrega

- Análise de compatibilidade concluída.
- Requisitos históricos recuperados e confrontados com o código atual.
- Suíte do SendAiPlus executada: 15 testes aprovados.
- Reproduzidos os problemas de repetição zero e janela atravessando meia-noite.
- Documento de arquitetura e sequência de migração criado.
- Implementados motor de regras, banco próprio, fila, resposta citada pela conexão Baileys existente, telas, importação JSON e backup/restauração locais.
- Validados offline os fluxos de oferta existentes, regras, deduplicação, resposta citada e confirmação, bridge/backend empacotados e a interface em navegador local.
- Teste de publicação ao vivo não realizado: é preciso escolher explicitamente o grupo de teste e enviar uma mensagem nova após ativar o modo real.
- Versionamento aplicado: 0.12.1 → 0.13.0 (MINOR).

Referências oficiais do Baileys:

- Recebimento de atualizações: https://github.com/WhiskeySockets/baileys.wiki-site/blob/main/docs/socket/receiving-updates.md
- Envio e resposta citada: https://github.com/WhiskeySockets/docs/blob/main/messaging/sending-messages.mdx
