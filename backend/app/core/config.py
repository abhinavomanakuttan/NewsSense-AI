from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    # General
    environment: str = "development"
    debug: bool = True
    secret_key: str
    project_name: str = "SmartFeed AI"
    version: str = "1.0.0"

    # Database
    database_url: str
    database_sync_url: str

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # RabbitMQ
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672//"

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_api_key: str | None = None

    # Elasticsearch
    elasticsearch_hosts: str = "http://localhost:9200"
    elasticsearch_api_key: str | None = None

    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "smartfeed"
    minio_secure: bool = False

    # Celery
    celery_broker_url: str = "amqp://guest:guest@localhost:5672//"
    celery_result_backend: str = "redis://localhost:6379/1"

    # AI Models
    embedding_model_name: str = "all-MiniLM-L6-v2"
    classification_model_name: str = "facebook/bart-large-mnli"
    summarization_model_name: str = "facebook/bart-large-cnn"
    ner_model_name: str = "en_core_web_lg"
    translation_model_name: str = "Helsinki-NLP/opus-mt-en-{lang}"
    enable_enrichment: bool = True

    # OpenAI (optional)
    openai_api_key: str | None = None
    openai_model_name: str = "gpt-4o-mini"

    # News API
    newsapi_key: str | None = None
    newsapi_base_url: str = "https://newsapi.org/v2"

    # JWT
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # Rate Limiting
    rate_limit_requests: int = 100
    rate_limit_period_seconds: int = 60

    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:8000"


settings = Settings()
