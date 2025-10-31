"""
Alabia Conductor - Main FastAPI Application
Orquestrador de LLM com MCP (Model Context Protocol)
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from apps.orchestrator.settings import settings
from apps.orchestrator.routes import chat

# Logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events"""
    # Startup
    logger.info("🚀 Alabia Conductor starting...")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Anthropic Model: {settings.anthropic_model}")

    # TODO: Inicializar MCP Servers aqui
    # - RAG Server
    # - Calendar Server
    # - Web Search Server

    yield

    # Shutdown
    logger.info("👋 Alabia Conductor shutting down...")
    # TODO: Cleanup de MCP servers


# FastAPI App
app = FastAPI(
    title="Alabia Conductor",
    description="Orquestrador de LLM com MCP para atendimento inteligente",
    version="1.0.0",
    lifespan=lifespan,
    debug=settings.debug
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(chat.router, prefix="/api", tags=["chat"])


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "Alabia Conductor",
        "version": "1.0.0",
        "status": "online",
        "environment": settings.environment
    }


@app.get("/health")
async def health():
    """Detailed health check"""
    return {
        "status": "healthy",
        "checks": {
            "api": "ok",
            # TODO: Adicionar checks dos MCP servers
            # "rag_server": "ok",
            # "calendar_server": "ok",
        }
    }


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Handler global de exceções"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc) if settings.debug else "An error occurred"
        }
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
        log_level=settings.log_level
    )
