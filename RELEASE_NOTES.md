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
