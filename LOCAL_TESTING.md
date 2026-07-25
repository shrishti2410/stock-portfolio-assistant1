# Local Testing Guide

This guide walks through running the Stock Portfolio Assistant locally on your Mac,
plus setting it up to auto-launch every morning at login with a confirmation dialog.

---

## ⚡ Quick start — test it right now

From the repo root:

```bash
./start.sh
```

This will:
1. Kill anything already running on ports 8000 / 5173
2. Create a Python venv if missing, install dependencies
3. Start the FastAPI backend on http://localhost:8000
4. Start the React/Vite frontend on http://localhost:5173
5. Install `node_modules` if missing
6. Open the dashboard in your default browser

When it's running you should see:

```
✅ Backend is running
✅ Frontend is running
🌐 Opening dashboard in browser...
```

Press `Ctrl+C` in the terminal to stop everything. Or run `./stop.sh` from another terminal.

---

## 🧪 What to test

Once the dashboard is open at http://localhost:5173:

### 1. Trading Engine (existing feature)
- Click **Trading** in the nav → you should see the Trading Dashboard
- Click **Settings** → confirm all 3 strategies are enabled, paper mode is ON
- Click **Start Engine** → engine indicator turns green, scan runs every 5 min
- Click **Scan Now** → should show 1+ pending proposals for NIFTY / BANKNIFTY
- Click any proposal → review → **Approve** → position appears in Open Positions
- Paper Trading Account section shows ₹1,00,000 starting capital with live P&L

### 2. IT Bear module (new)
- Click **IT Bear** in the nav (red dot — bearish)
- **Sector Dashboard** — thesis score, NIFTY IT vs NIFTY 50, sector heatmap
- **Earnings** — upcoming earnings sorted by date with countdown colors
- **Universe** — all 13 India + 8 US IT stocks
- **Scanner** — click "Run Scan" → 15-25+ short signals across 5 strategies
- **Strategy Builder** — pick a stock, conviction, horizon → get structure suggestion
- **US Signals** — manual execution checklist for eToro/IBKR trades
- **Notifications** — set up email + Telegram (instructions in UI)

### 3. Check logs if something breaks

```bash
tail -f /tmp/backend.log     # backend logs
tail -f /tmp/frontend.log    # frontend logs
```

---

## 🌅 Auto-launch every morning at login

You want the app to ask "Can I run this?" when you open your laptop in the morning,
and start everything if you say yes. Here's how:

### Install

From the repo root:

```bash
bash install_morning_launcher.sh
```

That single command:
1. Substitutes the absolute path to this repo into the LaunchAgent plist
2. Copies it to `~/Library/LaunchAgents/com.user.stock-portfolio.plist`
3. Loads it with `launchctl`

From the next time you log in to your Mac, you'll see a native dialog:

```
┌─────────────────────────────────────────────┐
│  📈 Stock Portfolio Assistant               │
│                                              │
│  Good morning! Do you want to start the     │
│  trading dashboard?                          │
│                                              │
│  This will launch:                           │
│   • Backend API on port 8000                 │
│   • Frontend UI on port 5173                 │
│   • Open browser to http://localhost:5173    │
│                                              │
│       [ Not now ]    [ Yes, start it ]     │
└─────────────────────────────────────────────┘
```

- **Yes, start it** → opens a Terminal window running `start.sh`, then notifies
  you when the dashboard is ready.
- **Not now** (or close the dialog) → does nothing, no app started.
- Dialog auto-cancels after 30 seconds if you don't interact.

### Test the morning launcher right now (without rebooting)

```bash
bash morning_launch.sh
```

This runs the exact same flow that would run at login — you'll see the dialog
immediately and can click through.

### Uninstall

```bash
bash install_morning_launcher.sh remove
```

Removes the LaunchAgent so the dialog never appears again.

### Where the logs live

The launcher writes to:
- `~/Library/Logs/stock-portfolio-assistant.log` — dialog flow
- `/tmp/stock-portfolio-launch.out.log` — LaunchAgent stdout
- `/tmp/stock-portfolio-launch.err.log` — LaunchAgent stderr

If the dialog doesn't appear at login, check `/tmp/stock-portfolio-launch.err.log` first.

---

## 🔧 Manual debugging

### Backend won't start
```bash
cd backend
source venv/bin/activate
python -m uvicorn main:app --port 8000
# Watch the output for the actual error.
```

### Frontend won't start
```bash
cd frontend
npm install
npx vite
# Should print "ready in XXXms"
```

### Reset everything
```bash
./stop.sh                          # kill servers
rm backend/data/portfolio.db       # reset paper trading state
rm -rf backend/venv                # force venv reinstall on next start
rm -rf frontend/node_modules       # force npm reinstall
./start.sh                         # fresh start
```

### Engine won't generate signals on weekend
This is expected — NSE option chain returns empty when market is closed.
The system falls back to a **synthetic option chain** (yfinance close + India VIX
+ Black-Scholes) so you can test paper trading 24/7. You'll see
`[options] Market closed — using synthetic chain` in the backend log.

---

## 📬 Notifications setup (optional)

### Email (SMTP)

Add to `backend/.env`:

```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your.email@gmail.com
SMTP_PASS=your_app_password   # NOT your gmail password — create at https://myaccount.google.com/apppasswords
NOTIFY_EMAIL=your.email@gmail.com
```

Test from the IT Bear → Notifications page → "Send Test Email".

### Telegram

1. Open Telegram, search for `@BotFather`, send `/newbot`
2. Pick a name, get your `TELEGRAM_BOT_TOKEN` (looks like `123456:ABC-DEF...`)
3. Open chat with your new bot, send `/start`
4. Get your `TELEGRAM_CHAT_ID`:
   ```bash
   curl "https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates" | python3 -m json.tool
   ```
   Look for `"chat": {"id": 123456789}`.
5. Add to `backend/.env`:
   ```bash
   TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
   TELEGRAM_CHAT_ID=123456789
   ```
6. Test from IT Bear → Notifications → "Send Test Telegram".

---

## 🐙 Pushing to your own GitHub fork

The repo lives at `shrishti2410/stock-portfolio-assistant1`. To push from your
own account (e.g. `rtaori21`):

```bash
# 1. Log into gh as your account
gh auth login
# Choose: GitHub.com → HTTPS → "Login with a web browser" → paste rtaori21 credentials

# 2. Fork the repo to your account (via web UI or gh):
gh repo fork shrishti2410/stock-portfolio-assistant1 --clone=false

# 3. Add the fork as a remote
git remote add myfork git@github.com:rtaori21/stock-portfolio-assistant1.git

# 4. Push the branch
git push myfork claude/stoic-mclean

# 5. Open a PR from your fork to upstream:
gh pr create --repo shrishti2410/stock-portfolio-assistant1 \
  --head rtaori21:claude/stoic-mclean \
  --title "feat: IT Bear module + morning auto-launch"
```
