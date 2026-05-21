import base64
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

from app.config import Settings


DEFAULT_NEWS_SOURCE_URLS = [
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://venturebeat.com/category/ai/feed/",
    "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "https://hnrss.org/newest?q=AI",
    "https://hnrss.org/newest?q=OpenAI",
]


class AIServiceError(RuntimeError):
    pass


def is_ai_enabled(settings: Settings) -> bool:
    provider = settings.llm_provider.lower()
    if provider == "openai":
        return bool(settings.openai_api_key)
    if provider == "minimax":
        return bool(settings.minimax_api_key)
    return False


def discover_ai_news(settings: Settings) -> list[dict[str, Any]]:
    candidates = fetch_news_candidates(settings)
    if not candidates:
        raise AIServiceError("没有从新闻源抓取到候选新闻，请检查 NEWS_SOURCE_URLS")

    prompt = f"""
你是一个严谨的 AI 行业新闻编辑。请从候选新闻中筛选最近 24-72 小时内最重要的 AI 资讯。

要求：
- 只能使用候选新闻里提供的事实、标题、来源、链接和发布时间。
- 不要编造候选集中不存在的新闻。
- 排除低质量转载、重复新闻、广告稿和无法判断主题的内容。
- 返回 8-12 条；如果候选不足，可少于 8 条。
- 每条必须保留真实 URL，不能使用 example.com。

候选新闻：
{json.dumps(candidates, ensure_ascii=False, indent=2)}

输出 JSON，格式为：
{{
  "items": [
    {{
      "title": "中文标题",
      "source": "来源名称",
      "url": "https://...",
      "published_at": "ISO 8601 时间；未知可为空字符串",
      "summary": "2-3 句中文摘要，包含事实和影响",
      "category": "模型发布/研究进展/企业应用/开源项目/基础设施/开发者工具/产品更新/政策监管",
      "importance_score": 0-100,
      "key_facts": ["事实1", "事实2", "事实3"],
      "image_prompt": "如果需要配图，用于生成科技媒体风格概念图的英文提示词"
    }}
  ]
}}
"""
    data = create_json_response(settings=settings, prompt=prompt)
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
- 如果安全新闻不足，请增加 fallback_prompts，主题应覆盖整篇文章的共同主线，仍然只能是抽象科技信息图。

新闻：
{json.dumps(news_items, ensure_ascii=False, indent=2)}

输出 JSON：
{{
  "items": [
    {{
      "index": 0,
      "should_generate": true,
      "risk_reason": "为什么安全或为什么不安全",
      "prompt": "英文生图提示词"
    }}
  ],
  "fallback_prompts": ["英文兜底提示词"]
}}
"""
    data = create_json_response(settings=settings, prompt=prompt)
    items = data.get("items")
    if not isinstance(items, list):
        data["items"] = []
    fallbacks = data.get("fallback_prompts")
    if not isinstance(fallbacks, list):
        data["fallback_prompts"] = []
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


def fetch_news_candidates(settings: Settings) -> list[dict[str, Any]]:
    urls = parse_source_urls(settings.news_source_urls) or DEFAULT_NEWS_SOURCE_URLS
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max(24, settings.news_lookback_hours))
    candidates: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    with httpx.Client(timeout=20, follow_redirects=True) as client:
        for url in urls:
            try:
                response = client.get(url)
                response.raise_for_status()
            except httpx.HTTPError:
                continue
            for item in parse_feed(response.text, source_url=url):
                item_url = str(item.get("url", "")).strip()
                if not item_url or item_url in seen_urls:
                    continue
                published_at = parse_datetime(item.get("published_at"))
                if published_at and published_at < cutoff:
                    continue
                seen_urls.add(item_url)
                candidates.append(item)
                if len(candidates) >= settings.max_news_candidates:
                    return candidates
    return candidates


def parse_feed(xml_text: str, source_url: str) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    items: list[dict[str, Any]] = []
    for node in root.findall(".//item"):
        title = text_of(node, "title")
        url = text_of(node, "link")
        published = text_of(node, "pubDate") or text_of(node, "published")
        summary = text_of(node, "description")
        if title and url:
            items.append(build_candidate(title, url, published, summary, source_url))

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    for node in root.findall(".//atom:entry", ns):
        title = text_of(node, "atom:title", ns)
        url = ""
        for link in node.findall("atom:link", ns):
            href = link.attrib.get("href")
            if href:
                url = href
                break
        published = text_of(node, "atom:published", ns) or text_of(node, "atom:updated", ns)
        summary = text_of(node, "atom:summary", ns)
        if title and url:
            items.append(build_candidate(title, url, published, summary, source_url))
    return items


def build_candidate(title: str, url: str, published: str, summary: str, source_url: str) -> dict[str, Any]:
    return {
        "title": clean_text(title)[:500],
        "source": source_name_from_url(source_url),
        "url": url.strip(),
        "published_at": normalize_datetime_string(published),
        "summary": clean_text(strip_html(summary))[:1000],
    }


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


def parse_source_urls(value: str) -> list[str]:
    return [url.strip() for url in value.split(",") if url.strip()]


def text_of(node: ET.Element, path: str, ns: dict[str, str] | None = None) -> str:
    child = node.find(path, ns or {})
    if child is None or child.text is None:
        return ""
    return child.text.strip()


def normalize_datetime_string(value: str) -> str:
    parsed = parse_datetime(value)
    return parsed.isoformat() if parsed else ""


def parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def strip_html(value: str) -> str:
    return re.sub(r"<[^>]+>", " ", value)


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def source_name_from_url(url: str) -> str:
    match = re.search(r"https?://(?:www\.)?([^/]+)", url)
    return match.group(1) if match else url


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower()).strip("-")
    return slug[:48] or "image"
