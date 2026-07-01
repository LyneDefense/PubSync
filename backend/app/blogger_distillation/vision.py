"""视觉层:对图文笔记的封面/正文图跑 VLM(智谱 GLM),提取图内逐字文字 + 结构化视觉摘要。

与 ASR 层结构对称:ASR 取"视频语音"里的内容(transcript_text),视觉层取"图片"里的内容
(image_text + visual_digest)。默认直传图片公网 URL(GLM 服务器去拉);被防盗链挡住时下载转 base64 兜底。
"""

from __future__ import annotations

import base64
import json
import logging
import re
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from app.blogger_distillation.asr import download_file
from app.config import Settings
from app.services.ai_service import AIServiceError, glm_vision_chat


logger = logging.getLogger(__name__)

# GLM 视觉单请求最多 5 张图。
GLM_VISION_MAX_IMAGES = 5

ProgressCallback = Callable[[str], None]


class VisionError(RuntimeError):
    pass


@dataclass
class VisionResult:
    image_text: str = ""
    visual_digest: dict[str, Any] = field(default_factory=dict)
    image_count: int = 0
    provider: str = "glm_vision"


VISION_PROMPT = (
    "你是小红书内容分析助手。下面给你一篇笔记的若干张图片(第一张通常是封面)。请完成两件事，"
    "**只输出一个 JSON 对象**，不要 Markdown、不要解释、不要 <think>：\n"
    "1) image_text：把图片里出现的所有文字**逐字**转写(封面大字、卡片要点、清单、教程步骤、截图文字、"
    "数据、联系方式/要求等)，按图片顺序合并；看不清写 [模糊]；**绝不编造或补全**图里没有的文字。\n"
    "2) visual_digest：一个对象，字段为 cover_hook(封面主文案/钩子，没有则空串)、layout(版式，如 "
    "卡片/清单/对比/大字/截图/实拍/合集)、style(配色·字体·信息密度·风格调性，一句话)、"
    "info_points(图片传达的关键信息点数组，≤6 条)。\n"
    '严格输出：{"image_text":"...","visual_digest":{"cover_hook":"...","layout":"...","style":"...","info_points":["..."]}}'
)


class VisionProvider:
    def analyze_images(self, image_urls: list[str], *, source_id: str = "", on_progress: ProgressCallback | None = None) -> VisionResult:
        raise NotImplementedError


class DisabledVisionProvider(VisionProvider):
    def analyze_images(self, image_urls: list[str], *, source_id: str = "", on_progress: ProgressCallback | None = None) -> VisionResult:
        raise VisionError("视觉理解未开启")


class GlmVisionProvider(VisionProvider):
    """智谱 GLM 视觉:多图一次请求,同步返回。凭据复用文本/配图那套 GLM。"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        if not settings.glm_api_key:
            raise VisionError("未配置智谱 GLM API Key(GLM_API_KEY)，无法使用视觉理解")

    def analyze_images(self, image_urls: list[str], *, source_id: str = "", on_progress: ProgressCallback | None = None) -> VisionResult:
        urls = [u for u in image_urls if isinstance(u, str) and u.startswith("http")][:GLM_VISION_MAX_IMAGES]
        if not urls:
            raise VisionError("没有可解析的图片 URL")
        if on_progress is not None:
            on_progress(f"正在理解图片…共 {len(urls)} 张")
        # 先直传 URL(GLM 服务器去拉,省下载);失败且允许兜底则下载转 base64 再试一次。
        try:
            raw = glm_vision_chat(self.settings, image_parts=list(urls), instruction=VISION_PROMPT, model=self.settings.vision_model)
        except AIServiceError as exc:
            if not self.settings.vision_download_fallback:
                raise VisionError(f"GLM 视觉调用失败：{exc}") from exc
            logger.info("GLM 直传图 URL 失败,改下载转 base64 兜底：source=%s，原因=%s", source_id, exc)
            parts = self._download_as_base64(urls)
            if not parts:
                raise VisionError(f"GLM 视觉调用失败且图片下载兜底为空：{exc}") from exc
            raw = glm_vision_chat(self.settings, image_parts=parts, instruction=VISION_PROMPT, model=self.settings.vision_model)
        image_text, digest = parse_vision_response(raw)
        return VisionResult(image_text=image_text, visual_digest=digest, image_count=len(urls), provider="glm_vision")

    def _download_as_base64(self, urls: list[str]) -> list[str]:
        parts: list[str] = []
        max_bytes = 8 * (1 << 20)  # 单图硬上限 8MB,防个别大图撑爆请求
        with tempfile.TemporaryDirectory(prefix="pubsync-vision-") as tmp_dir:
            for index, url in enumerate(urls):
                target = Path(tmp_dir) / f"img_{index}"
                try:
                    download_file(url, target, max_seconds=60, max_bytes=max_bytes)
                    raw = target.read_bytes()
                except (httpx.HTTPError, OSError, RuntimeError) as exc:
                    logger.info("视觉兜底下载单图失败,跳过：url=%s，原因=%s", url[:80], exc)
                    continue
                mime = _guess_image_mime(raw)
                encoded = base64.b64encode(raw).decode("ascii")
                parts.append(f"data:{mime};base64,{encoded}")
        return parts


def build_vision_provider(settings: Settings) -> VisionProvider:
    if not settings.vision_enabled:
        return DisabledVisionProvider()
    if settings.vision_provider == "glm":
        return GlmVisionProvider(settings)
    raise VisionError(f"不支持的 VISION_PROVIDER：{settings.vision_provider}")


def select_note_images(cover_url: str, media_urls: list[str], *, scope: str, max_body_images: int) -> list[str]:
    """挑要解析的图:封面在前,cover 模式只回封面;cover_body 再补正文图(去重、限量)。

    media_urls[0] 通常就是封面;视频笔记 media_urls[0] 是视频直链,故封面单独传入优先。
    """
    ordered: list[str] = []
    seen: set[str] = set()

    def add(url: str) -> None:
        if isinstance(url, str) and url.startswith("http") and url not in seen:
            seen.add(url)
            ordered.append(url)

    add(cover_url)
    if scope == "cover_body":
        body_images = [u for u in media_urls if _is_image_url(u)]
        for url in body_images[: max(max_body_images, 0)]:
            add(url)
    if not ordered:
        # 没单独封面(或封面就在 media 里):退回用 media 里的图片。
        for url in media_urls:
            if _is_image_url(url):
                add(url)
                if scope == "cover" or len(ordered) >= max_body_images + 1:
                    break
    return ordered[:GLM_VISION_MAX_IMAGES]


def parse_vision_response(raw: str) -> tuple[str, dict[str, Any]]:
    """把 VLM 回复解析成 (image_text, visual_digest dict)。容错:去代码块围栏、取第一个 JSON 对象;
    实在解析不出就把整段当作 image_text(不丢内容)。"""
    text = (raw or "").strip()
    if not text:
        return "", {}
    payload = _loads_lenient(text)
    if isinstance(payload, dict):
        image_text = str(payload.get("image_text") or "").strip()
        digest = payload.get("visual_digest")
        digest = digest if isinstance(digest, dict) else {}
        return image_text, digest
    # 非 JSON:整段当图内文字兜底。
    return text, {}


def _loads_lenient(text: str) -> Any:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z]*\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped).strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    start = stripped.find("{")
    end = stripped.rfind("}")
    if 0 <= start < end:
        try:
            return json.loads(stripped[start : end + 1])
        except json.JSONDecodeError:
            return None
    return None


def _is_image_url(url: Any) -> bool:
    if not isinstance(url, str) or not url.startswith("http"):
        return False
    low = url.lower()
    if any(marker in low for marker in (".mp4", ".m3u8", "/video", "video/", ".mov")):
        return False
    return True


def _guess_image_mime(data: bytes) -> str:
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    return "image/jpeg"
