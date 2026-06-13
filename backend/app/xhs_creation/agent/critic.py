from __future__ import annotations

import json
from typing import Any

from app.config import Settings
from app.services.ai_service import create_json_response
from app.synthesis import Critic
from app.xhs_creation.agent.context import CreationContext
from app.xhs_creation.agent.platforms import PLATFORM_SPECS


def make_creation_critic(settings: Settings, model: str | None) -> Critic:
    """推理型评审:对照 Skill 给创作稿挑刺,产出面向模型的纠错指令。"""

    def critic(result: dict[str, Any], ctx: CreationContext) -> str:
        platform_name = PLATFORM_SPECS[ctx.platform].name
        prompt = f"""你是{platform_name}资深创作顾问。下面是一份基于“对标博主方法论 Skill”生成的草稿。
请挑出最多 5 条最该改进的问题(每条给出具体怎么改):
- 是否冒充了原博主或复制了其原文/经历
- 是否只是套了 Skill 的方法、却产出了用户自己的、围绕主题的内容
- 标题是否够吸引、正文是否够实用、结尾互动是否得体
- 是否有夸大或编造的事实

只输出 JSON:{{"feedback": "一段中文纠错指令,分条列出问题与改法"}}

Skill 摘要:{ctx.skill.skill_markdown[:4000]}
草稿:{json.dumps(result, ensure_ascii=False, default=str)[:5000]}
"""
        data = create_json_response(settings, prompt, model=model)
        feedback = data.get("feedback")
        return str(feedback).strip() if isinstance(feedback, str) else ""

    return critic
