"""Auth router — register / login / me / forgot-password."""
import random
import string
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.db import get_db
from app.db.models import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# 内存验证码存储：phone -> (code, expires_at)。MVP 单进程够用；多 worker 需换 Redis。
_PWD_RESET_CODES: dict[str, tuple[str, float]] = {}
_PWD_RESET_TTL = timedelta(minutes=10)
_PWD_RESET_CODE_LEN = 6


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.username == body.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")

    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        phone=body.phone,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token)


@router.post("/forgot-password/request-code", status_code=status.HTTP_200_OK)
async def forgot_password_request_code(body: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    """找回密码第一步：按手机号定位账号并"发送"验证码。

    生产环境应接入短信服务商（阿里云/腾讯云 SMS）；MVP 用内存验证码，
    DEBUG 模式下把验证码直接放进响应（前端 toast 提示），方便体验联调。
    """
    user = (await db.execute(select(User).where(User.phone == body.phone))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="该手机号未注册")

    code = "".join(random.choices(string.digits, k=_PWD_RESET_CODE_LEN))
    import time as _time

    _PWD_RESET_CODES[body.phone] = (code, _time.time() + _PWD_RESET_TTL.total_seconds())

    resp: dict = {"message": "验证码已发送"}
    if settings.DEBUG:
        resp["debug_code"] = code  # 仅开发环境返回，生产严禁
    return resp


@router.post("/forgot-password/reset", status_code=status.HTTP_200_OK)
async def forgot_password_reset(body: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    """找回密码第二步：验证码校验 + 重置密码。"""
    import time as _time

    stored = _PWD_RESET_CODES.get(body.phone)
    if not stored or stored[1] < _time.time():
        _PWD_RESET_CODES.pop(body.phone, None)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="验证码无效或已过期")

    code, _ = stored
    if code != body.code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="验证码错误")

    user = (await db.execute(select(User).where(User.phone == body.phone))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="该手机号未注册")

    user.password_hash = hash_password(body.new_password)
    await db.commit()
    _PWD_RESET_CODES.pop(body.phone, None)  # 一次性：重置后作废

    return {"message": "密码已重置，请使用新密码登录"}


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=str(current_user.id),
        username=current_user.username,
        major=current_user.major,
        is_member=current_user.is_member,
        is_active=True,
    )
