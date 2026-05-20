# PubSync Deployment

PubSync is designed to share the existing `eyangpet-nginx` entrypoint and the same main domain.

These commands are intended to run on your Ubuntu server, not on your local macOS machine.

Production routes:

- Front end: `https://your-domain.com/pubsync/`
- API: `https://your-domain.com/pubsync/api/`

## First Deploy

On the Ubuntu server, clone or copy this PubSync project next to your existing `eyangpet` directory, for example:

```text
/home/ubuntu/eyangpet/
/home/ubuntu/PubSync/
```

```bash
cd pubsync-deployment
./deploy.sh init
```

Edit `.env`:

```env
DOMAIN=your-domain.com
EYANGPET_DEPLOY_DIR=/home/ubuntu/eyangpet/eyangpet-deployment
SHARED_NGINX_NETWORK=eyangpet-deployment_eyangpet-network
DB_PASSWORD=change_me
WECHAT_APP_ID=wx...
WECHAT_APP_SECRET=...
CORS_ORIGINS=https://your-domain.com
```

Install PubSync locations into the existing eyangpet nginx templates:

```bash
./deploy.sh install-nginx
```

Then regenerate and reload nginx from the eyangpet deployment directory:

```bash
cd /home/ubuntu/eyangpet/eyangpet-deployment
./deploy.sh nginx-https
docker compose up -d nginx
docker compose exec nginx nginx -t
docker compose exec nginx nginx -s reload
```

Start PubSync:

```bash
cd /home/ubuntu/PubSync/pubsync-deployment
./deploy.sh update
```

## WeChat IP Whitelist

After deployment, add the server public outbound IPv4 to:

`微信公众平台 -> 设置与开发 -> 基本配置 -> IP 白名单`

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
