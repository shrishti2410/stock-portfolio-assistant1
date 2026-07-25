# ════════════════════════════════════════════════════════════════
# Trading Desk — single-container build (ARM64 + x86_64 compatible,
# works on Oracle Cloud Always-Free A1 instances).
#
# Stage 1 builds the React SPA; Stage 2 runs FastAPI and serves the
# built SPA from the same origin (auth middleware protects /api/*).
# ════════════════════════════════════════════════════════════════

# ── Stage 1: frontend build ─────────────────────────────────────
FROM node:20-slim AS webbuild
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npx vite build

# ── Stage 2: backend + built SPA ────────────────────────────────
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Kolkata

WORKDIR /app/backend

# tvDatafeed is optional (MCX fallback already uses yfinance) and its
# PyPI package is unreliable — exclude it from the container build.
COPY backend/requirements.txt ./
RUN grep -viE '^tvDatafeed' requirements.txt > /tmp/req.txt \
    && pip install -r /tmp/req.txt

COPY backend/ ./
COPY --from=webbuild /app/frontend/dist /app/frontend/dist

# SQLite lives here — mount a volume over it in compose
VOLUME ["/app/backend/data"]

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
