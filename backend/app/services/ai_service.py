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


def decide_article_image(
    settings: Settings,
    news_item: dict[str, Any],
    forced: bool = False,
    image_style: str = "抽象科技视觉、信息图、芯片、网络、云与模型架构",
) -> dict[str, Any]:
    mode_instruction = (
        "这次是强制补图：必须返回 should_generate=true，并给出一个安全、抽象、可生成的 prompt。"
        if forced
        else "请判断这条新闻是否适合配一张正文图。should_generate 只表示是否适合配抽象图，不表示是否包含人物或公司。"
    )
    prompt = f"""
你是公众号的视觉编辑。请基于单条新闻事实判断是否生成正文配图，并生成图片 prompt。

目标：
- {mode_instruction}
- 新闻里出现人物、CEO、创始人、公司、产品、真实场景，并不代表不能配图；只是生成 prompt 不能描绘真实人物、肖像、logo、产品截图或新闻现场。
- 配图视觉方向：{image_style}。
- 配图只能是抽象视觉、信息图、概念插画或非人物隐喻。
- prompt 必须动态贴合新闻内容，但要把具体人物、公司 logo、真实产品界面、真实现场改写成抽象隐喻；不要直接写人物姓名、公司 logo、产品截图或新闻现场。
- prompt 必须包含安全约束：no human, no face, no celebrity, no real person, no logo, no brand mark, no photorealistic news scene, no UI screenshot, no text.
- 即使 should_generate=false，也要返回 fallback_prompt，供代码在最低配图数量不足时强制补图。
- fallback_prompt 必须由新闻内容动态生成，不能套固定模板，且同样包含上面的安全约束。

新闻：
{json.dumps(news_item, ensure_ascii=False, indent=2)}

输出 JSON：
{{
  "should_generate": true,
  "reason": "是否适合生成配图的简短原因",
  "prompt": "英文生图提示词",
  "fallback_prompt": "英文安全抽象兜底提示词"
}}
"""
    return create_json_response(settings=settings, prompt=prompt)


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
