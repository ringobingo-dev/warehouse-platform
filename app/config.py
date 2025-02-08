from functools import lru_cache
from typing import List, Optional
from pydantic import field_validator, ValidationInfo
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Application settings with environment variable overrides.
    """
    # Environment
    ENV: str = "development"
    DEBUG: bool = True
    
    # API Settings
    API_VERSION: str = "v1"
    API_PREFIX: str = f"/api/{API_VERSION}"
    PROJECT_NAME: str = "Warehouse Management Service"
    
    # Database Settings
    CUSTOMERS_TABLE: str = "dev-Customers"
    WAREHOUSES_TABLE: str = "dev-Warehouses"
    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    DYNAMODB_ENDPOINT_URL: Optional[str] = None  # For local development/testing
    
    # CORS Settings
    CORS_ORIGINS: List[str] = ["*"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["*"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]
    
    # Security Settings
    AUTH_REQUIRED: bool = True
    AUTH_TOKEN_EXPIRE_MINUTES: int = 60
    AUTH_SECRET_KEY: str = "development_secret_key"  # Override in production
    
    # Logging Settings
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Application Limits
    MAX_WAREHOUSE_CAPACITY: int = 1000
    MAX_STACK_HEIGHT: int = 10
    
    # Email Settings
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: Optional[int] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        env_prefix="WMS_",
        extra="ignore"
    )
    
    @field_validator("ENV")
    def validate_environment(cls, v: str) -> str:
        allowed = {"development", "staging", "production"}
        if v not in allowed:
            raise ValueError(f"Environment must be one of {allowed}")
        return v
    
    @field_validator("AUTH_SECRET_KEY")
    def validate_secret_key(cls, v: str, info: ValidationInfo) -> str:
        if info.data.get("ENV") == "production" and v == "development_secret_key":
            raise ValueError("Production environment requires a secure AUTH_SECRET_KEY")
        return v
    
    @field_validator("MAX_STACK_HEIGHT")
    def validate_stack_height(cls, v: int) -> int:
        if v < 1 or v > 20:
            raise ValueError("Stack height must be between 1 and 20")
        return v
    
    def get_database_settings(self) -> dict:
        """
        Returns database configuration settings.
        """
        return {
            "region_name": self.AWS_REGION,
            "aws_access_key_id": self.AWS_ACCESS_KEY_ID,
            "aws_secret_access_key": self.AWS_SECRET_ACCESS_KEY,
        }
    
    def get_cors_settings(self) -> dict:
        """
        Returns CORS configuration settings.
        """
        return {
            "allow_origins": self.CORS_ORIGINS,
            "allow_credentials": self.CORS_ALLOW_CREDENTIALS,
            "allow_methods": self.CORS_ALLOW_METHODS,
            "allow_headers": self.CORS_ALLOW_HEADERS,
        }
    
    def get_email_settings(self) -> dict:
        """
        Returns email configuration settings.
        """
        return {
            "smtp_host": self.SMTP_HOST,
            "smtp_port": self.SMTP_PORT,
            "smtp_user": self.SMTP_USER,
            "smtp_password": self.SMTP_PASSWORD,
        }

@lru_cache
def get_settings() -> Settings:
    """
    Returns cached settings instance.
    """
    return Settings()

