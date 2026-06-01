from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_ENV: str = "dev"
    REPO_BACKEND: str = "memory"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_CHAT_MODEL: str = "gemma4:26B"
    OLLAMA_EMBED_MODEL: str = "nomic-embed-text"
    OLLAMA_REQUEST_TIMEOUT: int = 120
    TIMESFM_CHECKPOINT: str = "google/timesfm-2.0-500m-pytorch"
    TIMESFM_BACKEND: str = "cpu"
    SEED_PATH: str = "./data/seeds/zarqa.json"
    REDIS_URL: str = "redis://localhost:6379/0"
    ARTIFACTS_DIR: str = "./data/artifacts"

    # VOC360 PostgreSQL
    VOC_DB_HOST: str = "87.239.129.246"
    VOC_DB_PORT: int = 5432
    VOC_DB_NAME: str = "voc360"
    VOC_DB_USER: str = "voc_admin"
    VOC_DB_PASSWORD: str = "uqKEQXkfzJL9qUXGvgzzIyFuQ281"
    VOC_DB_SSLMODE: str = "require"
    VOC_DB_POOL_SIZE: int = 5
    VOC_DB_MAX_OVERFLOW: int = 10

    @property
    def voc_database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.VOC_DB_USER}:{self.VOC_DB_PASSWORD}"
            f"@{self.VOC_DB_HOST}:{self.VOC_DB_PORT}/{self.VOC_DB_NAME}"
            f"?ssl=require"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
