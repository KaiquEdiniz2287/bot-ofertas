import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from ofertas import settings, pipeline, product_search
from ofertas.bot_interativo import BotRuntime, _job_ciclo
from ofertas.models import Oferta


class MarketplaceSelectionTests(unittest.TestCase):
    def test_desativar_fontes_preserva_chaves_e_parametros(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            with patch.multiple(settings,ENV_PATH=root/'.env',YAML_PATH=root/'config.yaml'),patch('ofertas.config.reload_config'):
                settings.write_settings({'env':{'AMAZON_TAG':'teste-20','AMAZON_CREDENTIAL_SECRET':'ação-secreta','ALIEXPRESS_APP_SECRET':'segredo'},'config':{'geral':{'max_posts_por_ciclo':3},'fontes':{'mercadolivre':{'ativa':True,'paginas':2},'amazon':{'ativa':True,'buscas':['café']},'aliexpress':{'ativa':True,'limite':40}}}})
                before=settings.read_env(root/'.env')
                settings.write_settings({'env':{'AMAZON_CREDENTIAL_SECRET':'','ALIEXPRESS_APP_SECRET':''},'config':{'fontes':{'mercadolivre':{'ativa':True},'amazon':{'ativa':False},'shopee':{'ativa':False},'aliexpress':{'ativa':False},'shein':{'ativa':False}}}})
                after=settings._read_yaml()['fontes']
                self.assertEqual(settings.read_env(root/'.env'),before)
                self.assertEqual(after['mercadolivre']['paginas'],2)
                self.assertEqual(after['amazon']['buscas'],['café'])
                self.assertEqual(after['aliexpress']['limite'],40)
                self.assertEqual([key for key,value in after.items() if value['ativa']],['mercadolivre'])

    def test_coleta_e_busca_consultam_somente_a_fonte_ativa(self):
        names=['mercadolivre','amazon','shopee','aliexpress','shein']
        config={f'fonte_{"ml" if key=="mercadolivre" else key}':{'ativa':key=='mercadolivre'} for key in names}
        offer=Oferta('mercadolivre','1','Café ☕','https://meli.la/teste',preco=20)
        with patch.multiple(pipeline.config,**config),patch.object(pipeline.mercadolivre,'tem_sessao',return_value=True),patch.object(pipeline.mercadolivre,'buscar_ofertas',return_value=[offer]) as ml,patch.object(pipeline.amazon,'buscar_ofertas') as amazon,patch.object(pipeline.shopee,'buscar_ofertas') as shopee,patch.object(pipeline.aliexpress,'buscar_ofertas') as ali,patch.object(pipeline.shein,'buscar_ofertas') as shein:
            self.assertEqual(pipeline.coletar(),[offer])
            ml.assert_called_once()
            for disabled in (amazon,shopee,ali,shein):disabled.assert_not_called()
            with patch.object(product_search,'_buscar_fonte',return_value=[offer]) as search:
                result=product_search.buscar('café')
                search.assert_called_once_with('mercadolivre','café')
                self.assertEqual(result['results'][0]['platform'],'mercadolivre')

    def test_agendamento_preserva_pausa_e_permite_reativar_fontes(self):
        callback=Mock()
        runtime=BotRuntime(state_callback=callback)
        queue=Mock()
        runtime._app=SimpleNamespace(job_queue=queue)
        sources={name:{'ativa':False} for name in ('fonte_ml','fonte_amazon','fonte_shopee','fonte_aliexpress','fonte_shein')}
        with patch.multiple(pipeline.config,**sources,chat_id='123',intervalo_minutos=45):
            self.assertFalse(runtime.ensure_cycle_scheduled())
            queue.run_once.assert_not_called()
            with patch.object(pipeline.config,'fonte_ml',{'ativa':True}):
                queue.jobs.return_value=[SimpleNamespace(callback=_job_ciclo)]
                self.assertFalse(runtime.ensure_cycle_scheduled())
                queue.run_once.assert_not_called()
                queue.jobs.return_value=[]
                self.assertTrue(runtime.ensure_cycle_scheduled())
                queue.run_once.assert_called_once()
                self.assertEqual(queue.run_once.call_args.kwargs['when'],30)
                self.assertIn('nextCycleAt',callback.call_args.args[0])
