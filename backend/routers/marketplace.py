"""
routers/marketplace.py — Unified Strategy Registry API.

Endpoints:
    GET    /api/marketplace/strategies          list (filters: source, category, market, q)
    GET    /api/marketplace/strategies/{slug}   one strategy (404 if missing)
    POST   /api/marketplace/strategies          create (or fork if body.forked_from)
    PUT    /api/marketplace/strategies/{slug}   update editable strategy
    DELETE /api/marketplace/strategies/{slug}   delete custom/llm/forked strategy
    POST   /api/marketplace/seed                seed registry from all sources
"""

from fastapi import APIRouter, HTTPException, Query

from marketplace import registry
from marketplace.seeds import seed_all

router = APIRouter(prefix="/api/marketplace", tags=["marketplace"])


@router.get("/strategies")
async def list_strategies(
    source: str | None = Query(default=None, description="predefined | it_bear | custom | llm"),
    category: str | None = Query(default=None, description="options | commodity | screening | ..."),
    market: str | None = Query(default=None, description="IN | US | BOTH"),
    q: str | None = Query(default=None, description="search in name/description/slug/tags"),
):
    """List strategies with optional filters."""
    return await registry.list_strategies(
        source=source, category=category, market=market, q=q
    )


@router.get("/strategies/{slug}")
async def get_strategy(slug: str):
    """Fetch one strategy by slug."""
    strategy = await registry.get_strategy(slug)
    if strategy is None:
        raise HTTPException(status_code=404, detail=f"Strategy '{slug}' not found")
    return strategy


@router.post("/strategies")
async def create_strategy(body: dict):
    """Create a new strategy — or fork an existing one if body.forked_from is set."""
    try:
        if body.get("forked_from"):
            slug = await registry.fork_strategy(
                body["forked_from"], new_name=body.get("name")
            )
        else:
            slug = await registry.create_strategy(body)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc).strip("'\""))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"slug": slug}


@router.put("/strategies/{slug}")
async def update_strategy(slug: str, body: dict):
    """Update an editable strategy. 400 if the strategy is read-only (fork it instead)."""
    try:
        return await registry.update_strategy(slug, body or {})
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc).strip("'\""))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/strategies/{slug}")
async def delete_strategy(slug: str):
    """Delete a strategy. Only custom, llm or forked strategies can be removed."""
    try:
        await registry.delete_strategy(slug)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc).strip("'\""))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"deleted": slug}


@router.post("/seed")
async def seed_registry():
    """Seed strategy_defs from all sources (idempotent)."""
    return await seed_all()
