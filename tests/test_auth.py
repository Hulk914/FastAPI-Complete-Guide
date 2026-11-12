"""Authentication regressions: leaked secrets, forged tokens, and stale accounts."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from pwdlib.hashers.argon2 import Argon2Hasher
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import ALGORITHM, create_access_token, password_hash
from app.models import Seller

PASSWORD = "LearnFastAPI!2026"


def test_registration_normalizes_identity_and_hashes_password(client, sessions):
    response = client.post(
        "/seller",
        json={"username": " Alice ", "email": "ALICE@example.com", "password": PASSWORD},
    )
    assert response.status_code == 201
    assert response.json() == {"id": 1, "username": "alice", "email": "alice@example.com"}
    assert PASSWORD not in response.text
    with sessions() as db:
        seller = db.get(Seller, 1)
        assert seller.hashed_password.startswith("$argon2id$")
        assert password_hash.verify(PASSWORD, seller.hashed_password)


@pytest.mark.parametrize(
    "duplicate",
    [
        {"username": "ALICE", "email": "other@example.com"},
        {"username": "other", "email": "ALICE@example.com"},
    ],
)
def test_duplicate_registration_is_conflict_and_session_recovers(
    client, owner, account_factory, duplicate
):
    response = client.post("/seller", json={**duplicate, "password": PASSWORD})
    assert response.status_code == 409
    assert response.json() == {"detail": "Username or email already registered"}
    account_factory("charlie")  # A conflict must not break subsequent requests.


@pytest.mark.parametrize(
    "change",
    [
        {"password": "short"},
        {"password": "x" * 129},
        {"email": "not-an-email"},
        {"username": "a"},
        {"username": "invalid name"},
        {"unexpected": "value"},
    ],
)
def test_registration_validation_never_echoes_input(client, change):
    response = client.post(
        "/seller",
        json={"username": "alice", "email": "alice@example.com", "password": PASSWORD, **change},
    )
    assert response.status_code == 422
    assert PASSWORD not in response.text
    assert all("input" not in error and "ctx" not in error for error in response.json()["detail"])


def test_login_profile_and_token_contract(client, owner):
    seller, headers = owner
    response = client.post("/login", data={"username": " ALICE ", "password": PASSWORD})
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    settings = get_settings()
    claims = jwt.decode(
        response.json()["access_token"],
        settings.jwt_secret_key.get_secret_value(),
        algorithms=[ALGORITHM],
        audience=settings.jwt_audience,
        issuer=settings.jwt_issuer,
    )
    assert claims["sub"] == str(seller["id"])
    assert claims["exp"] - claims["iat"] == settings.access_token_expire_minutes * 60
    assert client.get("/seller/me", headers=headers).json() == seller


def test_bad_login_does_not_reveal_which_credential_failed(client, owner):
    wrong_password = client.post("/login", data={"username": "alice", "password": "wrong"})
    unknown_user = client.post("/login", data={"username": "nobody", "password": "wrong"})
    for response in (wrong_password, unknown_user):
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"
        assert response.json() == {"detail": "Incorrect username or password"}


def test_login_requires_form_data(client):
    response = client.post("/login", json={"username": "alice", "password": PASSWORD})
    assert response.status_code == 422


@pytest.mark.parametrize("password", ["x" * 129, "\u00e9" * 60])
def test_oversized_password_is_rejected_without_server_error(client, owner, password):
    assert (
        client.post("/login", data={"username": "alice", "password": password}).status_code == 401
    )


@pytest.mark.parametrize(
    "change",
    [
        {"exp": 1},
        {"iat": 4_000_000_000},
        {"iss": "another-service"},
        {"aud": "another-audience"},
        {"sub": "not-an-id"},
        {"sub": "0"},
        {"sub": "-1"},
        {"sub": "\u0661"},
        {"sub": "9" * 30},
        {"sub": str(2**63)},
        {"sub": 1},
    ],
)
def test_invalid_claims_are_unauthorized(client, owner, change):
    now = datetime.now(UTC)
    settings = get_settings()
    claims = {
        "sub": str(owner[0]["id"]),
        "iat": now,
        "exp": now + timedelta(minutes=5),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        **change,
    }
    token = jwt.encode(claims, settings.jwt_secret_key.get_secret_value(), algorithm=ALGORITHM)
    response = client.get("/seller/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("claim", ["sub", "iat", "exp", "iss", "aud"])
def test_required_token_claims_cannot_be_omitted(client, owner, claim):
    settings = get_settings()
    now = datetime.now(UTC)
    claims = {
        "sub": str(owner[0]["id"]),
        "iat": now,
        "exp": now + timedelta(minutes=5),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }
    del claims[claim]
    token = jwt.encode(claims, settings.jwt_secret_key.get_secret_value(), algorithm=ALGORITHM)
    assert client.get("/seller/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


@pytest.mark.parametrize("kind", ["malformed", "wrong-key", "wrong-algorithm"])
def test_untrusted_tokens_are_rejected(client, owner, kind):
    settings = get_settings()
    token = "not.a.jwt"
    if kind != "malformed":
        token = jwt.encode(
            {"sub": str(owner[0]["id"])},
            "a-different-signing-secret-that-is-at-least-32-characters"
            if kind == "wrong-key"
            else settings.jwt_secret_key.get_secret_value(),
            algorithm="HS256" if kind == "wrong-key" else "HS512",
        )
    assert client.get("/seller/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_token_for_deleted_account_is_rejected(client, owner, sessions):
    seller, headers = owner
    with sessions() as db:
        db.delete(db.get(Seller, seller["id"]))
        db.commit()
    assert client.get("/seller/me", headers=headers).status_code == 401


def test_argon2_cost_settings_are_upgraded_on_login(client, sessions):
    # A deliberately cheaper test hash simulates an account saved before a cost upgrade.
    older_hash = Argon2Hasher(time_cost=1, memory_cost=8192, parallelism=1).hash(PASSWORD)
    with sessions() as db:
        db.add(
            Seller(
                username="returning",
                email="returning@example.com",
                hashed_password=older_hash,
            )
        )
        db.commit()
    assert (
        client.post("/login", data={"username": "returning", "password": PASSWORD}).status_code
        == 200
    )
    with sessions() as db:
        seller = db.scalar(select(Seller).where(Seller.username == "returning"))
        assert seller.hashed_password.startswith("$argon2id$")
        assert seller.hashed_password != older_hash
        assert password_hash.verify_and_update(PASSWORD, seller.hashed_password) == (True, None)


def test_nonexistent_account_token_is_rejected(client):
    token = create_access_token(999)
    assert client.get("/seller/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
