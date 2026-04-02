from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import DbSession, get_current_user, require_roles
from app.models.user import User, UserRole
from app.schemas.user import UserRead, UserRoleUpdate, UserStatusUpdate
from app.services.user_service import get_user_by_id, list_users, update_user_role, update_user_status

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserRead)
def read_me(current_user: Annotated[User, Depends(get_current_user)]) -> UserRead:
    return current_user


@router.get("", response_model=list[UserRead])
def read_users(
    db: DbSession, current_user: Annotated[User, Depends(require_roles(UserRole.admin))]
) -> list[UserRead]:
    return list_users(db)


@router.put("/{user_id}/role", response_model=UserRead)
def change_user_role(
    user_id: int,
    payload: UserRoleUpdate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_roles(UserRole.admin))],
) -> UserRead:
    target = get_user_by_id(db, user_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return update_user_role(db, target, payload.role)


@router.put("/{user_id}/status", response_model=UserRead)
def change_user_status(
    user_id: int,
    payload: UserStatusUpdate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_roles(UserRole.admin))],
) -> UserRead:
    target = get_user_by_id(db, user_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return update_user_status(db, current_user, target, payload.is_active)
