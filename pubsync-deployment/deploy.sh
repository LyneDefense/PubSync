#!/bin/bash

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

DEPLOY_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$DEPLOY_DIR")"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

check_ubuntu_server() {
    if [ "$(uname -s)" != "Linux" ]; then
        echo -e "${YELLOW}提示: 当前不是 Linux。部署脚本设计为在 Ubuntu 服务器上执行。${NC}"
        echo "本地 macOS 只建议运行前端/后端开发命令，不建议执行部署命令。"
        exit 1
    fi
    if [ -f /etc/os-release ] && ! grep -qi "ubuntu" /etc/os-release; then
        echo -e "${YELLOW}提示: 当前 Linux 发行版不是 Ubuntu，脚本仍可能可用，但请确认 Docker、Node.js、npm 已安装。${NC}"
    fi
}

check_env() {
    if [ ! -f "$DEPLOY_DIR/.env" ]; then
        echo -e "${RED}错误: .env 文件不存在${NC}"
        echo "请先执行：cp .env.example .env，然后修改其中的服务器配置和微信配置。"
        exit 1
    fi
    set -a
    # shellcheck disable=SC1091
    source "$DEPLOY_DIR/.env"
    set +a
}

init() {
    check_ubuntu_server
    echo -e "${GREEN}初始化 PubSync 部署目录...${NC}"
    if [ ! -f "$DEPLOY_DIR/.env" ]; then
        cp "$DEPLOY_DIR/.env.example" "$DEPLOY_DIR/.env"
        echo -e "${YELLOW}已创建 .env，请先填写 DOMAIN、EYANGPET_DEPLOY_DIR、DB_PASSWORD、WECHAT_APP_ID、WECHAT_APP_SECRET${NC}"
    fi
    mkdir -p "$DEPLOY_DIR/backups"
    echo -e "${GREEN}初始化完成${NC}"
}

build_frontend() {
    check_ubuntu_server
    echo -e "${GREEN}构建 Vue 前端...${NC}"
    cd "$FRONTEND_DIR"
    npm install
    npm run build
    cd "$DEPLOY_DIR"
    echo -e "${GREEN}前端构建完成${NC}"
}

sync_frontend_to_nginx() {
    check_ubuntu_server
    check_env
    if [ -z "$EYANGPET_DEPLOY_DIR" ]; then
        echo -e "${RED}错误: 请在 .env 中设置 EYANGPET_DEPLOY_DIR${NC}"
        exit 1
    fi
    if [ ! -d "$EYANGPET_DEPLOY_DIR" ]; then
        echo -e "${RED}错误: EYANGPET_DEPLOY_DIR 不存在: $EYANGPET_DEPLOY_DIR${NC}"
        exit 1
    fi
    if [ ! -d "$FRONTEND_DIR/dist" ]; then
        echo -e "${YELLOW}前端 dist 不存在，先构建前端${NC}"
        build_frontend
    fi

    local target="$EYANGPET_DEPLOY_DIR/nginx/pubsync-dist"
    mkdir -p "$target"
    rm -rf "$target"/*
    cp -R "$FRONTEND_DIR/dist"/. "$target"/
    echo -e "${GREEN}已同步前端到 $target${NC}"
}

patch_eyangpet_compose() {
    check_env
    local compose_file="$EYANGPET_DEPLOY_DIR/docker-compose.yml"
    if [ ! -f "$compose_file" ]; then
        echo -e "${RED}错误: 找不到 eyangpet docker-compose.yml: $compose_file${NC}"
        exit 1
    fi
    if grep -q "/usr/share/nginx/pubsync:ro" "$compose_file"; then
        echo -e "${YELLOW}eyangpet docker-compose.yml 已包含 PubSync 前端挂载，跳过${NC}"
        return
    fi

    local tmp_file
    tmp_file="$(mktemp)"
    awk '
        {
            print
            if ($0 ~ /\.\.\/eyangpet-frontend\/dist:\/usr\/share\/nginx\/html:ro/) {
                print "      - ./nginx/pubsync-dist:/usr/share/nginx/pubsync:ro"
            }
        }
    ' "$compose_file" > "$tmp_file"
    cp "$compose_file" "$compose_file.bak.$(date +%Y%m%d%H%M%S)"
    mv "$tmp_file" "$compose_file"
    echo -e "${GREEN}已给 eyangpet nginx 增加 PubSync 静态文件挂载${NC}"
}

patch_nginx_template() {
    local template_file="$1"
    local block_file="$DEPLOY_DIR/nginx/pubsync.locations.conf"

    if [ ! -f "$template_file" ]; then
        echo -e "${RED}错误: 找不到 nginx 模板: $template_file${NC}"
        exit 1
    fi
    if grep -q "PubSync managed block start" "$template_file"; then
        echo -e "${YELLOW}$template_file 已包含 PubSync nginx block，跳过${NC}"
        return
    fi

    local tmp_file
    tmp_file="$(mktemp)"
    awk -v block_file="$block_file" '
        { lines[NR] = $0 }
        END {
            last = 0
            for (i = NR; i >= 1; i--) {
                if (lines[i] ~ /^}$/) {
                    last = i
                    break
                }
            }
            for (i = 1; i <= NR; i++) {
                if (i == last) {
                    while ((getline line < block_file) > 0) {
                        print line
                    }
                    close(block_file)
                }
                print lines[i]
            }
        }
    ' "$template_file" > "$tmp_file"
    cp "$template_file" "$template_file.bak.$(date +%Y%m%d%H%M%S)"
    mv "$tmp_file" "$template_file"
    echo -e "${GREEN}已更新 nginx 模板: $template_file${NC}"
}

install_nginx() {
    check_ubuntu_server
    check_env
    if [ -z "$EYANGPET_DEPLOY_DIR" ]; then
        echo -e "${RED}错误: 请在 .env 中设置 EYANGPET_DEPLOY_DIR${NC}"
        exit 1
    fi

    patch_eyangpet_compose
    patch_nginx_template "$EYANGPET_DEPLOY_DIR/nginx/conf.d/default.conf.template"
    patch_nginx_template "$EYANGPET_DEPLOY_DIR/nginx/conf.d/default.conf.ssl.template"
    sync_frontend_to_nginx

    echo -e "${GREEN}PubSync nginx 配置已安装到 eyangpet 部署目录${NC}"
    echo -e "${YELLOW}下一步请在 eyangpet-deployment 里重新生成 nginx 配置并重启 nginx，例如：${NC}"
    echo "  cd $EYANGPET_DEPLOY_DIR"
    echo "  ./deploy.sh nginx-https"
    echo "  docker compose up -d nginx"
    echo "  docker compose exec nginx nginx -t"
    echo "  docker compose exec nginx nginx -s reload"
}

build_backend() {
    check_ubuntu_server
    check_env
    cd "$DEPLOY_DIR"
    echo -e "${GREEN}构建后端镜像...${NC}"
    docker compose build backend
}

start() {
    check_ubuntu_server
    check_env
    cd "$DEPLOY_DIR"
    echo -e "${GREEN}启动 PubSync 后端和数据库...${NC}"
    docker compose up -d
    docker compose ps
}

stop() {
    check_ubuntu_server
    cd "$DEPLOY_DIR"
    docker compose down
}

restart() {
    stop
    start
}

update() {
    check_env
    build_frontend
    sync_frontend_to_nginx
    build_backend
    start
    reload_shared_nginx
}

update_backend() {
    build_backend
    cd "$DEPLOY_DIR"
    docker compose up -d backend
}

update_frontend() {
    build_frontend
    sync_frontend_to_nginx
    reload_shared_nginx
}

reload_shared_nginx() {
    check_ubuntu_server
    check_env
    if [ -z "$EYANGPET_DEPLOY_DIR" ]; then
        echo -e "${RED}错误: 请在 .env 中设置 EYANGPET_DEPLOY_DIR${NC}"
        exit 1
    fi
    cd "$EYANGPET_DEPLOY_DIR"
    echo -e "${GREEN}检查并重载 eyangpet-nginx...${NC}"
    docker compose exec nginx nginx -t
    docker compose exec nginx nginx -s reload
}

logs() {
    cd "$DEPLOY_DIR"
    docker compose logs -f --tail=100 "$@"
}

status() {
    cd "$DEPLOY_DIR"
    echo -e "${BLUE}========== PubSync 服务状态 ==========${NC}"
    docker compose ps
    echo ""
    echo -e "${BLUE}========== PubSync 资源使用 ==========${NC}"
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" 2>/dev/null || true
}

db_backup() {
    check_ubuntu_server
    check_env
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
    install-nginx)
        install_nginx
        ;;
    build-frontend)
        build_frontend
        ;;
    build-backend)
        build_backend
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
        reload_shared_nginx
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
        echo "PubSync 部署脚本"
        echo ""
        echo "使用方法: ./deploy.sh [命令]"
        echo ""
        echo "首次部署:"
        echo "  init             创建 .env"
        echo "  install-nginx    给 eyangpet 共享 nginx 安装 /pubsync 路由和静态挂载"
        echo "  update           构建前端和后端，启动服务，重载共享 nginx"
        echo ""
        echo "日常更新:"
        echo "  update           更新全部"
        echo "  update-backend   只更新后端"
        echo "  update-frontend  只更新前端并重载 nginx"
        echo ""
        echo "服务管理:"
        echo "  start            启动 PubSync 后端和数据库"
        echo "  stop             停止 PubSync 后端和数据库"
        echo "  restart          重启 PubSync 后端和数据库"
        echo "  logs [服务名]    查看日志"
        echo "  status           查看状态"
        echo "  reload-nginx     重载 eyangpet 共享 nginx"
        echo ""
        echo "数据库:"
        echo "  db-backup        备份 PubSync 数据库"
        ;;
esac
