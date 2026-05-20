# PubSync Standalone Deployment

These commands are intended to run on your Ubuntu/Linux server, not on your local macOS development machine.

PubSync is deployed as an independent Docker Compose stack:

- `pubsync-db`: PostgreSQL
- `pubsync-backend`: FastAPI backend
- `pubsync-nginx`: standalone nginx serving the Vue frontend and proxying API requests

Production routes:

- Frontend: `http://your-domain.com/`
- API: `http://your-domain.com/api/`
- API docs: `http://your-domain.com/api/docs`

For HTTPS, put this stack behind your server-level TLS reverse proxy, CDN, or a separate certificate-managed nginx/Caddy entrypoint.

## First Deploy

On the server:

```bash
cd /home/ubuntu
git clone git@github.com:LyneDefense/PubSync.git
cd PubSync/pubsync-deployment
./deploy.sh init
```

Edit `.env`:

```env
DOMAIN=pubsync.example.com
NGINX_HTTP_PORT=80
FRONTEND_BASE_PATH=/
DB_NAME=pubsync
DB_USER=pubsync
DB_PASSWORD=change_me_to_a_strong_password
PIP_INDEX_URL=https://mirrors.cloud.tencent.com/pypi/simple
PIP_TRUSTED_HOST=mirrors.cloud.tencent.com
NPM_REGISTRY=https://registry.npmmirror.com
WECHAT_APP_ID=wx...
WECHAT_APP_SECRET=...
CORS_ORIGINS=https://pubsync.example.com
```

Start the stack:

```bash
./deploy.sh update
```

If the Docker build is stopped during `pip install`, it will not damage the project or database. The incomplete image layer is discarded, and the next build resumes from the last completed cached layer. The pip step itself may run again, but the Dockerfile uses a BuildKit pip cache so already downloaded packages can usually be reused.

Then visit:

```text
http://pubsync.example.com/
http://pubsync.example.com/api/docs
```

## If Port 80 Is Already Used

Only one process can listen on host port `80`. If another service already owns it, set PubSync to an internal port:

```env
NGINX_HTTP_PORT=8081
```

Then run:

```bash
./deploy.sh update
```

Point your server-level reverse proxy at:

```text
http://127.0.0.1:8081
```

## WeChat IP Whitelist

After deployment, add the server public outbound IPv4 to:

```text
微信公众平台 -> 设置与开发 -> 基本配置 -> IP 白名单
```

Check the server IP:

```bash
curl -4 ifconfig.me
```

## Common Commands

```bash
./deploy.sh update
./deploy.sh update-backend
./deploy.sh update-frontend
./deploy.sh logs backend
./deploy.sh status
./deploy.sh db-backup
```
