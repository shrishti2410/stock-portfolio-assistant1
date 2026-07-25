#!/bin/bash
# ──────────────────────────────────────────────────────────────
# Stock Portfolio Assistant — Start Script
# Usage: double-click this file or run: ./start.sh
# ──────────────────────────────────────────────────────────────

DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$DIR/backend"
FRONTEND_DIR="$DIR/frontend"

echo "🚀 Starting Stock Portfolio Assistant..."
echo ""

# ── Kill any existing processes on our ports ──────────────────
lsof -ti:8000 2>/dev/null | xargs kill -9 2>/dev/null
lsof -ti:5173 2>/dev/null | xargs kill -9 2>/dev/null
sleep 1

# ── Start Backend (FastAPI) ──────────────────────────────────
echo "📦 Starting backend on http://localhost:8000 ..."
cd "$BACKEND_DIR"

# Create venv if it doesn't exist
if [ ! -d "venv" ]; then
    echo "   Creating Python virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt jugaad-trader pyotp pandas_ta jugaad-data aiosqlite 2>&1 | tail -1
else
    source venv/bin/activate
fi

python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload > /tmp/backend.log 2>&1 &
BACKEND_PID=$!
echo "   Backend PID: $BACKEND_PID"

# ── Start Frontend (Vite + React) ────────────────────────────
echo "🎨 Starting frontend on http://localhost:5173 ..."
cd "$FRONTEND_DIR"

# Install node_modules if missing
if [ ! -d "node_modules" ]; then
    echo "   Installing npm dependencies..."
    npm install 2>&1 | tail -1
fi

npx vite --host 0.0.0.0 --port 5173 > /tmp/frontend.log 2>&1 &
FRONTEND_PID=$!
echo "   Frontend PID: $FRONTEND_PID"

# ── Wait for servers to be ready ─────────────────────────────
echo ""
echo "⏳ Waiting for servers..."
sleep 3

# Check backend
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Backend is running"
else
    echo "⚠️  Backend may still be starting (check /tmp/backend.log)"
fi

# Check frontend
if curl -s -o /dev/null http://localhost:5173/ 2>/dev/null; then
    echo "✅ Frontend is running"
else
    echo "⚠️  Frontend may still be starting (check /tmp/frontend.log)"
fi

# ── IT-Bear: pre-fetch today's earnings calendar (if stale) ───
# The backend's startup hook already kicks this off, but we also poke the
# endpoint here so the user sees a clear "refreshing" message on first launch.
echo ""
STATUS=$(curl -s http://localhost:8000/api/it-bear/earnings/refresh-status 2>/dev/null)
if echo "$STATUS" | grep -q '"is_fresh_today": true'; then
    echo "📅 IT-Bear earnings cache: ✅ fresh"
else
    echo "📅 IT-Bear earnings cache: ⏳ stale → refreshing in background (~25s)..."
    # Fire and forget: hits the endpoint which is idempotent
    curl -s -X POST "http://localhost:8000/api/it-bear/earnings/refresh" > /dev/null 2>&1 &
    echo "   (Open Earnings tab in a moment to see fresh data)"
fi

# ── Open browser ─────────────────────────────────────────────
echo ""
echo "🌐 Opening dashboard in browser..."
sleep 1
open http://localhost:5173/

echo ""
echo "════════════════════════════════════════════════════════"
echo "  Dashboard: http://localhost:5173/"
echo "  API Docs:  http://localhost:8000/docs"
echo "  Logs:      /tmp/backend.log  /tmp/frontend.log"
echo ""
echo "  Press Ctrl+C to stop all servers"
echo "════════════════════════════════════════════════════════"

# ── Keep script running (Ctrl+C stops everything) ────────────
trap "echo ''; echo 'Stopping servers...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo 'Done.'; exit 0" INT TERM

wait
