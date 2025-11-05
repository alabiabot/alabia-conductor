"""
Configurações do Alabia Conductor
Carrega variáveis de ambiente e valida configurações
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    """Configurações globais da aplicação"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Anthropic API
    anthropic_api_key: str
    anthropic_model: str = "claude-sonnet-4-5-20250929"
    anthropic_max_tokens: int = 4096
    anthropic_temperature: float = 0.7

    # Google Calendar
    google_calendar_credentials_json: str = "./secrets/google-credentials.json"
    google_calendar_id: str
    google_calendar_timezone: str = "America/Sao_Paulo"

    # ChromaDB
    chroma_persist_dir: str = "./data/chroma_db"
    chroma_host: str = "localhost"
    chroma_port: int = 8001

    # OpenAI (para embeddings)
    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-small"

    # FastAPI
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = True
    log_level: str = "info"

    # CORS
    allowed_origins: str = "http://localhost:3000"

    # Sistema
    environment: str = "development"
    debug: bool = True

    # Limites e timeouts
    max_tool_iterations: int = 10
    tool_timeout_seconds: int = 60

    @property
    def allowed_origins_list(self) -> List[str]:
        """Converte string de origins em lista"""
        return [origin.strip() for origin in self.allowed_origins.split(",")]

    @property
    def is_production(self) -> bool:
        """Checa se está em produção"""
        return self.environment.lower() == "production"


# Singleton global
settings = Settings()
