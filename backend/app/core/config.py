"""
Configurações centrais da aplicação via variáveis de ambiente.
"""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    APP_NAME: str = "Gêmeo Digital Ceará - Queimadas"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://ceara:ceara@localhost:5432/queimadas"
    DATABASE_POOL_SIZE: int = 10

    # LLM (DeepSeek — API compatível com OpenAI)
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_API_BASE: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"
    DEEPSEEK_EMBEDDING_MODEL: str = "deepseek-embedding-v2"

    # RAG / FAISS (chat da pesquisa)
    FAISS_INDEX_DIR: str = "data/faiss_pesquisa"
    FAISS_CHUNK_SIZE: int = 900
    FAISS_CHUNK_OVERLAP: int = 120
    FAISS_TOP_K: int = 5
    FAISS_LOCAL_EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    # Legado (não usado pelos agentes; mantido para compatibilidade de .env antigo)
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    ANTHROPIC_API_KEY: str = ""

    # INPE BDQueimadas (CSV público — API anterior desativada)
    # Antigo: queimadas.dgi.inpe.br/api (301 → terrabrasilis 404)
    # Novo:   https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/diario/Brasil/
    INPE_API_URL: str = "https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/diario/Brasil"
    INPE_API_KEY: Optional[str] = None

    # NASA FIRMS
    NASA_FIRMS_API_KEY: str = ""
    NASA_FIRMS_URL: str = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"

    # GOES-16 (AWS S3 público)
    GOES16_S3_BUCKET: str = "noaa-goes16"
    GOES16_PRODUCT: str = "ABI-L2-FDCF"

    # FUNCEME
    FUNCEME_API_URL: str = "https://api.funceme.br"
    FUNCEME_API_KEY: Optional[str] = None

    # INMET
    INMET_API_URL: str = "https://apitempo.inmet.gov.br"
    INMET_TOKEN: Optional[str] = None

    # MapBiomas
    MAPBIOMAS_API_URL: str = "https://api.mapbiomas.org/api/v1"
    MAPBIOMAS_TOKEN: Optional[str] = None

    # IBGE
    IBGE_API_URL: str = "https://servicodados.ibge.gov.br/api/v1"

    # Coleta periódica (minutos)
    COLETA_INTERVALO_MINUTOS: int = 15

    # Alertas
    ALERTA_WEBHOOK_URL: Optional[str] = None
    ALERTA_EMAIL_FROM: Optional[str] = None
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None

    # Limites de risco
    RISCO_CRITICO_THRESHOLD: float = 75.0
    RISCO_ALTO_THRESHOLD: float = 50.0
    RISCO_MODERADO_THRESHOLD: float = 25.0

    # Bounding box Ceará
    CEARA_LAT_MIN: float = -7.85
    CEARA_LAT_MAX: float = -2.78
    CEARA_LON_MIN: float = -41.42
    CEARA_LON_MAX: float = -37.25

    # Redis (cache e filas)
    REDIS_URL: str = "redis://localhost:6379/0"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
