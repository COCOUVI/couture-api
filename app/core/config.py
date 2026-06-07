from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    DATABASE_URL: str
    SECRET_KEY: str = "dev_secret_key"
    ENVIRONMENT: str = "development"
    MODEL_PATH: str = "pose_landmarker_heavy.task"
    MIN_CONFIDENCE: float = 0.5


settings = Settings()
