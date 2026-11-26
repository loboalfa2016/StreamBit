from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import bearer_scheme, get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.permissions import require_permission
from app.core.security import decode_access_token, revoke_token, verify_password
from app.models.community import Comment, Rating
from app.models.notifications import MovieAvailabilityAlert, Notification
from app.models.user import User
from app.models.user_lists import Favorite, UserList
from app.models.watch_history import WatchHistory
from app.schemas.privacy import (
    AccountDeleteRequest,
    PrivacyPolicyResponse,
    RetentionCleanupResponse,
    UserDataExportResponse,
    UserProfileExport,
    UserProfileRectifyRequest,
)
from app.services.audit import record_admin_audit

router = APIRouter(tags=["Privacy & Data Protection"])


@router.get(
    "/privacy/policy",
    response_model=PrivacyPolicyResponse,
    summary="Consultar política de privacidad, minimización de datos y retención",
)
async def get_privacy_policy():
    return PrivacyPolicyResponse(
        version="1.0.0",
        last_updated="2026-11-26",
        data_collected={
            "cookies_and_sessions": "Tokens JWT de autenticación en cabecera Authorization Bearer; sin cookies de rastreo de terceros.",
            "analytics": "Métricas agregadas de catálogo, reproducciones verificadas y clics publicitarios sin perfilamiento invasivo.",
            "advertising": "Anuncios pre-roll limitados por sesión de reproducción (playback_session_id) y código de país ISO-2.",
            "playback_history": "Último evento de reproducción, posición y estado verificado asociado únicamente a usuarios autenticados (sin IP ni User-Agent).",
            "community": "Comentarios y calificaciones; para visitantes sin cuenta se usa únicamente un hash SHA-256 con sal secreta para control antiduplicados.",
        },
        retention_policy={
            "history_retention_days": settings.HISTORY_RETENTION_DAYS,
            "notifications_retention_days": settings.NOTIFICATIONS_RETENTION_DAYS,
        },
        user_rights=[
            {
                "right": "Acceso y portabilidad",
                "endpoint": "GET /api/v1/me/privacy/export",
            },
            {
                "right": "Rectificación de perfil",
                "endpoint": "PATCH /api/v1/me/privacy/profile",
            },
            {
                "right": "Supresión / Eliminación de cuenta",
                "endpoint": "DELETE /api/v1/me/privacy/account",
            },
        ],
        regional_compliance_notes=(
            "Diseñado bajo principios de minimización, finalidad y derechos ARCO "
            "(Acceso, Rectificación, Cancelación y Oposición) aplicables en Latinoamérica "
            "(Ley 1581 de 2012 en Colombia, LFPDPPP en México, LGPD en Brasil y equivalentes regionales)."
        ),
    )


@router.get(
    "/me/privacy/export",
    response_model=UserDataExportResponse,
    summary="Exportar todos los datos personales del usuario autenticado",
)
async def export_my_data(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    favorites = list(
        (
            await db.execute(
                select(Favorite).where(Favorite.user_id == current_user.id)
            )
        )
        .scalars()
        .all()
    )
    user_lists = list(
        (
            await db.execute(
                select(UserList)
                .options(selectinload(UserList.items))
                .where(UserList.user_id == current_user.id)
            )
        )
        .scalars()
        .all()
    )
    history = list(
        (
            await db.execute(
                select(WatchHistory).where(WatchHistory.user_id == current_user.id)
            )
        )
        .scalars()
        .all()
    )
    ratings = list(
        (
            await db.execute(
                select(Rating).where(Rating.user_id == current_user.id)
            )
        )
        .scalars()
        .all()
    )
    comments = list(
        (
            await db.execute(
                select(Comment).where(Comment.user_id == current_user.id)
            )
        )
        .scalars()
        .all()
    )
    alerts = list(
        (
            await db.execute(
                select(MovieAvailabilityAlert).where(
                    MovieAvailabilityAlert.user_id == current_user.id
                )
            )
        )
        .scalars()
        .all()
    )
    notifications = list(
        (
            await db.execute(
                select(Notification).where(Notification.user_id == current_user.id)
            )
        )
        .scalars()
        .all()
    )

    return UserDataExportResponse(
        exported_at=datetime.now(timezone.utc),
        profile=UserProfileExport.model_validate(current_user),
        favorites=[
            {"movie_id": f.movie_id, "created_at": f.created_at} for f in favorites
        ],
        lists=[
            {
                "id": ul.id,
                "name": ul.name,
                "description": ul.description,
                "movie_ids": [item.movie_id for item in ul.items],
                "created_at": ul.created_at,
            }
            for ul in user_lists
        ],
        watch_history=[
            {
                "movie_id": h.movie_id,
                "last_event": h.last_event,
                "position_seconds": h.position_seconds,
                "is_completed_verified": h.is_completed_verified,
                "last_watched_at": h.last_watched_at,
            }
            for h in history
        ],
        ratings=[
            {
                "movie_id": r.movie_id,
                "score": r.score,
                "created_at": r.created_at,
                "updated_at": r.updated_at,
            }
            for r in ratings
        ],
        comments=[
            {
                "id": c.id,
                "movie_id": c.movie_id,
                "parent_id": c.parent_id,
                "content": c.content,
                "created_at": c.created_at,
            }
            for c in comments
        ],
        availability_alerts=[
            {"movie_id": a.movie_id, "created_at": a.created_at} for a in alerts
        ],
        notifications=[
            {
                "id": n.id,
                "type": n.type,
                "title": n.title,
                "message": n.message,
                "is_read": n.is_read,
                "created_at": n.created_at,
            }
            for n in notifications
        ],
    )


@router.patch(
    "/me/privacy/profile",
    response_model=UserProfileExport,
    summary="Rectificar datos del perfil propio (username)",
)
async def rectify_my_profile(
    payload: UserProfileRectifyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    new_username = payload.username.strip()
    if len(new_username) < 3:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El nombre de usuario debe tener al menos 3 caracteres.",
        )

    existing = (
        await db.execute(
            select(User.id).where(
                User.username == new_username,
                User.id != current_user.id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El nombre de usuario ya está en uso.",
        )

    old_username = current_user.username
    current_user.username = new_username

    await record_admin_audit(
        db=db,
        actor_user_id=current_user.id,
        action="user_profile_rectified",
        resource_type="user",
        resource_id=str(current_user.id),
        details={"old_username": old_username, "new_username": new_username},
        commit=False,
    )
    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.delete(
    "/me/privacy/account",
    status_code=status.HTTP_200_OK,
    summary="Eliminar cuenta y datos personales propios (con confirmación de contraseña)",
)
async def delete_my_account(
    payload: AccountDeleteRequest,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not payload.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debes confirmar explícitamente la eliminación de tu cuenta (confirm=true).",
        )

    if not verify_password(payload.password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Contraseña actual incorrecta.",
        )

    user_id_str = str(current_user.id)
    await record_admin_audit(
        db=db,
        actor_user_id=current_user.id,
        action="user_account_deleted",
        resource_type="user",
        resource_id=user_id_str,
        details={"reason": "self_service_erasure"},
        commit=False,
    )
    await db.flush()

    await db.delete(current_user)
    await db.commit()

    token_payload = decode_access_token(credentials.credentials, expected_type="access")
    if token_payload and "jti" in token_payload:
        revoke_token(token_payload["jti"])

    return {"message": "Cuenta y datos personales eliminados correctamente."}


@router.post(
    "/admin/privacy/retention-cleanup",
    response_model=RetentionCleanupResponse,
    summary="Ejecutar limpieza por política de retención de historial y notificaciones leídas",
)
async def run_retention_cleanup(
    actor: User = Depends(require_permission("manage_users")),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    history_cutoff = now - timedelta(days=settings.HISTORY_RETENTION_DAYS)
    notif_cutoff = now - timedelta(days=settings.NOTIFICATIONS_RETENTION_DAYS)

    res_hist = await db.execute(
        delete(WatchHistory).where(WatchHistory.last_watched_at < history_cutoff)
    )
    res_notif = await db.execute(
        delete(Notification).where(
            Notification.is_read.is_(True),
            Notification.created_at < notif_cutoff,
        )
    )

    deleted_history = int(res_hist.rowcount or 0)
    deleted_notifs = int(res_notif.rowcount or 0)

    await record_admin_audit(
        db=db,
        actor_user_id=actor.id,
        action="retention_cleanup_executed",
        resource_type="system",
        resource_id=None,
        details={
            "deleted_history_records": deleted_history,
            "deleted_read_notifications": deleted_notifs,
        },
        commit=False,
    )
    await db.commit()

    return RetentionCleanupResponse(
        deleted_history_records=deleted_history,
        deleted_read_notifications=deleted_notifs,
        executed_at=now,
    )
