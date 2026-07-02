"""视觉层:对图文笔记的封面/正文图跑 VLM(智谱 GLM),提取图内逐字文字 + 结构化视觉摘要。

与 ASR 层结构对称:ASR 取"视频语音"里的内容(transcript_text),视觉层取"图片"里的内容
(image_text + visual_digest)。默认直传图片公网 URL(GLM 服务器去拉);被防盗链挡住时下载转 base64 兜底。
"""

from __future__ import annotations

import base64
import json
import logging
import re
import shutil
import subprocess
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
    "你是小红书内容分析助手。下面按顺序给你一篇笔记的若干张图片(第一张通常是封面)。"
    "**只输出一个 JSON 对象**，不要 Markdown、不要解释、不要 <think>。**逐张**分析,结构如下：\n"
    '{\n'
    '  "images": [\n'
    '    {"index": 1, "role": "封面/正文卡片/清单/对比/教程步骤/截图/实拍/合集 等",\n'
    '     "text": "这张图里出现的所有文字,逐字转写(大字、要点、清单、数据、联系方式/要求等),看不清写[模糊],绝不编造",\n'
    '     "desc": "这张图在讲什么,一句话"}\n'
    '  ],\n'
    '  "cover_hook": "封面主文案/钩子,没有则空串",\n'
    '  "layout": "整体版式,如 卡片清单/大字/图文混排",\n'
    '  "style": "配色·字体·信息密度·风格调性,一句话"\n'
    '}\n'
    "images 按图片顺序,有几张图就几项;每张的 text 逐字转写、**绝不编造**图里没有的文字。"
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
        if not shutil.which("ffmpeg"):
            raise VisionError("服务器未安装 ffmpeg，无法转换图片格式")

    def analyze_images(self, image_urls: list[str], *, source_id: str = "", on_progress: ProgressCallback | None = None) -> VisionResult:
        urls = [u for u in image_urls if isinstance(u, str) and u.startswith("http")][:GLM_VISION_MAX_IMAGES]
        if not urls:
            raise VisionError("没有可解析的图片 URL")
        if on_progress is not None:
            on_progress(f"正在识别并理解图片…共 {len(urls)} 张")
        # 小红书图多为 webp、视频封面是 mp4,GLM 视觉都会拒收(400 图片格式/解析错误)。
        # 统一下载后用 ffmpeg 转 JPEG(视频取首帧,恰好就是封面)再 base64 上传,最稳。
        parts = self._to_jpeg_base64(urls)
        if not parts:
            raise VisionError("图片下载/转码失败，无可用图片")
        try:
            raw = glm_vision_chat(self.settings, image_parts=parts, instruction=VISION_PROMPT, model=self.settings.vision_model)
        except AIServiceError as exc:
            raise VisionError(f"GLM 视觉调用失败：{exc}") from exc
        image_text, digest = parse_vision_response(raw)
        return VisionResult(image_text=image_text, visual_digest=digest, image_count=len(parts), provider="glm_vision")

    def _to_jpeg_base64(self, urls: list[str]) -> list[str]:
        """下载每张图并用 ffmpeg 转成 JPEG(视频取首帧);统一格式绕开 GLM 对 webp/mp4 的拒收。单张失败则跳过。"""
        parts: list[str] = []
        max_bytes = 8 * (1 << 20)  # 单图/单封面硬上限 8MB
        with tempfile.TemporaryDirectory(prefix="pubsync-vision-") as tmp_dir:
            for index, url in enumerate(urls):
                src = Path(tmp_dir) / f"src_{index}"
                dst = Path(tmp_dir) / f"img_{index}.jpg"
                try:
                    download_file(url, src, max_seconds=60, max_bytes=max_bytes)
                except (httpx.HTTPError, OSError, RuntimeError) as exc:
                    logger.info("视觉下载单图失败,跳过：url=%s，原因=%s", url[:80], exc)
                    continue
                try:
                    # 缩到 ≤1280px(等比,高取偶数):降内存/上传体积/GLM tokens,也更快。视频取首帧。
                    subprocess.run(
                        ["ffmpeg", "-y", "-i", str(src), "-frames:v", "1", "-vf", "scale='min(1280,iw)':-2", str(dst)],
                        capture_output=True,
                        text=True,
                        check=False,
                        timeout=60,
                    )
                except subprocess.TimeoutExpired:
                    logger.info("视觉转码超时,跳过：url=%s", url[:80])
                    continue
                if not dst.exists():
                    logger.info("视觉转码单图失败,跳过：url=%s", url[:80])
                    continue
                parts.append("data:image/jpeg;base64," + base64.b64encode(dst.read_bytes()).decode("ascii"))
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
    """把 VLM 回复解析成 (image_text, visual_digest)。

    新结构:visual_digest = {cover_hook, layout, style, images:[{index, role, text, desc}]};
    image_text 由各图文字带「第N张(角色)」标签拼接 —— 不再糅成一坨,也便于下游按图引用。
    兼容旧形态(顶层 image_text / 嵌套 visual_digest / 无 images)与非 JSON 兜底。
    """
    text = (raw or "").strip()
    if not text:
        return "", {}
    payload = _loads_lenient(text)
    if not isinstance(payload, dict):
        return text, {}  # 非 JSON:整段当图内文字兜底
    digest: dict[str, Any] = {}
    for key in ("cover_hook", "layout", "style"):
        val = str(payload.get(key) or "").strip()
        if val:
            digest[key] = val
    images = payload.get("images")
    if isinstance(images, list) and images:
        norm: list[dict[str, Any]] = []
        parts: list[str] = []
        for i, item in enumerate(images, 1):
            if not isinstance(item, dict):
                continue
            raw_idx = item.get("index")
            idx = int(raw_idx) if isinstance(raw_idx, (int, float)) or (isinstance(raw_idx, str) and raw_idx.isdigit()) else i
            role = str(item.get("role") or "").strip()
            body = str(item.get("text") or "").strip()
            desc = str(item.get("desc") or "").strip()
            norm.append({"index": idx, "role": role, "text": body, "desc": desc})
            if body:
                label = f"第{idx}张" + (f"（{role}）" if role else "")
                parts.append(f"{label}：{body}")
        digest["images"] = norm
        return "\n\n".join(parts).strip(), digest
    # 兼容旧形态:顶层 image_text + 可能嵌套的 visual_digest。
    image_text = str(payload.get("image_text") or "").strip()
    nested = payload.get("visual_digest")
    if isinstance(nested, dict):
        for key in ("cover_hook", "layout", "style"):
            val = str(nested.get(key) or "").strip()
            if val and key not in digest:
                digest[key] = val
    return image_text, digest


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
