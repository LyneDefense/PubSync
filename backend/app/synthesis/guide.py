from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class TaskGuide:
    """任务「指南」（feedforward control）：把提示词与产出规范集中成可复用对象。

    build_prompt(context)：构造 user 提示词（本次可变数据；不含纠错反馈，反馈由循环用 with_feedback 追加）。
    build_system(context)：构造业务级 system（角色 + 硬边界 + 输出契约，稳定可缓存、与抓取数据分层抗注入）。
        可选；不给则 system=None，退回 ai_service 的通用系统句（旧行为）。
    normalize(data, context)：对模型返回做确定性补全/清洗（可选）。
    """

    name: str
    build_prompt: Callable[[Any], str]
    build_system: Callable[[Any], str] | None = None
    normalize: Callable[[dict[str, Any], Any], dict[str, Any]] | None = None


REVISION_HEADER = "上一版输出存在以下问题，请在保持合法 JSON、字段不变的前提下逐条修正后重新输出完整结果："


def with_feedback(base_prompt: str, corrective_feedback: str) -> str:
    """把纠错反馈追加到基础提示词后面（修订轮使用）。"""
    if not corrective_feedback.strip():
        return base_prompt
    return f"{base_prompt}\n\n{REVISION_HEADER}\n{corrective_feedback.strip()}"
