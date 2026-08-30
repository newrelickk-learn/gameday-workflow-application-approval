from typing import List

from sqlalchemy.orm import Session

from app.models.chapter_mission import ChapterMission


class ChapterMissionService:

    @staticmethod
    def get_active_missions(db: Session) -> List[ChapterMission]:
        return (
            db.query(ChapterMission)
            .filter(ChapterMission.is_active == True)
            .order_by(ChapterMission.order)
            .all()
        )
