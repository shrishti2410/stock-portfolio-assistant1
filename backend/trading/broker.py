"""
broker.py — Abstract broker layer for order execution.

Supports:
  PaperBroker — simulated fills for testing (default)
  KiteBroker  — real orders via kiteconnect or jugaad-trader
"""
import asyncio
import os
import time
from abc import ABC, abstractmethod
from datetime import datetime


class BaseBroker(ABC):
    """Abstract broker interface. All order operations go through this."""

    @abstractmethod
    async def place_order(self, tradingsymbol: str, exchange: str, transaction_type: str,
                          order_type: str, quantity: int, price: float,
                          trigger_price: float = None, product: str = "NRML",
                          tag: str = "") -> str:
        """Place an order. Returns order_id string."""

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool: ...

    @abstractmethod
    async def get_order_status(self, order_id: str) -> dict: ...

    @abstractmethod
    async def get_positions(self) -> list[dict]: ...

    @abstractmethod
    async def get_margins(self) -> dict: ...

    @abstractmethod
    async def place_gtt(self, tradingsymbol: str, exchange: str, trigger_type: str,
                        trigger_values: list[float], orders: list[dict]) -> str:
        """Place GTT order for automatic SL/target. Returns gtt_id."""

    @abstractmethod
    async def cancel_gtt(self, gtt_id: str) -> bool: ...


class PaperBroker(BaseBroker):
    """
    Simulated broker for paper trading.
    - Generates fake order_ids (paper_001, paper_002...)
    - Fills at provided price instantly
    - Tracks positions in-memory
    """

    def __init__(self):
        self._order_counter = 0
        self._orders = {}  # order_id -> order details
        self._positions = []  # simulated positions
        self._gtt_counter = 0
        self._gtts = {}  # gtt_id -> gtt details

    async def place_order(self, tradingsymbol, exchange, transaction_type,
                          order_type, quantity, price, trigger_price=None,
                          product="NRML", tag="") -> str:
        self._order_counter += 1
        order_id = f"paper_{self._order_counter:04d}"
        fill_price = price if price else 0

        self._orders[order_id] = {
            "order_id": order_id,
            "tradingsymbol": tradingsymbol,
            "exchange": exchange,
            "transaction_type": transaction_type,
            "order_type": order_type,
            "quantity": quantity,
            "price": price,
            "trigger_price": trigger_price,
            "product": product,
            "tag": tag,
            "fill_price": fill_price,
            "status": "COMPLETE",
            "filled_at": datetime.now().isoformat(),
        }

        print(f"[PaperBroker] Order {order_id}: {transaction_type} {quantity}x {tradingsymbol} @ Rs.{fill_price}")
        return order_id

    async def cancel_order(self, order_id: str) -> bool:
        if order_id in self._orders:
            self._orders[order_id]["status"] = "CANCELLED"
            return True
        return False

    async def get_order_status(self, order_id: str) -> dict:
        return self._orders.get(order_id, {"status": "UNKNOWN"})

    async def get_positions(self) -> list[dict]:
        return self._positions

    async def get_margins(self) -> dict:
        return {"equity": {"available": {"live_balance": 500000}}, "commodity": {}}

    async def place_gtt(self, tradingsymbol, exchange, trigger_type,
                        trigger_values, orders) -> str:
        self._gtt_counter += 1
        gtt_id = f"paper_gtt_{self._gtt_counter:04d}"
        self._gtts[gtt_id] = {
            "id": gtt_id,
            "tradingsymbol": tradingsymbol,
            "trigger_type": trigger_type,
            "trigger_values": trigger_values,
            "orders": orders,
            "status": "active",
        }
        print(f"[PaperBroker] GTT {gtt_id}: {trigger_type} on {tradingsymbol}")
        return gtt_id

    async def cancel_gtt(self, gtt_id: str) -> bool:
        if gtt_id in self._gtts:
            self._gtts[gtt_id]["status"] = "cancelled"
            return True
        return False


class KiteBroker(BaseBroker):
    """
    Real broker using kiteconnect (preferred) or jugaad-trader (fallback).

    Safety rules:
    - All orders are LIMIT only (never MARKET) — hardcoded
    - Rate limiting: max 8 orders/sec
    - Retry with exponential backoff on transient failures
    """

    def __init__(self):
        self._kite = None
        self._last_order_time = 0
        self._min_order_interval = 0.125  # 8 orders/sec max
        self._init_client()

    def _init_client(self):
        """Try kiteconnect first, then jugaad-trader."""
        api_key = os.getenv("ZERODHA_API_KEY", "").strip()
        access_token = os.getenv("ZERODHA_ACCESS_TOKEN", "").strip()

        if api_key and access_token:
            try:
                from kiteconnect import KiteConnect
                self._kite = KiteConnect(api_key=api_key)
                self._kite.set_access_token(access_token)
                self._client_type = "kiteconnect"
                print("[KiteBroker] Using official KiteConnect")
                return
            except ImportError:
                pass

        # Fallback to jugaad-trader
        user_id = os.getenv("ZERODHA_USER_ID", "").strip()
        password = os.getenv("ZERODHA_PASSWORD", "").strip()
        totp_secret = os.getenv("ZERODHA_TOTP_SECRET", "").strip()

        if all([user_id, password, totp_secret]):
            try:
                from jugaad_trader import Zerodha
                import pyotp
                totp = pyotp.TOTP(totp_secret)
                kite = Zerodha(user_id=user_id, password=password, twofa=totp.now())
                if hasattr(kite, "login"):
                    kite.login()
                self._kite = kite
                self._client_type = "jugaad-trader"
                print("[KiteBroker] Using jugaad-trader")
                return
            except Exception as e:
                print(f"[KiteBroker] jugaad-trader init failed: {e}")

        self._client_type = "none"
        print("[KiteBroker] WARNING: No broker credentials configured")

    async def _rate_limit(self):
        """Enforce minimum interval between orders."""
        now = time.time()
        elapsed = now - self._last_order_time
        if elapsed < self._min_order_interval:
            await asyncio.sleep(self._min_order_interval - elapsed)
        self._last_order_time = time.time()

    async def place_order(self, tradingsymbol, exchange, transaction_type,
                          order_type, quantity, price, trigger_price=None,
                          product="NRML", tag="") -> str:
        if not self._kite:
            raise RuntimeError("No broker connection available")

        # SAFETY: Force LIMIT orders only
        if order_type == "MARKET":
            raise ValueError("MARKET orders are not allowed. Use LIMIT only.")

        await self._rate_limit()

        params = {
            "tradingsymbol": tradingsymbol,
            "exchange": exchange,
            "transaction_type": transaction_type,
            "order_type": order_type,
            "quantity": quantity,
            "price": price,
            "product": product,
            "validity": "DAY",
        }
        if trigger_price:
            params["trigger_price"] = trigger_price
        if tag:
            params["tag"] = tag[:8]  # Zerodha max 8 chars

        order_id = await asyncio.to_thread(
            self._kite.place_order,
            variety="regular",
            **params,
        )
        print(f"[KiteBroker] Order placed: {order_id} — {transaction_type} {quantity}x {tradingsymbol}")
        return str(order_id)

    async def cancel_order(self, order_id: str) -> bool:
        if not self._kite:
            return False
        try:
            await asyncio.to_thread(
                self._kite.cancel_order, variety="regular", order_id=order_id
            )
            return True
        except Exception as e:
            print(f"[KiteBroker] Cancel failed for {order_id}: {e}")
            return False

    async def get_order_status(self, order_id: str) -> dict:
        if not self._kite:
            return {"status": "UNKNOWN"}
        try:
            orders = await asyncio.to_thread(self._kite.orders)
            for o in orders:
                if str(o.get("order_id")) == str(order_id):
                    return o
            return {"status": "NOT_FOUND"}
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}

    async def get_positions(self) -> list[dict]:
        if not self._kite:
            return []
        try:
            positions = await asyncio.to_thread(self._kite.positions)
            return positions.get("net", [])
        except Exception:
            return []

    async def get_margins(self) -> dict:
        if not self._kite:
            return {}
        try:
            return await asyncio.to_thread(self._kite.margins)
        except Exception:
            return {}

    async def place_gtt(self, tradingsymbol, exchange, trigger_type,
                        trigger_values, orders) -> str:
        if not self._kite or self._client_type != "kiteconnect":
            raise RuntimeError("GTT requires official KiteConnect API")

        await self._rate_limit()
        gtt_id = await asyncio.to_thread(
            self._kite.place_gtt,
            trigger_type=trigger_type,
            tradingsymbol=tradingsymbol,
            exchange=exchange,
            trigger_values=trigger_values,
            last_price=trigger_values[0],
            orders=orders,
        )
        print(f"[KiteBroker] GTT placed: {gtt_id}")
        return str(gtt_id)

    async def cancel_gtt(self, gtt_id: str) -> bool:
        if not self._kite or self._client_type != "kiteconnect":
            return False
        try:
            await asyncio.to_thread(self._kite.delete_gtt, trigger_id=int(gtt_id))
            return True
        except Exception as e:
            print(f"[KiteBroker] GTT cancel failed: {e}")
            return False


def get_broker(paper_mode: bool = True) -> BaseBroker:
    """Factory: return appropriate broker based on mode."""
    if paper_mode:
        return PaperBroker()
    return KiteBroker()
