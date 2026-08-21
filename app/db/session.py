from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings

# データベースエンジンの作成
# SQLite（pytestのテスト用DB）はQueuePool系の引数(pool_size/max_overflow)をサポートしない
# デフォルトプール(SingletonThreadPool)を使うため、SQLite以外の場合のみ指定する
_engine_kwargs = {"pool_pre_ping": True}
if not settings.database_url.startswith("sqlite"):
    _engine_kwargs["pool_size"] = 10
    _engine_kwargs["max_overflow"] = 20

engine = create_engine(settings.database_url, **_engine_kwargs)

# セッションファクトリーの作成
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """データベースセッションを取得します"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

