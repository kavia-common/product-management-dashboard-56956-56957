from __future__ import annotations

import datetime as dt
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ProductBase(BaseModel):
    """Shared fields for product payloads."""

    name: str = Field(..., description="Product name (non-empty).", min_length=1)
    description: Optional[str] = Field(
        None, description="Optional product description."
    )
    sku: Optional[str] = Field(
        None,
        description="Optional SKU. Must be unique when provided.",
        min_length=1,
    )
    quantity: int = Field(
        0, description="Inventory quantity (must be >= 0).", ge=0
    )
    unit_price_cents: int = Field(
        0,
        description="Unit price in integer cents (must be >= 0).",
        ge=0,
    )


class ProductCreate(ProductBase):
    """Payload for creating a product."""
    pass


class ProductUpdate(BaseModel):
    """Payload for updating a product (partial update via PUT in this app)."""

    name: Optional[str] = Field(None, description="Product name (non-empty).", min_length=1)
    description: Optional[str] = Field(None, description="Optional product description.")
    sku: Optional[str] = Field(
        None,
        description="Optional SKU. Must be unique when provided.",
        min_length=1,
    )
    quantity: Optional[int] = Field(None, description="Inventory quantity (>= 0).", ge=0)
    unit_price_cents: Optional[int] = Field(
        None, description="Unit price in integer cents (>= 0).", ge=0
    )


class ProductOut(ProductBase):
    """Product response model."""

    id: UUID = Field(..., description="Product ID (UUID).")
    created_at: dt.datetime = Field(..., description="Created timestamp (UTC).")
    updated_at: dt.datetime = Field(..., description="Updated timestamp (UTC).")

    model_config = {"from_attributes": True}


class InventoryEvent(BaseModel):
    """Server-Sent Event payload emitted on product changes."""

    type: str = Field(..., description='Event type: "created" | "updated" | "deleted".')
    product_id: Optional[str] = Field(
        None, description="Product ID (UUID) when applicable."
    )
