from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exceptions import BadRequestError, ConflictError, NotFoundError
from app.models.user import User, UserRole
from app.schemas.user import PublicUserCreate, UserCreate
from app.services.auth_service import get_password_hash


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email))


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def list_users(db: Session) -> list[User]:
    return list(db.scalars(select(User).order_by(User.created_at.desc())))


def create_user(db: Session, payload: UserCreate) -> User:
    existing = get_user_by_email(db, payload.email)
    if existing:
        raise ConflictError("Email already registered")

    user = User(
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
        full_name=payload.full_name,
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def register_user(db: Session, payload: PublicUserCreate) -> User:
    existing = get_user_by_email(db, payload.email)
    if existing:
        raise ConflictError("Email already registered")

    user = User(
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
        full_name=payload.full_name,
        role=UserRole.viewer,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user_role(db: Session, target_user: User, role: UserRole) -> User:
    target_user.role = role
    db.add(target_user)
    db.commit()
    db.refresh(target_user)
    return target_user


def update_user_status(db: Session, current_user: User, target_user: User, is_active: bool) -> User:
    if current_user.id == target_user.id and not is_active:
        raise BadRequestError("User cannot deactivate themselves")

    target_user.is_active = is_active
    db.add(target_user)
    db.commit()
    db.refresh(target_user)
    return target_user


def get_user_by_id_or_404(db: Session, user_id: int) -> User:
    user = get_user_by_id(db, user_id)
    if user is None:
        raise NotFoundError("User not found")
    return user
