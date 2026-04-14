import os
import warnings
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "TestAgent - 心理测评系统"

    # 运行环境
    APP_ENV: str = os.environ.get("APP_ENV", "development")

    # 自动读取环境变量
    DEEPSEEK_API_KEY: str = os.environ.get("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DASHSCOPE_API_KEY: str = os.environ.get("DASHSCOPE_API_KEY", "")
    ZHIPU_API_KEY: str = os.environ.get("ZHIPU_API_KEY", "")

    # 数据库信息 (PostgreSQL)
    DATABASE_URL: str = os.environ.get("DATABASE_URL", "postgresql://postgres:123456@localhost:5432/atmr_db")

    # JWT 认证配置
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "atmr-test-agent-secret-key-change-in-production")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

    # CORS 允许的前端来源（逗号分隔，开发环境可用 * 放行所有）
    ALLOWED_ORIGINS: list[str] = [
        origin.strip()
        for origin in os.environ.get("ALLOWED_ORIGINS", "*").split(",")
        if origin.strip()
    ]

    def check_security(self):
        """启动前安全检查"""
        default_key = "atmr-test-agent-secret-key-change-in-production"
        if self.SECRET_KEY == default_key:
            warnings.warn(
                "SECRET_KEY 使用了默认值！生产环境必须设置为强随机字符串。"
                "可通过环境变量 SECRET_KEY 或 .env 文件配置。",
                RuntimeWarning,
                stacklevel=2,
            )
            if self.APP_ENV == "production":
                raise RuntimeError(
                    "生产环境不允许使用默认 SECRET_KEY。"
                    "请设置环境变量 SECRET_KEY 为一个强随机字符串。"
                )

    class Config:
        case_sensitive = True


settings = Settings()
settings.check_security()
