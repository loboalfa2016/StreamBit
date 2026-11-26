import json
import uuid

from sqlalchemy import select

from app.models.audit_log import AdminAuditLog
from app.models.movie import Movie


async def test_health_cors_and_security_headers(client):
    resp = await client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("x-frame-options") == "DENY"
    assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"


async def test_auth_and_rbac_flow(client, user_factory):
    uid = uuid.uuid4().hex[:8]
    reg_payload = {
        "username": f"int_usr_{uid}",
        "email": f"int_usr_{uid}@example.com",
        "password": "TestPassword123!",
    }
    r_reg = await client.post("/api/v1/auth/register", json=reg_payload)
    assert r_reg.status_code == 201

    r_login = await client.post(
        "/api/v1/auth/login",
        json={"email": reg_payload["email"], "password": reg_payload["password"]},
    )
    assert r_login.status_code == 200
    usr_token = r_login.json()["access_token"]
    usr_headers = {"Authorization": f"Bearer {usr_token}"}

    r_me = await client.get("/api/v1/auth/me", headers=usr_headers)
    assert r_me.status_code == 200
    assert r_me.json()["email"] == reg_payload["email"]

    # Usuario común bloqueado en /admin/*
    r_forb = await client.get("/api/v1/admin/reports/overview", headers=usr_headers)
    assert r_forb.status_code == 403

    # Analista accede solo lectura
    analyst, ana_pwd = await user_factory(role="analyst")
    ana_tok = (
        await client.post(
            "/api/v1/auth/login",
            json={"email": analyst.email, "password": ana_pwd},
        )
    ).json()["access_token"]
    r_ana = await client.get(
        "/api/v1/admin/reports/overview",
        headers={"Authorization": f"Bearer {ana_tok}"},
    )
    assert r_ana.status_code == 200

    # Limpieza de usuario registrado vía API
    await client.request(
        "DELETE",
        "/api/v1/me/privacy/account",
        headers=usr_headers,
        json={"password": reg_payload["password"], "confirm": True},
    )


async def test_catalog_search_and_collections(client, db_session):
    uid = uuid.uuid4().hex[:8]
    movie = Movie(
        title=f"IntCatalogMovie {uid}",
        is_available=True,
        is_published=True,
    )
    db_session.add(movie)
    await db_session.commit()
    await db_session.refresh(movie)

    try:
        r_movies = await client.get(f"/api/v1/movies?q={uid}&page=1&page_size=10")
        assert r_movies.status_code == 200
        data = r_movies.json()
        assert data["total"] >= 1
        assert any(item["id"] == movie.id for item in data["items"])

        r_coll = await client.get("/api/v1/catalog/collections")
        assert r_coll.status_code == 200
    finally:
        m = (
            await db_session.execute(select(Movie).where(Movie.id == movie.id))
        ).scalar_one_or_none()
        if m:
            await db_session.delete(m)
            await db_session.commit()


async def test_community_ratings_comments_and_moderation(client, db_session, user_factory):
    uid = uuid.uuid4().hex[:8]
    movie = Movie(title=f"IntCommMovie {uid}", is_available=True, is_published=True)
    db_session.add(movie)
    await db_session.commit()
    await db_session.refresh(movie)

    admin, adm_pwd = await user_factory(role="admin")
    user, usr_pwd = await user_factory(role="user")

    adm_tok = (
        await client.post(
            "/api/v1/auth/login", json={"email": admin.email, "password": adm_pwd}
        )
    ).json()["access_token"]
    usr_tok = (
        await client.post(
            "/api/v1/auth/login", json={"email": user.email, "password": usr_pwd}
        )
    ).json()["access_token"]
    adm_h = {"Authorization": f"Bearer {adm_tok}"}
    usr_h = {"Authorization": f"Bearer {usr_tok}"}

    try:
        # Calificaciones (1-5 y rechazo de 6)
        r_bad = await client.post(
            f"/api/v1/movies/{movie.id}/ratings", headers=usr_h, json={"score": 6}
        )
        assert r_bad.status_code == 422
        r_ok = await client.post(
            f"/api/v1/movies/{movie.id}/ratings", headers=usr_h, json={"score": 5}
        )
        assert r_ok.status_code == 201

        # Comentarios, respuesta y bloqueo de 2do nivel
        r_c = await client.post(
            f"/api/v1/movies/{movie.id}/comments",
            headers=usr_h,
            json={"content": "Comentario de prueba integración"},
        )
        assert r_c.status_code == 201
        cid = r_c.json()["id"]

        r_rep = await client.post(
            f"/api/v1/movies/{movie.id}/comments",
            headers=adm_h,
            json={"content": "Respuesta nivel 1", "parent_id": cid},
        )
        assert r_rep.status_code == 201
        rid = r_rep.json()["id"]

        r_rep2 = await client.post(
            f"/api/v1/movies/{movie.id}/comments",
            headers=usr_h,
            json={"content": "Respuesta nivel 2", "parent_id": rid},
        )
        assert r_rep2.status_code == 400

        # Denuncia y moderación (ocultar)
        r_report = await client.post(
            f"/api/v1/comments/{cid}/reports",
            headers={"X-Visitor-Id": f"vis-{uid}"},
            json={"reason": "spam"},
        )
        assert r_report.status_code == 201

        r_hide = await client.patch(
            f"/api/v1/admin/moderation/comments/{cid}/hide",
            headers=adm_h,
            json={"reason": "Test hide"},
        )
        assert r_hide.status_code == 200
    finally:
        m = (
            await db_session.execute(select(Movie).where(Movie.id == movie.id))
        ).scalar_one_or_none()
        if m:
            await db_session.delete(m)
            await db_session.commit()


async def test_privacy_policy_and_export(client, db_session, user_factory):
    r_pol = await client.get("/api/v1/privacy/policy")
    assert r_pol.status_code == 200
    assert "retention_policy" in r_pol.json()

    user, pwd = await user_factory(role="user")
    tok = (
        await client.post(
            "/api/v1/auth/login", json={"email": user.email, "password": pwd}
        )
    ).json()["access_token"]
    r_exp = await client.get(
        "/api/v1/me/privacy/export", headers={"Authorization": f"Bearer {tok}"}
    )
    assert r_exp.status_code == 200
    assert "hashed_password" not in json.dumps(r_exp.json())
    assert r_exp.json()["profile"]["email"] == user.email

    # Limpieza de posibles logs de auditoría
    logs = (
        await db_session.execute(
            select(AdminAuditLog).where(AdminAuditLog.actor_user_id == user.id)
        )
    ).scalars().all()
    for log in logs:
        await db_session.delete(log)
    await db_session.commit()
