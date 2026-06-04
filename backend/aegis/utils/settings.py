"""Application settings loaded from .env via pydantic-settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_API_KEY: str = ""
    LLM_MODEL_PRIMARY: str = "gpt-4o"
    LLM_MODEL_MINI: str = "gpt-4o-mini"

    # 券商
    FUTU_HOST: str = "127.0.0.1"
    FUTU_PORT: int = 11111
    LONGBRIDGE_APP_KEY: str = ""
    LONGBRIDGE_APP_SECRET: str = ""
    LONGBRIDGE_ACCESS_TOKEN: str = ""
    TIGER_PRIVATE_KEY: str = ""
    TIGER_TIGER_ID: str = ""
    TIGER_PRIVATE_KEY_PATH: str = ""

    # 券商启用开关
    BROKER_ENABLED: list[str] = ["futu"]

    # 数据源 — 基础
    ALPHA_VANTAGE_API_KEY: str = ""
    FRED_API_KEY: str = ""
    TAVILY_API_KEY: str = ""
    STOCKTWITS_ACCESS_TOKEN: str = ""
    REDDIT_CLIENT_ID: str = ""
    REDDIT_CLIENT_SECRET: str = ""
    X_BEARER_TOKEN: str = ""

    # 数据源 — v1.2 新增
    UNUSUAL_WHALES_API_KEY: str = ""
    MARKET_CHAMELEON_API_KEY: str = ""
    BARCHART_API_KEY: str = ""
    FINVIZ_API_KEY: str = ""

    # 数据源 — M2 新增
    ETF_FUND_FLOW_SOURCE: str = "etfdb"
    FUTU_TRADE_ENV: str = "SIMULATE"
    LONGBRIDGE_REGION: str = "us"
    TIGER_ACCOUNT: str = ""

    # FastAPI
    FASTAPI_HOST: str = "0.0.0.0"
    FASTAPI_PORT: int = 8000

    # Memory
    MEMORY_SHORT_TTL_DAYS: int = 14

    # 推送
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    # 路径
    DATA_DIR: str = "./data"
    CHROMA_PERSIST_DIR: str = "./data/chroma"

    # 数据库
    DATABASE_URL: str = "sqlite:///./data/aegis.db"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
