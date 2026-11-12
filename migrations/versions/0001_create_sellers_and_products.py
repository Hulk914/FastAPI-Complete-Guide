"""Create the seller/product tables and constraints for a fresh installation."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sellers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.UniqueConstraint("username", name="uq_sellers_username"),
        sa.UniqueConstraint("email", name="uq_sellers_email"),
    )
    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("desc", sa.String(1000), nullable=False),
        sa.Column("price", sa.Integer(), nullable=False),
        sa.Column("seller_id", sa.Integer(), nullable=False),
        sa.CheckConstraint("price >= 0 AND price <= 2147483647", name="ck_products_price"),
        sa.ForeignKeyConstraint(["seller_id"], ["sellers.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_products_seller_id", "products", ["seller_id"])


def downgrade() -> None:
    # Drop the dependent table first; its foreign key references sellers.
    op.drop_index("ix_products_seller_id", table_name="products")
    op.drop_table("products")
    op.drop_table("sellers")
