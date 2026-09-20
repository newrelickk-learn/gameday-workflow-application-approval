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

    game_master_service_base_url: str = "http://gameday-workflow-game-master:8006"
    game_master_service_api_key: str = "InternalServiceApiKeyForGameDayWorkflow2024!"

    # 出張申請の説明文をレビューするAI(Amazon Bedrock)。GameDay当日に止めたくなったら
    # AI_REVIEW_ENABLED=false で無効化できる。
    ai_review_enabled: bool = True
    ai_review_region: str = "ap-northeast-1"
    ai_review_model_id: str = "anthropic.claude-haiku-4-5-20251001-v1:0"
    ai_review_timeout_seconds: float = 5.0
    ai_review_connect_timeout_seconds: float = 2.0

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

