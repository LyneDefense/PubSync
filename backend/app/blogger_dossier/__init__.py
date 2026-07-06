"""博主档案(Dossier):物理信息(身份+笔记池)→ 分析信息(统计/轨迹/受众需求)。

设计见 docs/成长趋势与受众需求_优化方案设计.md。
- :mod:`.pool`       —— 笔记池:列表级行 upsert、增量/全量同步(物理层)
- :mod:`.stats`      —— 账号事实统计:从全量池算,含发布节奏/成长趋势(从蒸馏拆出)
- :mod:`.trajectory` —— 成长趋势:内容表现时序、爆发点、分位带、表现分布(纯函数)
- :mod:`.audience`   —— 受众需求:从读者评论归纳"读者最常问"(LLM,按钮触发)
- :mod:`.service`    —— 编排:一键建档(五阶段)、档案聚合读、构建互斥

注意:此包不在 __init__ 里 re-export —— service 依赖 collection,而 collection 依赖本包的
pool;急切导入会构成循环。调用方直接 ``from app.blogger_dossier import pool`` / ``service``。
"""
