import base64
import json
import logging
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

from app.config import Settings
from app.cost.context import record_image_usage, record_text_usage


logger = logging.getLogger(__name__)


class AIServiceError(RuntimeError):
    pass


def is_ai_enabled(settings: Settings) -> bool:
    provider = settings.llm_provider.lower()
    if provider == "openai":
        return bool(settings.openai_api_key)
    if provider == "minimax":
        return bool(settings.minimax_api_key)
    if provider in ("claude", "anthropic"):
        return bool(settings.anthropic_api_key)
    if provider in ("glm", "zhipu", "bigmodel"):
        return bool(settings.glm_api_key)
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
    elif provider in ("glm", "zhipu", "bigmodel"):
        image_bytes, extension = generate_glm_image(settings, prompt)
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


# 通用 JSON 约束:所有 provider 共用。传入业务 system 时,它会叠加在业务规则之后。
_JSON_RULE = (
    "所有输出必须是合法 JSON。"
    "不要输出 Markdown 代码块、解释文字、推理过程、<think> 标签或 JSON 之外的任何字符。"
)


def _compose_system(system: str | None, default_persona: str) -> str:
    """组装最终 system 消息。

    - system 为空 → 沿用原通用系统提示(default_persona + JSON 规则),旧行为完全不变。
    - 传入业务 system → 业务角色/规则在前 + JSON 规则在后(不再套用通用 persona)。
    """
    if system and system.strip():
        return f"{system.strip()}\n\n{_JSON_RULE}"
    return f"{default_persona}{_JSON_RULE}"


def create_json_response(
    settings: Settings,
    prompt: str,
    model: str | None = None,
    *,
    system: str | None = None,
    timeout: int | None = None,
) -> dict[str, Any]:
    """system(可选):业务级系统提示(角色/规则/输出契约)。不传则沿用旧通用系统提示,行为不变。

    timeout(秒):None → 默认 180;分类型短任务可传更短值,卡住快速失败而非干等。
    """
    provider = settings.llm_provider.lower()
    if provider == "minimax":
        text = minimax_text(settings, prompt, model=model, system=system, timeout=timeout)
    elif provider == "openai":
        text = openai_text(settings, prompt, model=model, system=system, timeout=timeout)
    elif provider in ("claude", "anthropic"):
        text = anthropic_text(settings, prompt, model=model, system=system, timeout=timeout)
    elif provider in ("glm", "zhipu", "bigmodel"):
        text = glm_text(settings, prompt, model=model, system=system, timeout=timeout)
    else:
        raise AIServiceError(f"不支持的 LLM_PROVIDER: {settings.llm_provider}")

    try:
        parsed = parse_json_object_text(text)
    except json.JSONDecodeError as exc:
        logger.warning("AI 首次返回不是合法 JSON，开始尝试修复：错误=%s，片段=%s", exc, text[:240])
        normalized_text = normalize_unescaped_json_quotes(text)
        if normalized_text != text:
            try:
                parsed = parse_json_object_text(normalized_text)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                return parsed
        repaired_text = repair_json_response(settings, text)
        try:
            parsed = parse_json_object_text(repaired_text)
        except json.JSONDecodeError as repaired_exc:
            normalized_repaired_text = normalize_unescaped_json_quotes(repaired_text)
            try:
                parsed = parse_json_object_text(normalized_repaired_text)
            except json.JSONDecodeError:
                raise AIServiceError(f"AI 返回不是合法 JSON：{text[:500]}") from repaired_exc
    if not isinstance(parsed, dict):
        raise AIServiceError("AI 返回 JSON 不是对象")
    return parsed


def openai_text(settings: Settings, prompt: str, model: str | None = None, *, system: str | None = None, timeout: int | None = None) -> str:
    payload: dict[str, Any] = {
        "model": model or settings.openai_text_model,
        "input": prompt,
        "text": {"format": {"type": "json_object"}},
    }
    if system and system.strip():
        # Responses API 用 instructions 承载系统级指令(system=None 时保持原样,不引入变化)
        payload["instructions"] = _compose_system(system, "")
    data = openai_post(settings=settings, path="/responses", payload=payload, timeout=timeout or 180)
    record_text_usage("openai", payload["model"], data)
    return extract_openai_response_text(data)


def minimax_text(settings: Settings, prompt: str, model: str | None = None, *, system: str | None = None, timeout: int | None = None) -> str:
    if not settings.minimax_api_key:
        raise AIServiceError("未配置 MINIMAX_API_KEY")

    model = model or settings.minimax_text_model
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "name": "PubSync",
                "content": _compose_system(system, "你是严谨的 AI 新闻编辑。"),
            },
            {"role": "user", "name": "User", "content": prompt},
        ],
        "temperature": 0.2,
        "reasoning_split": True,
    }
    if supports_minimax_response_format(model):
        payload["response_format"] = {"type": "json_object"}
    data = minimax_post(settings, "/chat/completions", payload, timeout=timeout or 180)
    record_text_usage("minimax", model, data)
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            return str(message["content"])
    reply = data.get("reply")
    if isinstance(reply, str):
        return reply
    raise AIServiceError(f"MiniMax 文本响应中没有可解析内容：{data}")


def anthropic_text(settings: Settings, prompt: str, model: str | None = None, *, system: str | None = None, timeout: int | None = None) -> str:
    if not settings.anthropic_api_key:
        raise AIServiceError("未配置 ANTHROPIC_API_KEY")
    model = model or settings.anthropic_text_model
    payload = {
        "model": model,
        "max_tokens": int(settings.anthropic_max_tokens),
        "system": _compose_system(system, "你是严谨的助手。"),
        "messages": [{"role": "user", "content": prompt}],
    }
    data = anthropic_post(settings, "/v1/messages", payload, timeout=timeout or 180)
    record_text_usage("anthropic", model, data)
    content = data.get("content")
    if isinstance(content, list):
        texts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
        joined = "".join(texts).strip()
        if joined:
            return joined
    raise AIServiceError(f"Anthropic 文本响应中没有可解析内容：{data}")


def glm_text(settings: Settings, prompt: str, model: str | None = None, *, system: str | None = None, timeout: int | None = None) -> str:
    """智谱 GLM 文本(OpenAI 兼容 /chat/completions)。"""
    if not settings.glm_api_key:
        raise AIServiceError("未配置 GLM_API_KEY")
    model = model or settings.glm_text_model
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": _compose_system(system, "你是严谨的助手。"),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    data = glm_post(settings, "/chat/completions", payload, timeout=timeout or 180)
    record_text_usage("glm", model, data)
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            return str(message["content"])
    raise AIServiceError(f"GLM 文本响应中没有可解析内容：{data}")


def glm_vision_chat(
    settings: Settings,
    *,
    image_parts: list[str],
    instruction: str,
    model: str | None = None,
    system: str | None = None,
    timeout: int | None = None,
) -> str:
    """智谱 GLM 视觉理解(OpenAI 兼容 /chat/completions,多模态 content)。

    image_parts 每项是图片公网 URL 或 data:image/...;base64,... 。返回模型文本回复(由调用方解析)。
    单请求图片数由调用方控制(GLM 上限 5 张)。用量走 record_text_usage 记账(与 glm_text 一致)。
    system 非空 → 作为独立 system 消息(自动附加 JSON 规则),契约与图片分层、抵御图内夹带的指令;
    为空则维持旧行为(仅一条 user 消息)。
    """
    if not settings.glm_api_key:
        raise AIServiceError("未配置 GLM_API_KEY")
    model = model or settings.vision_model
    content: list[dict[str, Any]] = [{"type": "text", "text": instruction}]
    for part in image_parts:
        content.append({"type": "image_url", "image_url": {"url": part}})
    messages: list[dict[str, Any]] = []
    if system and system.strip():
        messages.append({"role": "system", "content": _compose_system(system, "")})
    messages.append({"role": "user", "content": content})
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
    }
    data = glm_post(settings, "/chat/completions", payload, timeout=timeout or 180)
    record_text_usage("glm", model, data)
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            return str(message["content"])
    raise AIServiceError(f"GLM 视觉响应中没有可解析内容：{data}")


def supports_minimax_response_format(model: str) -> bool:
    return model.strip().lower() in {"minimax-text-01", "text-01"}


def repair_json_response(settings: Settings, raw_text: str) -> str:
    prompt = f"""
下面是一个大模型返回结果。它本应是合法 JSON，但可能混入了 <think>、解释文字、Markdown 或其他非 JSON 内容。

请只做格式修复：
- 只能返回一个合法 JSON 对象。
- 不要新增事实，不要改写字段含义。
- 不要输出 Markdown、解释文字、<think> 或 JSON 之外的任何字符。
- 如果原文里有多个 JSON 片段，选择最完整、字段最多、最符合任务结果的那个。

原始返回：
{raw_text[:12000]}
"""
    provider = settings.llm_provider.lower()
    if provider == "minimax":
        return minimax_text(settings, prompt)
    if provider == "openai":
        return openai_text(settings, prompt)
    if provider in ("claude", "anthropic"):
        return anthropic_text(settings, prompt)
    if provider in ("glm", "zhipu", "bigmodel"):
        return glm_text(settings, prompt)
    raise AIServiceError(f"不支持的 LLM_PROVIDER: {settings.llm_provider}")


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
    record_image_usage("openai", settings.openai_image_model, 1)
    return base64.b64decode(str(first["b64_json"])), "png"


def generate_glm_image(settings: Settings, prompt: str) -> tuple[bytes, str]:
    """智谱 CogView 文生图(OpenAI 兼容 /images/generations)。返回 (图片字节, 扩展名)。

    CogView 通常返回图片 URL(而非 base64),这里两种都兼容:有 b64_json 直接解码,否则下载 url。
    """
    data = glm_post(
        settings,
        "/images/generations",
        {"model": settings.glm_image_model, "prompt": prompt, "size": "1024x1024"},
        timeout=180,
    )
    images = data.get("data")
    if not isinstance(images, list) or not images or not isinstance(images[0], dict):
        raise AIServiceError(f"GLM 图片生成返回为空：{data}")
    first = images[0]
    if first.get("b64_json"):
        record_image_usage("glm", settings.glm_image_model, 1)
        return base64.b64decode(str(first["b64_json"])), "png"
    url = first.get("url")
    if isinstance(url, str) and url:
        with httpx.Client(timeout=120) as client:
            resp = client.get(url)
        if resp.status_code >= 400:
            raise AIServiceError(f"GLM 图片下载失败 HTTP {resp.status_code}")
        record_image_usage("glm", settings.glm_image_model, 1)
        return resp.content, "png"
    raise AIServiceError(f"GLM 图片生成返回缺少 url/b64_json：{data}")


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
    record_image_usage("minimax", settings.minimax_image_model, 1)
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


def anthropic_post(settings: Settings, path: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    if not settings.anthropic_api_key:
        raise AIServiceError("未配置 ANTHROPIC_API_KEY")
    with httpx.Client(timeout=timeout) as client:
        response = client.post(
            f"{settings.anthropic_base_url.rstrip('/')}{path}",
            headers={
                "x-api-key": settings.anthropic_api_key,
                "anthropic-version": settings.anthropic_version,
                "content-type": "application/json",
            },
            json=payload,
        )
    return parse_json_response(response, "Anthropic")


def glm_post(settings: Settings, path: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    if not settings.glm_api_key:
        raise AIServiceError("未配置 GLM_API_KEY")
    with httpx.Client(timeout=timeout) as client:
        response = client.post(
            f"{settings.glm_base_url.rstrip('/')}{path}",
            headers={
                "Authorization": f"Bearer {settings.glm_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
    return parse_json_response(response, "GLM")


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


def parse_json_object_text(text: str) -> dict[str, Any]:
    stripped = extract_json_object(text)
    decoder = json.JSONDecoder()
    for index, char in enumerate(stripped):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(stripped[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return json.loads(stripped)


def extract_json_object(text: str) -> str:
    stripped = remove_reasoning_text(text).strip()
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


def normalize_unescaped_json_quotes(text: str) -> str:
    try:
        source = extract_json_object(text)
    except Exception:
        source = text
    result: list[str] = []
    in_string = False
    escaped = False
    length = len(source)
    for index, char in enumerate(source):
        if not in_string:
            result.append(char)
            if char == '"':
                in_string = True
            continue
        if escaped:
            result.append(char)
            escaped = False
            continue
        if char == "\\":
            result.append(char)
            escaped = True
            continue
        if char == '"':
            next_index = index + 1
            while next_index < length and source[next_index].isspace():
                next_index += 1
            if next_index >= length or source[next_index] in {":", ",", "}", "]"}:
                result.append(char)
                in_string = False
            else:
                result.append('\\"')
            continue
        result.append(char)
    return "".join(result)


def remove_reasoning_text(text: str) -> str:
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"<think>.*", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
    return cleaned.strip()


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower()).strip("-")
    return slug[:48] or "image"
