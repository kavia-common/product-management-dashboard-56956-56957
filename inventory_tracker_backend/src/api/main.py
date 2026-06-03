from __future__ import annotations

import datetime as dt
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.db import get_db_session
from src.api.events import SseBroker, sse_response
from src.api.models import Product
from src.api.schemas import InventoryEvent, ProductCreate, ProductOut, ProductUpdate

openapi_tags = [
    {
        "name": "Health",
        "description": "Basic health/readiness endpoints.",
    },
    {
        "name": "Products",
        "description": "CRUD endpoints for products in inventory.",
    },
    {
        "name": "LiveUpdates",
        "description": "Server-Sent Events stream broadcasting inventory changes.",
    },
]

app = FastAPI(
    title="Inventory Tracker API",
    description=(
        "Backend API for product inventory management. "
        "Provides CRUD endpoints and a live updates stream.\n\n"
        "Live updates: connect via SSE to `GET /events` (EventSource in browsers)."
    ),
    version="1.0.0",
    openapi_tags=openapi_tags,
)

# In-memory broker used for SSE broadcasts.
_broker = SseBroker()

_ALLOWED_ORIGINS = {
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
}

app.add_middleware(
    CORSMiddleware,
    # Allow common dev origins explicitly.
    #
    # IMPORTANT:
    # - When allow_credentials=True, using "*" for allow_origins is invalid per CORS rules and
    #   Starlette will not emit the expected CORS headers. This breaks browser requests.
    # - Explicit origins ensure the frontend (localhost dev servers) can call the API and use SSE.
    allow_origins=list(_ALLOWED_ORIGINS),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def ensure_cors_headers(request: Request, call_next):
    """
    Ensure CORS headers are present on *all* responses, including unhandled 500s.

    Starlette's CORSMiddleware should handle this, but if an exception occurs before
    it can attach headers (or during app startup edge-cases), browsers will surface it
    as a CORS failure. This middleware is a defensive layer for localhost dev.
    """
    origin = request.headers.get("origin")
    origin_allowed = origin in _ALLOWED_ORIGINS if origin else False

    # Defensive preflight handling (so mis-ordered middleware can't break OPTIONS).
    if request.method == "OPTIONS" and origin_allowed:
        resp = Response(status_code=204)
        resp.headers["Access-Control-Allow-Origin"] = origin  # echo back origin when credentials are used
        resp.headers["Vary"] = "Origin"
        resp.headers["Access-Control-Allow-Credentials"] = "true"
        resp.headers["Access-Control-Allow-Methods"] = request.headers.get(
            "access-control-request-method", "GET,POST,PUT,DELETE,OPTIONS"
        )
        resp.headers["Access-Control-Allow-Headers"] = request.headers.get(
            "access-control-request-headers", "*"
        )
        return resp

    try:
        response = await call_next(request)
    except Exception:
        # Return a JSON 500 while still attaching CORS headers so the frontend can read it.
        response = Response(
            content='{"detail":"Internal Server Error"}',
            status_code=500,
            media_type="application/json",
        )

    if origin_allowed:
        response.headers.setdefault("Access-Control-Allow-Origin", origin)
        response.headers.setdefault("Vary", "Origin")
        response.headers.setdefault("Access-Control-Allow-Credentials", "true")
    return response


@app.get("/", tags=["Health"], summary="Health check")
def health_check():
    """
    Health check endpoint.

    Returns:
      JSON {"message": "Healthy"} when the service is running.
    """
    return {"message": "Healthy"}


@app.get(
    "/products",
    response_model=list[ProductOut],
    tags=["Products"],
    summary="List products",
    description="Return all products sorted by updated_at (desc) then created_at (desc).",
)
async def list_products(db: AsyncSession = Depends(get_db_session)) -> list[ProductOut]:
    """
    List all products.

    Returns:
      Array of Product objects.
    """
    stmt = select(Product).order_by(Product.updated_at.desc(), Product.created_at.desc())
    res = await db.execute(stmt)
    return list(res.scalars().all())


@app.post(
    "/products",
    response_model=ProductOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Products"],
    summary="Create a product",
    description="Create a new product row and broadcast a live update event.",
)
async def create_product(
    payload: ProductCreate,
    db: AsyncSession = Depends(get_db_session),
) -> ProductOut:
    """
    Create a product.

    Parameters:
      payload: ProductCreate

    Returns:
      Created Product.
    """
    now = dt.datetime.now(dt.timezone.utc)

    p = Product(
        # id is generated by DB default in schema; if trigger/ddl differs, we keep DB source of truth.
        name=payload.name,
        description=payload.description,
        sku=payload.sku,
        quantity=payload.quantity,
        unit_price_cents=payload.unit_price_cents,
        created_at=now,
        updated_at=now,
    )

    db.add(p)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Conflict creating product (possible duplicate SKU).",
        ) from e

    await db.refresh(p)
    await _broker.broadcast(InventoryEvent(type="created", product_id=str(p.id)).model_dump())
    return ProductOut.model_validate(p)


@app.put(
    "/products/{product_id}",
    response_model=ProductOut,
    tags=["Products"],
    summary="Update a product",
    description="Update a product row and broadcast a live update event.",
)
async def update_product(
    product_id: UUID,
    payload: ProductUpdate,
    db: AsyncSession = Depends(get_db_session),
) -> ProductOut:
    """
    Update an existing product.

    Parameters:
      product_id: UUID path parameter
      payload: ProductUpdate (partial fields allowed)

    Returns:
      Updated Product.
    """
    p = await db.get(Product, product_id)
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")

    if payload.name is not None:
        p.name = payload.name
    if payload.description is not None:
        p.description = payload.description
    if payload.sku is not None:
        p.sku = payload.sku
    if payload.quantity is not None:
        p.quantity = payload.quantity
    if payload.unit_price_cents is not None:
        p.unit_price_cents = payload.unit_price_cents

    p.updated_at = dt.datetime.now(dt.timezone.utc)

    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Conflict updating product (possible duplicate SKU).",
        ) from e

    await db.refresh(p)
    await _broker.broadcast(InventoryEvent(type="updated", product_id=str(p.id)).model_dump())
    return ProductOut.model_validate(p)


@app.delete(
    "/products/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Products"],
    summary="Delete a product",
    description="Delete a product row and broadcast a live update event.",
)
async def delete_product(
    product_id: UUID,
    db: AsyncSession = Depends(get_db_session),
) -> Response:
    """
    Delete a product.

    Parameters:
      product_id: UUID path parameter

    Returns:
      204 No Content if deleted.
    """
    p = await db.get(Product, product_id)
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")

    await db.delete(p)
    await db.commit()

    await _broker.broadcast(InventoryEvent(type="deleted", product_id=str(product_id)).model_dump())
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get(
    "/events",
    tags=["LiveUpdates"],
    summary="Live inventory updates (SSE)",
    description=(
        "Server-Sent Events endpoint. Clients should connect using EventSource.\n\n"
        "Example (browser):\n"
        "  const es = new EventSource('http://localhost:8000/events');\n"
        "  es.onmessage = (e) => console.log(JSON.parse(e.data));\n"
    ),
    responses={
        200: {
            "content": {"text/event-stream": {}},
            "description": "SSE stream of inventory change events.",
        }
    },
)
async def events():
    """
    Live updates stream using Server-Sent Events (SSE).

    Returns:
      StreamingResponse with `text/event-stream` media type.
    """
    return sse_response(_broker)
