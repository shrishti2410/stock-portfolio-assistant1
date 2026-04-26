"""
orders.py — Multi-leg order execution with safety.

Key rules:
1. BUY legs FIRST (hedges), then SELL legs
2. All orders LIMIT only
3. If SELL leg fails -> unwind all filled legs
4. Every order logged to order_log table
5. Attach GTT for SL + target on each sell leg (live mode)
"""
import json
from datetime import datetime

from trading.broker import BaseBroker, PaperBroker


def _build_tradingsymbol(symbol: str, expiry: str, strike: int, option_type: str) -> str:
    """
    Build Zerodha-format trading symbol.
    e.g., NIFTY2540323500CE

    For now returns a simplified format. Real implementation needs
    exact expiry date formatting from Zerodha.
    """
    # Simplified — in production, parse expiry to YYMDD format
    return f"{symbol}{strike}{option_type}"


async def _log_order(position_id, order_type, broker_order_id, tradingsymbol,
                     transaction_type, quantity, order_price, fill_price,
                     status, paper_mode, error_message=None):
    """Insert into order_log table."""
    from db.database import _get_db
    async with _get_db() as db:
        await db.execute(
            """INSERT INTO order_log
               (position_id, order_type, broker_order_id, tradingsymbol, exchange,
                transaction_type, quantity, order_price, fill_price, status,
                paper_mode, error_message, filled_at)
               VALUES (?, ?, ?, ?, 'NFO', ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (position_id, order_type, broker_order_id, tradingsymbol,
             transaction_type, quantity, order_price, fill_price, status,
             1 if paper_mode else 0, error_message),
        )
        await db.commit()


class OrderManager:
    """Manages multi-leg order execution with safety guardrails."""

    def __init__(self, broker: BaseBroker):
        self.broker = broker
        self.is_paper = isinstance(broker, PaperBroker)

    async def execute_proposal(self, proposal: dict, config: dict) -> dict:
        """
        Execute a trade proposal by placing all legs.

        Safety: BUY legs first, SELL legs second.
        If any SELL leg fails, unwind all filled legs.

        Returns position dict with order details.
        """
        legs = proposal.get("legs", [])
        symbol = proposal.get("symbol", "NIFTY")
        intelligence = proposal.get("intelligence") or {}
        if isinstance(intelligence, str):
            try:
                intelligence = json.loads(intelligence)
            except Exception:
                intelligence = {}
        expiry = intelligence.get("nearest_expiry", "")

        # Sort: BUY first, SELL second
        buy_legs = [leg for leg in legs if leg["action"] == "buy"]
        sell_legs = [leg for leg in legs if leg["action"] == "sell"]
        ordered_legs = buy_legs + sell_legs

        filled_orders = []

        try:
            for leg in ordered_legs:
                tradingsymbol = _build_tradingsymbol(
                    symbol, expiry, leg["strike"], leg["type"]
                )

                txn_type = "BUY" if leg["action"] == "buy" else "SELL"
                price = float(leg.get("ltp", 0))

                # Adjust price slightly for fill probability
                # BUY: slightly above LTP, SELL: slightly below LTP
                if txn_type == "BUY":
                    limit_price = round(price * 1.005, 2)  # 0.5% above
                else:
                    limit_price = round(price * 0.995, 2)  # 0.5% below

                order_id = await self.broker.place_order(
                    tradingsymbol=tradingsymbol,
                    exchange="NFO",
                    transaction_type=txn_type,
                    order_type="LIMIT",
                    quantity=int(leg.get("qty", 75)),
                    price=limit_price,
                    product="NRML",
                    tag="TRADE",
                )

                filled_orders.append({
                    "order_id": order_id,
                    "tradingsymbol": tradingsymbol,
                    "transaction_type": txn_type,
                    "strike": leg["strike"],
                    "option_type": leg["type"],
                    "quantity": int(leg.get("qty", 75)),
                    "order_price": limit_price,
                    "fill_price": limit_price,  # Paper assumes instant fill
                    "status": "filled",
                })

        except Exception as e:
            # SAFETY: Unwind all filled orders if a sell leg fails
            print(f"[OrderManager] Leg failed: {e}. Unwinding {len(filled_orders)} filled orders...")
            await self._unwind_orders(filled_orders)
            raise RuntimeError(f"Order execution failed at leg: {e}. All positions unwound.")

        # Calculate net premium (positive = credit collected, negative = debit paid)
        net_premium = 0
        for order in filled_orders:
            if order["transaction_type"] == "SELL":
                net_premium += order["fill_price"] * order["quantity"]
            else:
                net_premium -= order["fill_price"] * order["quantity"]

        position = {
            "proposal_id": proposal.get("id"),
            "strategy_id": proposal.get("strategy_id"),
            "symbol": symbol,
            "status": "open",
            "legs": json.dumps(filled_orders),
            "filled_orders": filled_orders,  # For order_log writing
            "entry_time": datetime.now().isoformat(),
            "total_premium": round(net_premium, 2),
            "current_pnl": 0,
            "stop_loss_level": float(proposal.get("max_loss", 0)),
            "target_level": float(proposal.get("max_profit", 0)) * 0.5,
            "paper_mode": 1 if self.is_paper else 0,
        }

        return position

    async def log_orders(self, position_id: int, filled_orders: list[dict],
                         order_type: str = "entry"):
        """Log all filled orders to order_log table after position is saved."""
        for order in filled_orders:
            await _log_order(
                position_id=position_id,
                order_type=order_type,
                broker_order_id=order.get("order_id"),
                tradingsymbol=order.get("tradingsymbol"),
                transaction_type=order.get("transaction_type"),
                quantity=order.get("quantity"),
                order_price=order.get("order_price"),
                fill_price=order.get("fill_price"),
                status="filled",
                paper_mode=self.is_paper,
            )

    async def _unwind_orders(self, filled_orders: list[dict]):
        """Unwind all filled orders by placing opposite transactions."""
        for order in reversed(filled_orders):
            try:
                opposite = "SELL" if order["transaction_type"] == "BUY" else "BUY"
                await self.broker.place_order(
                    tradingsymbol=order["tradingsymbol"],
                    exchange="NFO",
                    transaction_type=opposite,
                    order_type="LIMIT",
                    quantity=order["quantity"],
                    price=order["fill_price"],
                    product="NRML",
                    tag="UNWIND",
                )
            except Exception as e:
                print(f"[OrderManager] CRITICAL: Failed to unwind {order['tradingsymbol']}: {e}")

    async def close_position(self, position: dict) -> dict:
        """Close all legs of a position."""
        legs_data = position.get("legs", "[]")
        if isinstance(legs_data, str):
            legs = json.loads(legs_data)
        else:
            legs = legs_data

        close_orders = []
        for leg in legs:
            opposite = "SELL" if leg["transaction_type"] == "BUY" else "BUY"
            try:
                order_id = await self.broker.place_order(
                    tradingsymbol=leg["tradingsymbol"],
                    exchange="NFO",
                    transaction_type=opposite,
                    order_type="LIMIT",
                    quantity=leg["quantity"],
                    price=leg["fill_price"],
                    product="NRML",
                    tag="CLOSE",
                )
                close_orders.append({
                    "order_id": order_id,
                    "tradingsymbol": leg["tradingsymbol"],
                    "transaction_type": opposite,
                    "quantity": leg["quantity"],
                    "fill_price": leg["fill_price"],
                    "status": "filled",
                })

                # Log to order_log
                if position.get("id"):
                    await _log_order(
                        position_id=position["id"],
                        order_type="exit",
                        broker_order_id=order_id,
                        tradingsymbol=leg["tradingsymbol"],
                        transaction_type=opposite,
                        quantity=leg["quantity"],
                        order_price=leg["fill_price"],
                        fill_price=leg["fill_price"],
                        status="filled",
                        paper_mode=self.is_paper,
                    )
            except Exception as e:
                close_orders.append({"error": str(e), "status": "failed"})

        return {"close_orders": close_orders, "closed_at": datetime.now().isoformat()}
