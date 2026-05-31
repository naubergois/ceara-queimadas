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

    # LLM
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    ANTHROPIC_API_KEY: str = ""

    # INPE BDQueimadas
    INPE_API_URL: str = "https://queimadas.dgi.inpe.br/api"
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
