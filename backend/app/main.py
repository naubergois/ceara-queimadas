"""
Ponto de entrada da aplicação FastAPI.
Suporta dois modos:
  - Com banco (PostgreSQL + PostGIS): endpoints completos
  - Sem banco (modo standalone): apenas endpoints de dados reais
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.focos_reais import router as router_real
from app.core.config import settings

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Iniciando %s v%s", settings.APP_NAME, settings.APP_VERSION)

    # Tenta inicializar banco — se falhar, continua sem ele
    try:
        from app.core.database import init_db
        await init_db()
        logger.info("Banco de dados inicializado")
    except Exception as e:
        logger.warning("Banco indisponível — modo standalone ativo: %s", e)

    yield
    logger.info("Encerrando aplicação")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Gêmeo Digital do Ceará para descoberta online de queimadas. "
        "Dados reais: NASA FIRMS (VIIRS/MODIS) + Open-Meteo + Nominatim. "
        "Agentes: LangChain ReAct + LangGraph."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS para o frontend React
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS + ["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Endpoints de dados reais (sem banco) ──
app.include_router(router_real, prefix="/api/v1")

# ── Endpoints com banco (opcional) ──
try:
    from app.api.routes import router
    app.include_router(router, prefix="/api/v1")
    logger.info("Endpoints com banco registrados")
except Exception as e:
    logger.warning("Endpoints com banco não registrados: %s", e)


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "modo": "standalone (sem banco)" if True else "completo",
    }
