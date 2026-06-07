import logging

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.schemas.user import LoginOut, UserLogin, UserOut, UserRegister
from app.services import audit
from app.services.auth import create_access_token, get_current_user, hash_password, verify_password

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=201)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    try:
        audit.log(db, action="registered", user_id=user.id)
    except Exception as e:
        logger.warning(f"Audit log failed for register user {user.id}: {e}")
    return user


@router.post("/login", response_model=LoginOut)
def login(payload: UserLogin, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        try:
            masked = payload.email[:3] + "***" if payload.email else "***"
            audit.log(db, action="login_failed", after_state={"email": masked})
        except Exception as e:
            logger.warning(f"Audit log failed for login_failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid credentials")
    try:
        audit.log(db, action="login_success", user_id=user.id)
    except Exception as e:
        logger.warning(f"Audit log failed for login_success user {user.id}: {e}")

    token = create_access_token(user.id)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )
    return {"access_token": token, "token_type": "bearer", "user": user}


@router.post("/logout")
def logout(response: Response):
    """Clear the httpOnly access_token cookie."""
    response.delete_cookie(key="access_token", path="/")
    return {"message": "Logged out"}


@router.get("/me", response_model=UserOut)
def get_me(user: User = Depends(get_current_user)):
    """Return the currently authenticated user. Used by frontend on startup
    to restore session state from the httpOnly cookie without storing the token in JS.
    """
    return user
