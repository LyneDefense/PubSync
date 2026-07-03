"""博主档案(Dossier):物理信息(身份+笔记池)→ 分析信息(统计/轨迹/归因)。

设计见 docs/博主画像模块_全景设计.md 与 docs/博主档案页_流程设计.md。
- :mod:`.pool`       —— 笔记池:列表级行 upsert、增量/全量同步(物理层)
- :mod:`.stats`      —— 账号事实统计:从全量池算,含发布节奏/成长趋势(从蒸馏拆出)
- :mod:`.trajectory` —— 成长轨迹:内容表现时序、爆发点、阶段划分(纯函数)
- :mod:`.attribution`—— 爆文归因:LLM 生成"有据的假设"(按钮触发)
- :mod:`.service`    —— 编排:一键建档(五阶段)、档案聚合读、构建互斥

注意:此包不在 __init__ 里 re-export —— service 依赖 collection,而 collection 依赖本包的
pool;急切导入会构成循环。调用方直接 ``from app.blogger_dossier import pool`` / ``service``。
"""
