"""
engine.py — Trading engine that runs scans every 15 minutes.

Lifecycle:
1. Start as asyncio background task
2. Every scan_interval: collect data -> evaluate strategies -> risk check -> notify
3. Monitor open positions between scans
4. Stop gracefully on command
"""
import asyncio
import json
import time
from datetime import datetime, date

from trading.events import is_market_hours, get_upcoming_events, is_blackout_period
from trading.risk import run_risk_checks, all_checks_passed
from trading.strategies import ALL_EVALUATORS
from trading.intelligence import get_market_snapshot
from trading.broker import get_broker, PaperBroker
from trading.orders import OrderManager

# IT-Bear evaluators (imported lazily to avoid circular deps at module load)
_IT_BEAR_EVALUATORS = None


def _get_it_bear_evaluators():
    global _IT_BEAR_EVALUATORS
    if _IT_BEAR_EVALUATORS is None:
        try:
            from trading.strategies_it_bear import ALL_IT_BEAR_EVALUATORS
            _IT_BEAR_EVALUATORS = ALL_IT_BEAR_EVALUATORS
        except Exception as e:
            print(f"[TradingEngine] IT-Bear evaluators not loaded: {e}")
            _IT_BEAR_EVALUATORS = []
    return _IT_BEAR_EVALUATORS


class TradingEngine:
    """
    Core trading engine. Runs as an asyncio background task.

    Safety:
    - OFF by default (engine_enabled must be True)
    - Scans only during market hours
    - Every proposal requires user approval
    - 12 risk checks must pass before any proposal
    """

    def __init__(self):
        self._running = False
        self._task: asyncio.Task | None = None
        self._scan_count = 0
        self._last_scan_time: str | None = None
        self._next_scan_time: str | None = None
        self._ws_clients: list = []  # WebSocket connections for notifications
        self._broker = None
        self._order_manager = None
        # IT-Bear layer config: {layer_name: auto_execute_enabled}
        self.auto_execute_layers: dict[str, bool] = {
            "core": False,
            "tactical": False,
            "us": False,
            "hedge": False,
        }

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def status(self) -> dict:
        return {
            "running": self._running,
            "scan_count": self._scan_count,
            "last_scan": self._last_scan_time,
            "next_scan": self._next_scan_time,
            "market_open": is_market_hours(),
            "upcoming_events": get_upcoming_events(days_ahead=3),
        }

    async def start(self, config: dict):
        """Start the engine as a background task."""
        if self._running:
            return {"status": "already_running"}

        paper_mode = bool(config.get("paper_mode", 1))
        self._broker = get_broker(paper_mode=paper_mode)
        self._order_manager = OrderManager(self._broker)

        self._running = True
        self._task = asyncio.create_task(self._run_loop(config))

        mode = "PAPER" if paper_mode else "LIVE"
        print(f"[TradingEngine] Started in {mode} mode")
        return {"status": "started", "mode": mode}

    async def stop(self):
        """Stop the engine gracefully."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        print("[TradingEngine] Stopped")
        return {"status": "stopped"}

    async def _run_loop(self, config: dict):
        """Main loop: scan every N minutes. Paper mode runs even outside market hours."""
        interval_min = config.get("scan_interval_min", 15)
        interval_sec = interval_min * 60
        paper_mode = bool(config.get("paper_mode", 1))

        while self._running:
            try:
                if is_market_hours() or paper_mode:
                    await self.run_scan(config)
                    # Update P&L for open paper positions
                    if paper_mode:
                        try:
                            await self.update_paper_pnl()
                        except Exception as e:
                            print(f"[TradingEngine] P&L update error: {e}")
                else:
                    print("[TradingEngine] Market closed, waiting...")

                # Calculate next scan time
                self._next_scan_time = datetime.now().isoformat()
                await asyncio.sleep(interval_sec)

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[TradingEngine] Scan error: {e}")
                await asyncio.sleep(60)  # Wait 1 min on error

    async def run_scan(self, config: dict = None) -> dict:
        """
        Execute one scan cycle:
        1. Fetch market data for NIFTY and BANKNIFTY
        2. Run all enabled strategy evaluators
        3. Risk-check any signals
        4. Create proposals and notify
        """
        if config is None:
            config = await self._load_config()

        start_time = time.time()
        self._scan_count += 1
        self._last_scan_time = datetime.now().isoformat()

        enabled_strategies = json.loads(config.get("strategies_enabled", "[]"))
        symbols = ["NIFTY", "BANKNIFTY"]

        all_signals = []
        blocked_reasons = []

        paper_mode = bool(config.get("paper_mode", 1))

        for symbol in symbols:
            try:
                # 1. Fetch option chain (with synthetic fallback for paper mode)
                from data.synthetic_options import get_chain_with_fallback
                option_data = await asyncio.to_thread(
                    get_chain_with_fallback, symbol, paper_mode
                )

                if option_data.get("market_closed") and not paper_mode:
                    blocked_reasons.append(f"{symbol}: market closed")
                    continue

                if option_data.get("strike_count", 0) == 0:
                    blocked_reasons.append(f"{symbol}: no strike data available")
                    continue

                # 2. Get market intelligence snapshot
                snapshot = await get_market_snapshot(symbol, option_data)

                # 3. Get technical indicators (for directional strategy)
                indicators = {}
                try:
                    # Indices: use yfinance directly. Stocks: use screener.
                    if symbol in ("NIFTY", "BANKNIFTY", "FINNIFTY"):
                        from trading.index_indicators import get_index_indicators
                        indicators = await asyncio.to_thread(get_index_indicators, symbol)
                    else:
                        from analysis.screener import screen_stock
                        screen_result = await asyncio.to_thread(screen_stock, symbol)
                        indicators = screen_result.indicators
                        indicators["overall_score"] = screen_result.overall_score
                except Exception as e:
                    print(f"[engine] Indicator fetch error for {symbol}: {e}")
                    pass  # Indicators optional for non-directional strategies

                # 4. Run each enabled evaluator
                for evaluator in ALL_EVALUATORS:
                    if evaluator.strategy_id not in enabled_strategies:
                        continue

                    try:
                        proposal = await evaluator.evaluate(snapshot, option_data, indicators)
                        if proposal:
                            # 5. Run risk checks
                            risk_results = await run_risk_checks(proposal, config)
                            proposal["risk_checks"] = json.dumps(risk_results)

                            if all_checks_passed(risk_results):
                                proposal["status"] = "pending"
                                # Save to DB
                                proposal_id = await self._save_proposal(proposal)
                                proposal["id"] = proposal_id

                                # Notify via WebSocket
                                await self._notify_clients({
                                    "type": "new_proposal",
                                    "proposal": proposal,
                                })

                                all_signals.append(proposal)
                                print(f"[TradingEngine] Signal: {evaluator.strategy_name} on {symbol} "
                                      f"(confidence: {proposal['confidence']:.0%})")
                            else:
                                failed = [r for r in risk_results if not r["passed"]]
                                blocked_reasons.append(
                                    f"{evaluator.strategy_name}/{symbol}: "
                                    f"blocked by {', '.join(r['check'] for r in failed)}"
                                )
                    except Exception as e:
                        print(f"[TradingEngine] Evaluator {evaluator.strategy_id} error: {e}")

            except Exception as e:
                print(f"[TradingEngine] Error processing {symbol}: {e}")
                blocked_reasons.append(f"{symbol}: {str(e)[:100]}")

        # ── IT-Bear scan: run evaluators over IT universe ──────────────────
        it_bear_enabled = bool(config.get("it_bear_enabled", 1))
        it_evaluators = _get_it_bear_evaluators()

        if it_bear_enabled and it_evaluators:
            try:
                from data.it_universe import get_india
                from data.synthetic_options import generate_synthetic_chain

                it_stocks = get_india()  # 12 Indian IT names + NIFTY IT index

                # Reload auto-execute layer config from DB config
                self.auto_execute_layers = {
                    "core": bool(config.get("auto_layer_core", 0)),
                    "tactical": bool(config.get("auto_layer_tactical", 0)),
                    "us": bool(config.get("auto_layer_us", 0)),
                    "hedge": bool(config.get("auto_layer_hedge", 0)),
                }

                for stock in it_stocks:
                    sym = stock["symbol"]
                    yf_sym = stock.get("yf", sym)

                    try:
                        # Synthetic chain for IT stocks (single-stock options)
                        # Falls back to NIFTY IT chain if stock chain unavailable
                        from data.synthetic_options import get_chain_with_fallback as _gcwf
                        try:
                            it_chain = await asyncio.to_thread(
                                _gcwf, sym, paper_mode
                            )
                            if it_chain.get("strike_count", 0) == 0:
                                it_chain = await asyncio.to_thread(
                                    generate_synthetic_chain, "NIFTYIT"
                                )
                        except Exception:
                            it_chain = await asyncio.to_thread(
                                generate_synthetic_chain, "NIFTYIT"
                            )

                        # Build minimal snapshot for this stock
                        spot = it_chain.get("spot_price", 0)
                        it_snapshot = {
                            "symbol": sym,
                            "spot": spot,
                            "vix": it_chain.get("vix", 0),
                            "vix_regime": "unknown",
                            "pcr": it_chain.get("pcr", 0),
                            "atm": {},
                            "expected_move": 0,
                            "max_pain": 0,
                            "oi_levels": {"support": 0, "resistance": 0},
                            "iv_percentile": -1,
                            "nearest_expiry": "",
                            "days_to_expiry": 28,
                            "greeks": {},
                        }

                        # Run each IT-bear evaluator
                        for evaluator in it_evaluators:
                            try:
                                proposal = await evaluator.evaluate(
                                    it_snapshot, it_chain, indicators=None
                                )
                                if proposal:
                                    risk_results = await run_risk_checks(proposal, config)
                                    proposal["risk_checks"] = json.dumps(risk_results)

                                    if all_checks_passed(risk_results):
                                        proposal["status"] = "pending"
                                        proposal_id = await self._save_proposal(proposal)
                                        proposal["id"] = proposal_id

                                        # Fan out via dispatcher (not just WebSocket)
                                        try:
                                            from notifications.dispatcher import notify_trade_alert
                                            asyncio.create_task(notify_trade_alert(proposal))
                                        except Exception as ne:
                                            print(f"[TradingEngine] Dispatcher error: {ne}")
                                            # Fallback to direct WS
                                            await self._notify_clients({
                                                "type": "new_proposal",
                                                "proposal": proposal,
                                            })

                                        # Auto-execute if layer is enabled
                                        layer = proposal.get("intelligence", {}).get("layer", "")
                                        if self.auto_execute_layers.get(layer, False):
                                            try:
                                                await self.execute_approved(proposal_id)
                                                print(f"[TradingEngine] Auto-executed {evaluator.strategy_name} "
                                                      f"on {sym} (layer={layer})")
                                            except Exception as ae:
                                                print(f"[TradingEngine] Auto-execute failed: {ae}")

                                        all_signals.append(proposal)
                                        print(f"[TradingEngine] IT-Bear: {evaluator.strategy_name} "
                                              f"on {sym} ({proposal['confidence']:.0%})")
                                    else:
                                        failed = [r for r in risk_results if not r["passed"]]
                                        blocked_reasons.append(
                                            f"IT-Bear/{evaluator.strategy_id}/{sym}: "
                                            f"blocked by {', '.join(r['check'] for r in failed)}"
                                        )
                            except Exception as e:
                                print(f"[TradingEngine] IT-Bear evaluator {evaluator.strategy_id} "
                                      f"error on {sym}: {e}")

                    except Exception as e:
                        print(f"[TradingEngine] IT-Bear error for {sym}: {e}")
                        blocked_reasons.append(f"IT-Bear/{sym}: {str(e)[:80]}")

            except Exception as e:
                print(f"[TradingEngine] IT-Bear scan block failed: {e}")

        # ── End IT-Bear scan ────────────────────────────────────────────────

        duration_ms = int((time.time() - start_time) * 1000)

        # Log scan
        scan_record = {
            "market_data": json.dumps({"symbols": symbols, "timestamp": self._last_scan_time}),
            "signals": json.dumps([{"strategy": s["strategy_id"], "symbol": s["symbol"],
                                    "confidence": s["confidence"]} for s in all_signals]),
            "blocked_reason": "; ".join(blocked_reasons) if blocked_reasons else None,
            "duration_ms": duration_ms,
        }
        await self._save_scan_log(scan_record)

        result = {
            "scan_number": self._scan_count,
            "signals": len(all_signals),
            "blocked": len(blocked_reasons),
            "duration_ms": duration_ms,
        }

        print(f"[TradingEngine] Scan #{self._scan_count}: {len(all_signals)} signals, "
              f"{len(blocked_reasons)} blocked, {duration_ms}ms")

        return result

    async def execute_approved(self, proposal_id: int) -> dict:
        """Execute an approved trade proposal."""
        proposal = await self._load_proposal(proposal_id)
        if not proposal:
            return {"error": "Proposal not found"}

        if proposal.get("status") != "pending":
            return {"error": f"Proposal status is {proposal.get('status')}, expected 'pending'"}

        config = await self._load_config()

        # Ensure broker + order manager are initialized (engine may not be running)
        if self._broker is None or self._order_manager is None:
            paper_mode = bool(config.get("paper_mode", 1))
            self._broker = get_broker(paper_mode=paper_mode)
            self._order_manager = OrderManager(self._broker)

        # Re-run risk checks (conditions may have changed)
        risk_results = await run_risk_checks(proposal, config)
        if not all_checks_passed(risk_results):
            failed = [r for r in risk_results if not r["passed"]]
            await self._update_proposal_status(proposal_id, "rejected")
            return {"error": f"Risk checks failed: {', '.join(r['check'] for r in failed)}"}

        # Execute via order manager
        try:
            position = await self._order_manager.execute_proposal(proposal, config)

            # Save position to DB
            position_id = await self._save_position(position)

            # Log all orders to order_log
            filled_orders = position.get("filled_orders", [])
            if filled_orders:
                await self._order_manager.log_orders(position_id, filled_orders, "entry")

            # Update proposal status
            await self._update_proposal_status(proposal_id, "executed")

            # Notify
            await self._notify_clients({
                "type": "position_opened",
                "position_id": position_id,
                "strategy": proposal["strategy_id"],
                "symbol": proposal["symbol"],
            })

            return {"status": "executed", "position_id": position_id}

        except Exception as e:
            await self._update_proposal_status(proposal_id, "rejected")
            return {"error": f"Execution failed: {str(e)}"}

    async def update_paper_pnl(self):
        """Update P&L for all open paper positions using current synthetic chain prices."""
        from db.database import _get_db
        import aiosqlite

        async with _get_db() as db:
            db.row_factory = aiosqlite.Row
            rows = await db.execute_fetchall(
                "SELECT * FROM positions WHERE status = 'open' AND paper_mode = 1"
            )
            open_positions = [dict(r) for r in rows]

        if not open_positions:
            return 0

        # Group by symbol to fetch chain once
        symbols_needed = set(p["symbol"] for p in open_positions)
        chains = {}
        for sym in symbols_needed:
            try:
                from data.synthetic_options import get_chain_with_fallback
                chain = await asyncio.to_thread(get_chain_with_fallback, sym, True)
                chains[sym] = chain
            except Exception as e:
                print(f"[engine] Chain fetch failed for {sym}: {e}")

        updated = 0
        for pos in open_positions:
            try:
                chain = chains.get(pos["symbol"])
                if not chain:
                    continue

                legs = json.loads(pos.get("legs", "[]"))
                current_pnl = 0
                for leg in legs:
                    strike = leg.get("strike")
                    opt_type = leg.get("option_type")
                    qty = leg.get("quantity", 0)
                    entry_price = leg.get("fill_price", 0)
                    txn = leg.get("transaction_type")

                    # Find current LTP
                    current_ltp = 0
                    for s in chain.get("strikes", []):
                        if s.get("strikePrice") == strike:
                            current_ltp = s.get(opt_type, {}).get("ltp", 0)
                            break

                    if current_ltp == 0:
                        continue

                    # P&L: SELL gains when price drops, BUY gains when price rises
                    if txn == "SELL":
                        pnl = (entry_price - current_ltp) * qty
                    else:  # BUY
                        pnl = (current_ltp - entry_price) * qty
                    current_pnl += pnl

                async with _get_db() as db:
                    await db.execute(
                        "UPDATE positions SET current_pnl = ? WHERE id = ?",
                        (round(current_pnl, 2), pos["id"]),
                    )
                    await db.commit()
                updated += 1
            except Exception as e:
                print(f"[engine] P&L update failed for position #{pos['id']}: {e}")

        return updated

    async def close_position(self, position_id: int, reason: str = "manual") -> dict:
        """Force-close a position."""
        position = await self._load_position(position_id)
        if not position:
            return {"error": "Position not found"}

        result = await self._order_manager.close_position(position)
        await self._update_position_status(position_id, "closed", reason)

        await self._notify_clients({
            "type": "position_closed",
            "position_id": position_id,
            "reason": reason,
        })

        return result

    # --- WebSocket notification ---

    def register_ws(self, ws):
        self._ws_clients.append(ws)

    def unregister_ws(self, ws):
        self._ws_clients = [c for c in self._ws_clients if c != ws]

    async def _notify_clients(self, message: dict):
        """Send message to all connected WebSocket clients."""
        for ws in self._ws_clients[:]:
            try:
                await ws.send_json(message)
            except Exception:
                self._ws_clients.remove(ws)

    # --- DB helpers ---

    async def _load_config(self) -> dict:
        from db.database import _get_db
        async with _get_db() as db:
            db.row_factory = __import__("aiosqlite").Row
            rows = await db.execute_fetchall("SELECT * FROM trading_config WHERE id = 1")
            if rows:
                return dict(rows[0])
            # Insert default config
            await db.execute(
                "INSERT OR IGNORE INTO trading_config (id) VALUES (1)"
            )
            await db.commit()
            rows = await db.execute_fetchall("SELECT * FROM trading_config WHERE id = 1")
            return dict(rows[0]) if rows else {}

    async def _save_proposal(self, proposal: dict) -> int:
        from db.database import _get_db
        async with _get_db() as db:
            cursor = await db.execute(
                """INSERT INTO trade_proposals
                   (strategy_id, symbol, direction, legs, greeks, intelligence,
                    max_profit, max_loss, margin_needed, confidence, reasoning, risk_checks,
                    status, expires_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending',
                           datetime('now', '+10 minutes'))""",
                (proposal["strategy_id"], proposal["symbol"], proposal.get("direction"),
                 json.dumps(proposal["legs"]), json.dumps(proposal.get("greeks", {})),
                 json.dumps(proposal.get("intelligence", {})),
                 proposal.get("max_profit"), proposal.get("max_loss"),
                 proposal.get("margin_needed"), proposal.get("confidence"),
                 proposal.get("reasoning"), proposal.get("risk_checks", "[]")),
            )
            await db.commit()
            return cursor.lastrowid

    async def _load_proposal(self, proposal_id: int) -> dict | None:
        from db.database import _get_db
        async with _get_db() as db:
            db.row_factory = __import__("aiosqlite").Row
            rows = await db.execute_fetchall(
                "SELECT * FROM trade_proposals WHERE id = ?", (proposal_id,)
            )
            if not rows:
                return None
            d = dict(rows[0])
            # Parse JSON fields back to objects
            for field in ("legs", "greeks", "intelligence", "risk_checks"):
                if d.get(field) and isinstance(d[field], str):
                    try:
                        d[field] = json.loads(d[field])
                    except Exception:
                        pass
            return d

    async def _update_proposal_status(self, proposal_id: int, status: str):
        from db.database import _get_db
        async with _get_db() as db:
            await db.execute(
                "UPDATE trade_proposals SET status = ?, decided_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, proposal_id),
            )
            await db.commit()

    async def _save_position(self, position: dict) -> int:
        from db.database import _get_db
        async with _get_db() as db:
            cursor = await db.execute(
                """INSERT INTO positions
                   (proposal_id, strategy_id, symbol, status, legs,
                    total_premium, stop_loss_level, target_level, paper_mode)
                   VALUES (?, ?, ?, 'open', ?, ?, ?, ?, ?)""",
                (position.get("proposal_id"), position["strategy_id"], position["symbol"],
                 position["legs"], position.get("total_premium", 0),
                 position.get("stop_loss_level", 0), position.get("target_level", 0),
                 position.get("paper_mode", 1)),
            )
            await db.commit()
            return cursor.lastrowid

    async def _load_position(self, position_id: int) -> dict | None:
        from db.database import _get_db
        async with _get_db() as db:
            db.row_factory = __import__("aiosqlite").Row
            rows = await db.execute_fetchall(
                "SELECT * FROM positions WHERE id = ?", (position_id,)
            )
            return dict(rows[0]) if rows else None

    async def _update_position_status(self, position_id: int, status: str, reason: str = ""):
        from db.database import _get_db
        async with _get_db() as db:
            await db.execute(
                """UPDATE positions SET status = ?, exit_time = CURRENT_TIMESTAMP,
                   adjustments = COALESCE(adjustments, '') || ? WHERE id = ?""",
                (status, f"\n{reason}" if reason else "", position_id),
            )
            await db.commit()

    async def _save_scan_log(self, record: dict):
        from db.database import _get_db
        async with _get_db() as db:
            await db.execute(
                """INSERT INTO scan_log (market_data, signals, blocked_reason, duration_ms)
                   VALUES (?, ?, ?, ?)""",
                (record["market_data"], record["signals"],
                 record.get("blocked_reason"), record.get("duration_ms")),
            )
            await db.commit()


# Singleton engine instance
trading_engine = TradingEngine()
