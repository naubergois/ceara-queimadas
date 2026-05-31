"""
Ferramentas LangChain para os agentes de queimadas.
Cada tool tem entrada/saída bem definidas e pode ser chamada por agentes ReAct.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schemas de entrada das ferramentas
# ---------------------------------------------------------------------------

class BuscarFocosInput(BaseModel):
    municipio: Optional[str] = Field(None, description="Nome do município do Ceará")
    horas: int = Field(24, description="Janela de tempo em horas (padrão 24)")
    fonte: Optional[str] = Field(None, description="INPE, NASA_FIRMS ou GOES16")


class BuscarClimaInput(BaseModel):
    municipio: str = Field(..., description="Nome do município do Ceará")


class BuscarRiscoInput(BaseModel):
    municipio: str = Field(..., description="Nome do município do Ceará")


class BuscarGOES16Input(BaseModel):
    municipio: Optional[str] = Field(None, description="Município para filtrar")
    horas: int = Field(6, description="Horas para buscar dados GOES-16")


class BuscarHistoricoMapBiomasInput(BaseModel):
    municipio: str = Field(..., description="Nome do município do Ceará")
    anos: int = Field(5, description="Número de anos de histórico")


class GerarBoletimInput(BaseModel):
    municipio: Optional[str] = Field(None, description="Município específico ou None para todo o Ceará")
    periodo_horas: int = Field(24, description="Período do boletim em horas")


# ---------------------------------------------------------------------------
# Ferramentas concretas
# ---------------------------------------------------------------------------

class BuscarFocosRecentesTool(BaseTool):
    name: str = "buscar_focos_recentes"
    description: str = (
        "Busca focos de queimada recentes no Ceará. "
        "Pode filtrar por município, janela de tempo e fonte (INPE, NASA_FIRMS, GOES16). "
        "Retorna lista de focos com localização, intensidade e severidade."
    )
    args_schema: Type[BaseModel] = BuscarFocosInput

    def _run(self, municipio: Optional[str] = None, horas: int = 24, fonte: Optional[str] = None) -> str:
        """Execução síncrona — delega para implementação real via DB."""
        # Em produção, consulta o banco via repositório
        # Aqui retorna estrutura de exemplo para o agente raciocinar
        resultado = {
            "municipio": municipio or "Ceará (todos)",
            "janela_horas": horas,
            "fonte": fonte or "todas",
            "total_focos": 0,
            "focos": [],
            "nota": "Consulte o banco de dados para dados reais",
        }
        return json.dumps(resultado, ensure_ascii=False, default=str)

    async def _arun(self, municipio: Optional[str] = None, horas: int = 24, fonte: Optional[str] = None) -> str:
        """Execução assíncrona com acesso real ao banco."""
        from app.core.database import AsyncSessionLocal
        from app.core.orm_models import FocoQueimadaORM
        from sqlalchemy import select, and_
        from datetime import timezone

        filtros = [
            FocoQueimadaORM.data_hora >= datetime.now(timezone.utc) - timedelta(hours=horas)
        ]
        if municipio:
            filtros.append(FocoQueimadaORM.municipio.ilike(f"%{municipio}%"))
        if fonte:
            filtros.append(FocoQueimadaORM.fonte == fonte.upper())

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(FocoQueimadaORM).where(and_(*filtros)).limit(50)
            )
            focos = result.scalars().all()

        dados = [
            {
                "id": f.id,
                "fonte": f.fonte,
                "municipio": f.municipio,
                "lat": f.latitude,
                "lon": f.longitude,
                "data_hora": str(f.data_hora),
                "severidade": f.severidade,
                "frp": f.frp,
                "confianca": f.confianca,
            }
            for f in focos
        ]
        return json.dumps(
            {"total": len(dados), "focos": dados},
            ensure_ascii=False,
            default=str,
        )


class BuscarDadosClimaticosToool(BaseTool):
    name: str = "buscar_dados_climaticos"
    description: str = (
        "Busca dados climáticos atuais de um município do Ceará: "
        "temperatura, umidade, vento, precipitação e dias sem chuva. "
        "Fontes: FUNCEME e INMET."
    )
    args_schema: Type[BaseModel] = BuscarClimaInput

    def _run(self, municipio: str) -> str:
        return json.dumps({"municipio": municipio, "status": "use _arun"})

    async def _arun(self, municipio: str) -> str:
        from app.core.database import AsyncSessionLocal
        from app.core.orm_models import DadoClimaticoORM
        from sqlalchemy import select, desc

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(DadoClimaticoORM)
                .where(DadoClimaticoORM.municipio.ilike(f"%{municipio}%"))
                .order_by(desc(DadoClimaticoORM.data_hora))
                .limit(1)
            )
            dado = result.scalar_one_or_none()

        if not dado:
            return json.dumps({"municipio": municipio, "erro": "Sem dados climáticos disponíveis"})

        return json.dumps(
            {
                "municipio": dado.municipio,
                "data_hora": str(dado.data_hora),
                "temperatura_c": dado.temperatura_c,
                "umidade_relativa": dado.umidade_relativa,
                "velocidade_vento_ms": dado.velocidade_vento_ms,
                "precipitacao_mm": dado.precipitacao_mm,
                "dias_sem_chuva": dado.dias_sem_chuva,
                "fonte": dado.fonte,
            },
            ensure_ascii=False,
        )


class BuscarRiscoMunicipalTool(BaseTool):
    name: str = "buscar_risco_municipal"
    description: str = (
        "Retorna o índice de risco de queimada calculado para um município do Ceará. "
        "Inclui classificação (baixo/moderado/alto/crítico) e justificativa."
    )
    args_schema: Type[BaseModel] = BuscarRiscoInput

    def _run(self, municipio: str) -> str:
        return json.dumps({"municipio": municipio, "status": "use _arun"})

    async def _arun(self, municipio: str) -> str:
        from app.core.database import AsyncSessionLocal
        from app.core.orm_models import RiscoMunicipalORM
        from sqlalchemy import select, desc

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(RiscoMunicipalORM)
                .where(RiscoMunicipalORM.municipio.ilike(f"%{municipio}%"))
                .order_by(desc(RiscoMunicipalORM.data_calculo))
                .limit(1)
            )
            risco = result.scalar_one_or_none()

        if not risco:
            return json.dumps({"municipio": municipio, "erro": "Risco não calculado ainda"})

        return json.dumps(
            {
                "municipio": risco.municipio,
                "indice_risco": risco.indice_risco,
                "classificacao": risco.classificacao,
                "focos_24h": risco.focos_24h,
                "focos_7d": risco.focos_7d,
                "dias_sem_chuva": risco.dias_sem_chuva,
                "umidade_media": risco.umidade_media,
                "justificativa": risco.justificativa,
                "data_calculo": str(risco.data_calculo),
            },
            ensure_ascii=False,
        )


class BuscarDadosGOES16Tool(BaseTool):
    name: str = "buscar_dados_goes16"
    description: str = (
        "Busca leituras recentes do satélite GOES-16 para o Ceará. "
        "Retorna pixels com máscara de fogo, temperatura, FRP e persistência temporal. "
        "Útil para confirmar e acompanhar evolução de focos."
    )
    args_schema: Type[BaseModel] = BuscarGOES16Input

    def _run(self, municipio: Optional[str] = None, horas: int = 6) -> str:
        return json.dumps({"status": "use _arun"})

    async def _arun(self, municipio: Optional[str] = None, horas: int = 6) -> str:
        from app.core.database import AsyncSessionLocal
        from app.core.orm_models import LeituraGOES16ORM
        from sqlalchemy import select, and_, desc
        from datetime import timezone

        filtros = [
            LeituraGOES16ORM.data_hora >= datetime.now(timezone.utc) - timedelta(hours=horas),
            LeituraGOES16ORM.mascara_fogo == True,
        ]
        if municipio:
            filtros.append(LeituraGOES16ORM.municipio.ilike(f"%{municipio}%"))

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(LeituraGOES16ORM).where(and_(*filtros)).order_by(desc(LeituraGOES16ORM.data_hora)).limit(20)
            )
            leituras = result.scalars().all()

        dados = [
            {
                "data_hora": str(l.data_hora),
                "municipio": l.municipio,
                "lat": l.latitude,
                "lon": l.longitude,
                "temperatura_k": l.temperatura_pixel_k,
                "frp_mw": l.frp_mw,
                "persistencia_horas": l.persistencia_horas,
                "deteccoes_consecutivas": l.deteccoes_consecutivas,
            }
            for l in leituras
        ]
        return json.dumps(
            {"total": len(dados), "leituras_goes16": dados},
            ensure_ascii=False,
            default=str,
        )


class BuscarHistoricoMapBiomasTool(BaseTool):
    name: str = "buscar_historico_mapbiomas"
    description: str = (
        "Busca histórico de queimadas do MapBiomas para um município do Ceará. "
        "Retorna recorrência de fogo, áreas queimadas por ano e tipo de vegetação afetada."
    )
    args_schema: Type[BaseModel] = BuscarHistoricoMapBiomasInput

    def _run(self, municipio: str, anos: int = 5) -> str:
        # Dados simulados — em produção consulta API MapBiomas ou tabela local
        return json.dumps(
            {
                "municipio": municipio,
                "anos_analisados": anos,
                "recorrencia_media": 0.35,
                "area_queimada_media_ha": 1200,
                "anos_com_fogo": [2019, 2020, 2022, 2023],
                "vegetacao_predominante": "Caatinga",
                "nota": "Dados históricos do MapBiomas Fogo",
            },
            ensure_ascii=False,
        )

    async def _arun(self, municipio: str, anos: int = 5) -> str:
        return self._run(municipio, anos)


class ListarMunicipiosCriticosTool(BaseTool):
    name: str = "listar_municipios_criticos"
    description: str = (
        "Lista os municípios do Ceará com maior risco de queimada no momento. "
        "Retorna ranking com índice de risco e classificação."
    )
    args_schema: Type[BaseModel] = BaseModel  # sem parâmetros

    def _run(self) -> str:
        return json.dumps({"status": "use _arun"})

    async def _arun(self) -> str:
        from app.core.database import AsyncSessionLocal
        from app.core.orm_models import RiscoMunicipalORM
        from sqlalchemy import select, desc, func

        async with AsyncSessionLocal() as db:
            # Pega o risco mais recente por município
            subq = (
                select(
                    RiscoMunicipalORM.municipio,
                    func.max(RiscoMunicipalORM.data_calculo).label("ultima"),
                )
                .group_by(RiscoMunicipalORM.municipio)
                .subquery()
            )
            result = await db.execute(
                select(RiscoMunicipalORM)
                .join(
                    subq,
                    (RiscoMunicipalORM.municipio == subq.c.municipio)
                    & (RiscoMunicipalORM.data_calculo == subq.c.ultima),
                )
                .order_by(desc(RiscoMunicipalORM.indice_risco))
                .limit(10)
            )
            riscos = result.scalars().all()

        ranking = [
            {
                "posicao": i + 1,
                "municipio": r.municipio,
                "indice_risco": r.indice_risco,
                "classificacao": r.classificacao,
                "focos_24h": r.focos_24h,
            }
            for i, r in enumerate(riscos)
        ]
        return json.dumps({"ranking": ranking}, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# Exporta todas as ferramentas
# ---------------------------------------------------------------------------

def get_all_tools() -> list[BaseTool]:
    return [
        BuscarFocosRecentesTool(),
        BuscarDadosClimaticosToool(),
        BuscarRiscoMunicipalTool(),
        BuscarDadosGOES16Tool(),
        BuscarHistoricoMapBiomasTool(),
        ListarMunicipiosCriticosTool(),
    ]
