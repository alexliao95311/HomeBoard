from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.database import get_database_session
from app.models.user import User
from app.schemas.auth import AuthenticatedUser

router = APIRouter()

ALLOWED_MODELS = {
    "openai/gpt-4o",
    "anthropic/claude-sonnet-5",
    "google/gemini-3.5-flash",
    "x-ai/grok-4.3",
}


class UserSettingsResponse(BaseModel):
    preferred_model: str


class UserSettingsUpdateRequest(BaseModel):
    preferred_model: str


def _get_or_create_user(
    authenticated_user: AuthenticatedUser,
    session: Session,
) -> User:
    user = session.scalar(select(User).where(User.firebase_uid == authenticated_user.uid))
    if user is None:
        user = User(
            firebase_uid=authenticated_user.uid,
            email=authenticated_user.email,
            name=authenticated_user.name,
        )
        session.add(user)
        session.flush()
    return user


@router.get("", response_model=UserSettingsResponse)
def get_user_settings(
    authenticated_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_database_session)],
) -> UserSettingsResponse:
    user = _get_or_create_user(authenticated_user, session)
    session.commit()
    return UserSettingsResponse(
        preferred_model=user.preferred_model or "openai/gpt-4o",
    )


@router.patch("", response_model=UserSettingsResponse)
def update_user_settings(
    request: UserSettingsUpdateRequest,
    authenticated_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_database_session)],
) -> UserSettingsResponse:
    if request.preferred_model not in ALLOWED_MODELS:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Model must be one of: {', '.join(sorted(ALLOWED_MODELS))}",
        )
    user = _get_or_create_user(authenticated_user, session)
    user.preferred_model = request.preferred_model
    session.commit()
    return UserSettingsResponse(preferred_model=user.preferred_model)
