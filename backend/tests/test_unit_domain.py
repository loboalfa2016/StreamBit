from app.core.permissions import ROLE_PERMISSIONS
from app.core.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    revoke_token,
    verify_password,
)
from app.services.moderation import evaluate_comment_content


def test_evaluate_comment_content_clean():
    is_spam, reason = evaluate_comment_content("Excelente película, muy recomendada.")
    assert is_spam is False
    assert reason is None


def test_evaluate_comment_content_excessive_links():
    is_spam, reason = evaluate_comment_content(
        "Mira https://a.com https://b.com https://c.com"
    )
    assert is_spam is True
    assert reason is not None


def test_evaluate_comment_content_repeated_chars():
    is_spam, reason = evaluate_comment_content("Holaaaaaaaa que buen estreno")
    assert is_spam is True
    assert reason is not None


def test_evaluate_comment_content_spam_keyword():
    is_spam, reason = evaluate_comment_content("Gana dinero con Free Money hoy mismo")
    assert is_spam is True
    assert reason is not None


def test_password_hashing_and_jwt_lifecycle():
    hashed = get_password_hash("SecretPass123!")
    assert hashed != "SecretPass123!"
    assert verify_password("SecretPass123!", hashed) is True
    assert verify_password("WrongPass!", hashed) is False

    token = create_access_token(subject="42", role="user")
    payload = decode_access_token(token, expected_type="access")
    assert payload is not None
    assert payload["sub"] == "42"
    assert payload["role"] == "user"

    revoke_token(payload["jti"])
    assert decode_access_token(token, expected_type="access") is None


def test_role_permissions_matrix():
    analyst_perms = ROLE_PERMISSIONS["analyst"]
    assert "view_analytics" in analyst_perms
    assert "view_moderation" in analyst_perms
    assert "view_ads_reports" in analyst_perms
    assert "manage_users" not in analyst_perms
    assert "manage_catalog" not in analyst_perms
    assert "manage_ads" not in analyst_perms
    assert "moderate_comments" not in analyst_perms

    cat_perms = ROLE_PERMISSIONS["catalog_manager"]
    assert "manage_catalog" in cat_perms
    assert "manage_ads" not in cat_perms
    assert "manage_users" not in cat_perms

    ads_perms = ROLE_PERMISSIONS["ads_manager"]
    assert "manage_ads" in ads_perms
    assert "manage_catalog" not in ads_perms
    assert "manage_users" not in ads_perms
