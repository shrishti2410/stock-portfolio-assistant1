"""models/ — Pydantic models shared across the app."""

from pydantic import BaseModel


class StrategyCreateRequest(BaseModel):
    input: str
    symbols: list[str] = []


class StrategyUpdateRequest(BaseModel):
    name: str | None = None
    is_active: bool | None = None


class WatchlistRequest(BaseModel):
    symbols: list[str]
