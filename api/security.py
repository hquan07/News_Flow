from collections.abc import Callable
from typing import Annotated

import jwt
from bson import ObjectId
from fastapi import Cookie, Header, HTTPException, status

from api.config import get_settings
from api.database import get_mongo_db


ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "user": frozenset({
        "dashboard.read",
        "reports.export",
    }),
    "analyst": frozenset({
        "dashboard.read",
        "reports.export",
        "reports.export_full",
    }),
    "operator": frozenset({
        "dashboard.read",
        "reports.export",
        "alerts.read",
        "alerts.manage",
        "crawler.read",
        "crawler.run",
        "system.read",
    }),
    "admin": frozenset({
        "dashboard.read",
        "reports.export",
        "reports.export_full",
        "alerts.read",
        "alerts.manage",
        "crawler.read",
        "crawler.run",
        "system.read",
        "users.manage",
        "audit.read",
        "mock_data.create",
    }),
}

VALID_ROLES = frozenset(ROLE_PERMISSIONS)


def permissions_for_role(role: str | None) -> list[str]:
    return sorted(ROLE_PERMISSIONS.get(role or "", frozenset()))


def create_access_token(payload: dict) -> str:
    settings = get_settings()
    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    access_token: Annotated[str | None, Cookie()] = None,
) -> dict:
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
    elif access_token:
        token = access_token
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
        )
    authenticated_user = decode_access_token(token)
    role = authenticated_user.get("role", "user")
    subject = str(authenticated_user.get("sub", ""))
    if ObjectId.is_valid(subject):
        account = await get_mongo_db().users.find_one(
            {"_id": ObjectId(subject)},
            {"email": 1, "role": 1, "is_active": 1},
        )
        if account is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account no longer exists",
            )
        if account.get("is_active", True) is False:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is disabled",
            )
        role = account.get("role", "user")
        authenticated_user["email"] = account.get(
            "email", authenticated_user.get("email", "")
        )
    if role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Unknown account role",
        )
    return {
        **authenticated_user,
        "role": role,
        "permissions": permissions_for_role(role),
    }


def require_permission(permission: str) -> Callable:
    async def permission_dependency(
        authorization: Annotated[str | None, Header()] = None,
        access_token: Annotated[str | None, Cookie()] = None,
    ) -> dict:
        authenticated_user = await get_current_user(authorization, access_token)
        if permission not in authenticated_user["permissions"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Missing permission '{permission}'",
            )
        return authenticated_user

    return permission_dependency


async def get_admin_user(
    authorization: Annotated[str | None, Header()] = None,
    access_token: Annotated[str | None, Cookie()] = None,
) -> dict:
    return await require_permission("users.manage")(
        authorization=authorization,
        access_token=access_token,
    )
