import os
import secrets
import warnings
from urllib.parse import quote_plus

from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_DEEPSEEK_CHAT_MODEL = "deepseek-v4-flash"
DEFAULT_DEEPSEEK_THINKING_MODE = "disabled"


def normalize_deepseek_base_url(base_url: str | None) -> str:
    return (base_url or DEFAULT_DEEPSEEK_BASE_URL).rstrip("/")


def normalize_deepseek_thinking_mode(
    thinking_mode: str | None,
    default: str = DEFAULT_DEEPSEEK_THINKING_MODE,
) -> str:
    normalized = (thinking_mode or default).strip().lower()
    if normalized in {"enabled", "disabled"}:
        return normalized
    return default


def build_deepseek_thinking_payload(thinking_mode: str | None) -> dict:
    return {"thinking": {"type": normalize_deepseek_thinking_mode(thinking_mode)}}


def get_deepseek_api_key() -> str:
    return os.environ.get("DEEPSEEK_API_KEY", "")


def get_deepseek_base_url() -> str:
    return normalize_deepseek_base_url(os.environ.get("DEEPSEEK_BASE_URL"))


def get_deepseek_chat_model() -> str:
    return os.environ.get("DEEPSEEK_CHAT_MODEL", DEFAULT_DEEPSEEK_CHAT_MODEL)


def get_deepseek_analysis_model() -> str:
    return os.environ.get("DEEPSEEK_ANALYSIS_MODEL") or get_deepseek_chat_model()


def get_deepseek_rag_model() -> str:
    return os.environ.get("DEEPSEEK_RAG_MODEL") or get_deepseek_chat_model()


def get_deepseek_rag_retrieve_model() -> str:
    return os.environ.get("DEEPSEEK_RAG_RETRIEVE_MODEL") or get_deepseek_rag_model()


def get_deepseek_chat_thinking_mode() -> str:
    return normalize_deepseek_thinking_mode(os.environ.get("DEEPSEEK_CHAT_THINKING"))


def get_deepseek_analysis_thinking_mode() -> str:
    return normalize_deepseek_thinking_mode(
        os.environ.get("DEEPSEEK_ANALYSIS_THINKING"),
        default=get_deepseek_chat_thinking_mode(),
    )


def get_deepseek_rag_thinking_mode() -> str:
    return normalize_deepseek_thinking_mode(
        os.environ.get("DEEPSEEK_RAG_THINKING"),
        default=get_deepseek_chat_thinking_mode(),
    )


def get_deepseek_chat_completions_url() -> str:
    return f"{get_deepseek_base_url()}/chat/completions"


def build_database_url_from_env() -> str:
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        return database_url

    app_env = os.environ.get("APP_ENV", "development").lower()
    use_sqlite_dev = os.environ.get("USE_SQLITE_DEV", "1") == "1"
    if app_env == "development" and use_sqlite_dev:
        sqlite_path = os.environ.get("SQLITE_PATH", "data/testagent_dev.db")
        return f"sqlite:///{sqlite_path}"

    db_user = os.environ.get("DB_USER", "postgres")
    db_password = quote_plus(os.environ.get("DB_PASSWORD", ""))
    db_host = os.environ.get("DB_HOST", "localhost")
    db_port = os.environ.get("DB_PORT", "5432")
    db_name = os.environ.get("DB_NAME", "atmr_db")

    if db_password:
        return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    return f"postgresql://{db_user}@{db_host}:{db_port}/{db_name}"


def build_secret_key(app_env: str) -> str:
    secret_key = os.environ.get("SECRET_KEY")
    if secret_key:
        return secret_key
    if app_env == "production":
        return ""
    return f"dev-only-{secrets.token_urlsafe(32)}"


class Settings(BaseSettings):
    PROJECT_NAME: str = "TestAgent - 心理测评系统"

    APP_ENV: str = os.environ.get("APP_ENV", "development").lower()

    DEEPSEEK_API_KEY: str = get_deepseek_api_key()
    DEEPSEEK_BASE_URL: str = get_deepseek_base_url()
    DEEPSEEK_CHAT_MODEL: str = get_deepseek_chat_model()
    DEEPSEEK_ANALYSIS_MODEL: str = get_deepseek_analysis_model()
    DEEPSEEK_RAG_MODEL: str = get_deepseek_rag_model()
    DEEPSEEK_RAG_RETRIEVE_MODEL: str = get_deepseek_rag_retrieve_model()
    DEEPSEEK_CHAT_THINKING: str = get_deepseek_chat_thinking_mode()
    DEEPSEEK_ANALYSIS_THINKING: str = get_deepseek_analysis_thinking_mode()
    DEEPSEEK_RAG_THINKING: str = get_deepseek_rag_thinking_mode()
    DASHSCOPE_API_KEY: str = os.environ.get("DASHSCOPE_API_KEY", "")
    ZHIPU_API_KEY: str = os.environ.get("ZHIPU_API_KEY", "")

    DATABASE_URL: str = build_database_url_from_env()

    SECRET_KEY: str = build_secret_key(os.environ.get("APP_ENV", "development").lower())
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
    AUTO_CREATE_TABLES: bool = os.environ.get(
        "AUTO_CREATE_TABLES",
        "1" if os.environ.get("APP_ENV", "development").lower() == "development" else "0",
    ) == "1"
    ADMIN_USERNAMES: str = os.environ.get("ADMIN_USERNAMES", "admin")

    ALLOWED_ORIGINS: list[str] = ["*"]

    MULTIMODAL_ROOT_DIR: str = os.environ.get("MULTIMODAL_ROOT_DIR", "uploads/multimodal_personality")
    MULTIMODAL_VIDEO_DIR: str = os.environ.get("MULTIMODAL_VIDEO_DIR", "uploads/multimodal_personality/videos")
    MULTIMODAL_TASK_DIR: str = os.environ.get("MULTIMODAL_TASK_DIR", "uploads/multimodal_personality/tasks")
    MULTIMODAL_ARTIFACT_DIR: str = os.environ.get(
        "MULTIMODAL_ARTIFACT_DIR",
        "uploads/multimodal_personality/artifacts",
    )
    MULTIMODAL_CHECKPOINT_PATH: str = os.environ.get(
        "MULTIMODAL_CHECKPOINT_PATH",
        "reports/night_lr1e4_drop02/agtn_mtl_lr1e4_drop02.pt",
    )
    MULTIMODAL_DEVICE: str = os.environ.get("MULTIMODAL_DEVICE", "auto")

    model_config = SettingsConfigDict(case_sensitive=True, enable_decoding=False)

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value):
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return ["*"]

    def check_security(self):
        if "SECRET_KEY" not in os.environ:
            warnings.warn(
                "SECRET_KEY 未显式配置。开发环境将使用仅当前进程有效的随机密钥，"
                "生产环境必须通过环境变量或 .env 配置固定强密钥。",
                RuntimeWarning,
                stacklevel=2,
            )
            if self.APP_ENV == "production":
                raise RuntimeError("生产环境必须配置 SECRET_KEY。")


settings = Settings()
settings.check_security()
