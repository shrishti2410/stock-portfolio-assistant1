# Deploying Trading Desk — Oracle Cloud Always-Free (₹0/month)

A step-by-step guide to run the app on a free, always-on cloud server with
its own login, HTTPS, and **hard guarantees that Oracle never charges you**.

> Time: ~30–45 min the first time. You need: an email, a phone number, and a
> credit/debit card (for identity verification — **not charged** in Always-Free mode).

---

## 0. The cost guarantee (read this first)

Oracle asks for a card at signup. You will **not** be charged as long as you stay
on Always-Free resources. The protections, in order of importance:

1. **Stay in "Always Free" account mode.** A fresh account is in a free trial
   with $300 credits; when the trial ends the account becomes **Always-Free-only**
   *unless you click "Upgrade to Paid"*. **Never click Upgrade.** In Always-Free
   mode Oracle **cannot bill you** — over-limit actions are simply refused.
2. **Only ever create Always-Free-eligible resources** (this guide uses exactly one):
   - 1× VM.Standard.A1.Flex — up to **4 OCPU + 24 GB RAM free** (we use 2+12, room to spare)
   - Boot volume ≤ 200 GB (we use ~50 GB)
   - These are marked **"Always Free"** in the console — if a shape isn't labelled that, don't pick it.
3. **Set a $1 budget alert anyway** (Step 7) — belt and suspenders: email if spend ever exceeds $1.
4. **The app self-monitors** — Settings → System shows disk/RAM/load; a daily
   Telegram health ping (if configured) tells you it's alive and within limits.

---

## 1. Create the Oracle account

1. Go to **oracle.com/cloud/free** → "Start for free".
2. **Home region: choose "India South (Hyderabad)" or "India West (Mumbai)".**
   ⚠ This is permanent and can't be changed — an Indian region is what makes
   NSE data fetch reliably.
3. Verify email → phone → card (identity only). Finish signup.

---

## 2. Create the free VM

1. Console → hamburger menu → **Compute → Instances → Create Instance**.
2. Name: `trading-desk`.
3. **Image & shape → Change shape → Ampere → VM.Standard.A1.Flex** (labelled
   *Always Free eligible*). Set **OCPUs = 2, Memory = 12 GB**.
4. Image: **Canonical Ubuntu 22.04**.
5. **Networking:** create a new VCN with default settings. Ensure
   "Assign a public IPv4 address" is on.
6. **SSH keys:** "Generate a key pair for me" → **download the private key**
   (`ssh-key-*.key`) — keep it safe.
7. Create. Wait ~1 min for it to reach **Running**. Note the **Public IP**.

### Open the web ports
Networking → your VCN → its default **Security List** → **Add Ingress Rules**:
| Source CIDR | Protocol | Dest Port |
|---|---|---|
| `0.0.0.0/0` | TCP | `80` |
| `0.0.0.0/0` | TCP | `443` |

---

## 3. (Recommended) A free hostname for HTTPS

HTTPS needs a domain. **DuckDNS** gives one free:
1. **duckdns.org** → sign in → create a subdomain, e.g. `mytradingdesk`.
2. Set its IP to your VM's Public IP → you now have `mytradingdesk.duckdns.org`.

(Skip this to test over plain HTTP on the raw IP first — set `APP_DOMAIN=:80`.)

---

## 4. Connect and install Docker

```bash
chmod 600 ssh-key-*.key
ssh -i ssh-key-*.key ubuntu@YOUR_PUBLIC_IP

# On the VM:
sudo apt update && sudo apt install -y docker.io docker-compose-plugin git
sudo usermod -aG docker $USER && newgrp docker

# Ubuntu's default firewall blocks 80/443 — open them:
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

---

## 5. Get the code and configure

```bash
git clone https://github.com/shrishti2410/stock-portfolio-assistant1.git
cd stock-portfolio-assistant1
git checkout claude/stoic-mclean      # until merged to main

cp .env.deploy.example .env
nano .env
```

Fill in `.env`:
- `APP_DOMAIN` → `mytradingdesk.duckdns.org` (or `:80` for the IP-only test)
- `APP_SECRET_KEY` → run `openssl rand -hex 32` and paste the output
- `APP_ADMIN_USER` / `APP_ADMIN_PASSWORD` → your login
- LLM / Telegram keys → optional, add anytime later
- **Leave all `ZERODHA_*` blank** — you and your friend each connect Zerodha
  from the UI after logging in.

---

## 6. Launch

```bash
docker compose up -d --build      # first build ~5–8 min on ARM
docker compose ps                 # both services "running"/"healthy"
docker compose logs -f app        # watch startup; Ctrl-C to stop watching
```

Open **https://mytradingdesk.duckdns.org** (HTTPS cert issues automatically on
first load; give it ~30s). Log in with your admin credentials.

### Add your friend
Settings → **Users** → Add user (their own username + password). They log in,
go to Settings → **Broker Connection**, and enter *their* Zerodha details —
stored encrypted, visible only to their login. They never see your portfolio.

---

## 7. The $1 budget alert (2 min, do it once)

Console → **Billing & Cost Management → Budgets → Create Budget**:
- Target: your compartment (root is fine)
- Amount: **$1**, alert at **100%** → your email.

If this ever fires, something non-free was created — but in Always-Free mode it
can't actually bill; the alert is just a tripwire.

---

## 8. Day-to-day

```bash
# Update to the latest code
cd ~/stock-portfolio-assistant1 && git pull && docker compose up -d --build

# Logs / restart / stop
docker compose logs -f app
docker compose restart app
docker compose down            # stop (data persists in the named volume)
```

**Backups:** everything lives in the `app-data` Docker volume (SQLite DB).
Back it up with:
```bash
docker run --rm -v stock-portfolio-assistant1_app-data:/d -v $PWD:/b alpine \
  tar czf /b/tradingdesk-backup-$(date +%F).tgz -C /d .
```

---

## Health & limits at a glance

- **In-app:** Settings → System — live disk %, RAM %, load average, DB size.
- **Oracle console:** Compute → Instance → Metrics — CPU/network graphs.
- **Free-tier headroom:** we allocate 2 OCPU / 12 GB of the 4 / 24 free — the app
  idles at a few hundred MB, so you're never near the ceiling.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Site won't load | Ingress rules (Step 2) + `iptables` (Step 4) both done? `docker compose ps` healthy? |
| HTTPS cert error | DuckDNS IP must equal the VM IP; wait 60s; check `docker compose logs caddy`. |
| NSE data empty | Confirm the VM is in an **India** region (Step 1). |
| "Out of host capacity" on A1 | Oracle Mumbai A1 is popular — retry the Create step a few times over a day, or try the other India region. |
| Forgot admin password | `docker compose exec app python -c "import asyncio; from auth.service import change_password; asyncio.run(change_password(1,'newpass'))"` |
