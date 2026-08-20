from fastapi import APIRouter
from app.api.v1.endpoints import applications, approvals, game_progress, chapter_diagnosis
from app.api.v1.admin import assertion_rules as admin_assertion_rules
from app.api.v1.admin import game_progress as admin_game_progress

api_router = APIRouter()

api_router.include_router(applications.router, tags=["Applications"])
api_router.include_router(approvals.router, tags=["Approvals"])
api_router.include_router(game_progress.router, tags=["GameProgress"])
api_router.include_router(chapter_diagnosis.router, tags=["Chapters"])
api_router.include_router(admin_assertion_rules.router, tags=["Admin"])
api_router.include_router(admin_game_progress.router, tags=["Admin"])

