import base64
import json
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

from app.config import Settings


OPENAI_API_BASE = "https://api.openai.com/v1"


class AIServiceError(RuntimeError):
    pass


def is_ai_enabled(settings: Settings) -> bool:
    return bool(settings.openai_api_key)


def discover_ai_news(settings: Settings) -> list[dict[str, Any]]:
    prompt = """
你是一个严谨的 AI 行业新闻编辑。请联网检索最近 24-48 小时的重要 AI 资讯，优先使用官方博客、研究机构、公司公告、权威科技媒体。

返回 8-12 条候选新闻。每条必须有真实来源 URL。不要使用 example.com。不要编造发布时间、来源或链接。

筛选标准：
- 模型发布、产品更新、研究进展、开源项目、基础设施、政策监管、企业应用。
- 排除纯营销、低质量转载和无法核验来源的内容。

输出 JSON，格式为：
{
  "items": [
    {
      "title": "中文标题",
      "source": "来源名称",
      "url": "https://...",
      "published_at": "ISO 8601 时间；未知可为空字符串",
      "summary": "2-3 句中文摘要，包含事实和影响",
      "category": "模型发布/研究进展/企业应用/开源项目/基础设施/开发者工具/产品更新/政策监管",
      "importance_score": 0-100,
      "key_facts": ["事实1", "事实2", "事实3"],
      "image_prompt": "如果需要配图，用于生成科技媒体风格概念图的英文提示词"
    }
  ]
}
"""
    data = create_json_response(
        settings=settings,
        prompt=prompt,
        use_web_search=True,
    )
    items = data.get("items", [])
    if not isinstance(items, list):
        raise AIServiceError("AI 新闻发现返回格式不正确：items 不是列表")
    return [item for item in items if isinstance(item, dict)]


def generate_wechat_article(settings: Settings, news_items: list[dict[str, Any]]) -> dict[str, Any]:
    prompt = f"""
你是微信公众号 AI 科技早报主编。请基于下面的新闻事实生成一篇中文公众号草稿。

要求：
- 不能改变新闻事实，不能编造来源、融资金额、发布日期、产品能力或人物观点。
- 可以做编辑化提炼、背景解释、影响分析，但事实和判断要区分。
- 文章要适合公众号阅读，结构清晰，段落不要太长。
- 每条新闻都保留来源链接。
- 正文 HTML 可以使用 h2/h3/p/ul/li/blockquote/a/img 标签，不要使用 script、iframe、外链 CSS。
- 如果新闻有 image_url，则在对应小节插入一张图片。
- 输出 JSON。

新闻事实：
{json.dumps(news_items, ensure_ascii=False, indent=2)}

输出格式：
{{
  "title": "不超过 64 字的公众号标题",
  "intro": "不超过 120 字的摘要导语",
  "cover_prompt": "英文封面图提示词，科技媒体风格，不含真实人物肖像和真实 logo",
  "content_html": "公众号正文 HTML"
}}
"""
    data = create_json_response(settings=settings, prompt=prompt, use_web_search=False)
    for key in ("title", "intro", "content_html"):
        if not data.get(key):
            raise AIServiceError(f"AI 文章生成返回缺少 {key}")
    return data


def generate_image(settings: Settings, prompt: str, filename_prefix: str) -> str | None:
    if not prompt.strip():
        return None

    response = openai_post(
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
    data = response.get("data")
    if not isinstance(data, list) or not data:
        raise AIServiceError("图片生成返回为空")

    first = data[0]
    if not isinstance(first, dict) or not first.get("b64_json"):
        raise AIServiceError("图片生成返回缺少 b64_json")

    image_bytes = base64.b64decode(str(first["b64_json"]))
    static_root = Path(settings.static_dir)
    target_dir = static_root / "generated"
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{safe_slug(filename_prefix)}-{uuid4().hex[:10]}.png"
    target_path = target_dir / filename
    target_path.write_bytes(image_bytes)

    public_path = f"/static/generated/{filename}"
    if settings.public_api_base_url:
        return f"{settings.public_api_base_url.rstrip('/')}{public_path}"
    return public_path


def create_json_response(settings: Settings, prompt: str, use_web_search: bool) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": settings.openai_text_model,
        "input": prompt,
        "text": {"format": {"type": "json_object"}},
    }
    if use_web_search:
        payload["tools"] = [{"type": "web_search_preview"}]

    data = openai_post(settings=settings, path="/responses", payload=payload, timeout=180)
    text = extract_response_text(data)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AIServiceError(f"AI 返回不是合法 JSON：{text[:500]}") from exc
    if not isinstance(parsed, dict):
        raise AIServiceError("AI 返回 JSON 不是对象")
    return parsed


def openai_post(settings: Settings, path: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    if not settings.openai_api_key:
        raise AIServiceError("未配置 OPENAI_API_KEY")

    with httpx.Client(timeout=timeout) as client:
        response = client.post(
            f"{OPENAI_API_BASE}{path}",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
    try:
        data = response.json()
    except ValueError as exc:
        raise AIServiceError(f"OpenAI 返回非 JSON 响应，HTTP {response.status_code}") from exc

    if response.status_code >= 400:
        raise AIServiceError(f"OpenAI 请求失败，HTTP {response.status_code}: {data}")
    if not isinstance(data, dict):
        raise AIServiceError("OpenAI 返回格式不正确")
    return data


def extract_response_text(data: dict[str, Any]) -> str:
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


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower()).strip("-")
    return slug[:48] or "image"
