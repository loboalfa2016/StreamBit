from fastapi import Depends, HTTPException, status 
from app.api.auth import get_current_user
from app.models.user import User

VALID_ROLES = {"user", "moderator", "admin"}


def require_roles(*allowed_roles: str):
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos suficientes para realizar esta acción."
            )
        return current_user

    return role_checker