"""Users & roles Pydantic DTOs."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.domain.value_objects.cedula import Cedula


class CreateUserDto(BaseModel):
    username: str = Field(min_length=3, max_length=30)
    name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    cedula: str | None = Field(default=None, max_length=20)
    email: EmailStr
    password: str = Field(min_length=8, max_length=10)
    role_ids: list[int] = Field(default_factory=list)

    @field_validator("cedula")
    @classmethod
    def _validate_cedula(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        cleaned = value.strip().replace(" ", "").replace("-", "")
        Cedula(cleaned)
        return cleaned


class UpdateUserDto(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    cedula: str | None = Field(default=None, max_length=20)
    email: EmailStr | None = None
    is_active: bool | None = None

    @field_validator("cedula")
    @classmethod
    def _validate_cedula(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        cleaned = value.strip().replace(" ", "").replace("-", "")
        Cedula(cleaned)
        return cleaned


class AssignRolesDto(BaseModel):
    role_ids: list[int]


class UserResponseDto(BaseModel):
    id: int
    username: str
    email: EmailStr
    name: str
    last_name: str
    cedula: str | None
    is_active: bool
    roles: list[str]


class RoleResponseDto(BaseModel):
    id: int
    name: str
    description: str | None


class ErrorLogResponseDto(BaseModel):
    id: int
    message: str
    exception_type: str | None
    user_id: int | None
    path: str
    source: str | None
    created_at: str
