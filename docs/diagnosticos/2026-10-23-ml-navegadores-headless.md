# Teste de coleta do Mercado Livre sem janela

Data: 23/10/2026. Ambiente: Windows x64, máquina local do usuário.

## Resultado

O CloakBrowser coletou ofertas em três consultas sem janela. O Camoufox não retornou produtos nas duas consultas realizadas. O Chrome atual, usado como controle com perfil novo, pediu verificação da conta.

| Navegador | Consulta | Resultado | Tempo da consulta |
| --- | --- | --- | --- |
| Chrome 155.0.8059.86 | Ofertas gerais, perfil novo | HTTP 200, redirecionamento para `/gz/account-verification`, zero ofertas | 15,62 s |
| Camoufox 156.0.1-beta.36 | Ofertas gerais, perfil novo | HTTP 200 em `/ofertas`, nenhum cartão encontrado durante a espera | 35,93 s |
| Camoufox 156.0.1-beta.36 | Ofertas gerais, reabertura do mesmo perfil | HTTP 200, `/captcha/wall`, página “Segurança — Mercado Livre”, zero ofertas | 12,64 s |
| CloakBrowser Chromium 146.0.7680.177.5 | Ofertas gerais, perfil novo | 48 cartões e 48 ofertas extraídas | 14,12 s |
| CloakBrowser Chromium 146.0.7680.177.5 | Ofertas gerais, reabertura do mesmo perfil | 48 cartões e 48 ofertas extraídas | 2,93 s |
| CloakBrowser Chromium 146.0.7680.177.5 | Informática (`MLB1648`), página 2, nova reabertura | 48 cartões e 48 ofertas extraídas | 2,68 s |

Os tempos medem navegação e inspeção, não instalação nem inicialização completa dos navegadores. As 48 ofertas de cada consulta não representam necessariamente produtos diferentes entre consultas.

Em cada consulta bem-sucedida, as 48 ofertas tinham título, preço positivo, imagem e URL de produto preenchidos pelo parser existente do aplicativo. A consulta de Informática retornou, entre outros, tablet VAIO, processador Ryzen e projetor. Não foram testadas geração de links afiliados, entrega de imagens ou publicação nesta rodada.

## Condições e isolamento

- Todos os testes foram feitos com `headless=True`, sem janela visível, sem proxy e sem login no Mercado Livre.
- Cada navegador recebeu seu próprio perfil de teste. As repetições reutilizaram somente o respectivo perfil experimental.
- O Chrome foi iniciado pelo helper atual do projeto. Os outros navegadores foram iniciados por suas bibliotecas, reutilizando `ofertas.sources.mercadolivre._parse_pagina` para ler os produtos.
- Playwright 1.62.0 tanto no ambiente atual quanto no ambiente experimental; pacotes Camoufox 0.5.8 e CloakBrowser 0.6.3.
- Não houve interação com CAPTCHA, login, Linkbuilder, WhatsApp ou Telegram.
- O aplicativo instalado permaneceu aberto. Seu perfil `ml_profile`, suas credenciais e suas dependências não foram alterados.
- O ambiente experimental usou `BOT_OFERTAS_HOME` separado. Não houve execução do ciclo nem publicação.

## Materiais locais para reprodução

Ambiente Python, script `probe.py` e perfis experimentais:

`C:\Users\Kaio Diniz\AppData\Local\Temp\bot-ml-camoufox-f32eb7fb43a84c78bc600c70b2de5882`

O script aceita `chrome`, `camoufox` ou `cloakbrowser`, além de `--attempt`, `--category` e `--page`. Executar a partir da raiz do projeto; usar o Python atual do projeto para o controle Chrome e o Python da pasta `venv` experimental para os demais. O script imprime os resultados em JSON no terminal e não gera links nem publica ofertas. Esses materiais estão em pasta temporária e podem ser removidos pelo Windows.

Os navegadores baixados permanecem nos caches próprios para eventual continuação dos testes:

- Camoufox: `%LOCALAPPDATA%\camoufox\camoufox\Cache` (download informado: aproximadamente 1,3 GB).
- CloakBrowser: `C:\Users\Kaio Diniz\.cloakbrowser\chromium-146.0.7680.177.5` (download informado: 535 MB; o instalador verificou assinatura e SHA-256).

## Conclusão e limites

O CloakBrowser é o candidato sustentado por este teste inicial para uma integração restrita à coleta. Três sucessos locais não provam disponibilidade permanente nem ausência de bloqueios futuros. Não houve teste prolongado entre ciclos, teste autenticado ou comparação de consumo de memória.

O resultado negativo do Camoufox se limita ao perfil sem autenticação e à versão testada. Não demonstra que uma sessão autenticada falharia; também não justifica substituí-lo no aplicativo neste momento.

A versão do CloakBrowser testada foi a gratuita disponibilizada sem chave. Versões mais recentes não foram testadas. Seu binário tem licença distinta do wrapper MIT, com restrições de redistribuição: a inclusão no instalador precisa ser avaliada antes de distribuir o app. A documentação distingue listagem como dependência, com download pelo usuário nos canais oficiais, de distribuição do binário junto ao produto.

O fluxo de produção continua inalterado. Nenhuma integração foi implementada, nenhuma versão foi incrementada e nenhum instalador foi gerado nesta rodada de testes.

Referências oficiais:

- https://github.com/CloakHQ/cloakbrowser
- https://github.com/CloakHQ/CloakBrowser/blob/main/BINARY-LICENSE.md
- https://github.com/daijro/camoufox
- https://camoufox.com/python/installation/
- https://camoufox.com/python/usage/

## Integração posterior — versão 0.18.6

Após autorização do usuário, o coletor passou a tentar acesso público, CloakBrowser e, em caso de falha, a recuperação existente pelo Chrome. A integração fica restrita à coleta de ofertas; pesquisa manual e Linkbuilder mantêm o navegador anterior.

- Perfil próprio: `data/ml_coleta_profile`.
- Instalação pelo botão existente **Instalar navegador**, junto do Chromium. O ciclo não baixa o binário; se ele estiver ausente, informa a instalação e usa a recuperação existente.
- Dependência Python `cloakbrowser==0.6.3` e navegador validado `146.0.7680.177.5`.
- Validação real da função integrada, categoria Informática: 48 ofertas, todas com preço e imagem.
- Validação real do backend empacotado por PyInstaller: `testar ml` coletou 48 ofertas pelo CloakBrowser após o acesso público pedir verificação, sem janela e sem publicar.
- 38 testes Python direcionados e 28 testes da interface aprovados; `cargo check` aprovado.
- O executável de validação foi gerado em pasta temporária; nenhum instalador ou release foi criado.
