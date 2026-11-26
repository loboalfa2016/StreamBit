from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.community import Comment
from app.models.movie import Movie
from app.models.notifications import MovieAvailabilityAlert, Notification
from app.models.user import User


async def notify_movie_became_available(
    db: AsyncSession,
    movie: Movie,
    event_ref: str,
) -> int:
    stmt = (
        select(User.id)
        .join(MovieAvailabilityAlert, MovieAvailabilityAlert.user_id == User.id)
        .where(
            MovieAvailabilityAlert.movie_id == movie.id,
            User.is_active.is_(True),
            User.notify_availability.is_(True),
        )
    )
    user_ids = list((await db.execute(stmt)).scalars().all())
    if not user_ids:
        return 0

    candidate_keys = {uid: f"avail:{uid}:{movie.id}:{event_ref}" for uid in user_ids}
    existing_keys = set(
        (
            await db.execute(
                select(Notification.dedup_key).where(
                    Notification.dedup_key.in_(list(candidate_keys.values()))
                )
            )
        )
        .scalars()
        .all()
    )

    new_notifications = [
        Notification(
            user_id=uid,
            type="movie_available",
            title="¡Película ya disponible!",
            message=f'"{movie.title}" ya está disponible para ver en StreamBit.',
            movie_id=movie.id,
            dedup_key=dedup_key,
        )
        for uid, dedup_key in candidate_keys.items()
        if dedup_key not in existing_keys
    ]
    if not new_notifications:
        return 0

    db.add_all(new_notifications)
    await db.commit()
    return len(new_notifications)


async def notify_comment_reply(
    db: AsyncSession,
    parent_comment: Comment,
    reply_comment: Comment,
    movie_title: str,
) -> bool:
    if parent_comment.user_id is None or parent_comment.user_id == reply_comment.user_id:
        return False

    parent_author = (
        await db.execute(
            select(User).where(
                User.id == parent_comment.user_id,
                User.is_active.is_(True),
                User.notify_comment_replies.is_(True),
            )
        )
    ).scalar_one_or_none()
    if not parent_author:
        return False

    dedup_key = f"reply:{parent_comment.user_id}:{reply_comment.id}"
    exists = (
        await db.execute(
            select(Notification.id).where(Notification.dedup_key == dedup_key)
        )
    ).scalar_one_or_none()
    if exists:
        return False

    notification = Notification(
        user_id=parent_comment.user_id,
        type="comment_reply",
        title="Nueva respuesta a tu comentario",
        message=f'Alguien respondió a tu comentario en "{movie_title}".',
        movie_id=reply_comment.movie_id,
        comment_id=reply_comment.id,
        dedup_key=dedup_key,
    )
    db.add(notification)
    await db.commit()
    return True
