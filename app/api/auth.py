import base64
import os
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
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
from app.models.question import User

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
async def register(payload: AuthRequest, db: Session = Depends(get_db)):
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
        avatar_url=user.avatar_url,
    )


@router.post("/login", response_model=TokenResponse)
async def login(payload: AuthRequest, db: Session = Depends(get_db)):
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
        avatar_url=user.avatar_url,
    )


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    """获取当前登录用户信息"""
    return {
        "user_id": current_user.id,
        "username": current_user.username,
        "avatar_url": current_user.avatar_url,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
    }


@router.post("/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """上传用户头像（Base64 存入数据库）"""
    # 校验文件扩展名
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="仅支持 jpg/png/gif/webp 格式的图片")

    # 读取并校验大小
    content = await file.read()
    if len(content) > MAX_AVATAR_SIZE:
        raise HTTPException(status_code=400, detail="图片大小不能超过 2MB")

    # 转为 base64 数据 URI
    mime = MIME_MAP.get(ext, "image/jpeg")
    b64 = base64.b64encode(content).decode("ascii")
    avatar_data = f"data:{mime};base64,{b64}"

    # 重新从当前 db session 查询用户
    user = db.query(User).filter(User.id == current_user.id).first()

    # 更新数据库
    user.avatar_url = avatar_data
    db.commit()

    return {"avatar_url": avatar_data}
