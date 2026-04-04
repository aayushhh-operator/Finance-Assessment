from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app.rate_limiting import LOGIN_LIMIT, REGISTER_LIMIT, create_rate_limiter
from app.schemas.user import Token, UserCreate, UserRead
from app.services.auth_service import create_access_token, verify_password
from app.services.user_service import create_user, get_user_by_email

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(
    payload: UserCreate,
    _: Annotated[None, Depends(create_rate_limiter(REGISTER_LIMIT, key_strategy="ip"))],
    db: Annotated[Session, Depends(get_db)],
) -> UserRead:
    return create_user(db, payload)


@router.post("/login", response_model=Token)
def login(
    _: Annotated[None, Depends(create_rate_limiter(LOGIN_LIMIT, key_strategy="ip"))],
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[Session, Depends(get_db)],
) -> Token:
    user = get_user_by_email(db, form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user account")

    access_token = create_access_token(subject=user.email)
    return Token(access_token=access_token)
