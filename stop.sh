#!/bin/bash
# ──────────────────────────────────────────────────────────────
# Stock Portfolio Assistant — Stop Script
# Kills backend and frontend servers
# ──────────────────────────────────────────────────────────────

echo "🛑 Stopping Stock Portfolio Assistant..."

lsof -ti:8000 2>/dev/null | xargs kill -9 2>/dev/null && echo "   Backend stopped" || echo "   Backend was not running"
lsof -ti:5173 2>/dev/null | xargs kill -9 2>/dev/null && echo "   Frontend stopped" || echo "   Frontend was not running"

echo "✅ All servers stopped."
