# Bot de Ofertas para Telegram e WhatsApp 🔥

Bot que roda **no seu PC** (Windows), garimpa promoções em **Mercado Livre, Shopee, Amazon, AliExpress e SHEIN** e publica no Telegram e, opcionalmente, em um grupo e/ou Canal próprio do WhatsApp com **os seus links de afiliado**. Tudo local, sem servidor nem mensalidade.

> ⚠️ Você precisa das **suas próprias** contas de afiliado (Mercado Livre, Amazon Associados, Shopee Afiliados e AliExpress Portals). As comissões vão para quem configurar — cada pessoa usa as suas.

## Exportar ofertas para o SendAiPlus

Com o **SendAiPlus 0.12.0 ou superior aberto** no mesmo usuário do Windows (inclusive na bandeja), use **Exportar SendAi** em cada oferta do Histórico ou de Buscar produtos. O botão é habilitado automaticamente ao detectar o aplicativo; versões anteriores precisam ser atualizadas.

A exportação cria um post **Texto com link**, ativo, com o nome do produto como nome interno, sem título opcional e com o mesmo texto formatado usado por **Copiar**. Ela não publica mensagens, não interrompe o ciclo e não seleciona o post no respondedor: escolha-o depois na biblioteca do SendAiPlus. Registros antigos sem link não podem ser exportados.

A conexão é local (`127.0.0.1`), com uma credencial temporária por execução. O Bot só confirma depois que o SendAiPlus salva. Se a confirmação falhar, repetir o botão na mesma sessão reutiliza o identificador para evitar duplicação. O estado “Exportado” é da sessão atual; depois de reabrir o Bot, uma nova exportação é uma nova inclusão.

## Como funciona

### Converter link no aplicativo

Na aba **Converter link**, cole um endereço de produto do Mercado Livre, Shopee, Amazon, AliExpress ou SHEIN e clique em **Converter para meu link de afiliado**. A plataforma é identificada automaticamente e usa as credenciais salvas em Configurações. Mercado Livre e SHEIN precisam do respectivo perfil de login preparado em Operação.

O resultado oferece **Copiar link** e, quando o nome do produto estiver disponível, **Copiar oferta formatada**, usando o mesmo modelo das publicações. Dados ausentes não são inventados. A conversão não publica, não registra no histórico e pode ser usada com o bot ativo; o acesso ao perfil do ML aguarda a geração de links que já estiver em andamento.

### SHEIN

Em **Operação → Login da SHEIN**, faça login na janela exclusiva, confira o conversor e o catálogo de afiliados e feche o navegador. A sessão fica em `data/shein_profile`, separada do Mercado Livre e do seu Chrome pessoal. O perfil detectado indica apenas que há dados locais; use **Testar SHEIN** para confirmar busca e conversão de um produto, sem publicar.

Ative **Configurações → SHEIN → Pesquisar e publicar ofertas da SHEIN** para incluir a fonte no ciclo e na busca manual. Ela começa desativada nas instalações existentes. A aba **Converter link** também aceita links `shein.com`, `onelink.shein.com` e `shein.top`, usando a mesma sessão. Não é necessário preencher App Key nem copiar cookies.

A coleta consulta os **produtos recomendados do painel de afiliados** ou até dois termos por ciclo, em rodízio, respeitando as categorias escolhidas. A pesquisa avulsa usa o formulário de pesquisa do mesmo painel. A busca pública `/pdsearch/`, que exigiu verificação nos testes, deixou de fazer parte desses fluxos. Cada consulta aproveita até duas páginas de resultados carregadas pela própria interface, com limite de espera; o Console mostra o termo e a quantidade encontrada. O painel pode disponibilizar menos produtos que a loja pública.

Os filtros gerais de preço, desconto e repetição continuam valendo. Comissão e bônus do afiliado não são tratados como desconto do produto. Produtos sugeridos pelo painel sem correspondência textual com a pesquisa são descartados. Links afiliados são gerados no conversor oficial somente para as ofertas escolhidas no ciclo e os três melhores resultados da busca manual. A resposta do conversor atualiza preços, imagem, avaliação e vendas quando disponíveis; o ciclo revalida o desconto antes de publicar.

Consulta e conversão começam pelo **Chrome sem janela**, usando o perfil salvo da SHEIN. O **CloakBrowser persistente** permanece como alternativa, em `data/shein_coleta_profile`. A sessão da conta é importada na primeira preparação e sincronizada depois de um novo login solicitado pelo usuário; apenas cookies e dados locais da SHEIN são transferidos. Nenhuma API privada é chamada diretamente: o módulo observa as respostas produzidas pela navegação e pelos formulários do painel. Apenas o login solicitado pelo usuário abre janela. Verificações reais continuam exigindo intervenção manual; nenhum navegador garante acesso permanente. Os testes e limites da correção estão em `docs/diagnosticos/2026-10-25-shein-catalogo-afiliados.md`.

Comandos opcionais: `uv run python -m ofertas shein-login` e `uv run python -m ofertas testar shein`. Não compartilhe a pasta de dados, pois ela contém sessões autenticadas.

### Escolher marketplaces

Em **Configurações → 02 Marketplaces**, Mercado Livre, Amazon, Shopee e AliExpress têm subblocos próprios com suas credenciais e um interruptor **Usar**. A SHEIN mantém o interruptor em seu bloco separado. Desmarque as fontes que não deseja consultar e salve: a seleção passa a valer no próximo ciclo e nas novas pesquisas manuais. Uma operação em andamento pode concluir usando a seleção anterior.

As chaves e os perfis permanecem salvos ao desativar uma fonte. O conversor de links avulsos continua disponível para plataformas desativadas. Se todas as fontes estavam desligadas quando o bot iniciou, habilitar uma delas agenda o primeiro ciclo em 30 segundos; pausas já agendadas são preservadas.

O visto verde no botão de login da SHEIN indica que o perfil foi salvo localmente. O teste da plataforma confirma o acesso atual; sessões podem expirar. No Console, consultas bem-sucedidas do Telegram aparecem como **Consulta de mensagens concluída. Aguardando novos comandos e links pelo Telegram.**, sem mudar a frequência das consultas ou ocultar falhas.

Dois modos, no mesmo programa:

1. **Automático** — de tempos em tempos busca ofertas, filtra por desconto mínimo, evita repetir produto e posta as melhores no canal, já com o seu link de afiliado.
2. **Conversor** — você cola qualquer link de produto no privado do bot; ele monta a prévia do post com o seu link e você decide **✅ Postar** ou **🗑 Descartar**.

| Plataforma | De onde vêm as ofertas | Link de afiliado |
|---|---|---|
| Mercado Livre | Página de ofertas, filtrada por categoria | API do Linkbuilder do painel (login 1x); gera `meli.la/...` |
| Shopee | Open API oficial de afiliados (busca por palavra-chave) | A API já devolve o link com sua comissão |
| Amazon | Creators API; ou, enquanto sua conta não é elegível, ofertas por departamento | Link com a sua tag |
| AliExpress | Affiliate API oficial, por nicho ou produtos em alta, em português e BRL | A API devolve ou gera o link com seu Tracking ID |
| SHEIN | Recomendações e pesquisa do painel de afiliados, com sessão local | Conversor oficial de afiliados, sem janela |

### Navegador do Mercado Livre

A coleta de ofertas do ML tenta primeiro o acesso público e depois o **CloakBrowser sem janela**, com um perfil separado em `data/ml_coleta_profile`. Prepare-o em **Operação → Instalar navegador**: essa ação instala Chromium e baixa o CloakBrowser diretamente do fornecedor (aproximadamente 535 MB na primeira instalação). O navegador fica no cache próprio do CloakBrowser, fora do instalador; o ciclo não inicia downloads grandes. Se o CloakBrowser estiver ausente ou falhar, permanece a recuperação pelo perfil salvo do Chrome: primeiro sem janela e, apenas se bloqueado, uma tentativa visível. A pesquisa manual continua no Chrome, e o Linkbuilder continua em segundo plano, em lotes de até 10 URLs no mesmo contexto. Se o site exigir nova verificação, use **Operação → Login do Mercado Livre** e confira ofertas e Linkbuilder antes de fechar. A mensagem de perfil salvo não garante acesso: execute o teste do ML para conferir.

O CloakBrowser é usado na coleta de ofertas e como alternativa para ler os detalhes de um produto no conversor de links, com a versão validada `146.0.7680.177.5` e wrapper `0.6.3`. Na conversão, ele só é iniciado se o acesso simples não fornecer nome, preço ou imagem; usa o perfil separado de coleta e nunca abre janela. Se a leitura falhar, o link afiliado ainda pode ser copiado. O código do wrapper e o binário possuem licenças distintas; o binário não é incluído no instalador. Antes de redistribuir o aplicativo, confira as [condições oficiais de integração e distribuição](https://github.com/CloakHQ/CloakBrowser/blob/main/BINARY-LICENSE.md).

### Creators API da Amazon

Salvar o Credential ID e o Credential Secret permite autenticar, mas o acesso ao catálogo depende também da elegibilidade da conta perante a Amazon. A resposta `AssociateNotEligible` indica que o catálogo não foi liberado; consulte os requisitos no painel de Associados (incluem 10 vendas qualificadas nos últimos 30 dias). Nessa situação, o bot tenta a busca alternativa pelo site e aguarda seis horas para tentar a API novamente.

Sem categorias ou termos específicos selecionados, a API consulta `ofertas` em todas as categorias. Isso não garante resultados em todas as categorias a cada ciclo; a Amazon determina os produtos retornados pela consulta. Categorias selecionadas e termos configurados continuam sendo usados normalmente.

### Integração com o AliExpress

A integração usa chamadas assinadas do Open Platform e não compartilha as credenciais com Telegram ou WhatsApp. O bot utiliza:

- `aliexpress.affiliate.product.query` para buscar ofertas por palavra-chave;
- `aliexpress.affiliate.product.query`, ordenado por volume, para produtos em alta quando nenhum nicho foi escolhido;
- `aliexpress.affiliate.productdetail.get` para converter um link colado no bot;
- `aliexpress.affiliate.link.generate` como garantia para gerar o link rastreável.

Antes da publicação, o link selecionado é normalizado pelo método oficial `link.generate` para o formato curto `s.click.aliexpress.com/e/_...`, mantendo o Tracking ID e a atribuição da comissão.

As consultas pedem moeda `BRL`, idioma `PT` e destino `BR`. Preencha App Key, Key Secret e Tracking ID em **Configurações → Afiliados** e valide em **Operação → Testar AliExpress** antes de ligar o ciclo automático. Se a aplicação não tiver permissão para algum método, o erro aparece no console e as demais plataformas continuam funcionando.

---

## 🖥️ Aplicativo desktop para Windows (recomendado)

Instale pelo arquivo `Bot de Ofertas_<versão>_x64-setup.exe`. O aplicativo abre sem terminal externo e reúne configuração, operação, histórico, WhatsApp e logs em uma única janela.

- Fechar a janela mantém o aplicativo na bandeja do Windows.
- “Iniciar com o Windows” e “Ligar o bot automaticamente” são opções independentes e vêm desativadas.
- Na primeira execução, use **Configurações → Importar instalação atual** para copiar `.env`, histórico e sessão do Mercado Livre. A pasta original não é alterada.
- Os dados ficam em `%LOCALAPPDATA%\br.com.kaiodiniz.botofertas` e não são incluídos no instalador.
- Use **Sair completamente** no menu da bandeja para encerrar também o backend.
- O aplicativo procura atualizações assinadas no GitHub automaticamente. Você pode atualizar imediatamente ou adiar; o aviso permanece no rodapé para continuar depois.
- O WhatsApp começa desativado. Para ativar, abra **Configurações → WhatsApp**, conecte pelo QR Code e escolha um grupo, um Canal ou os dois.
- Depois de ativado, o aplicativo tenta restaurar a conexão do WhatsApp automaticamente sempre que é aberto. Isso não liga o bot nem reenvia pendências.
- Para usar um Canal, cole seu link público ou ID `@newsletter`, clique em **Validar Canal** e confirme que o número conectado é administrador ou proprietário.
- Grupo e Canal recebem o mesmo texto e a mesma oferta. Com a foto completa desligada, o grupo usa a prévia expandida e o Canal usa um cartão compacto com a foto incorporada, compatível com o WhatsApp móvel. Quando ambos estão ativos, o aplicativo aguarda cinco segundos entre os envios.
- Se um envio ao WhatsApp falhar, ele fica visível na área **WhatsApp** por até seis horas. O aplicativo não reenvia sozinho; use **Enviar agora** quando quiser, em no máximo cinco tentativas manuais.
- Se a conexão do WhatsApp cair, o aplicativo tenta recuperá-la até cinco vezes. Sessão removida ou cinco falhas consecutivas devolvem o controle ao botão manual.
- Falhas conhecidas de descriptografia de mensagens recebidas são resumidas no console sem ocultar erros operacionais nem interferir nos envios.
- A sessão do WhatsApp fica somente em `%LOCALAPPDATA%\br.com.kaiodiniz.botofertas\data\whatsapp-session` e não entra no instalador.
- A aba **Buscar produtos** consulta as plataformas ativas sem pausar o bot. Ela mostra até três dos melhores resultados afiliados de cada marketplace e copia o texto completo já formatado, sem publicar nem registrar a pesquisa no histórico.
- Entre ofertas do mesmo ciclo, o bot sorteia uma pausa de **2 a 5 minutos** (em segundos). Depois que o ciclo automático termina, sorteia **40 a 60 minutos** até o próximo. A Visão geral e o Console exibem as faixas, o tempo sorteado e a contagem regressiva. O intervalo de cinco segundos entre grupo e Canal não muda.

O ícone **?** ao lado de cada configuração mostra uma explicação ao passar o mouse ou receber foco pelo teclado. No modo **Todos os grupos**, cooldown, limites e contagem de mensagens continuam separados por grupo, enquanto os limites globais continuam compartilhados. A mensagem recebida é um gatilho; o texto dela não é interpretado para escolher o post.

Se ainda não houver campanha com post ativo, salve a automação **desativada** e ative-a depois de concluir esses cadastros. O formulário mostra somente os campos aplicáveis à regra ou atraso escolhidos. Durante o desenvolvimento, `npm start` e `npm run dev` recompilam os componentes locais quando necessário; feche a instância anterior antes de reiniciar.

O instalador ainda não possui assinatura digital e pode exibir um aviso do Windows SmartScreen. Confira a origem do arquivo antes de executá-lo; não é necessário desativar mecanismos de segurança do Windows.

### Comandos npm

Execute na raiz do projeto:

```powershell
npm start                         # desenvolvimento
npm test                          # testes da interface
npm run whatsapp:test             # testes da ponte local do WhatsApp
npm run whatsapp:build            # gera o executável Windows x64 da ponte
npm run build                     # testes + backend + instalador
npm run set-version -- 0.5.1      # sincroniza a versão em todo o projeto
npm run release                   # build assinado + rascunho da GitHub Release
npm run release:test              # testa a automação da release sem publicar
```

`npm run release` gera o instalador, o arquivo `.sig` e o `latest.json` em `desktop/src-tauri/target/release/bundle/nsis`. Depois, cria automaticamente uma GitHub Release em **rascunho**, com título e tag `v<versão>` e uma descrição formada pelas seções posteriores à última release ou rascunho criado. Nenhum arquivo é enviado: você anexa os três arquivos ao rascunho e publica a release manualmente quando estiver pronto.

O build interrompe na primeira etapa com falha, mantendo o motivo original no terminal. As dependências Rust são preservadas por `Cargo.lock` e verificadas com `--locked`. Para mudar a versão do aplicativo, use `npm run set-version -- X.Y.Z`; não substitua números globalmente no lockfile, pois outras dependências podem usar o mesmo número.

Antes da primeira execução, instale e autentique o GitHub CLI:

```powershell
winget install --id GitHub.cli
gh auth login
```

O rascunho pode ser criado com alterações locais ainda não commitadas. Antes de publicar definitivamente a release no GitHub, faça commit e push do código correspondente. Executar novamente o comando na mesma versão atualiza a descrição do rascunho existente.

> Guarde um backup seguro de `desktop/src-tauri/tauri.key`. Essa chave é ignorada pelo Git, nunca deve ser publicada e é necessária para todas as atualizações futuras. Se ela for perdida, instalações existentes não aceitarão novas versões.

## Painel web legado

**Dê dois cliques em `PAINEL.bat`.** Ele prepara o ambiente sozinho e abre um painel no seu navegador, onde você faz tudo com formulário e botões — sem terminal:

- preenche a configuração (token, IDs, tags) num formulário;
- descobre os IDs do Telegram com o botão **🔎 Detectar IDs**;
- instala o navegador e faz o **login do Mercado Livre** por botões;
- testa as fontes (ML/Shopee/Amazon/AliExpress) e vê as ofertas na hora;
- **liga/desliga o bot** e acompanha o log ao vivo.

Na primeira vez, se o `uv` não estiver instalado, o `PAINEL.bat` instala e pede para você reabrir — só seguir a tela. Antes, tenha em mãos: o **token** do bot (@BotFather), um **canal** com o bot como **administrador**, e suas **contas de afiliado**.

> Prefere o terminal? O passo a passo manual está logo abaixo (dá no mesmo).

---

## Passo a passo (pelo terminal)

### 0. Instalar o uv (uma vez)
O projeto usa o [uv](https://docs.astral.sh/uv/) (gerenciador de Python — ele baixa o Python sozinho, você não precisa instalar Python separado). Abra o **PowerShell** e cole:
```powershell
winget install astral-sh.uv
```
Feche e reabra o PowerShell depois de instalar.

### 1. Baixar e abrir a pasta
Baixe o .zip, extraia para uma pasta (ex: `C:\ofertas-bot`) e entre nela no PowerShell:
```powershell
cd C:\ofertas-bot
```

### 2. Instalar as dependências
```powershell
uv sync
uv run python -m ofertas instalar-navegador
```
(O segundo comando baixa o navegador que gera os links do Mercado Livre, ~120 MB.)

### 3. Criar o bot no Telegram
Fale com o [@BotFather](https://t.me/BotFather) → `/newbot` → escolha um nome e um @username → **copie o token** que ele te dá.

### 4. Criar o canal e colocar o bot como admin
Crie um canal no Telegram. Abra os detalhes do canal → **Administradores** → adicione o seu bot com permissão de **Publicar mensagens**.

### 5. Preencher o `.env`
```powershell
Copy-Item .env.example .env
notepad .env
```
Preencha (o que você não tiver ainda, deixe em branco e preencha depois):
- `TELEGRAM_BOT_TOKEN` — o token do passo 3.
- `TELEGRAM_OWNER_ID` e `TELEGRAM_CHAT_ID` — o jeito fácil: salve o token, rode o bot (passo 7), mande `/id` para ele no privado (dá o seu **owner id**) e encaminhe um post do canal para ele (dá o **chat id**). Depois cole os dois no `.env`.
- `ML_ETIQUETA` — a "Etiqueta em uso" que aparece no [Linkbuilder](https://www.mercadolivre.com.br/afiliados/linkbuilder) do painel de afiliados do Mercado Livre.
- `AMAZON_TAG` — sua tag do [Amazon Associados](https://associados.amazon.com.br) (algo como `seunome-20`).
- `AMAZON_CREDENTIAL_ID` / `SECRET` — opcional (Creators API). Sem isso o bot funciona mesmo assim.
- `SHOPEE_APP_ID` / `SHOPEE_APP_SECRET` — no [painel de afiliados Shopee](https://affiliate.shopee.com.br), menu **Abrir API** (a aprovação pode demorar alguns dias).
- `ALIEXPRESS_APP_KEY` / `ALIEXPRESS_APP_SECRET` — credenciais da aplicação com acesso à Affiliate API no AliExpress Open Platform.
- `ALIEXPRESS_TRACKING_ID` — identificador da campanha no AliExpress Portals. Ele é obrigatório para os links rastreáveis; não é o App Key.

### 6. Login no Mercado Livre (uma vez só)
```powershell
uv run python -m ofertas ml-login
```
Abre um Chrome normal. Faça login na sua conta de afiliado, confira que o Linkbuilder aparece logado e **feche o navegador**. A sessão fica salva e o bot passa a gerar os links sozinho.

### 7. Conferir e rodar
```powershell
uv run python -m ofertas check     # mostra o que ainda falta configurar
uv run python -m ofertas run       # liga o bot (ou dê 2 cliques no run.bat)
```
Cole um link de produto no privado do bot para testar, ou espere o primeiro ciclo automático.

---

## Ajustes — `config.yaml`
Intervalo entre ciclos, quantos posts por vez, desconto mínimo, horário ativo e o **escopo do canal**. Por padrão o bot pega **ofertas de todas as categorias**. No aplicativo desktop, abra **Configurações → Categorias dos produtos** para escolher os nichos do próximo ciclo. Se nada estiver marcado, o bot continua pesquisando todas as categorias.

## Deixar rodando sozinho
- O bot posta enquanto a janela estiver aberta e o PC ligado. O `run.bat` reinicia sozinho se cair.
- `horario_ativo` no `config.yaml` evita posts de madrugada (padrão 08:00–23:00).
- Para o PC não dormir: Configurações → Sistema → Energia → *Suspender: nunca*.
- Iniciar junto com o Windows: `Win+R` → `shell:startup` → atalho para o `run.bat`.

---

## Problemas comuns

**`Failed to spawn: python` / "Uma política de Controle de Aplicativo bloqueou este arquivo"**
O **Smart App Control** do Windows 11 bloqueia programas sem assinatura (inclusive o Python que o uv baixa). Para desativar: aperte **Windows**, digite `Controle inteligente de aplicativos`, abra, marque **Desativado**, confirme e **reinicie o PC**. Isso não desliga o antivírus (o Windows Defender continua ativo). Obs.: uma vez desativado, o Smart App Control só volta a ligar reinstalando o Windows.

**`uv` não é reconhecido**
Feche e reabra o PowerShell depois de instalar o uv (passo 0).

**`testar ml` não acha ofertas / links param de sair**
Os sites mudam de layout de vez em quando. Refaça o `ml-login` (a sessão pode ter expirado) e, se persistir, os seletores ficam em `ofertas/sources/`.

---

## ⚖️ Uso responsável
- **Divulgação obrigatória**: os programas de afiliado (Amazon principalmente) exigem avisar que os links geram comissão. Coloque na descrição do canal algo como *"Contém links de afiliado; podemos receber comissão pelas compras, sem custo extra para você."*
- Respeite os termos de cada plataforma e não abuse da frequência de busca (os padrões do `config.yaml` já são comedidos).
- Os preços mudam a qualquer momento; o post reflete o preço no instante da coleta.

## Estrutura
```
ofertas/
├── main.py            # comandos (check, run, converter, postar, ml-login, testar)
├── bot_interativo.py  # bot do Telegram (conversor + agendador)
├── pipeline.py        # coleta → filtros → gera links → posta
├── formatter.py       # visual do post
├── db.py              # banco anti-repetição
├── config.py          # lê .env + config.yaml
└── sources/           # mercadolivre.py, shopee.py, amazon.py, aliexpress.py
```
