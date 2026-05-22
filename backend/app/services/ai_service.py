import base64
import json
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

from app.config import Settings


class AIServiceError(RuntimeError):
    pass


def is_ai_enabled(settings: Settings) -> bool:
    provider = settings.llm_provider.lower()
    if provider == "openai":
        return bool(settings.openai_api_key)
    if provider == "minimax":
        return bool(settings.minimax_api_key)
    return False


def generate_wechat_article(settings: Settings, news_items: list[dict[str, Any]]) -> dict[str, Any]:
    prompt = f"""
你是微信公众号 AI 科技早报主编。请基于下面的新闻事实生成一篇中文公众号草稿。

要求：
- 不能改变新闻事实，不能编造来源、融资金额、发布日期、产品能力或人物观点。
- 可以做编辑化提炼、背景解释、影响分析，但事实和判断要区分。
- 标题必须输出“AI科技早报 | xxx”格式，xxx 是你生成的标题内容；不要使用其他前缀。
- 文章要适合公众号阅读，结构清晰，段落不要太长，避免堆叠多个大标题。
- 开头先写 1 段 80-140 字导语，说明今天最重要的主线。
- 正文每条新闻都要写得充分一些，不能只复述摘要；每条至少包含“发生了什么”“为什么重要”“编辑观察”三个层次。
- 每条新闻建议 220-360 个中文字，既要有事实，也要有背景解释和影响分析。
- 每条新闻都保留来源链接。
- 正文 HTML 只能使用 section/h2/h3/p/ul/li/blockquote/a/img/strong 标签，不要使用 script、iframe、table、外链 CSS、class 或 style。
- 排版结构要适合微信公众号：每条新闻使用一个 section；section 内顺序为 h2、可选图片、正文段落、blockquote 编辑观察、来源链接 p。
- h2 使用“01｜新闻标题”这种编号格式，不要重复写过长标题。
- 不要在正文中展示发布时间、分类、重要性分数、内部评分、候选池排序等后台筛选信息。
- 正文段落保持短段落，每段 80-140 个中文字；不要把三四个观点塞进一个超长段落。
- 每条新闻用 2-3 个正文 p，加 1 个 blockquote“编辑观察”，形成可扫读节奏。
- 来源链接放在最后一行，格式为“来源：<a href='真实URL'>来源名称</a>”，不要单独展示长 URL。
- 如果新闻有 image_url，则最多插入一张图片，图片前后都要有正文，不要连续堆图。
- 输出 JSON。

新闻事实：
{json.dumps(news_items, ensure_ascii=False, indent=2)}

输出格式：
{{
  "title": "不超过 64 字的公众号标题",
  "intro": "不超过 120 字的摘要导语",
  "cover_prompt": "英文封面图提示词，只能是抽象科技视觉、信息图或概念插画；禁止真实人物肖像、虚构人物肖像、真实 logo、仿新闻现场照片",
  "content_html": "公众号正文 HTML"
}}
"""
    data = create_json_response(settings=settings, prompt=prompt)
    for key in ("title", "intro", "content_html"):
        if not data.get(key):
            raise AIServiceError(f"AI 文章生成返回缺少 {key}")
    return data


def plan_article_images(settings: Settings, news_items: list[dict[str, Any]], min_images: int, max_images: int) -> dict[str, Any]:
    prompt = f"""
你是 AI 新闻公众号的视觉编辑。请基于新闻事实规划正文配图。

目标：
- 除封面外，正文最好有 {min_images}-{max_images} 张配图。
- 不是每条新闻都需要配图。只给最适合抽象视觉表达的新闻配图。
- 如果新闻涉及具体人物、CEO、创始人、政治人物、明星、个人肖像、真实公司 logo、产品界面截图、灾难或真实现场，不要为该条新闻生成图片。
- 配图只能是抽象科技视觉、信息图、概念插画或数据/芯片/网络/云/机器人等非人物隐喻。
- prompt 必须动态贴合新闻内容，不能使用固定模板；但必须包含安全约束：no human, no face, no celebrity, no real person, no logo, no brand mark, no photorealistic news scene, no UI screenshot, no text.
- 请给每条新闻都返回 risk_level 和 fallback_prompt。即使 should_generate=false，也要给出一个在必须补足最低配图数量时可用的安全抽象 fallback_prompt。
- fallback_prompt 必须由新闻内容动态生成，不能套固定模板，且同样包含上面的安全约束。
- risk_level 只能是 low、medium、high。涉及真实人物肖像、logo、产品界面或真实现场的新闻应标为 high，但 fallback_prompt 仍可改写成抽象信息图方向。

新闻：
{json.dumps(news_items, ensure_ascii=False, indent=2)}

输出 JSON：
{{
  "items": [
    {{
      "index": 0,
      "should_generate": true,
      "risk_level": "low",
      "risk_reason": "为什么安全或为什么不安全",
      "prompt": "英文生图提示词",
      "fallback_prompt": "英文安全抽象兜底提示词"
    }}
  ]
}}
"""
    data = create_json_response(settings=settings, prompt=prompt)
    items = data.get("items")
    if not isinstance(items, list):
        data["items"] = []
    return data


def generate_image(settings: Settings, prompt: str, filename_prefix: str) -> str | None:
    if not prompt.strip():
        return None

    provider = settings.image_provider.lower()
    if provider == "minimax":
        image_bytes, extension = generate_minimax_image(settings, prompt)
    elif provider == "openai":
        image_bytes, extension = generate_openai_image(settings, prompt)
    else:
        raise AIServiceError(f"不支持的 IMAGE_PROVIDER: {settings.image_provider}")

    static_root = Path(settings.static_dir)
    target_dir = static_root / "generated"
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{safe_slug(filename_prefix)}-{uuid4().hex[:10]}.{extension}"
    target_path = target_dir / filename
    target_path.write_bytes(image_bytes)

    public_path = f"/static/generated/{filename}"
    if settings.public_api_base_url:
        return f"{settings.public_api_base_url.rstrip('/')}{public_path}"
    return public_path


def create_json_response(settings: Settings, prompt: str) -> dict[str, Any]:
    provider = settings.llm_provider.lower()
    if provider == "minimax":
        text = minimax_text(settings, prompt)
    elif provider == "openai":
        text = openai_text(settings, prompt)
    else:
        raise AIServiceError(f"不支持的 LLM_PROVIDER: {settings.llm_provider}")

    try:
        parsed = json.loads(extract_json_object(text))
    except json.JSONDecodeError as exc:
        raise AIServiceError(f"AI 返回不是合法 JSON：{text[:500]}") from exc
    if not isinstance(parsed, dict):
        raise AIServiceError("AI 返回 JSON 不是对象")
    return parsed


def openai_text(settings: Settings, prompt: str) -> str:
    payload: dict[str, Any] = {
        "model": settings.openai_text_model,
        "input": prompt,
        "text": {"format": {"type": "json_object"}},
    }
    data = openai_post(settings=settings, path="/responses", payload=payload, timeout=180)
    return extract_openai_response_text(data)


def minimax_text(settings: Settings, prompt: str) -> str:
    if not settings.minimax_api_key:
        raise AIServiceError("未配置 MINIMAX_API_KEY")

    payload = {
        "model": settings.minimax_text_model,
        "messages": [
            {
                "role": "system",
                "name": "PubSync",
                "content": "你是严谨的 AI 新闻编辑。所有输出必须是合法 JSON，不要输出 Markdown 代码块。",
            },
            {"role": "user", "name": "User", "content": prompt},
        ],
        "temperature": 0.2,
    }
    data = minimax_post(settings, "/chat/completions", payload, timeout=180)
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            return str(message["content"])
    reply = data.get("reply")
    if isinstance(reply, str):
        return reply
    raise AIServiceError(f"MiniMax 文本响应中没有可解析内容：{data}")


def generate_openai_image(settings: Settings, prompt: str) -> tuple[bytes, str]:
    data = openai_post(
        settings=settings,
        path="/images/generations",
        payload={
            "model": settings.openai_image_model,
            "prompt": prompt,
            "size": "1024x1024",
            "quality": "medium",
            "n": 1,
        },
        timeout=120,
    )
    images = data.get("data")
    if not isinstance(images, list) or not images:
        raise AIServiceError("OpenAI 图片生成返回为空")
    first = images[0]
    if not isinstance(first, dict) or not first.get("b64_json"):
        raise AIServiceError("OpenAI 图片生成返回缺少 b64_json")
    return base64.b64decode(str(first["b64_json"])), "png"


def generate_minimax_image(settings: Settings, prompt: str) -> tuple[bytes, str]:
    if not settings.minimax_api_key:
        raise AIServiceError("未配置 MINIMAX_API_KEY")

    data = minimax_post(
        settings,
        "/image_generation",
        {
            "model": settings.minimax_image_model,
            "prompt": prompt,
            "aspect_ratio": "16:9",
            "response_format": "base64",
        },
        timeout=180,
    )
    image = first_base64_image(data)
    if not image:
        raise AIServiceError(f"MiniMax 图片生成返回缺少 base64 图片：{data}")
    return base64.b64decode(image), "jpg"


def openai_post(settings: Settings, path: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    if not settings.openai_api_key:
        raise AIServiceError("未配置 OPENAI_API_KEY")

    with httpx.Client(timeout=timeout) as client:
        response = client.post(
            f"{settings.openai_base_url.rstrip('/')}{path}",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
    return parse_json_response(response, "OpenAI")


def minimax_post(settings: Settings, path: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    with httpx.Client(timeout=timeout) as client:
        response = client.post(
            f"{settings.minimax_base_url.rstrip('/')}{path}",
            headers={
                "Authorization": f"Bearer {settings.minimax_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
    return parse_json_response(response, "MiniMax")


def parse_json_response(response: httpx.Response, provider: str) -> dict[str, Any]:
    try:
        data = response.json()
    except ValueError as exc:
        raise AIServiceError(f"{provider} 返回非 JSON 响应，HTTP {response.status_code}") from exc

    if response.status_code >= 400:
        raise AIServiceError(f"{provider} 请求失败，HTTP {response.status_code}: {data}")
    if not isinstance(data, dict):
        raise AIServiceError(f"{provider} 返回格式不正确")
    base_resp = data.get("base_resp")
    if isinstance(base_resp, dict) and base_resp.get("status_code") not in (None, 0):
        raise AIServiceError(f"{provider} 请求失败：{base_resp}")
    return data


def extract_openai_response_text(data: dict[str, Any]) -> str:
    direct = data.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct

    parts: list[str] = []
    output = data.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for content_item in content:
                if not isinstance(content_item, dict):
                    continue
                text = content_item.get("text")
                if isinstance(text, str):
                    parts.append(text)
    text = "\n".join(parts).strip()
    if not text:
        raise AIServiceError("OpenAI 响应中没有可解析文本")
    return text


def first_base64_image(data: dict[str, Any]) -> str:
    for key in ("image_base64", "base64", "b64_json"):
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    images = data.get("data") or data.get("images")
    if isinstance(images, dict):
        for key in ("image_base64", "images", "data"):
            nested = images.get(key)
            if isinstance(nested, str) and nested:
                return nested
            if isinstance(nested, list) and nested:
                first = nested[0]
                if isinstance(first, str):
                    return first
                if isinstance(first, dict):
                    for image_key in ("image_base64", "base64", "b64_json"):
                        value = first.get(image_key)
                        if isinstance(value, str) and value:
                            return value
    if isinstance(images, list) and images:
        first = images[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            for key in ("image_base64", "base64", "b64_json"):
                value = first.get(key)
                if isinstance(value, str) and value:
                    return value
    return ""


def extract_json_object(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?", "", stripped).strip()
        stripped = re.sub(r"```$", "", stripped).strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        return stripped[start : end + 1]
    return stripped


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower()).strip("-")
    return slug[:48] or "image"
