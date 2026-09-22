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
