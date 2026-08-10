import newrelic.agent
newrelic.agent.initialize()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import os

from app.api.v1.router import api_router
from app.core.config import settings
from app.db.base import Base
from app.db.session import engine

logger = logging.getLogger(__name__)



@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリケーションのライフサイクル管理"""
    # 起動時: データベーステーブルの作成を試みる
    try:
        logger.info("データベーステーブルを作成中...")
        Base.metadata.create_all(bind=engine)
        logger.info("データベーステーブルの作成が完了しました")
    except Exception as e:
        logger.warning(f"データベーステーブルの作成に失敗しました（後で再試行可能）: {e}")
    
    yield
    
    # シャットダウン時（必要に応じて）
    pass


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="GameDay Workflow システムの申請・承認管理サービスAPI",
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本番環境では適切なオリジンを設定
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# APIルーターの登録
app.include_router(api_router, prefix="/api/v1")
logger.info("APIルーターを登録しました: /api/v1")
logger.info("登録されたエンドポイント:")
for route in app.routes:
    if hasattr(route, 'path') and hasattr(route, 'methods'):
        logger.info(f"  {list(route.methods)} {route.path}")


@app.get("/health")
async def health_check():
    """ヘルスチェックエンドポイント"""
    return {"status": "healthy", "version": settings.app_version}


@app.get("/")
async def root():
    """ルートエンドポイント"""
    return {
        "message": "Application & Approval Service API",
        "version": settings.app_version,
        "docs": "/docs",
    }

