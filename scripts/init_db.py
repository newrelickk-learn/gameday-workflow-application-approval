import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.db.base import Base
from app.db.session import engine
from app.core.config import settings

def init_db():
    print(f"データベースURL: {settings.database_url}")
    print("テーブルを作成中...")
    
    try:
        Base.metadata.create_all(bind=engine)
        print("✓ テーブルの作成が完了しました")
    except Exception as e:
        print(f"✗ エラーが発生しました: {e}")
        sys.exit(1)

if __name__ == "__main__":
    init_db()

