import os
import time
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.limiter import limiter
from app.core.security import (
    create_access_token,
    get_current_user,
    hash_password,
    is_legacy_hash,
    verify_password,
)
from app.models.user import User

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_AVATAR_SIZE = 2 * 1024 * 1024  # 2MB

router = APIRouter()

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
UPLOAD_DIR = os.path.join(PROJECT_ROOT, "uploads", "avatars")


class AuthRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str
    avatar_url: str | None = None


@router.post("/register", response_model=TokenResponse)
@limiter.limit("10/minute")
async def register(
    request: Request,
    payload: AuthRequest,
    db: Session = Depends(get_db),
):
    existing = db.query(User).filter(User.username == payload.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")

    user = User(username=payload.username, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id, user.username)
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        username=user.username,
        avatar_url=_resolve_avatar_url(user),
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    payload: AuthRequest,
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if is_legacy_hash(user.password_hash):
        user.password_hash = hash_password(payload.password)
        db.commit()

    token = create_access_token(user.id, user.username)
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        username=user.username,
        avatar_url=_resolve_avatar_url(user),
    )


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return {
        "user_id": current_user.id,
        "username": current_user.username,
        "avatar_url": _resolve_avatar_url(current_user),
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
    }


@router.post("/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="仅支持 jpg/png/gif/webp 格式的图片")

    content = await file.read()
    if len(content) > MAX_AVATAR_SIZE:
        raise HTTPException(status_code=400, detail="图片大小不能超过 2MB")

    user = db.query(User).filter(User.id == current_user.id).first()
    _remove_old_avatar(user.avatar_url)

    filename = f"user_{user.id}_{int(time.time())}{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    with open(filepath, "wb") as f:
        f.write(content)

    user.avatar_url = f"avatars/{filename}"
    db.commit()

    return {"avatar_url": f"/uploads/avatars/{filename}"}


def _resolve_avatar_url(user: User) -> Optional[str]:
    if not user.avatar_url:
        return None
    if user.avatar_url.startswith("data:"):
        return user.avatar_url
    relative_path = _normalize_avatar_relative_path(user.avatar_url)
    if relative_path and os.path.exists(os.path.join(PROJECT_ROOT, "uploads", relative_path)):
        return f"/uploads/{relative_path}"
    return None


def _remove_old_avatar(avatar_url: Optional[str]):
    if not avatar_url or avatar_url.startswith("data:"):
        return
    relative_path = _normalize_avatar_relative_path(avatar_url)
    if not relative_path or not relative_path.startswith("avatars/"):
        return
    filepath = os.path.join(PROJECT_ROOT, "uploads", relative_path)
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
        except OSError:
            pass


def _normalize_avatar_relative_path(avatar_url: str) -> Optional[str]:
    if avatar_url.startswith("avatars/"):
        return avatar_url
    if avatar_url.startswith("/uploads/"):
        return avatar_url.removeprefix("/uploads/")
    if avatar_url.startswith("uploads/"):
        return avatar_url.removeprefix("uploads/")
    return None
