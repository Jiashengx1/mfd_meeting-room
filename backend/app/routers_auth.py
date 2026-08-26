from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User, UserRole
from app.schemas import LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.staff_id == payload.staff_id, User.is_active.is_(True)).one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="工号或密码错误")
    return TokenResponse(access_token=create_access_token(user.staff_id), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.post("/register", response_model=TokenResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    staff_id = payload.staff_id.strip()
    confirm_staff_id = payload.confirm_staff_id.strip()
    if staff_id != confirm_staff_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="两次输入的工号不一致")
    existing = db.query(User).filter(User.staff_id == staff_id).one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该工号已存在，请直接登录；登录密码与工号相同")
    user = User(
        staff_id=staff_id,
        name=payload.name.strip(),
        department=payload.department.strip(),
        role=UserRole.user.value,
        password_hash=hash_password(staff_id),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenResponse(access_token=create_access_token(user.staff_id), user=UserOut.model_validate(user))
