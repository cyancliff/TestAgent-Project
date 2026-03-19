import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "TestAgent - 心理测评系统"

    # 自动读取你电脑里的环境变量
    DEEPSEEK_API_KEY: str = os.environ.get("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DASHSCOPE_API_KEY: str = os.environ.get("DASHSCOPE_API_KEY", "")
    ZHIPU_API_KEY: str = os.environ.get("ZHIPU_API_KEY", "")

    class Config:
        case_sensitive = True


settings = Settings()