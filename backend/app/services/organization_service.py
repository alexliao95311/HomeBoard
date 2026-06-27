from dataclasses import dataclass
import uuid

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from typing import Annotated

from app.api.routes.auth import get_current_user
from app.database import get_database_session
from app.models.organization import Organization, OrganizationMembership
from app.models.user import User
from app.schemas.auth import AuthenticatedUser


@dataclass(frozen=True)
class OrganizationContext:
    organization_id: uuid.UUID
    user_id: uuid.UUID
    role: str


def _default_organization_name(user: AuthenticatedUser) -> str:
    identity = user.name or user.email or "My"
    return f"{identity[:240]}'s HOA"


def get_current_organization(
    authenticated_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_database_session)],
) -> OrganizationContext:
    """Return the user's current organization, provisioning the first one."""
    user = session.scalar(
        select(User).where(User.firebase_uid == authenticated_user.uid)
    )

    if user is None:
        user = User(
            firebase_uid=authenticated_user.uid,
            email=authenticated_user.email,
            name=authenticated_user.name,
        )
        session.add(user)
        session.flush()
    else:
        user.email = authenticated_user.email
        user.name = authenticated_user.name

    membership = session.scalar(
        select(OrganizationMembership)
        .where(OrganizationMembership.user_id == user.id)
        .order_by(OrganizationMembership.created_at)
    )

    if membership is None:
        organization = Organization(name=_default_organization_name(authenticated_user))
        session.add(organization)
        session.flush()
        membership = OrganizationMembership(
            organization_id=organization.id,
            user_id=user.id,
            role="admin",
        )
        session.add(membership)

    session.commit()
    return OrganizationContext(
        organization_id=membership.organization_id,
        user_id=user.id,
        role=membership.role,
    )
