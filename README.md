# PubSync

PubSync is an AI news-to-WeChat draft workflow.

The current version is intentionally small but has real front-end/back-end separation, a Vue front end, and a real PostgreSQL data model.

## Scope

- Fetch today's AI news candidates.
- Select 5-10 important items.
- Generate a WeChat-style article draft.
- Use a configurable LLM provider to rank recent news candidates, rewrite and structure the article, and generate missing visuals when configured.
- Edit title, intro, cover image, and HTML.
- Send to a WeChat official account draft.
- Store news, articles, and settings in PostgreSQL.

The WeChat integration calls the official account API to get `access_token`, upload the cover image as permanent material, and create a draft.

## Run Locally

Start PostgreSQL:

```bash
docker compose up -d postgres
```

The compose file maps the project database to local port `55432` to avoid conflicts with any system PostgreSQL already listening on `5432`.

Create and activate a Python environment:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../pubsync-deployment/.env.example .env
uvicorn app.main:app --reload
```

Run the Vue front end:

```bash
cd frontend
npm install
npm run dev
```

Then visit:

- Front end: http://localhost:5173
- API docs: http://localhost:8000/docs

## Architecture

- `backend/`: FastAPI, SQLAlchemy, APScheduler, PostgreSQL.
- `frontend/`: Vue 3 + Vite app.
- `docker-compose.yml`: local PostgreSQL.
- `pubsync-deployment/`: standalone production deployment scripts.

## Production Deploy

PubSync is designed to run as an independent deployment:

- Front end: `https://enceladus.online/PubSync/`
- API: `https://enceladus.online/PubSync/api/`

The production setup uses Docker for PostgreSQL, the FastAPI backend, and the frontend nginx service. The host nginx handles public HTTPS and routes `/PubSync/` to the frontend service and `/PubSync/api/` to the backend service.

Run the deployment commands on your Ubuntu server. Your local macOS machine is only for development.

On the Ubuntu server:

```bash
cd pubsync-deployment
./deploy.sh init
```

Edit `pubsync-deployment/.env`, then run:

```bash
./deploy.sh update
```

See `pubsync-deployment/README.md` for host nginx deployment details.

## Next Integrations

- Add richer source management and article review controls.
- Add LLM-based ranking and article generation.
- Add richer WeChat draft status handling and media cleanup.
- Add auth before exposing this outside local development.
