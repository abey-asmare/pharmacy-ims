"""Request/response schemas for /auth and /users (SDD Table 3.3)."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.auth.models import Role


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int


class UserCreateRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8)
    role: Role


class UserRoleUpdateRequest(BaseModel):
    role: Role


class UserStatusUpdateRequest(BaseModel):
    is_active: bool


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    email: EmailStr
    role: Role
    is_active: bool
    created_at: datetime


class CurrentUser(BaseModel):
    """Lightweight view of the authenticated user, attached to each request."""

    id: uuid.UUID
    role: Role