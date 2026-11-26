from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_optional_current_user
from app.core.database import get_db
from app.core.permissions import require_permission
from app.core.security import build_visitor_fingerprint, check_rate_limit
from app.models.community import Comment
from app.models.moderation import CommentReport, ModerationLog
from app.models.user import User
from app.schemas.moderation import (
    CommentReportCreateRequest,
    CommentReportListResponse,
    CommentReportResponse,
    ModerationActionRequest,
    ModerationLogListResponse,
)

router = APIRouter(tags=["Moderation"])


async def _set_comment_visibility(
    db: AsyncSession,
    comment_id: int,
    is_hidden: bool,
    action: str,
    admin_user: User,
    reason: Optional[str],
) -> dict:
    comment = (
        await db.execute(select(Comment).where(Comment.id == comment_id))
    ).scalar_one_or_none()
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comentario no encontrado.",
        )

    now = datetime.now(timezone.utc)
    comment.is_hidden = is_hidden
    comment.updated_at = now

    await db.execute(
        update(CommentReport)
        .where(
            CommentReport.comment_id == comment_id,
            CommentReport.status == "pending",
        )
        .values(status="reviewed", reviewed_at=now, reviewed_by=admin_user.id)
    )

    log_entry = ModerationLog(
        comment_id=comment.id,
        admin_user_id=admin_user.id,
        action=action,
        reason=reason,
    )
    db.add(log_entry)
    await db.commit()

    return {
        "comment_id": comment.id,
        "is_hidden": comment.is_hidden,
        "action": action,
    }


@router.post(
    "/comments/{comment_id}/reports",
    response_model=CommentReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Denunciar un comentario visible",
)
async def report_comment(
    comment_id: int,
    payload: CommentReportCreateRequest,
    request: Request,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    comment = (
        await db.execute(
            select(Comment).where(
                Comment.id == comment_id,
                Comment.is_hidden == False,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comentario no encontrado.",
        )

    visitor_fp = None if current_user else build_visitor_fingerprint(request)
    rate_key = (
        f"report:user:{current_user.id}"
        if current_user
        else f"report:visitor:{visitor_fp}"
    )
    if not check_rate_limit(rate_key, max_requests=15, window_seconds=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiadas denuncias en poco tiempo. Intenta nuevamente en un minuto.",
        )

    identity_filter = (
        CommentReport.reporter_user_id == current_user.id
        if current_user
        else CommentReport.reporter_fingerprint == visitor_fp
    )
    existing = (
        await db.execute(
            select(CommentReport.id).where(
                CommentReport.comment_id == comment_id,
                identity_filter,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya denunciaste este comentario previamente.",
        )

    report = CommentReport(
        comment_id=comment_id,
        reporter_user_id=current_user.id if current_user else None,
        reporter_fingerprint=visitor_fp,
        reason=payload.reason,
        details=payload.details.strip() if payload.details else None,
        status="pending",
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return report


@router.get(
    "/admin/moderation/reports",
    response_model=CommentReportListResponse,
    summary="Listar cola de denuncias de comentarios",
)
async def list_moderation_reports(
    report_status: Optional[Literal["pending", "reviewed", "dismissed"]] = Query(
        default=None, alias="status"
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: User = Depends(require_permission("view_moderation")),
    db: AsyncSession = Depends(get_db),
):
    filters = []
    if report_status is not None:
        filters.append(CommentReport.status == report_status)

    total = (
        await db.execute(select(func.count(CommentReport.id)).where(*filters))
    ).scalar_one()

    stmt = (
        select(CommentReport)
        .where(*filters)
        .order_by(desc(CommentReport.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = (await db.execute(stmt)).scalars().all()

    return CommentReportListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.patch(
    "/admin/moderation/comments/{comment_id}/hide",
    summary="Ocultar un comentario y marcar denuncias pendientes como revisadas",
)
async def hide_comment(
    comment_id: int,
    payload: Optional[ModerationActionRequest] = Body(default=None),
    admin_user: User = Depends(require_permission("moderate_comments")),
    db: AsyncSession = Depends(get_db),
):
    return await _set_comment_visibility(
        db=db,
        comment_id=comment_id,
        is_hidden=True,
        action="hide",
        admin_user=admin_user,
        reason=payload.reason if payload else None,
    )


@router.patch(
    "/admin/moderation/comments/{comment_id}/restore",
    summary="Restaurar un comentario oculto",
)
async def restore_comment(
    comment_id: int,
    payload: Optional[ModerationActionRequest] = Body(default=None),
    admin_user: User = Depends(require_permission("moderate_comments")),
    db: AsyncSession = Depends(get_db),
):
    return await _set_comment_visibility(
        db=db,
        comment_id=comment_id,
        is_hidden=False,
        action="restore",
        admin_user=admin_user,
        reason=payload.reason if payload else None,
    )


@router.delete(
    "/admin/moderation/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un comentario definitivamente como moderador",
)
async def admin_delete_comment(
    comment_id: int,
    payload: Optional[ModerationActionRequest] = Body(default=None),
    admin_user: User = Depends(require_permission("moderate_comments")),
    db: AsyncSession = Depends(get_db),
):
    comment = (
        await db.execute(select(Comment).where(Comment.id == comment_id))
    ).scalar_one_or_none()
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comentario no encontrado.",
        )

    log_entry = ModerationLog(
        comment_id=comment.id,
        admin_user_id=admin_user.id,
        action="delete",
        reason=payload.reason if payload else None,
    )
    db.add(log_entry)
    await db.flush()
    await db.delete(comment)
    await db.commit()
    return None


@router.patch(
    "/admin/moderation/reports/{report_id}/dismiss",
    response_model=CommentReportResponse,
    summary="Descartar una denuncia",
)
async def dismiss_report(
    report_id: int,
    payload: Optional[ModerationActionRequest] = Body(default=None),
    admin_user: User = Depends(require_permission("moderate_comments")),
    db: AsyncSession = Depends(get_db),
):
    report = (
        await db.execute(select(CommentReport).where(CommentReport.id == report_id))
    ).scalar_one_or_none()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Denuncia no encontrada.",
        )

    now = datetime.now(timezone.utc)
    report.status = "dismissed"
    report.reviewed_at = now
    report.reviewed_by = admin_user.id

    log_entry = ModerationLog(
        comment_id=report.comment_id,
        admin_user_id=admin_user.id,
        action="dismiss_report",
        reason=payload.reason if payload else None,
    )
    db.add(log_entry)
    await db.commit()
    await db.refresh(report)
    return report


@router.get(
    "/admin/moderation/logs",
    response_model=ModerationLogListResponse,
    summary="Consultar bitácora de acciones de moderación",
)
async def list_moderation_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _: User = Depends(require_permission("view_moderation")),
    db: AsyncSession = Depends(get_db),
):
    total = (
        await db.execute(select(func.count(ModerationLog.id)))
    ).scalar_one()

    stmt = (
        select(ModerationLog)
        .order_by(desc(ModerationLog.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = (await db.execute(stmt)).scalars().all()

    return ModerationLogListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
