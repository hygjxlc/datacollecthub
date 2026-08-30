from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """环境变量驱动配置（大小写不敏感自动映射，如 DATABASE_URL → database_url）。"""

    model_config = SettingsConfigDict(env_file=".env")

    database_url: str = "sqlite:///./datacollecthub.db"
    jwt_secret_key: str = "dev-secret-change-me"
    jwt_expire_hours: int = 24
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "energydata-raw"
    minio_public_endpoint: str = "http://localhost:9000"
    presigned_expire_hours: int = 2


settings = Settings()
