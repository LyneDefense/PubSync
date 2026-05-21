# PubSync Deployment

These commands are intended to run on your Ubuntu/Linux server.

## Architecture

PubSync uses three Docker services and your existing host nginx:

```text
Browser
  -> host nginx :443
      /PubSync/      -> http://127.0.0.1:18082  pubsync-frontend
      /PubSync/api/  -> http://127.0.0.1:18000  pubsync-backend

Docker Compose
  pubsync-frontend  nginx serving the Vue build
  pubsync-backend   FastAPI
  pubsync-db        PostgreSQL
```

Production routes:

- Frontend: `https://enceladus.online/PubSync/`
- API: `https://enceladus.online/PubSync/api/`
- API docs: `https://enceladus.online/PubSync/api/docs`

## Environment

Edit `pubsync-deployment/.env`:

```env
DOMAIN=enceladus.online
BACKEND_HOST_PORT=18000
FRONTEND_HOST_PORT=18082
FRONTEND_BASE_PATH=/PubSync/
DB_NAME=pubsync
DB_USER=pubsync
DB_PASSWORD=change_me_to_a_strong_password
PIP_INDEX_URL=https://mirrors.cloud.tencent.com/pypi/simple
PIP_TRUSTED_HOST=mirrors.cloud.tencent.com
NPM_REGISTRY=https://registry.npmmirror.com
WECHAT_APP_ID=wx...
WECHAT_APP_SECRET=...
CORS_ORIGINS=https://enceladus.online,http://enceladus.online

# AI workflow. Leave OPENAI_API_KEY empty to keep using mock news and template articles.
OPENAI_API_KEY=sk-...
OPENAI_TEXT_MODEL=gpt-4.1
OPENAI_IMAGE_MODEL=gpt-image-1
GENERATE_ARTICLE_IMAGES=true
MAX_ARTICLE_IMAGES=3
PUBLIC_API_BASE_URL=https://enceladus.online/PubSync/api
AUTO_SEND_WECHAT_DRAFT=false
```

## Deploy

```bash
cd /home/ubuntu/PubSync
git pull
cd pubsync-deployment
./deploy.sh update
```

Check local service ports:

```bash
curl http://127.0.0.1:18082/
curl http://127.0.0.1:18000/health
```

## AI Workflow

When `OPENAI_API_KEY` is configured, the daily job does this:

```text
1. Use the text model with web search to discover recent AI news.
2. Store deduplicated candidates in PostgreSQL.
3. Select important items by model-assigned importance score.
4. Generate section images for the top selected items.
5. Generate a WeChat-style article with HTML formatting.
6. Generate a cover image.
7. Save the article locally.
8. If AUTO_SEND_WECHAT_DRAFT=true, upload the cover and create a WeChat draft.
```

If `OPENAI_API_KEY` is empty, PubSync keeps the current safe fallback:

```text
mock news -> template article -> manual WeChat draft sending
```

## Host Nginx

Your current domain config is:

```text
/etc/nginx/sites-enabled/nightly-pick
```

Add these locations inside the existing HTTPS `server { ... }` for `enceladus.online`, before any broader `location /` block:

```nginx
location = /PubSync {
    return 301 /PubSync/;
}

location = /PubSync/api {
    return 301 /PubSync/api/;
}

location /PubSync/api/ {
    proxy_pass http://127.0.0.1:18000/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 120s;
    proxy_send_timeout 120s;
}

location /PubSync/ {
    proxy_pass http://127.0.0.1:18082/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 120s;
    proxy_send_timeout 120s;
}
```

Reload host nginx:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

Test:

```bash
curl https://enceladus.online/PubSync/api/health
```

Expected:

```json
{"status":"ok"}
```

## Common Commands

```bash
./deploy.sh update
./deploy.sh update-backend
./deploy.sh update-frontend
./deploy.sh logs backend
./deploy.sh logs frontend
./deploy.sh status
./deploy.sh db-backup
```
