from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import get_current_user, get_optional_current_user
from app.core.database import get_db
from app.core.security import build_visitor_fingerprint, check_rate_limit
from app.models.community import Comment
from app.models.moderation import CommentReport
from app.models.movie import Movie
from app.models.user import User
from app.services.moderation import evaluate_comment_content
from app.services.notifications import notify_comment_reply
from app.schemas.comments import (
    CommentCreateRequest,
    CommentListResponse,
    CommentReplyResponse,
    CommentResponse,
)

router = APIRouter(tags=["Comments"])


async def _ensure_movie_exists(db: AsyncSession, movie_id: int) -> Movie:
    movie = (
        await db.execute(select(Movie).where(Movie.id == movie_id))
    ).scalar_one_or_none()
    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Película no encontrada.",
        )
    return movie


def _resolve_author(comment: Comment) -> tuple[str, bool]:
    if comment.user_id is not None and comment.user is not None:
        return comment.user.username, True
    if comment.user_id is not None:
        return "Usuario", True
    return (comment.guest_name or "Anónimo"), False


def _to_reply_response(comment: Comment) -> CommentReplyResponse:
    author_name, is_registered = _resolve_author(comment)
    return CommentReplyResponse(
        id=comment.id,
        movie_id=comment.movie_id,
        parent_id=comment.parent_id,
        author_name=author_name,
        is_registered_user=is_registered,
        content=comment.content,
        created_at=comment.created_at,
    )


def _to_comment_response(comment: Comment, replies: list[Comment]) -> CommentResponse:
    author_name, is_registered = _resolve_author(comment)
    reply_items = [_to_reply_response(reply) for reply in replies]
    return CommentResponse(
        id=comment.id,
        movie_id=comment.movie_id,
        parent_id=comment.parent_id,
        author_name=author_name,
        is_registered_user=is_registered,
        content=comment.content,
        created_at=comment.created_at,
        replies=reply_items,
        replies_count=len(reply_items),
    )


@router.post(
    "/movies/{movie_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Publicar un comentario o respuesta en una película",
)
async def create_comment(
    movie_id: int,
    payload: CommentCreateRequest,
    request: Request,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncSession = Depends(get_db),
):
    movie = await _ensure_movie_exists(db, movie_id)

    visitor_fp = None if current_user else build_visitor_fingerprint(request)
    rate_key = (
        f"comment:user:{current_user.id}"
        if current_user
        else f"comment:visitor:{visitor_fp}"
    )
    if not check_rate_limit(rate_key, max_requests=20, window_seconds=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados comentarios en poco tiempo. Intenta nuevamente en un minuto.",
        )

    parent: Optional[Comment] = None
    if payload.parent_id is not None:
        parent = (
            await db.execute(
                select(Comment).where(
                    Comment.id == payload.parent_id,
                    Comment.movie_id == movie_id,
                    Comment.is_hidden == False,  # noqa: E712
                )
            )
        ).scalar_one_or_none()
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Comentario padre no encontrado.",
            )
        if parent.parent_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Solo se permite un nivel de respuestas.",
            )

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
    identity_filter = (
        Comment.user_id == current_user.id
        if current_user
        else Comment.visitor_fingerprint == visitor_fp
    )
    duplicate = (
        await db.execute(
            select(Comment.id).where(
                Comment.movie_id == movie_id,
                Comment.content == payload.content,
                Comment.created_at >= cutoff,
                identity_filter,
            )
        )
    ).scalar_one_or_none()
    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya publicaste este mismo comentario recientemente.",
        )

    is_spam, spam_reason = evaluate_comment_content(payload.content)

    new_comment = Comment(
        movie_id=movie_id,
        user_id=current_user.id if current_user else None,
        visitor_fingerprint=visitor_fp,
        guest_name=None if current_user else payload.guest_name,
        parent_id=payload.parent_id,
        content=payload.content,
        is_hidden=is_spam,
    )
    db.add(new_comment)
    await db.flush()

    if is_spam:
        auto_report = CommentReport(
            comment_id=new_comment.id,
            reporter_user_id=current_user.id if current_user else None,
            reporter_fingerprint=visitor_fp,
            reason="auto_spam",
            details=spam_reason,
            status="pending",
        )
        db.add(auto_report)

    await db.commit()

    stmt = (
        select(Comment)
        .options(selectinload(Comment.user))
        .where(Comment.id == new_comment.id)
    )
    created = (await db.execute(stmt)).scalar_one()

    if parent is not None and not created.is_hidden:
        await notify_comment_reply(db, parent, created, movie.title)

    return _to_comment_response(created, replies=[])


@router.get(
    "/movies/{movie_id}/comments",
    response_model=CommentListResponse,
    status_code=status.HTTP_200_OK,
    summary="Listar comentarios y respuestas de una película",
)
async def list_movie_comments(
    movie_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    movie = await _ensure_movie_exists(db, movie_id)

    total = (
        await db.execute(
            select(func.count(Comment.id)).where(
                Comment.movie_id == movie_id,
                Comment.parent_id.is_(None),
                Comment.is_hidden == False,  # noqa: E712
            )
        )
    ).scalar_one()

    stmt = (
        select(Comment)
        .options(
            selectinload(Comment.user),
            selectinload(Comment.replies).selectinload(Comment.user),
        )
        .where(
            Comment.movie_id == movie_id,
            Comment.parent_id.is_(None),
            Comment.is_hidden == False,  # noqa: E712
        )
        .order_by(desc(Comment.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    root_comments = (await db.execute(stmt)).scalars().all()

    items = []
    for comment in root_comments:
        visible_replies = sorted(
            [reply for reply in comment.replies if not reply.is_hidden],
            key=lambda r: r.created_at,
        )
        items.append(_to_comment_response(comment, visible_replies))

    return CommentListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.delete(
    "/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un comentario propio o como administrador",
)
async def delete_comment(
    comment_id: int,
    current_user: User = Depends(get_current_user),
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

    if comment.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para eliminar este comentario.",
        )

    await db.delete(comment)
    await db.commit()
    return None
