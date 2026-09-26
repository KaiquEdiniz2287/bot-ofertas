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
