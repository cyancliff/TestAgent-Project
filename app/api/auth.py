import os
import time
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    create_access_token,
    get_current_user,
    hash_password,
    is_legacy_hash,
    verify_password,
)
from app.models.user import User

from app.core.limiter import limiter

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_AVATAR_SIZE = 2 * 1024 * 1024  # 2MB

MIME_MAP = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}

router = APIRouter()

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads", "avatars")


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

    # 自动迁移旧版 SHA256 密码到 bcrypt
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
    """获取当前登录用户信息"""
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
    """上传用户头像，文件存储到 uploads/avatars/"""
    # 校验文件扩展名
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="仅支持 jpg/png/gif/webp 格式的图片")

    # 读取并校验大小
    content = await file.read()
    if len(content) > MAX_AVATAR_SIZE:
        raise HTTPException(status_code=400, detail="图片大小不能超过 2MB")

    # 删除旧头像文件（如果存在且是本地文件）
    user = db.query(User).filter(User.id == current_user.id).first()
    _remove_old_avatar(user.avatar_url)

    # 生成文件名：user_{id}_{timestamp}.{ext}
    filename = f"user_{user.id}_{int(time.time())}{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    with open(filepath, "wb") as f:
        f.write(content)

    # 数据库存相对路径
    user.avatar_url = f"avatars/{filename}"
    db.commit()

    return {"avatar_url": f"/uploads/avatars/{filename}"}


def _resolve_avatar_url(user: User) -> Optional[str]:
    """兼容旧版 base64 数据，新版返回 /uploads/avatars/ 路径"""
    if not user.avatar_url:
        return None
    if user.avatar_url.startswith("data:"):
        # 旧版 base64 数据，直接返回（前端需兼容）
        return user.avatar_url
    if user.avatar_url.startswith("avatars/"):
        # 新版文件系统路径
        return f"/uploads/{user.avatar_url}"
    return user.avatar_url


def _remove_old_avatar(avatar_url: Optional[str]):
    """删除旧的头像文件"""
    if not avatar_url or avatar_url.startswith("data:"):
        return
    if avatar_url.startswith("avatars/"):
        filepath = os.path.join(UPLOAD_DIR, avatar_url)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except OSError:
                pass
