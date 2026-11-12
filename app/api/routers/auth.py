"""Exchange an OAuth2 form login for a short-lived bearer access token."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from app.api.dependencies import DbSession
from app.core.security import DUMMY_HASH, create_access_token, password_hash
from app.models import Seller
from app.schemas import Token

router = APIRouter(tags=["Authentication"])


@router.post("/login", response_model=Token)
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DbSession,
    response: Response,
) -> Token:
    """Send form fields `username` and `password`, rather than a JSON body."""
    seller = db.scalar(select(Seller).where(Seller.username == form.username.strip().lower()))
    # Run password verification even for an unknown account to reduce timing clues.
    stored_hash = seller.hashed_password if seller else DUMMY_HASH
    # Bound work for oversized input; registration already limits passwords to 128.
    valid = False
    updated_hash = None
    if len(form.password) <= 128:
        valid, updated_hash = password_hash.verify_and_update(form.password, stored_hash)
    if seller is None or not valid:
        # Same status and message for both failures; do not disclose account existence.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if updated_hash:
        # Upgrade older Argon2 cost settings only after the password is verified.
        seller.hashed_password = updated_hash
        db.commit()

    # Token responses should not be cached by browsers or intermediate proxies.
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return Token(access_token=create_access_token(seller.id))
