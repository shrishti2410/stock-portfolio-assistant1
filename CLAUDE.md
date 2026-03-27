# Stock Portfolio Assistant

## Project Overview
A web dashboard that connects to Zerodha, fetches portfolio holdings, and provides AI-powered Buy/Sell/Hold recommendations using the TradingAgents framework.

## Tech Stack
- Backend: FastAPI (Python 3.11+)
- Frontend: React + Vite + Tailwind CSS
- AI Analysis: TradingAgents (from /analysis/tradingagents/)
- Brokerage: Zerodha Kite Connect

## Project Structure
- /backend — FastAPI app, all Python code
- /frontend — React app
- /backend/analysis/ — TradingAgents integration

## Rules
- Never commit .env files
- Always use async functions in FastAPI
- Keep TradingAgents logic isolated in /backend/analysis/
- Use dummy data fallback if Zerodha token is missing

## API Keys (in .env)
- ZERODHA_API_KEY
- ZERODHA_ACCESS_TOKEN
- ANTHROPIC_API_KEY
```