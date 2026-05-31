"""
Schemas Pydantic para validação de todos os dados da plataforma.
Cobre focos de queimada, GOES-16, dados climáticos, alertas e respostas dos agentes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Foco de Queimada (INPE / NASA FIRMS / GOES-16)
# ---------------------------------------------------------------------------

class FocoQueimada(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    fonte: Literal["INPE", "NASA_FIRMS", "GOES16"]
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    data_hora: datetime
    municipio: Optional[str] = None
    estado: str = "CE"
    bioma: Optional[str] = None
    satelite: Optional[str] = None
    sensor: Optional[str] = None
    confianca: Optional[float] = Field(default=None, ge=0, le=100)
    temperatura_k: Optional[float] = Field(default=None, ge=200, le=2000)
    frp: Optional[float] = Field(default=None, ge=0)  # Fire Radiative Power (MW)
    area_estimada_ha: Optional[float] = Field(default=None, ge=0)
    severidade: Optional[Literal["baixa", "media", "alta", "critica"]] = None
    validado: bool = False

    @field_validator("latitude")
    @classmethod
    def latitude_ceara(cls, v: float) -> float:
        # Ceará: lat aprox -2.8 a -7.8
        if not (-8.5 <= v <= -2.0):
            raise ValueError(f"Latitude {v} fora do bounding box do Ceará")
        return v

    @field_validator("longitude")
    @classmethod
    def longitude_ceara(cls, v: float) -> float:
        # Ceará: lon aprox -41.4 a -37.2
        if not (-42.5 <= v <= -36.5):
            raise ValueError(f"Longitude {v} fora do bounding box do Ceará")
        return v


# ---------------------------------------------------------------------------
# Leitura GOES-16
# ---------------------------------------------------------------------------

class LeituraGOES16(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    data_hora: datetime
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    mascara_fogo: bool = False
    temperatura_pixel_k: Optional[float] = None
    frp_mw: Optional[float] = Field(default=None, ge=0)
    area_estimada_km2: Optional[float] = Field(default=None, ge=0)
    persistencia_horas: Optional[float] = Field(default=None, ge=0)
    deteccoes_consecutivas: int = Field(default=0, ge=0)
    municipio: Optional[str] = None
    produto: str = "ABI-L2-FDCF"  # produto padrão GOES-16 fogo


# ---------------------------------------------------------------------------
# Dado Climático
# ---------------------------------------------------------------------------

class DadoClimatico(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    municipio: str
    data_hora: datetime
    fonte: Literal["FUNCEME", "INMET", "CPTEC"] = "FUNCEME"
    temperatura_c: Optional[float] = Field(default=None, ge=-10, le=60)
    umidade_relativa: Optional[float] = Field(default=None, ge=0, le=100)
    velocidade_vento_ms: Optional[float] = Field(default=None, ge=0)
    direcao_vento_graus: Optional[float] = Field(default=None, ge=0, le=360)
    precipitacao_mm: Optional[float] = Field(default=None, ge=0)
    dias_sem_chuva: Optional[int] = Field(default=None, ge=0)
    pressao_hpa: Optional[float] = None
    indice_seca: Optional[float] = None  # 0-10


# ---------------------------------------------------------------------------
# Município
# ---------------------------------------------------------------------------

class Municipio(BaseModel):
    codigo_ibge: str
    nome: str
    regiao_planejamento: Optional[str] = None
    populacao: Optional[int] = None
    area_km2: Optional[float] = None
    latitude_centroide: float
    longitude_centroide: float
    tem_uc: bool = False  # Unidade de Conservação
    tem_area_urbana: bool = True


# ---------------------------------------------------------------------------
# Risco Municipal
# ---------------------------------------------------------------------------

class RiscoMunicipal(BaseModel):
    municipio: str
    codigo_ibge: str
    data_calculo: datetime
    indice_risco: float = Field(ge=0, le=100)
    classificacao: Literal["baixo", "moderado", "alto", "critico"]
    focos_24h: int = 0
    focos_48h: int = 0
    focos_7d: int = 0
    dias_sem_chuva: Optional[int] = None
    umidade_media: Optional[float] = None
    temperatura_media: Optional[float] = None
    vento_medio_ms: Optional[float] = None
    historico_recorrencia: Optional[float] = None  # 0-1
    justificativa: str = ""

    @model_validator(mode="after")
    def classificar_por_indice(self) -> "RiscoMunicipal":
        if self.indice_risco >= 75:
            self.classificacao = "critico"
        elif self.indice_risco >= 50:
            self.classificacao = "alto"
        elif self.indice_risco >= 25:
            self.classificacao = "moderado"
        else:
            self.classificacao = "baixo"
        return self


# ---------------------------------------------------------------------------
# Evento Consolidado de Queimada
# ---------------------------------------------------------------------------

class EventoQueimada(BaseModel):
    id_evento: str = Field(default_factory=lambda: str(uuid4()))
    municipio: str
    latitude_centroide: float
    longitude_centroide: float
    fontes: list[str]
    inicio: datetime
    ultima_deteccao: datetime
    quantidade_focos: int = Field(ge=1)
    severidade: Literal["baixa", "media", "alta", "critica"]
    confianca: float = Field(ge=0, le=100)
    frp_total_mw: Optional[float] = None
    area_estimada_ha: Optional[float] = None
    persistencia_horas: Optional[float] = None
    proxima_uc: Optional[str] = None
    proxima_area_urbana: Optional[str] = None
    distancia_uc_km: Optional[float] = None
    distancia_urbana_km: Optional[float] = None
    justificativa: str = ""
    goes16_confirmado: bool = False
    inpe_confirmado: bool = False
    firms_confirmado: bool = False


# ---------------------------------------------------------------------------
# Alerta de Queimada
# ---------------------------------------------------------------------------

class AlertaQueimada(BaseModel):
    id_alerta: str = Field(default_factory=lambda: str(uuid4()))
    evento_id: str
    nivel: Literal["informativo", "atencao", "alerta", "emergencia"]
    municipio: str
    mensagem: str
    recomendacao: str
    destinatarios: list[str] = []
    data_hora: datetime = Field(default_factory=datetime.utcnow)
    fontes_evidencia: list[str] = []
    agente_responsavel: str = ""
    ferramentas_consultadas: list[str] = []
    nivel_confianca: float = Field(default=0.0, ge=0, le=1)
    justificativa_tecnica: str = ""
    falso_positivo_suspeito: bool = False
    auditado: bool = False


# ---------------------------------------------------------------------------
# Resposta do Agente ReAct
# ---------------------------------------------------------------------------

class RespostaAgente(BaseModel):
    pergunta: str
    resposta: str
    resumo: str
    evidencias: list[str] = []
    fontes: list[str] = []
    data_hora_consulta: datetime = Field(default_factory=datetime.utcnow)
    nivel_confianca: float = Field(ge=0, le=1)
    recomendacao_operacional: str = ""
    ferramentas_usadas: list[str] = []
    passos_raciocinio: list[str] = []


# ---------------------------------------------------------------------------
# Relatório / Boletim Técnico
# ---------------------------------------------------------------------------

class BoletimTecnico(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    titulo: str
    data_hora: datetime = Field(default_factory=datetime.utcnow)
    periodo_referencia_inicio: datetime
    periodo_referencia_fim: datetime
    total_focos: int = 0
    municipios_criticos: list[str] = []
    eventos_ativos: list[str] = []
    alertas_emitidos: int = 0
    resumo_executivo: str = ""
    analise_tecnica: str = ""
    recomendacoes: list[str] = []
    fontes_consultadas: list[str] = []
    gerado_por: str = "AgentRelator"


# ---------------------------------------------------------------------------
# Log de Agente (rastreabilidade)
# ---------------------------------------------------------------------------

class LogAgente(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    agente: str
    acao: str
    entrada: dict = {}
    saida: dict = {}
    ferramentas_chamadas: list[str] = []
    data_hora: datetime = Field(default_factory=datetime.utcnow)
    duracao_ms: Optional[int] = None
    sucesso: bool = True
    erro: Optional[str] = None
    versao_modelo: str = ""


# ---------------------------------------------------------------------------
# Auditoria de Alerta (Agente Auditor)
# ---------------------------------------------------------------------------

class AuditoriaAlerta(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    alerta_id: str
    data_hora: datetime = Field(default_factory=datetime.utcnow)
    justificavel: bool
    fontes_confirmam: list[str] = []
    divergencias: list[str] = []
    suspeita_falso_positivo: bool = False
    dado_climatico_reforco: str = ""
    dado_climatico_enfraquecimento: str = ""
    parecer: str = ""
    confianca_auditoria: float = Field(ge=0, le=1)
