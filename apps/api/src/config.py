"""Application configuration using pydantic-settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = "postgresql+asyncpg://rag_user:rag_pass@postgres:5432/rag_pipeline"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # Qdrant
    qdrant_host: str = "qdrant"
    qdrant_port: int = 6333

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    # Celery
    celery_broker_url: str = "redis://redis:6379/1"
    celery_result_backend: str = "redis://redis:6379/2"

    # A2A Protocol
    a2a_base_url: str = "http://localhost:8000"
    a2a_streaming_enabled: bool = True
    a2a_push_notifications_enabled: bool = False

    # LLM (OpenAI-compatible endpoint)
    llm_endpoint: str = "http://spark-8013:4000/v1"
    llm_model: str = "qwen3.6-35b-a3b"
    llm_api_key: str = "sk-change-me-in-production"
    llm_temperature: float = 0.3
    llm_max_tokens: int = 4096

    model_config = {"env_prefix": "RAG_", "env_file": ".env"}


settings = Settings()
