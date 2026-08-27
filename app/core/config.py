from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    
    app_name: str = "Application & Approval Service"
    app_version: str = "1.0.0"
    debug: bool = False
    
    database_url: str = "postgresql://user:password@localhost:5432/gameday_workflow"
    
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    user_service_base_url: str = "http://gameday_workflow_user_api:80"
    user_service_api_key: str = "InternalServiceApiKeyForGameDayWorkflow2024!"  
    user_service_use_stub: bool = False  
    
    kafka_bootstrap_servers: Optional[str] = None
    kafka_topic: Optional[str] = None
    
    workflow_service_base_url: str = "http://workflow-notification-service:8003"
    workflow_service_use_stub: bool = False  

    chapter_diagnosis_key: Optional[str] = None
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

