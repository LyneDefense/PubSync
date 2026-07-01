#!/usr/bin/env bash
# PubSync 数据清理:备份 → 清空「跑出来的」业务数据 → 保留系统/工作区配置 → 验证。
#
# 保留(不动):
#   系统核心   tenants users system_config
#   工作区配置 wechat_accounts content_profiles content_groups
#             layout_settings publishing_settings app_settings news_sources
# 清空(TRUNCATE ... RESTART IDENTITY CASCADE):
#   博主/笔记/快照/蒸馏/技能/采集/诊断/对标/发现/Skill训练/任务历史/文章/新闻条目/发布包/费用历史
#
# 已验证:保留表没有任何外键指向清空表,故 CASCADE 不会波及保留表。
#
# 用法(在部署目录 /home/ubuntu/PubSync/pubsync-deployment 下):
#   ./db_cleanup.sh          # 备份 + 交互确认后清空
#   ./db_cleanup.sh --yes    # 跳过确认(慎用)
# 回滚:
#   pg_restore 见脚本结尾提示(用生成的 dump)。
set -euo pipefail

DB_CONTAINER="pubsync-db"
STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP="${HOME}/pubsync_backup_${STAMP}.dump"

# 要清空的 19 张表(空格分隔)。
DELETE_TABLES=(
  blogger_profiles blogger_posts blogger_collection_runs blogger_collection_posts
  blogger_snapshots blogger_distillation_runs blogger_skills skill_training_runs
  benchmark_recommendation_runs benchmark_discovery_sessions account_audit_runs
  account_metric_snapshots operation_tasks operation_task_events articles
  article_news_items news_items xhs_publish_packages cost_events
)
JOINED="$(IFS=, ; echo "${DELETE_TABLES[*]}")"

psql_exec() { docker exec -i "$DB_CONTAINER" sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"'; }

echo "① 备份整库 → ${BACKUP}"
docker exec "$DB_CONTAINER" sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$BACKUP"
if [ ! -s "$BACKUP" ]; then echo "✗ 备份文件为空,已中止(未清理)。"; exit 1; fi
echo "   备份大小 $(du -h "$BACKUP" | cut -f1)"

if [ "${1:-}" != "--yes" ]; then
  echo
  echo "② 即将清空这些表(已备份,可回滚):"
  echo "   ${JOINED}"
  read -r -p "   确认请输入 yes: " ans
  [ "$ans" = "yes" ] || { echo "已取消(未清理)。"; exit 0; }
fi

echo "② 清空中…"
printf 'TRUNCATE TABLE %s RESTART IDENTITY CASCADE;\n' "$JOINED" | psql_exec

echo "③ 验证(清空表应为 0,保留表应 >0):"
printf '%s\n' \
  "SELECT 'blogger_profiles(清)' AS 表, count(*) FROM blogger_profiles" \
  "UNION ALL SELECT 'blogger_posts(清)', count(*) FROM blogger_posts" \
  "UNION ALL SELECT 'blogger_distillation_runs(清)', count(*) FROM blogger_distillation_runs" \
  "UNION ALL SELECT 'operation_tasks(清)', count(*) FROM operation_tasks" \
  "UNION ALL SELECT 'cost_events(清)', count(*) FROM cost_events" \
  "UNION ALL SELECT 'users(留)', count(*) FROM users" \
  "UNION ALL SELECT 'system_config(留)', count(*) FROM system_config" \
  "UNION ALL SELECT 'wechat_accounts(留)', count(*) FROM wechat_accounts" \
  "UNION ALL SELECT 'content_profiles(留)', count(*) FROM content_profiles;" | psql_exec

echo
echo "✅ 完成。回滚(如需):"
echo "   docker exec -i ${DB_CONTAINER} sh -c 'pg_restore -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" --clean --if-exists' < ${BACKUP}"
