"""Public registration and an authenticated profile endpoint."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import CurrentSeller, DbSession
from app.core.security import password_hash
from app.models import Seller
from app.schemas import SellerCreate, SellerRead

router = APIRouter(prefix="/seller", tags=["Sellers"])


@router.post("", response_model=SellerRead, status_code=status.HTTP_201_CREATED)
def create_seller(request: SellerCreate, db: DbSession) -> Seller:
    """Hash passwords once; store only the hash, and never return it."""
    seller = Seller(
        username=request.username,
        email=str(request.email),
        hashed_password=password_hash.hash(request.password.get_secret_value()),
    )
    db.add(seller)
    try:
        db.commit()
    except IntegrityError:
        # A database constraint handles simultaneous registrations safely too.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already registered",
        ) from None
    db.refresh(seller)
    # SellerRead filters this ORM instance so the stored password hash cannot leak.
    return seller


@router.get("/me", response_model=SellerRead)
def read_profile(current_seller: CurrentSeller) -> Seller:
    """The dependency resolves the token to the actual database account."""
    return current_seller
