"""模态对齐的 rollout 助手:用 skill 就一个选题生成一条内容,并取该模态的 gold 参照。

PoC 教训(问题清单 #10):生成与 gold 必须同模态,否则字符层面几乎不重叠、StyleDist 失真。
- 视频号(talking_video):生成「口播脚本」,gold = 真笔记 transcript(去时间戳)。
- 图文号(其余):生成「图文正文」,gold = 真笔记 标题+正文。
"""

from __future__ import annotations

from app.blogger_distillation.service.extract import strip_asr_timestamps
from app.config import Settings
from app.services.ai_service import create_json_response

Modality = str  # "talking_video" | "image_text"


def modality_of(content_subtype: str) -> Modality:
    """把笔记的 content_subtype 归到训练用的两类模态。"""
    return "talking_video" if str(content_subtype) == "talking_video" else "image_text"


def extract_topic(post) -> str:
    """取一条笔记的「选题」当 rollout 输入:优先标题,退回正文首句。"""
    title = (getattr(post, "title", "") or "").strip()
    if title:
        return title
    body = (getattr(post, "body_text", "") or getattr(post, "transcript_text", "") or "").strip()
    return body.split("\n", 1)[0][:40] if body else "(无选题)"


def gold_text(post, modality: Modality) -> str:
    """该笔记在目标模态下的 gold 风格参照文本。"""
    if modality == "talking_video":
        return strip_asr_timestamps(getattr(post, "transcript_text", "") or "")
    title = (getattr(post, "title", "") or "").strip()
    body = (getattr(post, "body_text", "") or "").strip()
    return f"{title}\n{body}".strip()


def build_generation_prompt(skill_markdown: str, topic: str, modality: Modality) -> str:
    form = (
        "一段口播脚本(你对着镜头会说的话,不要分镜、不要时间戳、不要旁白标注)"
        if modality == "talking_video"
        else "一条小红书图文笔记(含标题 + 正文)"
    )
    return (
        "你要严格按下面这份「博主打法 Skill」来创作,模仿该博主的风格(选题、标题、结构、语气、用词、情绪节奏)。\n"
        "=== 博主打法 Skill ===\n"
        f"{skill_markdown}\n"
        "=== Skill 结束 ===\n\n"
        f"请就选题「{topic}」,写{form}。\n"
        '只输出 JSON:{"content": "正文文本"}。content 里就是成稿,不要解释、不要 markdown 代码块。'
    )


def generate_with_skill(
    settings: Settings,
    skill_markdown: str,
    topic: str,
    modality: Modality,
    model: str | None = None,
) -> str:
    """用 skill + 选题生成一条对齐模态的内容文本。"""
    prompt = build_generation_prompt(skill_markdown, topic, modality)
    data = create_json_response(settings, prompt, model=model)
    content = data.get("content", "") if isinstance(data, dict) else ""
    return str(content).strip()
