from fastapi import APIRouter
from app.api.v1.endpoints import applications, approvals, game_progress
from app.api.v1.admin import assertion_rules as admin_assertion_rules

api_router = APIRouter()

api_router.include_router(applications.router, tags=["Applications"])
api_router.include_router(approvals.router, tags=["Approvals"])
api_router.include_router(game_progress.router, tags=["GameProgress"])
api_router.include_router(admin_assertion_rules.router, tags=["Admin"])

