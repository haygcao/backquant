# BackQuant Quantitative Backtesting Platform

This repository includes a backend (Flask + RQAlpha) and a frontend (Vue 3), plus an integrated Research workspace (Jupyter Lab).
**Docker is the recommended deployment** so you can pull the image and run it directly with Flask, Jupyter, Nginx, and the built frontend.

## I. Docker Installation & Deployment

### Install Docker

```bash
sudo curl -fsSL https://get.docker.com | sh
```

### Start

```bash
cp .env.example .env
docker compose up --build
```

### RQAlpha & Daily Bundle Data

- The Docker image already includes RQAlpha (`rqalpha==6.1.2`).
- On first start, the RQAlpha daily data bundle is downloaded to `/data/rqalpha/bundle` (a persistent volume). This may take a few minutes.
- The daily bundle is updated monthly: on container start, a cron entry is created (`/etc/cron.d/rqalpha-bundle`, default is 03:00 on the 1st of each month).
- To change the schedule, set `RQALPHA_BUNDLE_CRON` (for example `0 4 1 * *`).
- To disable auto updates, set `RQALPHA_BUNDLE_CRON=off`.

### Access

- Frontend: `http://localhost:8080`

Note: Backend API and Jupyter are reverse-proxied under the same domain (`/api`, `/jupyter`), so you typically do not need to access their ports directly.

## II. Configuration

Backend configuration is mainly in `backtest/.env.wsgi`:

- `SECRET_KEY` JWT signing key, must be changed
- `LOCAL_AUTH_MOBILE` / `LOCAL_AUTH_PASSWORD` local login credentials
- `LOCAL_AUTH_PASSWORD_HASH` optional, bcrypt hash overrides plaintext password
- `RESEARCH_NOTEBOOK_*` Jupyter-related settings
- Note: Jupyter token can be empty (empty means token auth disabled; only recommended for LAN/local use).

Frontend supports two ways to configure API base:

- Build-time environment variable `VUE_APP_API_BASE`
- Runtime `frontend/public/config.js` (no rebuild needed)

## III. Others

### Local Development

#### Backend

```bash
cd backtest
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.wsgi.example .env.wsgi
python3 wsgi.py
```

Default port: `54321`.

#### Frontend

```bash
cd frontend
npm install
npm run serve
```

Default port: `8080`.

### Jupyter Examples

- Example Notebook: `docs/notebooks/example.ipynb`
- Details: `docs/jupyter.md`

### Nginx Reverse Proxy

See `docs/nginx.md` for production reference.

### API Docs

Backend API docs: `backtest/README.md`.

### License

Apache-2.0. See `LICENSE`.

### WeChat

Follow our WeChat public account: ETF量化老司机
