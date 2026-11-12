"""Password hashing and JWT signing, with no HTTP or database dependencies."""

import secrets
from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings

ALGORITHM = "HS256"  # Fix the accepted algorithm; never trust a token's alg header.
# pwdlib's recommended hasher uses Argon2id and stores its salt/cost in the hash.
password_hash = PasswordHash.recommended()
# Verify a dummy hash for unknown usernames too, reducing a login timing discrepancy.
DUMMY_HASH = password_hash.hash(secrets.token_urlsafe(32))


def create_access_token(seller_id: int) -> str:
    """Sign short-lived identity claims; a JWT payload is readable, not encrypted."""
    settings = get_settings()
    now = datetime.now(UTC)  # Aware UTC timestamps avoid local-time ambiguity.
    return jwt.encode(
        {
            "sub": str(seller_id),  # A stable ID survives a future username change.
            "iat": now,
            "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
        },
        settings.jwt_secret_key.get_secret_value(),
        algorithm=ALGORITHM,
    )


def decode_access_token(token: str) -> int:
    """Validate the signature AND required claims; return only the seller ID."""
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.jwt_secret_key.get_secret_value(),
        algorithms=[ALGORITHM],
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
        options={"require": ["sub", "iat", "exp", "iss", "aud"]},
    )
    # Restrict the signed subject to IDs the database can represent safely.
    # Signature/claim validation happens first; account existence is checked by the API.
    subject = payload["sub"]
    if (
        not isinstance(subject, str)
        or not subject.isascii()
        or not subject.isdecimal()
        or len(subject) > 19
        or not 0 < int(subject) <= 2**63 - 1
    ):
        raise jwt.InvalidTokenError("Invalid seller ID")
    return int(subject)
