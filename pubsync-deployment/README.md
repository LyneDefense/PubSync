# PubSync Deployment With Host Nginx

These commands are intended to run on your Ubuntu/Linux server, not on your local macOS development machine.

PubSync is deployed as:

- `pubsync-db`: PostgreSQL in Docker
- `pubsync-backend`: FastAPI backend in Docker, exposed only on `127.0.0.1`
- Host nginx: serves the Vue frontend from `frontend/dist` and proxies `/api/` to the backend

Production routes:

- Frontend: `https://enceladus.online/`
- API: `https://enceladus.online/api/`
- API docs: `https://enceladus.online/api/docs`

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
DOMAIN=enceladus.online
BACKEND_HOST_PORT=18000
FRONTEND_BASE_PATH=/
DB_NAME=pubsync
DB_USER=pubsync
DB_PASSWORD=change_me_to_a_strong_password
PIP_INDEX_URL=https://mirrors.cloud.tencent.com/pypi/simple
PIP_TRUSTED_HOST=mirrors.cloud.tencent.com
NPM_REGISTRY=https://registry.npmmirror.com
WECHAT_APP_ID=wx...
WECHAT_APP_SECRET=...
CORS_ORIGINS=https://enceladus.online,http://enceladus.online
```

Start the Docker services and build the frontend:

```bash
./deploy.sh update
```

This starts only PostgreSQL and the backend in Docker. It does not start a Docker nginx container.

## Configure Host Nginx

Create a host nginx site:

```bash
sudo nano /etc/nginx/sites-available/pubsync
```

Use this config:

```nginx
server {
    listen 80;
    server_name enceladus.online www.enceladus.online;

    root /home/ubuntu/PubSync/frontend/dist;
    index index.html;

    location = /api {
        return 301 /api/;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:18000/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

Enable and reload:

```bash
sudo ln -s /etc/nginx/sites-available/pubsync /etc/nginx/sites-enabled/pubsync
sudo nginx -t
sudo systemctl reload nginx
```

If another enabled nginx config already handles `enceladus.online`, edit that existing config instead of enabling a duplicate server block.

## HTTPS

If certbot is installed:

```bash
sudo certbot --nginx -d enceladus.online -d www.enceladus.online
```

Then test:

```bash
curl https://enceladus.online/api/health
```

Expected:

```json
{"status":"ok"}
```

## If Docker Build Is Interrupted

If the Docker build is stopped during `pip install`, it will not damage the project or database. The incomplete image layer is discarded, and the next build resumes from the last completed cached layer. The pip step itself may run again, but the Dockerfile uses a BuildKit pip cache so already downloaded packages can usually be reused.

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
