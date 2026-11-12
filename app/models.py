"""Database tables. Constraints protect data even when writes bypass the API."""

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Seller(Base):
    """One seller can own many products; normalized identity fields must be unique."""

    __tablename__ = "sellers"
    __table_args__ = (
        UniqueConstraint("username", name="uq_sellers_username"),
        UniqueConstraint("email", name="uq_sellers_email"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50))
    email: Mapped[str] = mapped_column(String(254))
    hashed_password: Mapped[str] = mapped_column(String(255))
    # back_populates connects both Python relationship attributes; the FK is below.
    products: Mapped[list["Product"]] = relationship(back_populates="seller")


class Product(Base):
    """A product always has an owner and a price in integer minor currency units."""

    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("price >= 0 AND price <= 2147483647", name="ck_products_price"),
    )

    # Non-optional Mapped types make these columns NOT NULL in the database schema.
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    desc: Mapped[str] = mapped_column(String(1000))
    # Integer minor units avoid floating-point rounding errors for money.
    price: Mapped[int] = mapped_column(Integer)
    seller_id: Mapped[int] = mapped_column(
        ForeignKey("sellers.id", ondelete="RESTRICT"), index=True
    )
    seller: Mapped[Seller] = relationship(back_populates="products")
