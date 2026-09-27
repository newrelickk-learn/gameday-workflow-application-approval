from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Any, Dict, Generator
from app.core.config import settings

_engine_kwargs: Dict[str, Any] = {"pool_pre_ping": True}
if not settings.database_url.startswith("sqlite"):
    # engineはuvicornのworkerプロセスごとに1つ作られる(Dockerfileで--workers 4、
    # k8sでreplicas 2なので実質8プロセス)。pool_size=10/max_overflow=20のままだと
    # 8プロセス x 最大30接続 = 240になり得て、全サービス共有のPostgres(max_connections=100)を
    # このサービスだけで食い潰してしまう(他サービスがconnection to server failed:
    # too many clients alreadyで落ちる)。8プロセス想定でも余裕を持って収まる値に絞る。
    _engine_kwargs["pool_size"] = 3
    _engine_kwargs["max_overflow"] = 5

engine = create_engine(settings.database_url, **_engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

