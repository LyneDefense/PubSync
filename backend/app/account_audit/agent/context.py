from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AuditContext:
    """一次账号诊断的上下文。

    kind=benchmark(对标诊断):我的账号真实内容 vs 对标账号真实内容,逐维度对比。
    kind=self(诊断我的):只看我的账号内容,产出优势/短板/增长动作。
    内容均来自已采集的 posts(由 service 用 build_account_content 拼好)。
    """

    platform: str
    platform_name: str
    kind: str  # benchmark | self
    my_name: str
    my_content: str
    benchmark_name: str = ""
    benchmark_content: str = ""
