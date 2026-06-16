"""费用台账:在 TikHub / 大模型 调用的 chokepoint 记账,落到 cost_events,供后台汇总。

- ``pricing``  —— 内置单价表 + 后台覆盖合并;按 token / 按图折算金额。
- ``context``  —— contextvar 费用上下文 + cost_capture 包裹任务 + record_* 记账封装。
"""
