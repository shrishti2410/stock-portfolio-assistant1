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


class TradingConfigUpdate(BaseModel):
    max_capital: float | None = None
    max_loss_per_trade: float | None = None
    max_daily_loss: float | None = None
    max_positions: int | None = None
    risk_per_trade_pct: float | None = None
    paper_mode: bool | None = None
    engine_enabled: bool | None = None
    strategies_enabled: list[str] | None = None
    scan_interval_min: int | None = None


class ProposalAction(BaseModel):
    action: str  # "approve" or "reject"
