from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from sqlalchemy import select

from app.core.config import settings
from app.models.sync_log import SyncLog
from app.services.tmdb_sync import sync_movies_from_tmdb


async def test_tmdb_sync_handles_timeout_and_logs_error(db_session, monkeypatch):
    monkeypatch.setattr(settings, "TMDB_API_KEY", "dummy-test-key")

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = False
    mock_client.get.side_effect = httpx.TimeoutException("TMDB request timed out")

    log_id = None
    try:
        with patch("app.services.tmdb_sync.httpx.AsyncClient", return_value=mock_client):
            log = await sync_movies_from_tmdb(db_session, trigger="manual")
            log_id = log.id
            assert log.status == "error"
            assert "timed out" in (log.error_message or "").lower()
    finally:
        if log_id is not None:
            row = (
                await db_session.execute(select(SyncLog).where(SyncLog.id == log_id))
            ).scalar_one_or_none()
            if row:
                await db_session.delete(row)
                await db_session.commit()


async def test_tmdb_sync_handles_http_500_and_malformed_response(db_session, monkeypatch):
    monkeypatch.setattr(settings, "TMDB_API_KEY", "dummy-test-key")

    # 1) HTTP 500
    request = httpx.Request("GET", "https://api.themoviedb.org/3/movie/popular")
    response_500 = httpx.Response(500, request=request)
    mock_client_500 = AsyncMock()
    mock_client_500.__aenter__.return_value = mock_client_500
    mock_client_500.__aexit__.return_value = False
    mock_client_500.get.return_value = response_500

    # 2) Respuesta malformada (json() devuelve string en lugar de dict)
    mock_resp_bad = MagicMock()
    mock_resp_bad.raise_for_status.return_value = None
    mock_resp_bad.json.return_value = ["malformed"]
    mock_client_bad = AsyncMock()
    mock_client_bad.__aenter__.return_value = mock_client_bad
    mock_client_bad.__aexit__.return_value = False
    mock_client_bad.get.return_value = mock_resp_bad

    created_log_ids: list[int] = []
    try:
        with patch("app.services.tmdb_sync.httpx.AsyncClient", return_value=mock_client_500):
            log_500 = await sync_movies_from_tmdb(db_session, trigger="manual")
            created_log_ids.append(log_500.id)
            assert log_500.status == "error"
            assert "500" in (log_500.error_message or "")

        with patch("app.services.tmdb_sync.httpx.AsyncClient", return_value=mock_client_bad):
            log_bad = await sync_movies_from_tmdb(db_session, trigger="manual")
            created_log_ids.append(log_bad.id)
            assert log_bad.status == "error"
            assert log_bad.error_message is not None
    finally:
        for lid in created_log_ids:
            row = (
                await db_session.execute(select(SyncLog).where(SyncLog.id == lid))
            ).scalar_one_or_none()
            if row:
                await db_session.delete(row)
        await db_session.commit()
