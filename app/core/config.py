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

    # game-masterとやり取りする署名付きトークン(signed_token)の署名鍵。game-masterを直接呼ぶことはない。
    game_master_service_api_key: str = "InternalServiceApiKeyForGameDayWorkflow2024!"

    # 出張申請の説明文をレビューするAI(Amazon Bedrock)。GameDay当日に止めたくなったら
    # AI_REVIEW_ENABLED=false で無効化できる。
    ai_review_enabled: bool = True
    ai_review_region: str = "ap-northeast-1"
    # 推論プロファイル(jp.*)経由で呼ぶ。素のモデルIDはオンデマンド非対応。
    # Haiku 4.5はこのAWSアカウントでモデルアクセスが無効(AccessDeniedException)のため、
    # 有効になっているSonnet 4.5を使う。Haikuを使いたい場合はBedrockのモデルアクセスを
    # 有効化してからこの値を戻す。
    ai_review_model_id: str = "jp.anthropic.claude-sonnet-4-5-20250929-v1:0"
    # Sonnetでのレビューは実測で3秒前後かかるため、余裕を持たせる。
    ai_review_timeout_seconds: float = 8.0
    ai_review_connect_timeout_seconds: float = 2.0

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

