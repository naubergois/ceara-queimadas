"""
Ponto de entrada da aplicação FastAPI.
Suporta dois modos:
  - Com banco (PostgreSQL + PostGIS): endpoints completos
  - Sem banco (modo standalone): apenas endpoints de dados reais
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat_pesquisa import router as router_pesquisa
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

    # Pré-aquece cache NASA FIRMS para a primeira visita ao mapa não estourar timeout
    try:
        from app.api.focos_reais import _garantir_cache

        asyncio.create_task(_garantir_cache())
        logger.info("Pré-aquecimento do cache de dados reais iniciado em background")
    except Exception as e:
        logger.warning("Pré-aquecimento do cache não iniciado: %s", e)

    # Carrega índice FAISS do chat da pesquisa (ou constrói em background)
    try:
        from app.rag.faiss_store import build_faiss_index, index_dir

        if (index_dir() / "index.faiss").exists():
            from app.rag.faiss_store import load_faiss_index

            load_faiss_index()
            logger.info("Índice FAISS da pesquisa carregado")
        else:
            asyncio.create_task(asyncio.to_thread(build_faiss_index))
            logger.info("Construção do índice FAISS iniciada em background")
    except Exception as e:
        logger.warning("FAISS pesquisa não iniciado: %s", e)

    yield
    logger.info("Encerrando aplicação")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Ceará Digital Twin for online wildfire discovery. "
        "Real data: NASA FIRMS (VIIRS/MODIS) + Open-Meteo + Nominatim. "
        "Agents: LangChain ReAct + LangGraph."
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
app.include_router(router_pesquisa, prefix="/api/v1")

# ── Endpoints de inovação (modelos Koopman/PI-GNN) ──
try:
    from app.api.inovacao import router as router_inovacao
    app.include_router(router_inovacao)
    logger.info("Endpoints de inovação (Koopman/PI-GNN) registrados")
except Exception as e:
    logger.warning("Endpoints de inovação não registrados: %s", e)

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
