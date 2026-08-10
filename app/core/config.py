from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """アプリケーション設定"""
    
    # アプリケーション設定
    app_name: str = "Application & Approval Service"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # データベース設定
    database_url: str = "postgresql://user:password@localhost:5432/gameday_workflow"
    
    # セキュリティ設定
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # ユーザーサービス設定
    # Dockerネットワーク内ではコンテナ名またはサービス名を使用
    # 内部ポート80を使用（外部ポート8001はホストマシン用）
    # コンテナ名の候補: gameday_workflow_user_api, gameday-workflow-user-api, workflow-user
    user_service_base_url: str = "http://gameday_workflow_user_api:80"
    user_service_api_key: str = "InternalServiceApiKeyForGameDayWorkflow2024!"  # 内部サービス間通信用API Key
    user_service_use_stub: bool = False  # Trueの場合、スタブ実装を使用（開発・テスト用）
    
    # Kafka設定（将来の拡張用）
    kafka_bootstrap_servers: Optional[str] = None
    kafka_topic: Optional[str] = None
    
    # ワークフローサービス設定
    workflow_service_base_url: str = "http://workflow-notification-service:8003"
    workflow_service_use_stub: bool = False  # Trueの場合、スタブ実装を使用（開発・テスト用）
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

