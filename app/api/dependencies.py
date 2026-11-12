"""Reusable dependency types: a database session and the authenticated seller."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database import get_db
from app.models import Seller

# Annotated keeps the Python type and FastAPI's injection instruction together.
DbSession = Annotated[Session, Depends(get_db)]
# This extracts the bearer string and documents login; it does not validate a JWT.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


def get_current_seller(token: Annotated[str, Depends(oauth2_scheme)], db: DbSession) -> Seller:
    """Resolve a trusted account or raise 401; ownership is a separate route rule."""
    error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        seller_id = decode_access_token(token)
    except InvalidTokenError:
        raise error from None

    # A valid signature is not enough: the account must still exist.
    seller = db.get(Seller, seller_id)
    if seller is None:
        raise error
    return seller


# Routes can reuse this alias without repeating the authentication implementation.
CurrentSeller = Annotated[Seller, Depends(get_current_seller)]
