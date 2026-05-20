# PubSync

PubSync is an MVP for an AI news-to-WeChat draft workflow.

The current version is intentionally small but has real front-end/back-end separation, a Vue front end, and a real PostgreSQL data model.

## MVP Scope

- Fetch today's AI news candidates.
- Select 5-10 important items.
- Generate a WeChat-style article draft.
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
cp .env.example .env
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
- `frontend/`: Vue 3 + Vite app deployed under `/pubsync/`.
- `docker-compose.yml`: local PostgreSQL.
- `pubsync-deployment/`: production deployment scripts for sharing the existing eyangpet nginx and domain.

## Production Deploy

PubSync is designed to share the same nginx and domain as `eyangpet`:

- Front end: `https://your-domain.com/pubsync/`
- API: `https://your-domain.com/pubsync/api/`

Run the deployment commands on your Ubuntu server. Your local macOS machine is only for development.

On the Ubuntu server:

```bash
cd pubsync-deployment
./deploy.sh init
```

Edit `pubsync-deployment/.env`, then run:

```bash
./deploy.sh install-nginx
./deploy.sh update
```

See `pubsync-deployment/README.md` for the shared nginx details.

## Next Integrations

- Replace mock news with RSS/news API ingestion.
- Add LLM-based ranking and article generation.
- Add richer WeChat draft status handling and media cleanup.
- Add auth before exposing this outside local development.
