"""Auth schemas."""
from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=150)
    password: str = Field(min_length=6, max_length=128)
    phone: str | None = Field(default=None, min_length=11, max_length=11)


class LoginRequest(BaseModel):
    username: str
    password: str


class ForgotPasswordRequest(BaseModel):
    """找回密码第一步：手机号 → 发验证码。"""

    phone: str = Field(min_length=11, max_length=11)


class ResetPasswordRequest(BaseModel):
    """找回密码第二步：验证码 + 新密码。"""

    phone: str = Field(min_length=11, max_length=11)
    code: str = Field(min_length=4, max_length=8)
    new_password: str = Field(min_length=6, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    username: str
    major: str | None = None
    is_member: bool
    is_active: bool
