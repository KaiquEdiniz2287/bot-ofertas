# Aplicativo Desktop Tauri para o Bot de Ofertas

**Data:** 21 de setembro de 2026  
**Estado:** desenho aprovado  
**Plataforma inicial:** Windows 10/11 x64  
**Versão atual:** 0.1.0  
**Versão prevista após implementação e validação:** 0.2.0

## 1. Objetivo

Transformar o projeto existente em um aplicativo desktop para Windows, com instalador, bandeja do sistema e console operacional integrado, preservando as funcionalidades atuais do bot de ofertas.

O aplicativo continuará coletando e convertendo ofertas do Mercado Livre, Shopee e Amazon, publicando no Telegram e mantendo o histórico anti-repetição. A operação diária não dependerá de uma janela de terminal nem de um navegador aberto para o painel.

## 2. Escopo

### Incluído

- Aplicativo desktop baseado em Tauri 2 para Windows x64.
- Interface em português do Brasil, com suporte correto a UTF-8, acentos, pontuação, emojis e caracteres especiais.
- Console operacional somente leitura, com logs ao vivo.
- Botões para todas as operações existentes relevantes.
- Bandeja do Windows com controles rápidos.
- Inicialização com o Windows configurável e desativada por padrão.
- Inicialização automática do bot configurável e desativada por padrão.
- Instalador NSIS.
- Backend Python empacotado e executado sem console externo.
- Migração segura dos dados da instalação atual.
- Preservação da CLI existente como caminho de diagnóstico e contingência.
- Testes automatizados para regras determinísticas e ciclo de vida.
- Validação real do instalador e dos principais fluxos locais.

### Não incluído nesta entrega

- Suporte a macOS, Linux, ARM64 ou Windows de 32 bits.
- Terminal PowerShell interativo ou execução de comandos arbitrários.
- Atualização automática do aplicativo.
- Assinatura digital do executável e do instalador.
- Publicação na Microsoft Store.
- Mudança das regras comerciais ou das integrações de afiliados.
- Postagens reais no Telegram feitas apenas para testar o instalador sem autorização explícita.

## 3. Princípios de compatibilidade

1. A lógica existente de Telegram, coleta, conversão, filtros, formatação, afiliados e SQLite continuará em Python.
2. A interface desktop não duplicará regras de negócio.
3. A CLI e o aplicativo chamarão os mesmos serviços internos.
4. Os formatos atuais de `.env`, `config.yaml`, `nichos.json` e `ofertas.db` permanecerão aceitos.
5. Dados existentes serão copiados e verificados antes de qualquer ativação.
6. A pasta atual continuará utilizável até a migração ser validada.

## 4. Arquitetura

### 4.1 Interface Tauri

A janela principal será construída com Tauri 2 e frontend estático em HTML, CSS e JavaScript puro. Não será introduzido React ou outro framework de frontend.

Responsabilidades:

- renderizar telas e estados;
- solicitar operações permitidas ao controlador;
- mostrar logs e progresso;
- apresentar configurações sem expor segredos;
- controlar comportamento de janela e bandeja por comandos restritos.

### 4.2 Controlador Tauri/Rust

O processo Tauri será o proprietário do ciclo de vida do backend.

Responsabilidades:

- garantir uma única instância do aplicativo;
- iniciar e encerrar o backend Python;
- encaminhar somente comandos explicitamente permitidos;
- receber eventos e logs estruturados;
- aplicar limites de reinício;
- administrar bandeja e inicialização com o Windows;
- impedir processos órfãos ao sair completamente ou durante o desligamento do Windows.

Não haverá uma API genérica para executar comandos do sistema.

### 4.3 Backend Python empacotado

O backend será empacotado com PyInstaller e continuará responsável por:

- bot e agendador do Telegram;
- coleta e conversão das três plataformas;
- geração de links de afiliado;
- Playwright e perfil do Mercado Livre;
- banco SQLite;
- filtros, escolha e formatação de ofertas;
- validação e persistência das configurações;
- migração e verificação de dados.

O backend fornecerá operações tipadas, incluindo:

- `get_status`;
- `get_settings`;
- `save_settings`;
- `start_bot`;
- `stop_bot`;
- `run_cycle`;
- `test_source`;
- `install_browser`;
- `start_ml_login`;
- `get_history`;
- `import_legacy_data`;
- `shutdown`.

O transporte entre Tauri e Python não usará o servidor HTTP local existente. Mensagens estruturadas serão trocadas pelos canais privados do processo, mantendo o painel HTTP apenas como contingência da CLI durante a transição.

## 5. Diretórios e dados

Arquivos empacotados serão somente leitura. Dados mutáveis serão armazenados sob o perfil do usuário:

```text
%LOCALAPPDATA%\BotOfertas\
├── config\
│   ├── .env
│   ├── config.yaml
│   └── nichos.json
├── data\
│   ├── ofertas.db
│   ├── ml_profile\
│   └── pw-browsers\
└── logs\
```

O backend aceitará explicitamente o diretório de dados fornecido pelo aplicativo. Execuções de desenvolvimento continuarão usando o diretório atual quando nenhum diretório externo for informado.

O instalador nunca incluirá:

- `.env` preenchido;
- `ofertas.db` do desenvolvedor;
- perfil ou cookies do Mercado Livre;
- navegadores existentes em `data/pw-browsers`;
- logs locais.

## 6. Migração da instalação atual

Na primeira execução, a interface oferecerá a importação de uma pasta existente. A operação copiará, sem mover ou apagar:

- `.env`;
- `config.yaml`;
- `data/nichos.json`;
- `data/ofertas.db`;
- `data/ml_profile`;
- `data/pw-browsers`, apenas se a versão for compatível; caso contrário, o navegador será reinstalado sob demanda.

Antes da ativação, uma área temporária será validada:

1. arquivos textuais precisam ser UTF-8 e legíveis;
2. YAML e JSON precisam ser válidos;
3. o SQLite precisa passar por `PRAGMA integrity_check`;
4. a quantidade de registros de `postadas` precisa ser preservada;
5. o perfil do Mercado Livre precisa ser legível;
6. o destino precisa aceitar escrita e substituição atômica.

Somente após todas as verificações os dados serão ativados. Falha ou cancelamento mantém a origem intacta e remove apenas a área temporária criada pela própria migração.

## 7. Interface e experiência

### 7.1 Estrutura principal

A navegação lateral terá cinco áreas:

1. **Visão geral:** estado do bot, próxima execução, quantidade publicada, fontes ativas e alertas.
2. **Operação:** ações manuais, progresso e tarefa corrente.
3. **Configurações:** credenciais, filtros, horário, categorias e preferências do aplicativo.
4. **Histórico:** registros publicados com plataforma, título, preço e data.
5. **Console:** logs completos e ferramentas de diagnóstico.

O estado e a ação principal de iniciar ou parar o bot permanecerão visíveis no cabeçalho.

### 7.2 Console operacional

O console será somente leitura e receberá eventos em tempo real. Cada entrada terá:

- data e hora;
- nível;
- origem;
- mensagem sanitizada.

Serão oferecidos filtros por nível e origem, busca textual, limpeza apenas da visualização e exportação de diagnóstico. Um painel reduzido poderá ser aberto na parte inferior de qualquer tela.

### 7.3 Configurações

- Segredos aparecerão mascarados.
- Campo secreto vazio preservará o valor já salvo.
- Haverá ação explícita para substituir ou remover um segredo.
- Dados serão validados antes da gravação.
- Alterações que dependem de reinício serão identificadas.
- A opção “Salvar e reiniciar o bot” fará uma parada graciosa e retomará somente após gravação bem-sucedida.
- “Iniciar com o Windows” e “Ligar o bot automaticamente” serão independentes e virão desativadas.

### 7.4 Bandeja

O menu da bandeja terá:

- Abrir aplicativo;
- Iniciar ou parar bot;
- Executar ciclo agora;
- Mostrar último erro;
- Sair completamente.

Fechar a janela a ocultará na bandeja. Na primeira ocorrência, o aplicativo explicará esse comportamento. “Sair completamente” encerrará tarefas e backend antes do processo Tauri.

### 7.5 Acessibilidade e apresentação

- Tema claro ou escuro conforme o Windows.
- Contraste adequado e estados que não dependam apenas de cor.
- Navegação por teclado e foco visível.
- Rótulos textuais para ícones.
- Layout utilizável em janelas menores, com tamanho mínimo definido.
- Mensagens de interface em português do Brasil e UTF-8.

## 8. Fluxo operacional e concorrência

O aplicativo permitirá apenas uma ação longa por vez. O bot poderá permanecer ligado durante operações compatíveis.

Operações que compartilham o perfil do Mercado Livre serão mutuamente exclusivas. Login, conversão ou teste que dependa desse perfil não começará enquanto outro uso estiver ativo. A interface explicará o bloqueio e oferecerá tentar novamente depois.

O login do Mercado Livre continuará abrindo o Google Chrome real. Senha e segundo fator permanecerão exclusivamente no navegador. O console interno mostrará instruções, estado e conclusão, mas não capturará credenciais.

Ao solicitar parada, atualização futura, saída completa ou desligamento do Windows, o backend terá oportunidade de:

1. interromper novos ciclos;
2. terminar ou cancelar com segurança a ação atual;
3. parar o polling e o agendador do Telegram;
4. liberar SQLite e perfil do navegador;
5. confirmar o encerramento.

Depois de um limite de espera, o aplicativo poderá forçar o encerramento e registrará o fato no diagnóstico.

## 9. Erros e recuperação

- Falhas de uma fonte não derrubarão as demais.
- Falha do backend manterá a interface aberta.
- A interface mostrará uma mensagem compreensível e detalhes técnicos expansíveis.
- Reinícios automáticos do backend terão quantidade e intervalo limitados.
- Não haverá reinício infinito.
- Logs terão rotação por tamanho e quantidade de arquivos.
- Tokens, secrets, cabeçalhos de autenticação, cookies e parâmetros sensíveis serão removidos dos logs.
- Arquivos de configuração serão gravados por substituição atômica.
- Corrupção de configuração manterá uma cópia recuperável e oferecerá restaurar valores padrão.

## 10. Segurança

- O frontend terá política de conteúdo restrita.
- Navegação remota dentro da janela principal será bloqueada.
- Links externos autorizados serão abertos no navegador padrão.
- O frontend não receberá acesso irrestrito ao shell ou ao sistema de arquivos.
- Comandos aceitos pelo backend usarão uma lista fixa e validação de tipos.
- Segredos não serão enviados como argumentos de linha de comando.
- Arquivos privados ficarão no perfil do usuário e não no diretório compartilhado do programa.
- O endpoint HTTP legado não será iniciado pela aplicação desktop.

## 11. Empacotamento e instalação

O backend será validado inicialmente no modo `onedir` do PyInstaller. O Tauri incluirá os arquivos internos necessários no instalador NSIS, mantendo para o usuário a experiência de um único instalador.

O WebView2 usará o runtime Evergreen e o instalador incluirá o bootstrapper pequeno. O navegador Chromium do Playwright não será empacotado. Quando necessário, será instalado sob demanda no diretório de dados do usuário.

O Google Chrome instalado no sistema continuará sendo a primeira opção para o Mercado Livre. A ausência do Chrome produzirá orientação clara na interface.

O desinstalador removerá binários e atalhos, preservando configurações, banco, sessões e logs. Exclusão completa dos dados exigirá uma ação separada e confirmação explícita.

Sem assinatura digital, o primeiro instalador poderá apresentar o aviso padrão do Windows SmartScreen. A interface e a documentação deverão explicar essa limitação sem recomendar a desativação geral de mecanismos de segurança do Windows.

## 12. Estratégia de testes

### 12.1 Testes Python

Serão adicionados testes com a biblioteca padrão sempre que suficiente, cobrindo:

- leitura, validação e gravação de configurações;
- caminhos de desenvolvimento e produção;
- preservação de segredos;
- parsing e formatação de preços;
- filtros e seleção de ofertas;
- banco e histórico;
- protocolo de comandos e eventos;
- sanitização de logs;
- migração válida, inválida, cancelada e interrompida.

### 12.2 Testes Rust/Tauri

- máquina de estados dos processos;
- lista de comandos permitidos;
- exclusão mútua de ações;
- limite de reinícios;
- encerramento gracioso e forçado;
- preferências de bandeja e autostart.

### 12.3 Verificação de entrega

- compilação Python sem erros;
- testes Python aprovados;
- frontend validado;
- `cargo test` aprovado;
- build Tauri aprovado;
- geração do instalador NSIS;
- instalação limpa em Windows x64;
- abertura sem console externo;
- minimizar e restaurar pela bandeja;
- autostart do aplicativo e do bot testados separadamente;
- importação mantendo os 99 registros existentes nesta instalação;
- ausência de processos órfãos após “Sair completamente”.

As integrações de Telegram, Mercado Livre, Shopee e Amazon serão verificadas separadamente. Testes que fariam publicação real exigirão autorização explícita. Comportamentos externos não exercitados serão reportados como não verificados.

## 13. Versionamento

O projeto permanecerá em `0.1.0` durante a implementação. Conforme `.skills/semver-versioning`, haverá um único incremento depois que a entrega estiver concluída e validada:

```text
Versão: 0.1.0 → 0.2.0
Tipo: MINOR
Motivo: adição do aplicativo desktop, instalador e gerenciamento operacional sem remoção intencional das funcionalidades existentes.
```

Se a implementação final introduzir uma incompatibilidade inevitável, o nível será reavaliado antes da alteração. Nenhuma versão será incrementada apenas pela criação desta especificação ou do plano.

## 14. Critérios de aceite

A entrega será aceita quando:

1. o aplicativo instalar e abrir sem terminal externo;
2. todas as ações existentes relevantes puderem ser iniciadas pela interface;
3. logs forem exibidos ao vivo no aplicativo;
4. fechar a janela mantiver o aplicativo na bandeja;
5. sair pela bandeja encerrar todos os processos;
6. as duas opções de inicialização automática funcionarem e vierem desativadas;
7. configurações e segredos forem preservados corretamente;
8. a importação não alterar a pasta original e mantiver banco e sessão;
9. dados privados não fizerem parte do instalador;
10. a CLI continuar disponível para diagnóstico;
11. testes e build definidos nesta especificação forem aprovados;
12. a versão for atualizada uma única vez, somente após a conclusão.
