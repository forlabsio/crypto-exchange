from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    DATABASE_URL: str
    REDIS_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    BINANCE_BASE_URL: str = "https://api.binance.com"
    BINANCE_API_KEY: str = ""
    BINANCE_API_SECRET: str = ""

    # Polygon / MetaMask settings
    POLYGON_RPC_URL: str = "https://polygon-rpc.com"
    PLATFORM_DEPOSIT_ADDRESS: str = ""
    POLYGON_USDT_CONTRACT: str = "0xc2132D05D31c914a87C6611C10748AEb04B58e8F"

    @field_validator('DATABASE_URL', mode='before')
    @classmethod
    def convert_database_url(cls, v):
        """Convert postgresql:// to postgresql+asyncpg:// for async support"""
        if isinstance(v, str) and v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

settings = Settings()
