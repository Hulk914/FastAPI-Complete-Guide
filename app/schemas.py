"""API contracts: validate inputs and explicitly allow fields in responses."""

from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    SecretStr,
    StringConstraints,
    field_validator,
)


class ProductWrite(BaseModel):
    """POST and PUT accept the same complete representation (PUT is not PATCH)."""

    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    desc: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
    price: int = Field(
        ge=0,
        le=2_147_483_647,
        strict=True,
        description="Price in minor units: 1299 means 12.99 in the chosen currency.",
        examples=[1299],
    )


class ProductRead(ProductWrite):
    """Reuse product fields and add server-managed identifiers to the output."""

    # Read values from ORM attributes rather than requiring a Python dictionary.
    model_config = ConfigDict(from_attributes=True)

    id: int
    seller_id: int


class SellerCreate(BaseModel):
    """Validate public registration data before hashing or storing anything."""

    model_config = ConfigDict(extra="forbid")

    username: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            to_lower=True,
            min_length=3,
            max_length=50,
            pattern=r"^[a-zA-Z0-9_]+$",
        ),
    ]
    email: EmailStr = Field(max_length=254)
    # Never trim passwords: spaces can intentionally be part of a passphrase.
    password: SecretStr = Field(min_length=12, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        # This application deliberately treats email addresses as case-insensitive.
        return value.lower()


class SellerRead(BaseModel):
    """Allowlist the account fields that are safe to return to the caller."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    # No password field: a response model is also a data-leak prevention boundary.


class Token(BaseModel):
    """The OAuth2-compatible token response consumed by Swagger and API clients."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"
