import logging
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_action_token,
    decode_access_token,
    revoke_token,
    check_rate_limit,
)
from app.models.user import User
from app.schemas.user import (
    UserRegister,
    UserResponse,
    UserLogin,
    TokenResponse,
    EmailRequest,
    VerifyEmailRequest,
    ResetPasswordRequest,
)

logger = logging.getLogger("streambit.auth")
logging.basicConfig(level=logging.INFO)

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])
bearer_scheme = HTTPBearer()
optional_bearer_scheme = HTTPBearer(auto_error=False)


async def _resolve_user_from_token(token: str, db: AsyncSession) -> User:
    payload = decode_access_token(token, expected_type="access")
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado.",
        )

    stmt = select(User).where(User.id == int(payload["sub"]))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no autorizado o inactivo.",
        )
    return user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    return await _resolve_user_from_token(credentials.credentials, db)


async def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    if credentials is None:
        return None
    return await _resolve_user_from_token(credentials.credentials, db)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(user_in: UserRegister, db: AsyncSession = Depends(get_db)):
    normalized_email = user_in.email.lower().strip()
    normalized_username = user_in.username.strip()

    stmt = select(User).where(
        or_(User.email == normalized_email, User.username == normalized_username)
    )
    result = await db.execute(stmt)
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se pudo completar el registro con los datos proporcionados."
        )

    new_user = User(
        username=normalized_username,
        email=normalized_email,
        hashed_password=get_password_hash(user_in.password),
        role="user",
        is_verified=False,
        is_active=True
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    logger.info("EVENT=USER_REGISTERED user_id=%s", new_user.id)
    return new_user


@router.post("/login", response_model=TokenResponse)
async def login_user(credentials: UserLogin, db: AsyncSession = Depends(get_db)):
    normalized_email = credentials.email.lower().strip()

    stmt = select(User).where(User.email == normalized_email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not verify_password(credentials.password, user.hashed_password):
        logger.warning("EVENT=LOGIN_FAILED")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas."
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta se encuentra desactivada."
        )

    access_token = create_access_token(subject=str(user.id), role=user.role)
    logger.info("EVENT=LOGIN_SUCCESS user_id=%s", user.id)
    return TokenResponse(access_token=access_token)


@router.get("/me", response_model=UserResponse)
async def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    payload = decode_access_token(credentials.credentials, expected_type="access")
    if not payload or "jti" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o ya revocado.",
        )

    revoke_token(payload["jti"])
    logger.info("EVENT=LOGOUT_SUCCESS user_id=%s", payload.get("sub"))
    return {"message": "Sesión cerrada correctamente."}


@router.post("/request-verification", status_code=status.HTTP_200_OK)
async def request_email_verification(data: EmailRequest, db: AsyncSession = Depends(get_db)):
    normalized_email = data.email.lower().strip()

    if not check_rate_limit(f"verify:{normalized_email}"):
        logger.warning("EVENT=VERIFICATION_RATE_LIMITED")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiadas solicitudes. Intenta nuevamente en unos minutos."
        )

    stmt = select(User).where(User.email == normalized_email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user and not user.is_verified:
        token = create_action_token(subject=str(user.id), purpose="email_verify", expire_minutes=15)
        logger.info("EVENT=EMAIL_VERIFICATION_REQUESTED user_id=%s", user.id)
        if settings.ENVIRONMENT == "development":
            print(f"\n[DEV ONLY] Token de verificación para user_id={user.id}: {token}\n", flush=True)

    return {"message": "Si el correo está registrado y pendiente de verificación, recibirás un enlace temporal."}


@router.post("/verify-email", status_code=status.HTTP_200_OK)
async def verify_email(data: VerifyEmailRequest, db: AsyncSession = Depends(get_db)):
    payload = decode_access_token(data.token, expected_type="email_verify")
    if not payload or "sub" not in payload or "jti" not in payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El enlace de verificación es inválido o ha expirado."
        )

    stmt = select(User).where(User.id == int(payload["sub"]))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El enlace de verificación es inválido o ha expirado."
        )

    user.is_verified = True
    await db.commit()
    revoke_token(payload["jti"])

    logger.info("EVENT=EMAIL_VERIFIED user_id=%s", user.id)
    return {"message": "Correo verificado correctamente."}


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
async def forgot_password(data: EmailRequest, db: AsyncSession = Depends(get_db)):
    normalized_email = data.email.lower().strip()

    if not check_rate_limit(f"reset:{normalized_email}"):
        logger.warning("EVENT=PASSWORD_RESET_RATE_LIMITED")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiadas solicitudes. Intenta nuevamente en unos minutos."
        )

    stmt = select(User).where(User.email == normalized_email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user and user.is_active:
        token = create_action_token(subject=str(user.id), purpose="password_reset", expire_minutes=15)
        logger.info("EVENT=PASSWORD_RESET_REQUESTED user_id=%s", user.id)
        if settings.ENVIRONMENT == "development":
            print(f"\n[DEV ONLY] Token de recuperación para user_id={user.id}: {token}\n", flush=True)

    return {"message": "Si el correo está registrado, recibirás instrucciones para restablecer tu contraseña."}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(data: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    payload = decode_access_token(data.token, expected_type="password_reset")
    if not payload or "sub" not in payload or "jti" not in payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El token de recuperación es inválido o ha expirado."
        )

    stmt = select(User).where(User.id == int(payload["sub"]))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El token de recuperación es inválido o ha expirado."
        )

    user.hashed_password = get_password_hash(data.new_password)
    await db.commit()
    revoke_token(payload["jti"])

    logger.info("EVENT=PASSWORD_RESET_COMPLETED user_id=%s", user.id)
    return {"message": "Contraseña actualizada correctamente."}