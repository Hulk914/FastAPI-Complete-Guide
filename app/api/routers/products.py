"""Authenticated CRUD; only a product's owner may update or delete it."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentSeller, DbSession
from app.models import Product
from app.schemas import ProductRead, ProductWrite

router = APIRouter(prefix="/product", tags=["Products"])
ProductId = Annotated[int, Path(gt=0, le=2**63 - 1)]


def get_product_or_404(product_id: int, db: Session) -> Product:
    """Share the lookup between read/update/delete to keep 404 behavior consistent."""
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


def require_owner(product: Product, seller_id: int) -> None:
    """Authentication answers who; authorization answers what they may change."""
    if product.seller_id != seller_id:
        raise HTTPException(status_code=403, detail="Only the owner can modify this product")


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_product(request: ProductWrite, db: DbSession, current_seller: CurrentSeller) -> Product:
    # Ownership comes from the verified token, never a client-supplied seller_id.
    product = Product(**request.model_dump(), seller_id=current_seller.id)
    db.add(product)
    # Commit before returning success; refresh loads database-generated values.
    db.commit()
    db.refresh(product)
    return product


@router.get("", response_model=list[ProductRead])
def list_products(
    db: DbSession,
    current_seller: CurrentSeller,
    offset: Annotated[int, Query(ge=0, le=2_147_483_647)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[Product]:
    """All signed-in sellers can browse; bounded pagination avoids unlimited reads."""
    # current_seller is intentionally required even though the query lists every owner.
    statement = select(Product).order_by(Product.id).offset(offset).limit(limit)
    return list(db.scalars(statement).all())


@router.get("/{product_id}", response_model=ProductRead)
def read_product(product_id: ProductId, db: DbSession, current_seller: CurrentSeller) -> Product:
    """Reading another seller's product is allowed once authentication succeeds."""
    return get_product_or_404(product_id, db)


@router.put("/{product_id}", response_model=ProductRead)
def update_product(
    product_id: ProductId,
    request: ProductWrite,
    db: DbSession,
    current_seller: CurrentSeller,
) -> Product:
    """PUT requires all writable fields; it never transfers ownership."""
    product = get_product_or_404(product_id, db)
    require_owner(product, current_seller.id)
    # Only schema-approved fields can be assigned; IDs and ownership are not writable.
    for field, value in request.model_dump().items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(product_id: ProductId, db: DbSession, current_seller: CurrentSeller) -> Response:
    product = get_product_or_404(product_id, db)
    require_owner(product, current_seller.id)
    db.delete(product)
    db.commit()
    # 204 intentionally has no JSON body.
    return Response(status_code=status.HTTP_204_NO_CONTENT)
