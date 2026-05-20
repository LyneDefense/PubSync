#!/bin/bash

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

DEPLOY_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$DEPLOY_DIR")"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

check_linux_server() {
    if [ "$(uname -s)" != "Linux" ]; then
        echo -e "${YELLOW}提示: 当前不是 Linux。部署脚本设计为在 Ubuntu/Linux 服务器上执行。${NC}"
        echo "本地 macOS 只建议运行开发命令，不建议执行部署命令。"
        exit 1
    fi
}

check_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo -e "${RED}错误: 未找到命令 $1${NC}"
        exit 1
    fi
}

check_docker_compose() {
    check_command docker
    if ! docker compose version >/dev/null 2>&1; then
        echo -e "${RED}错误: 当前 Docker 不支持 'docker compose' 命令${NC}"
        exit 1
    fi
}

check_env() {
    if [ ! -f "$DEPLOY_DIR/.env" ]; then
        echo -e "${RED}错误: .env 文件不存在${NC}"
        echo "请先执行：./deploy.sh init，然后修改 pubsync-deployment/.env。"
        exit 1
    fi
    set -a
    # shellcheck disable=SC1091
    source "$DEPLOY_DIR/.env"
    set +a
}

init() {
    check_linux_server
    echo -e "${GREEN}初始化 PubSync 独立部署目录...${NC}"
    if [ ! -f "$DEPLOY_DIR/.env" ]; then
        cp "$DEPLOY_DIR/.env.example" "$DEPLOY_DIR/.env"
        echo -e "${YELLOW}已创建 .env，请填写 DOMAIN、DB_PASSWORD、WECHAT_APP_ID、WECHAT_APP_SECRET${NC}"
    fi
    mkdir -p "$DEPLOY_DIR/backups"
    echo -e "${GREEN}初始化完成${NC}"
}

build_frontend() {
    check_linux_server
    check_env
    check_command npm

    echo -e "${GREEN}构建 Vue 前端...${NC}"
    cd "$FRONTEND_DIR"
    export VITE_BASE_PATH="${FRONTEND_BASE_PATH:-/}"
    npm install
    npm run build
    cd "$DEPLOY_DIR"
    echo -e "${GREEN}前端构建完成${NC}"
}

start() {
    check_linux_server
    check_env
    check_docker_compose

    if [ ! -d "$FRONTEND_DIR/dist" ]; then
        echo -e "${YELLOW}前端 dist 不存在，先构建前端${NC}"
        build_frontend
    fi

    cd "$DEPLOY_DIR"
    echo -e "${GREEN}启动 PubSync 独立服务...${NC}"
    docker compose up -d
    docker compose ps
}

stop() {
    check_linux_server
    check_docker_compose
    cd "$DEPLOY_DIR"
    docker compose down
}

restart() {
    stop
    start
}

update() {
    check_linux_server
    check_env
    check_docker_compose
    build_frontend
    cd "$DEPLOY_DIR"
    echo -e "${GREEN}构建并启动 PubSync 服务...${NC}"
    docker compose up -d --build
    docker compose ps
}

update_backend() {
    check_linux_server
    check_env
    check_docker_compose
    cd "$DEPLOY_DIR"
    docker compose up -d --build backend
    docker compose up -d nginx
}

update_frontend() {
    build_frontend
    reload_nginx
}

reload_nginx() {
    check_linux_server
    check_env
    check_docker_compose
    cd "$DEPLOY_DIR"
    echo -e "${GREEN}检查并重载 PubSync nginx...${NC}"
    docker compose exec nginx nginx -t
    docker compose exec nginx nginx -s reload
}

logs() {
    check_docker_compose
    cd "$DEPLOY_DIR"
    docker compose logs -f --tail=100 "$@"
}

status() {
    check_docker_compose
    cd "$DEPLOY_DIR"
    echo -e "${BLUE}========== PubSync 服务状态 ==========${NC}"
    docker compose ps
    echo ""
    echo -e "${BLUE}========== PubSync 资源使用 ==========${NC}"
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" 2>/dev/null || true
}

db_backup() {
    check_linux_server
    check_env
    check_docker_compose
    cd "$DEPLOY_DIR"
    mkdir -p backups
    local backup_file="backups/pubsync_$(date +%Y%m%d_%H%M%S).sql"
    docker exec pubsync-db pg_dump -U "${DB_USER:-pubsync}" "${DB_NAME:-pubsync}" > "$backup_file"
    echo -e "${GREEN}数据库备份完成: $backup_file${NC}"
}

case "$1" in
    init)
        init
        ;;
    build-frontend)
        build_frontend
        ;;
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    update)
        update
        ;;
    update-backend)
        update_backend
        ;;
    update-frontend)
        update_frontend
        ;;
    reload-nginx)
        reload_nginx
        ;;
    logs)
        shift
        logs "$@"
        ;;
    status)
        status
        ;;
    db-backup)
        db_backup
        ;;
    *)
        echo "PubSync 独立部署脚本"
        echo ""
        echo "使用方法: ./deploy.sh [命令]"
        echo ""
        echo "首次部署:"
        echo "  init             创建 .env 和 backups 目录"
        echo "  update           构建前端和后端，启动 postgres/backend/nginx"
        echo ""
        echo "日常更新:"
        echo "  update           更新全部"
        echo "  update-backend   只更新后端"
        echo "  update-frontend  只更新前端并重载 nginx"
        echo ""
        echo "服务管理:"
        echo "  start            启动 PubSync 服务"
        echo "  stop             停止 PubSync 服务"
        echo "  restart          重启 PubSync 服务"
        echo "  reload-nginx     检查并重载 PubSync nginx"
        echo "  logs [service]   查看日志，例如: ./deploy.sh logs backend"
        echo "  status           查看容器状态和资源占用"
        echo "  db-backup        备份 PostgreSQL 数据库"
        exit 1
        ;;
esac
