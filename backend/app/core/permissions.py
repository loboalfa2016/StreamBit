from fastapi import Depends, HTTPException, status

from app.api.auth import get_current_user
from app.models.user import User

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "user": set(),
    "analyst": {
        "admin:read",
        "users:read",
        "catalog:read",
        "ads:read",
        "analytics:read",
        "view_moderation",
    },
    "catalog_manager": {
        "admin:read",
        "catalog:read",
        "catalog:write",
    },
    "ads_manager": {
        "admin:read",
        "ads:read",
        "ads:write",
    },
    "admin": {
        "admin:read",
        "users:read",
        "users:manage_roles",
        "catalog:read",
        "catalog:write",
        "ads:read",
        "ads:write",
        "analytics:read",
        "view_moderation",
        "moderate_comments",
    },
}


def require_roles(*allowed_roles: str):
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos suficientes para realizar esta acción.",
            )
        return current_user

    return role_checker


def require_permission(permission: str):
    async def permission_checker(current_user: User = Depends(get_current_user)) -> User:
        user_permissions = ROLE_PERMISSIONS.get(current_user.role, set())
        if permission not in user_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permiso denegado: se requiere '{permission}'.",
            )
        return current_user

    return permission_checker