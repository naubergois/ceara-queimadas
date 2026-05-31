"""
Modelos ORM SQLAlchemy para PostgreSQL + PostGIS.
"""

from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class FocoQueimadaORM(Base):
    __tablename__ = "focos_queimada"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    fonte: Mapped[str] = mapped_column(String(20))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    geom: Mapped[object] = mapped_column(Geometry("POINT", srid=4326), nullable=True)
    data_hora: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    municipio: Mapped[str | None] = mapped_column(String(100))
    estado: Mapped[str] = mapped_column(String(2), default="CE")
    bioma: Mapped[str | None] = mapped_column(String(50))
    satelite: Mapped[str | None] = mapped_column(String(50))
    sensor: Mapped[str | None] = mapped_column(String(50))
    confianca: Mapped[float | None] = mapped_column(Float)
    temperatura_k: Mapped[float | None] = mapped_column(Float)
    frp: Mapped[float | None] = mapped_column(Float)
    area_estimada_ha: Mapped[float | None] = mapped_column(Float)
    severidade: Mapped[str | None] = mapped_column(String(10))
    validado: Mapped[bool] = mapped_column(Boolean, default=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class EventoQueimadaORM(Base):
    __tablename__ = "eventos_consolidados"

    id_evento: Mapped[str] = mapped_column(String(36), primary_key=True)
    municipio: Mapped[str] = mapped_column(String(100))
    latitude_centroide: Mapped[float] = mapped_column(Float)
    longitude_centroide: Mapped[float] = mapped_column(Float)
    geom: Mapped[object] = mapped_column(Geometry("POINT", srid=4326), nullable=True)
    fontes: Mapped[list] = mapped_column(JSON, default=list)
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ultima_deteccao: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    quantidade_focos: Mapped[int] = mapped_column(Integer, default=1)
    severidade: Mapped[str] = mapped_column(String(10))
    confianca: Mapped[float] = mapped_column(Float)
    frp_total_mw: Mapped[float | None] = mapped_column(Float)
    area_estimada_ha: Mapped[float | None] = mapped_column(Float)
    persistencia_horas: Mapped[float | None] = mapped_column(Float)
    proxima_uc: Mapped[str | None] = mapped_column(String(200))
    proxima_area_urbana: Mapped[str | None] = mapped_column(String(200))
    distancia_uc_km: Mapped[float | None] = mapped_column(Float)
    distancia_urbana_km: Mapped[float | None] = mapped_column(Float)
    justificativa: Mapped[str] = mapped_column(Text, default="")
    goes16_confirmado: Mapped[bool] = mapped_column(Boolean, default=False)
    inpe_confirmado: Mapped[bool] = mapped_column(Boolean, default=False)
    firms_confirmado: Mapped[bool] = mapped_column(Boolean, default=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    alertas: Mapped[list["AlertaQueimadaORM"]] = relationship(back_populates="evento")


class LeituraGOES16ORM(Base):
    __tablename__ = "leituras_goes16"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    data_hora: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    geom: Mapped[object] = mapped_column(Geometry("POINT", srid=4326), nullable=True)
    mascara_fogo: Mapped[bool] = mapped_column(Boolean, default=False)
    temperatura_pixel_k: Mapped[float | None] = mapped_column(Float)
    frp_mw: Mapped[float | None] = mapped_column(Float)
    area_estimada_km2: Mapped[float | None] = mapped_column(Float)
    persistencia_horas: Mapped[float | None] = mapped_column(Float)
    deteccoes_consecutivas: Mapped[int] = mapped_column(Integer, default=0)
    municipio: Mapped[str | None] = mapped_column(String(100))
    produto: Mapped[str] = mapped_column(String(50), default="ABI-L2-FDCF")


class MunicipioORM(Base):
    __tablename__ = "municipios_ceara"

    codigo_ibge: Mapped[str] = mapped_column(String(7), primary_key=True)
    nome: Mapped[str] = mapped_column(String(100))
    regiao_planejamento: Mapped[str | None] = mapped_column(String(100))
    populacao: Mapped[int | None] = mapped_column(Integer)
    area_km2: Mapped[float | None] = mapped_column(Float)
    latitude_centroide: Mapped[float] = mapped_column(Float)
    longitude_centroide: Mapped[float] = mapped_column(Float)
    geom: Mapped[object] = mapped_column(Geometry("MULTIPOLYGON", srid=4326), nullable=True)
    tem_uc: Mapped[bool] = mapped_column(Boolean, default=False)
    tem_area_urbana: Mapped[bool] = mapped_column(Boolean, default=True)


class RiscoMunicipalORM(Base):
    __tablename__ = "risco_municipal"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    municipio: Mapped[str] = mapped_column(String(100))
    codigo_ibge: Mapped[str] = mapped_column(String(7))
    data_calculo: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    indice_risco: Mapped[float] = mapped_column(Float)
    classificacao: Mapped[str] = mapped_column(String(10))
    focos_24h: Mapped[int] = mapped_column(Integer, default=0)
    focos_48h: Mapped[int] = mapped_column(Integer, default=0)
    focos_7d: Mapped[int] = mapped_column(Integer, default=0)
    dias_sem_chuva: Mapped[int | None] = mapped_column(Integer)
    umidade_media: Mapped[float | None] = mapped_column(Float)
    temperatura_media: Mapped[float | None] = mapped_column(Float)
    vento_medio_ms: Mapped[float | None] = mapped_column(Float)
    historico_recorrencia: Mapped[float | None] = mapped_column(Float)
    justificativa: Mapped[str] = mapped_column(Text, default="")


class DadoClimaticoORM(Base):
    __tablename__ = "dados_climaticos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    municipio: Mapped[str] = mapped_column(String(100))
    data_hora: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fonte: Mapped[str] = mapped_column(String(20))
    temperatura_c: Mapped[float | None] = mapped_column(Float)
    umidade_relativa: Mapped[float | None] = mapped_column(Float)
    velocidade_vento_ms: Mapped[float | None] = mapped_column(Float)
    direcao_vento_graus: Mapped[float | None] = mapped_column(Float)
    precipitacao_mm: Mapped[float | None] = mapped_column(Float)
    dias_sem_chuva: Mapped[int | None] = mapped_column(Integer)
    pressao_hpa: Mapped[float | None] = mapped_column(Float)
    indice_seca: Mapped[float | None] = mapped_column(Float)


class AlertaQueimadaORM(Base):
    __tablename__ = "alertas"

    id_alerta: Mapped[str] = mapped_column(String(36), primary_key=True)
    evento_id: Mapped[str] = mapped_column(String(36), ForeignKey("eventos_consolidados.id_evento"))
    nivel: Mapped[str] = mapped_column(String(15))
    municipio: Mapped[str] = mapped_column(String(100))
    mensagem: Mapped[str] = mapped_column(Text)
    recomendacao: Mapped[str] = mapped_column(Text)
    destinatarios: Mapped[list] = mapped_column(JSON, default=list)
    data_hora: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fontes_evidencia: Mapped[list] = mapped_column(JSON, default=list)
    agente_responsavel: Mapped[str] = mapped_column(String(50), default="")
    ferramentas_consultadas: Mapped[list] = mapped_column(JSON, default=list)
    nivel_confianca: Mapped[float] = mapped_column(Float, default=0.0)
    justificativa_tecnica: Mapped[str] = mapped_column(Text, default="")
    falso_positivo_suspeito: Mapped[bool] = mapped_column(Boolean, default=False)
    auditado: Mapped[bool] = mapped_column(Boolean, default=False)

    evento: Mapped["EventoQueimadaORM"] = relationship(back_populates="alertas")


class LogAgenteORM(Base):
    __tablename__ = "logs_agentes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    agente: Mapped[str] = mapped_column(String(50))
    acao: Mapped[str] = mapped_column(String(100))
    entrada: Mapped[dict] = mapped_column(JSON, default=dict)
    saida: Mapped[dict] = mapped_column(JSON, default=dict)
    ferramentas_chamadas: Mapped[list] = mapped_column(JSON, default=list)
    data_hora: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duracao_ms: Mapped[int | None] = mapped_column(Integer)
    sucesso: Mapped[bool] = mapped_column(Boolean, default=True)
    erro: Mapped[str | None] = mapped_column(Text)
    versao_modelo: Mapped[str] = mapped_column(String(50), default="")
