from __future__ import annotations

import json
from typing import Any

from app.account_audit.agent.context import AuditContext
from app.config import Settings
from app.services.ai_service import create_json_response
from app.synthesis import Critic


def make_audit_critic(settings: Settings, model: str | None) -> Critic:
    """推理型评审:挑出对比结论里空泛、不贴内容、不可执行的地方。"""

    def critic(result: dict[str, Any], ctx: AuditContext) -> str:
        prompt = f"""你是账号诊断的资深审稿人。下面是一份「用户内容 vs 对标博主」的对比结论。
请挑出最多 5 条最该改进的问题(空泛无据、没贴用户实际内容、差距说了等于没说、动作不可执行等),每条给出具体怎么改。

只输出 JSON:{{"feedback": "一段中文纠错指令,分条列出问题与改法"}}

对标博主方法论摘要:{ctx.skill_markdown[:3000]}
对比结论:{json.dumps(result, ensure_ascii=False, default=str)[:5000]}
"""
        data = create_json_response(settings, prompt, model=model)
        feedback = data.get("feedback")
        return str(feedback).strip() if isinstance(feedback, str) else ""

    return critic
