# 数据库迁移（Alembic）

Alembic 现在是数据库 schema 的**唯一权威来源**。`env.py` 以 ORM `Base.metadata`
为目标、从应用配置读取 `DATABASE_URL`，所以命令直接作用于当前配置的数据库。

## 启动即自动迁移

后端启动时（`app/main.py` 的 lifespan）会调用 `run_migrations()`，等价于
`alembic upgrade head`：

- 全新空库 → 跑 `0001_baseline`：基于模型建全部表 + 灌入默认种子数据。
- 已是最新 → 什么都不做（幂等）。

Worker（`app/worker.py`）**不**执行迁移，只消费任务；由单一后端负责迁移，避免并发竞争。

> `0001_baseline` 用 `Base.metadata.create_all` 在线建表，因此必须在线运行；
> 不支持离线 `alembic upgrade head --sql`。后续 autogenerate 出的迁移可正常离线生成。

## 常用命令（在 `backend/` 下，激活 venv 后）

```bash
alembic upgrade head        # 迁移到最新（容器内：docker compose exec backend alembic upgrade head）
alembic current             # 当前版本
alembic history             # 迁移历史
alembic downgrade -1        # 回退一步
```

改了 `app/models` 后生成新迁移：

```bash
alembic revision --autogenerate -m "描述本次改动"
alembic upgrade head
```

## 全量重建（清库 + 用 Alembic 重新建表）

> ⚠️ 会删除该库所有数据，仅在你确实想清空时执行。

```bash
# 1) 清空 schema（含 alembic_version），相当于全新空库
docker compose exec postgres psql -U <DB_USER> -d <DB_NAME> \
  -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

# 2) 用 Alembic 重新建表 + 灌种子（或直接重启 backend，启动时会自动跑）
docker compose exec backend alembic upgrade head
```
