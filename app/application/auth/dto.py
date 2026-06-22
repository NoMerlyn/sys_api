"""Auth Pydantic DTOs."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class LoginDto(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class RegisterUserDto(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    cedula: str | None = Field(default=None, max_length=20)
    email: EmailStr
    password: str = Field(min_length=8, max_length=10)
    role_ids: list[int] = Field(default_factory=list)


class AuthResponseDto(BaseModel):
    access_token: str
    expires_in: int


class MeResponseDto(BaseModel):
    id: int
    username: str
    email: EmailStr
    name: str
    last_name: str
    roles: list[str]
