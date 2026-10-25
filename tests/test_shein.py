import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from ofertas.sources import shein
from ofertas.models import Oferta
from ofertas import pipeline, product_search, settings
from ofertas.desktop_service import DesktopService
from ofertas.desktop_protocol import parse_request
from tests.test_desktop_service import CaptureEmitter, RunningRuntime


CARD = '''<div class="product-card"><a class="goods-title-link" aria-label="Camiseta ação ☕"
href="/Produto-p-12345.html?mallCode=1">Camiseta ação ☕</a>
<div data-before-crop-src="//img.ltwebstatic.com/produto.jpg"></div>
<div class="final-price">R$<span>26</span><span>,94</span></div>
<div class="retail-price">R$31,95</div><div class="price-description">Estimado</div></div>'''

CATALOG_ITEM = {"goodsId": 123, "goodsName": "Camiseta ação ☕", "currency": "BRL",
    "goodsUrl": "https://br.shein.com/Camiseta-p-123-cat-1978.html", "salesPriceText": "R$21,95",
    "retailPrice": "R$31,95", "commission": "99.00", "extraCommission": "30.00",
    "discount": 99, "mainImage": "https://img.ltwebstatic.com/produto.jpg", "spuSales": "1.4k+"}


def catalog_body(items=None, page=1, more=False):
    return {"code": "0", "info": {"goodsList": [CATALOG_ITEM] if items is None else items,
        "currency": "BRL", "pageNum": page, "hasNextPage": more}}


class SheinCatalogTests(unittest.TestCase):
    def test_preco_real_sem_confundir_bonus_desconto_ou_link_pronto(self):
        offers = shein._ofertas_catalogo(catalog_body(), "AÇÃO")
        self.assertEqual(len(offers), 1)
        self.assertEqual((offers[0].preco, offers[0].desconto), (21.95, 31))
        self.assertEqual(offers[0].url_afiliado, "")
        self.assertIn("1.4k+", offers[0].extra)

    def test_valida_produtos_moeda_urls_e_duplicatas(self):
        invalid = [{**CATALOG_ITEM, **changes} for changes in [
            {"goodsId": "outro"}, {"goodsUrl": "https://evil.test/Camiseta-p-123.html"},
            {"goodsUrl": "https://br.shein.com/Camiseta-p-999.html"}, {"valid": False},
            {"currency": "USD"}, {"salesPriceText": "NaN"}, {"goodsName": None}]]
        self.assertEqual(len(shein._ofertas_catalogo(catalog_body(invalid + [CATALOG_ITEM, CATALOG_ITEM]))), 1)

    def test_nao_retorna_recomendacoes_aleatorias_para_termo_inexistente(self):
        self.assertEqual(shein._ofertas_catalogo(catalog_body(), "zzzxqv987654321"), [])
        self.assertEqual(shein._ofertas_catalogo(catalog_body([])), [])
        for body in [{"code": "403"}, {"code": "0", "info": {}},
                     {"code": "0", "info": {"goodsList": [], "currency": "USD"}}]:
            with self.assertRaises(shein.SheinError):
                shein._ofertas_catalogo(body)

    def page_with_responses(self, entries):
        page = MagicMock()
        page.url = shein.CATALOG_SEARCH
        page.goto.return_value.status = 200
        holder = {}
        page.on.side_effect = lambda event, callback: holder.update(callback=callback)
        def emit(_):
            if not entries:
                return
            keyword, body, path = entries.pop(0)
            response = Mock(url="https://m.shein.com" + path, status=200)
            response.request.post_data_json = {"keywords": keyword}
            response.json.return_value = body
            holder["callback"](response)
        page.wait_for_timeout.side_effect = emit
        return page

    def test_busca_espera_duas_paginas_e_ignora_resposta_de_outro_termo(self):
        page = self.page_with_responses([
            ("anterior", catalog_body(), shein.SEARCH_PATH),
            ("camiseta", catalog_body(), "/br/affiliate/api/seller/activity/goods/list"),
            ("camiseta", catalog_body([], more=True), shein.SEARCH_PATH),
            ("camiseta", catalog_body(page=2), shein.SEARCH_PATH),
        ])
        offers = shein._coletar_catalogo(page, "camiseta", 10)
        self.assertEqual(len(offers), 1)
        self.assertEqual(page.wait_for_timeout.call_count, 4)
        page.goto.assert_called_once_with(shein.CATALOG_SEARCH, wait_until="domcontentloaded", timeout=30_000)
        page.get_by_placeholder.return_value.fill.assert_called_once_with("camiseta", timeout=15_000)
        page.remove_listener.assert_called_once()

    def test_catalogo_geral_nao_aciona_pesquisa_e_respeita_limite(self):
        page = self.page_with_responses([(None, catalog_body(), shein.RECOMMEND_PATH)])
        offers = shein._coletar_catalogo(page, "", 1)
        self.assertEqual(len(offers), 1)
        page.get_by_placeholder.assert_not_called()
        self.assertEqual(page.goto.call_args.args[0], shein.CATALOG)

    def test_erro_do_painel_nao_vira_lista_vazia_e_remove_observador(self):
        page = self.page_with_responses([("camiseta", {"code": "401"}, shein.SEARCH_PATH)])
        with self.assertRaisesRegex(shein.SheinError, "Login da SHEIN"):
            shein._coletar_catalogo(page, "camiseta", 10)
        page.remove_listener.assert_called_once()

    def test_painel_sem_resposta_tem_prazo_e_preserva_pagina_recebida(self):
        page = self.page_with_responses([])
        with patch.object(shein.time, "monotonic", side_effect=[0, 21]):
            with self.assertRaisesRegex(shein.SheinError, "20 segundos"):
                shein._coletar_catalogo(page, "camiseta", 10)
        page = self.page_with_responses([("camiseta", catalog_body(more=True), shein.SEARCH_PATH)])
        with patch.object(shein.time, "monotonic", side_effect=[0, 1, 21]):
            self.assertEqual(len(shein._coletar_catalogo(page, "camiseta", 10)), 1)
        page.remove_listener.assert_called_once()

    def test_rodizio_de_termos_nao_mistura_categorias_ou_consulta_loja_publica(self):
        offer = shein._ofertas_catalogo(catalog_body())[0]
        with patch.object(shein.config, "fonte_shein", {"buscas": ["tênis", "camiseta", "legging"]}), \
             patch.object(shein, "_cursor", 0), \
             patch.object(shein, "_executar", side_effect=lambda callback, **kw: callback(Mock())) as execute, \
             patch.object(shein, "_coletar_catalogo", return_value=[offer]) as collect, \
             patch.object(shein, "_coletar_pagina") as public:
            self.assertEqual(shein.buscar_ofertas(30), [offer])
            self.assertEqual([call.args[1] for call in collect.call_args_list], ["tênis", "camiseta"])
            collect.reset_mock()
            shein.buscar_ofertas(30)
            self.assertEqual([call.args[1] for call in collect.call_args_list], ["legging", "tênis"])
            self.assertTrue(execute.call_args.kwargs["exige_sessao"])
            public.assert_not_called()


class SheinParserTests(unittest.TestCase):
    def test_dominios_links_curtos_e_impostores(self):
        for url in ["https://br.shein.com/Produto-p-123.html", "https://onelink.shein.com/abc", "https://shein.top/abc"]:
            self.assertTrue(shein.e_link(url))
        for url in ["https://evil.test/?shein.com", "https://shein.com.evil.test/a", "https://shein.com@127.0.0.1/a", "file://shein.com/a", "https://shein.com:22/a"]:
            self.assertFalse(shein.e_link(url))

    def test_precos_centavos_imagem_e_estimativa_sem_duplicatas(self):
        offers = shein._parse_cards(CARD + CARD)
        self.assertEqual(len(offers), 1)
        offer = offers[0]
        self.assertEqual(offer.titulo, "Camiseta ação ☕")
        self.assertEqual((offer.preco, offer.preco_original), (26.94, 31.95))
        self.assertEqual(offer.url_produto, "https://br.shein.com/Produto-p-12345.html")
        self.assertEqual(offer.imagem, "https://img.ltwebstatic.com/produto.jpg")
        self.assertIn("estimado", offer.extra)
        self.assertEqual(offer.url_afiliado, "")

    def test_cartoes_de_busca_e_precos_duplicados(self):
        html = CARD.replace('class="product-card"', 'class="bs-product-card"').replace('class="goods-title-link"','class="bs-product-card__goods-title-link"')
        html = html.replace('class="final-price"','class="bs-product-card__final-price"').replace('R$<span>26</span><span>,94</span>', 'R$26,94R$26,94')
        self.assertEqual(shein._parse_cards(html)[0].preco, 26.94)
        for invalid in [CARD.replace("26", "invalid").replace(",94", ""), CARD.replace('/Produto-p-12345.html?mallCode=1', 'https://evil.test/Produto-p-12345.html')]:
            self.assertEqual(shein._parse_cards(invalid), [])

    def test_prefere_titulo_a_rotulo_de_navegacao_da_imagem(self):
        html = CARD.replace('<a class="goods-title-link"', '<a href="/Produto-p-12345.html" aria-label="Café，查看商品详情"><img alt="Café"></a><a class="goods-title-link"')
        self.assertEqual(shein._parse_cards(html)[0].titulo,"Camiseta ação ☕")

    def test_detalhes_oficiais_nao_confundem_comissao_com_preco(self):
        offer = shein._oferta_convertida({"goodsBasicInfo": {"goodsId":123, "goodsName":"Ação & moda 👗",
            "salesPrice":21.95,"retailPrice":"R$31,95", "commission":"4.39", "commentRankAverage":"4.89",
            "spuSales":"1.4k+", "mainImageOfOriginImage":"http://img.ltwebstatic.com/produto.jpg"}}, "https://onelink.shein.com/teste", "https://br.shein.com/p-123.html")
        self.assertEqual(offer.preco, 21.95)
        self.assertEqual(offer.desconto, 31)
        self.assertIn("1.4k+", offer.extra)
        self.assertEqual(offer.imagem, "https://img.ltwebstatic.com/produto.jpg")

    def test_verificacao_http_login_e_captcha_nao_sao_zero_resultados(self):
        for path in ["/risk/challenge", "/risk/action/limit", "/user/auth/login", "/captcha/wall"]:
            with self.subTest(path=path), self.assertRaises(shein.SheinError):
                shein._verificar(SimpleNamespace(url="https://br.shein.com"+path))
        for value in ["NaN", "Infinity", -10, 0]:
            self.assertIsNone(shein._preco(value))


class SheinBrowserTests(unittest.TestCase):
    @patch("playwright.sync_api.sync_playwright")
    @patch("ofertas.sources.mercadolivre._achar_chrome", return_value="chrome.exe")
    @patch.object(shein, "_executar_cloak")
    def test_conversao_preserva_chrome_primeiro(self, cloak, chrome, playwright):
        self.assertEqual(shein._executar(lambda page: ["oferta"]), ["oferta"])
        cloak.assert_not_called()
        chromium = playwright.return_value.__enter__.return_value.chromium
        self.assertTrue(chromium.launch_persistent_context.call_args.kwargs["headless"])
        chromium.launch_persistent_context.return_value.close.assert_called_once()

    @patch.object(shein, "_contexto_chrome")
    @patch.object(shein, "_executar_cloak", return_value=["oferta"])
    def test_coleta_comeca_pelo_cloak_sem_visitar_site_no_chrome(self, cloak, chrome):
        callback = Mock()
        self.assertEqual(shein._executar(callback, coleta=True), ["oferta"])
        cloak.assert_called_once_with(callback, None)
        chrome.assert_not_called()

    @patch("playwright.sync_api.sync_playwright")
    @patch("ofertas.sources.mercadolivre._achar_chrome", return_value="chrome.exe")
    @patch.object(shein, "_executar_cloak", side_effect=shein.SheinError("verificação"))
    def test_coleta_recupera_com_chrome_oculto_quando_cloak_falha(self, cloak, chrome, playwright):
        callback = Mock(return_value=["oferta"])
        self.assertEqual(shein._executar(callback, coleta=True), ["oferta"])
        callback.assert_called_once()
        self.assertFalse(shein._LOCK.locked())

    @patch("playwright.sync_api.sync_playwright")
    @patch("ofertas.sources.mercadolivre._achar_chrome", return_value="chrome.exe")
    @patch.object(shein, "_executar_cloak", return_value=True)
    def test_fallback_transfere_apenas_sessao_shein(self, cloak, chrome, playwright):
        ctx = playwright.return_value.__enter__.return_value.chromium.launch_persistent_context.return_value
        cookie = {"domain":".shein.com","name":"teste","value":"local"}
        origin = {"origin":"https://m.shein.com","localStorage":[]}
        ctx.storage_state.return_value = {"cookies":[cookie,{"domain":".google.com","name":"outro","value":"privado"}],"origins":[origin,{"origin":"https://google.com","localStorage":[]}]}
        callback = Mock(side_effect=shein.SheinError("verificação"))
        self.assertTrue(shein._executar(callback))
        cloak.assert_called_once_with(callback, {"cookies":[cookie],"origins":[origin]})
        ctx.close.assert_called_once()
        self.assertFalse(shein._LOCK.locked())

    @patch("playwright.sync_api.sync_playwright")
    @patch("ofertas.sources.mercadolivre._achar_chrome", side_effect=RuntimeError("Chrome ausente"))
    @patch.object(shein, "_executar_cloak", side_effect=RuntimeError("binário indisponível"))
    def test_falhas_liberam_perfil_e_orientam_usuario(self, cloak, chrome, playwright):
        with self.assertRaisesRegex(shein.SheinError, "Instalar navegador"):
            shein._executar(lambda page: [])
        self.assertFalse(shein._LOCK.locked())

    @patch.object(shein, "tem_sessao", return_value=False)
    @patch("playwright.sync_api.sync_playwright")
    def test_conversao_sem_perfil_pede_login_sem_abrir_janela(self, playwright, session):
        with self.assertRaisesRegex(shein.SheinError, "Login da SHEIN"):
            shein.converter("https://br.shein.com/Produto-p-12345.html")
        playwright.assert_not_called()

    @patch("cloakbrowser.launch_persistent_context")
    @patch("ofertas.sources.mercadolivre.cloak_instalado", return_value=True)
    @patch.object(shein, "_contexto_chrome")
    def test_cloak_persiste_perfil_e_so_sincroniza_apos_novo_login(self, chrome, installed, launch):
        import os
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            profile = root / "chrome"
            (profile / "Default").mkdir(parents=True)
            session = {"cookies":[{"domain":".shein.com","name":"session","value":"local"}],"origins":[]}
            chrome.return_value.__enter__.return_value.storage_state.return_value = session
            with patch.object(shein,"PROFILE",profile), patch.object(shein,"CLOAK_PROFILE",root/"cloak"):
                callback = Mock(return_value=["oferta"])
                shein._executar_cloak(callback)
                shein._executar_cloak(callback)
                chrome.assert_called_once()
                launch.return_value.add_cookies.assert_called_once_with(session["cookies"])
                self.assertTrue(launch.call_args.kwargs["headless"])
                self.assertEqual(launch.call_args.args[0],str(root/"cloak"))
                marker = profile / ".bot-login"
                marker.touch()
                after = (root/"cloak"/".bot-session-imported").stat().st_mtime_ns + 1_000_000
                os.utime(marker,ns=(after,after))
                shein._executar_cloak(callback)
                self.assertEqual(chrome.call_count,2)
                self.assertEqual(launch.return_value.close.call_count,3)

    @patch("cloakbrowser.launch_persistent_context")
    @patch("ofertas.sources.mercadolivre.cloak_instalado", return_value=False)
    def test_nao_baixa_cloak_durante_coleta(self, installed, launch):
        with self.assertRaisesRegex(shein.SheinError,"Instalar navegador"):
            shein._executar_cloak(Mock())
        launch.assert_not_called()

    @patch.object(shein, "_executar")
    def test_busca_preserva_acentos_e_usa_catalogo_autenticado(self, execute):
        execute.side_effect = lambda callback, **kwargs: callback(MagicMock())
        with patch.object(shein, "_coletar_catalogo", return_value=[]) as collect:
            shein.buscar_produtos("tênis infantil")
        self.assertEqual(collect.call_args.args[1], "tênis infantil")
        self.assertTrue(execute.call_args.kwargs["exige_sessao"])
        self.assertNotIn("coleta", execute.call_args.kwargs)

    def test_aguarda_cartao_hidratado_sem_fazer_nova_requisicao(self):
        page = MagicMock()
        page.url = shein.HOME + "/super-deals"
        page.goto.return_value.status = 200
        page.content.side_effect = ['<div class="product-card"><a href="javascript:void(0)">Café</a></div>', CARD]
        offers = shein._coletar_pagina(page,page.url,10)
        self.assertEqual(len(offers),1)
        page.goto.assert_called_once()
        page.wait_for_timeout.assert_called_once_with(500)

    @patch.object(shein.time, "monotonic", side_effect=[0,21])
    def test_limita_espera_e_distingue_vazio_de_dados_incompletos(self, clock):
        page = MagicMock()
        page.url = shein.HOME + "/super-deals"
        page.goto.return_value.status = 200
        page.content.return_value = '<div class="product-card"></div>'
        page.locator.return_value.inner_text.return_value = "Produtos"
        with self.assertRaisesRegex(shein.SheinError,"20 segundos"):
            shein._coletar_pagina(page,page.url,10)
        page.wait_for_timeout.assert_not_called()
        clock.side_effect = [0,21]
        page.locator.return_value.inner_text.return_value = "Nenhum resultado"
        self.assertEqual(shein._coletar_pagina(page,page.url,10),[])

    @patch.object(shein, "_executar", side_effect=lambda callback, **kwargs: callback(MagicMock()))
    @patch.object(shein, "_converter_pagina")
    def test_enriquece_somente_ofertas_shein_sem_link(self, convert, execute):
        selected = Oferta("shein", "123", "Camiseta", "", "https://br.shein.com/Produto-p-123.html", 10, 100, 90)
        other = Oferta("amazon", "123", "Outro", "https://amazon.com.br/dp/123")
        ready = Oferta("shein", "321", "Pronto", "https://onelink.shein.com/pronto")
        convert.return_value = Oferta("shein", "123", "Camiseta", "https://onelink.shein.com/gerado", preco=21.95, preco_original=31.95)
        shein.gerar_links_afiliado([selected,other,ready])
        convert.assert_called_once()
        self.assertEqual(selected.desconto, 31)
        self.assertEqual(other.url_afiliado, "https://amazon.com.br/dp/123")
        self.assertEqual(ready.url_afiliado, "https://onelink.shein.com/pronto")


class SheinIntegrationTests(unittest.TestCase):
    def test_desativada_nao_muda_o_ciclo_e_falha_ativa_nao_para_outras_fontes(self):
        sources = {key:{"ativa":False} for key in ("fonte_ml", "fonte_amazon", "fonte_aliexpress")}
        sources.update(fonte_shopee={"ativa":True}, shopee_app_id="teste", shopee_app_secret="teste")
        offer = Oferta("shopee","1","Outra fonte","https://shopee.com.br/teste")
        with patch.multiple(pipeline.config,**sources), patch.object(pipeline.shopee,"buscar_ofertas",return_value=[offer]), patch.object(shein,"buscar_ofertas",side_effect=shein.SheinError("verificação")) as search:
            with patch.object(pipeline.config,"fonte_shein",{"ativa":False}):
                self.assertEqual(pipeline.coletar(),[offer])
                search.assert_not_called()
            with patch.object(pipeline.config,"fonte_shein",{"ativa":True}):
                self.assertEqual(pipeline.coletar(),[offer])
                search.assert_called_once()

    def test_busca_manual_converte_apenas_os_melhores(self):
        offers=[Oferta("shein",str(i),"Camiseta ação ☕","",f"https://br.shein.com/Produto-p-{i}.html",20,30) for i in range(5)]
        def links(selected):
            for offer in selected: offer.url_afiliado="https://onelink.shein.com/"+offer.id_produto
        with patch.object(shein,"buscar_produtos",return_value=offers), patch.object(shein,"gerar_links_afiliado",side_effect=links) as convert:
            result=product_search._buscar_fonte("shein","camiseta")
        self.assertEqual(len(result),3)
        self.assertEqual(len(convert.call_args.args[0]),3)
        self.assertTrue(all(o.url_afiliado for o in result))

    def test_salvamento_da_shein_preserva_configuracao_de_outras_fontes(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with patch.object(settings,"YAML_PATH",root/"config.yaml"), patch.object(settings,"ENV_PATH",root/".env"):
                settings.write_settings({"config":{"geral":{"max_posts_por_ciclo":3},"fontes":{"mercadolivre":{"ativa":True,"paginas":2},"amazon":{"ativa":True}}}})
                before=settings._read_yaml()
                settings.write_settings({"config":{"fontes":{"shein":{"ativa":True}}}})
                after=settings._read_yaml()
                self.assertEqual(before["fontes"]["mercadolivre"],after["fontes"]["mercadolivre"])
                self.assertEqual(before["fontes"]["amazon"],after["fontes"]["amazon"])
                self.assertTrue(after["fontes"]["shein"]["ativa"])

    def test_configuracoes_invalidas_shein_sao_recusadas(self):
        for source in [{"ativa":"false"},{"limite":0},{"limite":41},{"buscas":"camiseta"},{"buscas":[None]}]:
            with self.subTest(source=source), self.assertRaises(settings.SettingsError):
                settings._validate_yaml({"fontes":{"shein":source}})


class SheinServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_ciclo_revalida_preco_shein_e_preserva_publicacao_de_outra_fonte(self):
        offer=Oferta("shein","123","Camiseta","","https://br.shein.com/Produto-p-123.html",50,100)
        other=Oferta("shopee","321","Produto original","https://shopee.com.br/teste",preco=50,preco_original=100)
        def update(offers):
            offers[0].url_afiliado="https://onelink.shein.com/teste"
            offers[0].preco=100
        with patch.object(pipeline,"coletar",return_value=[offer,other]), patch.object(pipeline,"dentro_do_horario",return_value=True), \
             patch.object(pipeline.db,"ja_postada",return_value=False), patch.object(pipeline.db,"registrar"), \
             patch.object(pipeline.db,"preparar_entregas_whatsapp",return_value=[]), patch.object(pipeline,"read_settings",return_value={"preferences":{}}), \
             patch.object(pipeline,"postar_oferta",new_callable=AsyncMock) as post, patch.object(shein,"gerar_links_afiliado",side_effect=update), \
             patch.multiple(pipeline.config,desconto_minimo=25,preco_minimo=0,preco_maximo=0,max_posts_por_ciclo=3,espacamento_segundos=0):
            result=await pipeline.executar_ciclo(object())
        self.assertEqual(result,1)
        self.assertEqual(post.call_args.args[1],other)

    async def test_teste_da_fonte_valida_busca_e_um_link_sem_publicar(self):
        service=DesktopService(CaptureEmitter(),RunningRuntime())
        offers=[Oferta("shein","1","Camiseta ação","","https://br.shein.com/Produto-p-1.html",20)]
        with patch("ofertas.desktop_service.reload_config"), patch.object(shein,"buscar_ofertas",return_value=offers), patch.object(shein,"gerar_links_afiliado") as convert, patch.object(pipeline,"executar_ciclo") as cycle:
            result=await service.handle({"command":"test_source","payload":{"source":"shein"}})
        self.assertTrue(result["ok"])
        convert.assert_called_once_with(offers[:1])
        cycle.assert_not_called()
        self.assertTrue(service.runtime.running)

    async def test_login_tem_autorizacao_e_tempo_estendido_nos_dois_protocolos(self):
        self.assertEqual(parse_request('{"command":"start_shein_login"}')["command"],"start_shein_login")
        rust=(Path(__file__).parents[1]/"desktop/src-tauri/src/backend.rs").read_text(encoding="utf-8")
        self.assertIn('"start_shein_login"',rust.split("const ALLOWED:")[1].split("];",1)[0])
        self.assertIn('"start_shein_login"',rust.split("let long_running = [")[1].split("];",1)[0])


if __name__ == "__main__":
    unittest.main()
