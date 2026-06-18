# CLAUDE.md

PubSync 项目的工作约定。Claude Code 在本仓库工作时须遵守以下规则。

## 写完代码后的固定流程

每次完成代码改动后，按顺序执行：

### 1. 提交并推送
- 提交后必须推送到远端（`git push`）。改动只提交不推送视为未完成。
- **commit message 不要带 co-author trailer**（不要 `Co-Authored-By:` 行）。

### 2. 部署最新代码到服务器
服务器：`ssh ubuntu@129.204.142.220`

```bash
# 1) 拉取最新代码
cd /home/ubuntu/PubSync && git pull --ff-only

# 2) 部署
cd /home/ubuntu/PubSync/pubsync-deployment && ./deploy.sh update
```

### 3. 查看后端日志确认部署成功
```bash
cd /home/ubuntu/PubSync/pubsync-deployment && ./deploy.sh logs backend
```

## 部署参考

`./deploy.sh` 子命令（在 `/home/ubuntu/PubSync/pubsync-deployment` 下执行）：
- `update` —— 构建前后端，启动 postgres/redis/backend/worker/frontend（全量更新）
- `update-backend` —— 只更新后端和 worker
- `update-frontend` —— 只更新前端容器
- `logs [service]` —— 查看日志，例如 `./deploy.sh logs backend`

## 问题清单维护（`问题清单.md`）

项目根目录的 `问题清单.md` 是用户维护的待办问题清单,规则:

- 用户说「**记住这个问题**」→ 把用户描述的问题**追加**到 `问题清单.md`,自动加上**递增序号**(接着已有最大序号 +1)和**记录时间**(用 `date` 取实际日期时间),状态默认「待解决」。只追加,不改动已有条目。
- 用户说「**解决问题清单的第 N 个**」(会给序号)→ 着手解决;**确实解决后**把第 N 条状态改为「✅ 已解决」并补上解决时间与一句话说明。没解决就不要标。
- 序号只增不复用;已解决条目保留存档,不删除。

## 站点 / 环境
- 线上：https://enceladus.online/PubSync/
- 服务器代码目录：`/home/ubuntu/PubSync`
- 部署目录：`/home/ubuntu/PubSync/pubsync-deployment`
- 绝不改动服务器 `.env` 里的密钥值；改 `.env` 前先备份。
