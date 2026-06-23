"""Auth router (login, register, me)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status

from app.application.auth import (
    GetCurrentUserHandler,
    GetCurrentUserQuery,
    LoginCommand,
    LoginHandler,
    LoginResult,
    RegisterUserCommand,
    RegisterUserHandler,
)
from app.application.auth.dto import (
    AuthResponseDto,
    LoginDto,
    MeResponseDto,
    RegisterUserDto,
)
from app.application.common.interfaces.user_repository import IUserRepository
from app.application.common.uow import uow
from app.core.rate_limit import limiter
from app.presentation.deps import CurrentUserDep, require_role

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_repo() -> IUserRepository:
    """Repository factory. FastAPI will instantiate per request via Depends."""
    raise NotImplementedError("Rewire to use request-scoped session dependency")


async def get_user_repo() -> IUserRepository:
    """Real factory: returns a repo bound to the request's session."""
    raise NotImplementedError("Rewire to use request-scoped session dependency")


@router.post("/login", response_model=AuthResponseDto)
@limiter.limit("5/minute")
async def login(request: Request, payload: LoginDto) -> AuthResponseDto:
    ip = request.client.host if request.client else None
    async with uow() as session:
        from app.infrastructure.repositories.user_repository import SqlUserRepository

        handler = LoginHandler(SqlUserRepository(session))
        try:
            result: LoginResult = await handler.handle(
                LoginCommand(email=payload.email, password=payload.password)
            )
        except Exception as exc:
            # Open a fresh uow() to record the failure outside the failing
            # transaction (the original one was rolled back by the time we
            # got here).
            try:
                async with uow() as fail_session:
                    from app.application.audit import audit as _audit

                    async with _audit(fail_session) as log:
                        await log.add(
                            action="LOGIN_FAILED",
                            entity="USER",
                            detail=str(getattr(exc, "detail", str(exc)))[:255] or None,
                            ip_address=ip,
                        )
            except Exception:
                pass
            raise
    # Audit success in a separate transaction.
    async with uow() as session:
        from app.application.audit import audit

        async with audit(session) as log:
            await log.add(
                action="LOGIN_SUCCESS",
                entity="USER",
                detail=payload.email,
                ip_address=ip,
            )
    return AuthResponseDto(access_token=result.access_token, expires_in=result.expires_in)


@router.post(
    "/register",
    response_model=MeResponseDto,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("ADMINISTRATOR"))],
)
async def register(payload: RegisterUserDto) -> MeResponseDto:
    async with uow() as session:
        from app.infrastructure.repositories.role_repository import SqlRoleRepository
        from app.infrastructure.repositories.user_repository import SqlUserRepository

        handler = RegisterUserHandler(SqlUserRepository(session), SqlRoleRepository(session))
        user_id = await handler.handle(
            RegisterUserCommand(
                username=payload.username,
                name=payload.name,
                last_name=payload.last_name,
                cedula=payload.cedula,
                email=payload.email,
                password=payload.password,
                role_ids=payload.role_ids,
            )
        )
        # Re-fetch to populate MeResponseDto.
        me_handler = GetCurrentUserHandler(SqlUserRepository(session))
        me = await me_handler.handle(GetCurrentUserQuery(user_id=user_id))
    return MeResponseDto(
        id=me.id,
        username=me.username,
        email=me.email,
        name=me.name,
        last_name=me.last_name,
        roles=me.roles,
    )


@router.get("/me", response_model=MeResponseDto)
async def me(user: CurrentUserDep) -> MeResponseDto:
    async with uow() as session:
        from app.infrastructure.repositories.user_repository import SqlUserRepository

        handler = GetCurrentUserHandler(SqlUserRepository(session))
        me = await handler.handle(GetCurrentUserQuery(user_id=user.id))
    return MeResponseDto(
        id=me.id,
        username=me.username,
        email=me.email,
        name=me.name,
        last_name=me.last_name,
        roles=me.roles,
    )
