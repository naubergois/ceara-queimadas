"""TASK-007: Testes para serviços backend — imports das funções/classes reais."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestDetector3Class:
    def test_municipios_list(self):
        from app.services.detector_3class import MUNICIPIOS
        assert len(MUNICIPIOS) >= 10
        assert "Fortaleza" in MUNICIPIOS
        assert len(MUNICIPIOS["Fortaleza"]) == 2

    def test_classify_municipality_import(self):
        from app.services.detector_3class import classify_municipality
        assert callable(classify_municipality)

    def test_detect_3class_import(self):
        from app.services.detector_3class import detect_3class
        assert callable(detect_3class)


class TestServicesImport:
    def test_firms_service_import(self):
        from app.services.firms_service import coletar_focos_firms
        assert callable(coletar_focos_firms)

    def test_firms_real_import(self):
        from app.services.firms_real import coletar_focos_firms_real
        assert callable(coletar_focos_firms_real)

    def test_clima_service_import(self):
        from app.services.clima_real import buscar_clima_municipios_ceara, buscar_clima_foco
        assert callable(buscar_clima_municipios_ceara)
        assert callable(buscar_clima_foco)

    def test_goes16_service_import(self):
        from app.services.goes16_service import coletar_dados_goes16
        assert callable(coletar_dados_goes16)

    def test_inpe_service_import(self):
        from app.services.inpe_service import coletar_focos_inpe
        assert callable(coletar_focos_inpe)

    def test_geo_service_import(self):
        from app.services.geo_service import (
            identificar_municipio,
            distancia_uc_mais_proxima,
            enriquecer_foco,
        )
        assert callable(identificar_municipio)
        assert callable(distancia_uc_mais_proxima)
        assert callable(enriquecer_foco)

    def test_alertas_real_import(self):
        from app.services.alertas_real import gerar_alertas_reais
        assert callable(gerar_alertas_reais)

    def test_predicao_v2_import(self):
        from app.services.predicao_v2 import DeterministicKoopmanV2, SimpleGNNPropagation
        assert DeterministicKoopmanV2 is not None
        assert SimpleGNNPropagation is not None


class TestAgentsImport:
    def test_explicador_agent_import(self):
        from app.agents.explicador_agent import explicar_foco
        assert callable(explicar_foco)

    def test_llm_factory_import(self):
        from app.agents.llm_factory import get_deepseek_model, llm_is_configured
        assert callable(get_deepseek_model)
        assert callable(llm_is_configured)

    def test_react_agent_import(self):
        from app.agents.react_agent import criar_agente_react, diagnosticar
        assert callable(criar_agente_react)
        assert callable(diagnosticar)

    def test_auditor_agent_import(self):
        from app.agents.auditor_agent import criar_agente_auditor, auditar_alerta
        assert callable(criar_agente_auditor)
        assert callable(auditar_alerta)

    def test_tools_import(self):
        from app.tools.queimada_tools import (
            BuscarFocosRecentesTool,
            BuscarDadosClimaticosToool,
            BuscarRiscoMunicipalTool,
            BuscarDadosGOES16Tool,
        )
        assert BuscarFocosRecentesTool is not None
        assert BuscarDadosClimaticosToool is not None

    def test_neko_explicador_import(self):
        from app.agents.neko_explicador_agent import (
            explicar_risco,
            simular_cenario,
            build_agent,
        )
        assert callable(build_agent)


class TestPipeline:
    def test_main_pipeline_import(self):
        """PipelineOrquestrador requer asyncpg (database); skip se ausente."""
        try:
            from app.pipeline.main_pipeline import PipelineOrquestrador
            assert PipelineOrquestrador is not None
        except ModuleNotFoundError as e:
            if "asyncpg" in str(e):
                pytest.skip("asyncpg not installed (database dependency)")
            raise

    def test_schemas(self):
        from app.models.schemas import (
            FocoQueimada,
            RiscoMunicipal,
            AlertaQueimada,
            EventoQueimada,
            BoletimTecnico,
        )
        assert FocoQueimada is not None
        assert RiscoMunicipal is not None

    def test_inovacao_models_init(self):
        from app.models.inovacao import (
            NeuralKoopmanOperator,
            PhysicsInformedGNN,
            RothermelLoss,
            NeKoPIGNN,
        )
        assert NeuralKoopmanOperator is not None
        assert PhysicsInformedGNN is not None
        assert RothermelLoss is not None
        assert NeKoPIGNN is not None
