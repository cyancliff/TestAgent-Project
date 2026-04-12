import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "TestAgent - 心理测评系统"

    # 自动读取环境变量
    DEEPSEEK_API_KEY: str = os.environ.get("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DASHSCOPE_API_KEY: str = os.environ.get("DASHSCOPE_API_KEY", "")
    ZHIPU_API_KEY: str = os.environ.get("ZHIPU_API_KEY", "")

    # 数据库信息 (PostgreSQL)
    DATABASE_URL: str = os.environ.get("DATABASE_URL", "postgresql://postgres:123456@localhost:5432/atmr_db")

    # JWT 认证配置
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "atmr-test-agent-secret-key-change-in-production")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 默认 24 小时

    class Config:
        case_sensitive = True


settings = Settings()
