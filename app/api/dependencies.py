from typing import Generator, Optional
import logging

import newrelic.agent
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import get_current_user
from app.services.user_service import UserService

logger = logging.getLogger(__name__)

security = HTTPBearer()


def _resolve_company_id(profile: Optional[dict]) -> Optional[int]:
    if not profile:
        return None
    company_id = profile.get("CompanyId") or profile.get("companyId")
    if company_id is None:
        return None
    try:
        return int(company_id)
    except (ValueError, TypeError):
        logger.error(f"Invalid company_id from UserService: {company_id}")
        return None


def get_current_user_dependency(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    token = credentials.credentials
    user_info = get_current_user(token)
    user_info["_token"] = token

    user_id = user_info.get("user_id") or user_info.get("sub")
    company_id = None
    if user_id:
        newrelic.agent.add_custom_attribute('user_id', user_id)

        profile = UserService.get_user_info(user_id, token)
        user_info["_profile"] = profile
        company_id = _resolve_company_id(profile)
        if company_id is not None:
            newrelic.agent.add_custom_attribute('company_id', company_id)

    user_info["company_id"] = company_id
    return user_info


def get_db_dependency() -> Generator[Session, None, None]:
    yield from get_db()
