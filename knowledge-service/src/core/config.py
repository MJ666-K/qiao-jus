from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_log_level: str = "INFO"

    jwt_secret_key: str = Field(min_length=16)
    jwt_algorithm: str = "HS256"
    jwt_access_ttl_minutes: int = 60
    jwt_refresh_ttl_days: int = 7

    database_url: str
    postgres_host: str = "postgres"
    postgres_port: int = 5432

    qdrant_url: str = "http://qdrant:6333"
    qdrant_collection: str = "knowledge"
    qdrant_vector_size: int = 1024

    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str

    redis_url: str
    celery_broker_url: str
    celery_result_backend: str

    # OpenAI-compatible LLM endpoint. Works with DashScope (qwen), ZhipuAI, OpenAI, etc.
    llm_api_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_api_key: str
    llm_model_id: str = "qwen-plus"
    llm_max_tokens: int = 8000

    # Embedding model id at the same OpenAI-compatible endpoint.
    embedding_model_id: str = "text-embedding-v3"
    embedding_dim: int = 1024

    chunk_parent_tokens: int = 1200
    chunk_child_tokens: int = 300
    chunk_overlap_tokens: int = 50

    search_top_k: int = 10
    rrf_k: int = 60
    rerank_top_k: int = 20

    # ===== Aliyun OSS (required for file uploads) =====
    # Without these, the upload endpoint will fail at first use.
    oss_access_key_id: str | None = None
    oss_access_key_secret: str | None = None
    # e.g. https://oss-cn-shanghai.aliyuncs.com
    oss_endpoint: str | None = None
    oss_bucket_name: str | None = None
    oss_prefix: str = "uploads/"

    @property
    def oss_enabled(self) -> bool:
        return bool(
            self.oss_access_key_id
            and self.oss_access_key_secret
            and self.oss_endpoint
            and self.oss_bucket_name
        )

    @property
    def is_dev(self) -> bool:
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
