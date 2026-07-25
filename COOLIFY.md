# Deploying Trading Desk on DigitalOcean + Coolify

The easy path: one DigitalOcean Droplet running **Coolify** (a self-hosted,
Vercel-like dashboard). Deploy this app — and later all your other apps — from
git with automatic HTTPS. ~₹1,030/mo, cancel anytime.

---

## 1. Create the Droplet (2 minutes)

DigitalOcean → **Create → Droplets**:

| Field | Value |
|---|---|
| Region | **Bangalore (BLR1)** |
| Image | **Ubuntu 24.04 (LTS) x64** |
| Type | **Basic → Regular (SSD)** |
| Plan | **2 GB RAM / 1 vCPU (~$12/mo)** — the minimum Coolify needs |
| Authentication | SSH key (preferred) or a strong password |
| Hostname | `trading-desk` |

Expand **Advanced Options → Add Initialization scripts (user data)** and paste:

```yaml
#cloud-config
runcmd:
  - curl -fsSL https://cdn.coollabs.io/coolify/install.sh | bash
```

Click **Create**. Wait ~5 minutes for Coolify to install on first boot.

> Bills hourly (~$0.018/hr); **destroy the droplet anytime to stop charges**.

---

## 2. Open Coolify

Visit **`http://YOUR_DROPLET_IP:8000`** → create your Coolify admin account
(this is Coolify's own login, separate from the app's login).

If the page doesn't load after ~5 min, SSH in and run the installer manually:
```bash
ssh root@YOUR_DROPLET_IP
curl -fsSL https://cdn.coollabs.io/coolify/install.sh | bash
```

---

## 3. (Recommended) Free HTTPS domain

HTTPS needs a hostname. **duckdns.org** (free): create e.g. `mytradingdesk`,
point it at the Droplet IP → you get `mytradingdesk.duckdns.org`.

---

## 4. Deploy the app in Coolify

1. **Projects → + New → Project** → name it `trading-desk` → **+ New Resource**.
2. Choose **Public Repository** (or connect your GitHub account for private repos)
   and enter:
   - Repository: `https://github.com/shrishti2410/stock-portfolio-assistant1`
   - Branch: `claude/stoic-mclean`  *(or `main` once merged)*
3. Build Pack: **Docker Compose**. Compose file path: **`docker-compose.coolify.yml`**
   ⚠ Use this file, **not** `docker-compose.yml` — the Coolify one omits Caddy so
   it doesn't clash with Coolify's built-in proxy.
4. **Environment Variables** tab — add:

   | Key | Value |
   |---|---|
   | `APP_SECRET_KEY` | a 64-char random string — run `openssl rand -hex 32` |
   | `APP_ADMIN_USER` | your login username |
   | `APP_ADMIN_PASSWORD` | a strong password |
   | `APP_DOMAIN` | `mytradingdesk.duckdns.org` (or leave blank for IP-only) |

   Optional, add anytime: `ANTHROPIC_API_KEY`, `GROQ_API_KEY`, `TELEGRAM_BOT_TOKEN`,
   `ALPACA_API_KEY`/`ALPACA_API_SECRET`, `DHAN_CLIENT_ID`/`DHAN_ACCESS_TOKEN`.
   **Do not set `ZERODHA_*`** — each user connects their own Zerodha in the UI.
5. **Domains** — set the app service's domain to your DuckDNS hostname mapped to
   **port 8000**. Coolify issues the Let's Encrypt certificate automatically.
6. Click **Deploy**. First build ~5–8 min (it builds the React app + Python image).

Open **`https://mytradingdesk.duckdns.org`** → log in with the admin credentials
you set. Add your friend at **Settings → Users**; each connects their own Zerodha
at **Settings → Broker Connection**.

---

## 5. Updates & your other apps

- **Update this app:** push to the branch → Coolify redeploys (enable "auto-deploy
  on push", or click Redeploy).
- **Data persists** in the `app-data` volume across redeploys. Coolify → Storages
  can schedule off-server backups to any S3 bucket.
- **Add another app:** + New Resource in the same project, point at its repo. Each
  app gets its own subdomain + auto-HTTPS. A 2 GB box handles ~4–6 small apps;
  resize the Droplet to 8 GB (two clicks + reboot) when you need more.

---

## Not using Coolify?

`docker-compose.yml` (with Caddy) + `DEPLOY.md` is the plain-VPS path — `docker
compose up -d --build` on any Ubuntu box. Coolify is just the easier front-end;
the app is identical either way, so you're never locked in.
