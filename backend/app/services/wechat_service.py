from html.parser import HTMLParser
from urllib.parse import urljoin
import struct
import time
import zlib

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Article, ArticleStatus


WECHAT_API_BASE = "https://api.weixin.qq.com"

_token_cache: dict[str, str | float] = {"access_token": "", "expires_at": 0.0}


class WeChatAPIError(RuntimeError):
    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


def send_article_to_wechat_draft(db: Session, article: Article) -> Article:
    try:
        settings = get_settings()
        access_token = get_access_token(settings.wechat_app_id, settings.wechat_app_secret)
        cover_bytes, content_type = get_cover_image(article.cover_image_url)
        thumb_media_id = upload_permanent_cover(access_token, cover_bytes, content_type)
        content_html = prepare_wechat_content_html(access_token, article.content_html, settings.public_api_base_url)
        draft_media_id = add_draft(access_token, article, thumb_media_id, content_html)

        article.wechat_draft_id = draft_media_id
        article.status = ArticleStatus.sent_to_wechat
        article.error_message = None
        db.commit()
        db.refresh(article)
        return article
    except WeChatAPIError as exc:
        article.status = ArticleStatus.failed
        article.error_message = str(exc)
        db.commit()
        db.refresh(article)
        raise


def get_access_token(app_id: str, app_secret: str) -> str:
    if not app_id or not app_secret:
        raise WeChatAPIError("未配置 WECHAT_APP_ID 或 WECHAT_APP_SECRET", status_code=400)
    if not app_id.startswith("wx"):
        raise WeChatAPIError("WECHAT_APP_ID 看起来不是微信公众号 AppID。请使用公众号后台“设置与开发 > 基本配置”里的 AppID，通常以 wx 开头。", status_code=400)

    cached_token = str(_token_cache["access_token"])
    if cached_token and float(_token_cache["expires_at"]) > time.time() + 60:
        return cached_token

    with httpx.Client(timeout=12) as client:
        response = client.get(
            f"{WECHAT_API_BASE}/cgi-bin/token",
            params={
                "grant_type": "client_credential",
                "appid": app_id,
                "secret": app_secret,
            },
        )
    data = parse_wechat_response(response, "获取 access_token 失败")
    access_token = data.get("access_token")
    if not access_token:
        raise WeChatAPIError(f"获取 access_token 失败：微信返回缺少 access_token，响应为 {safe_wechat_payload(data)}")

    _token_cache["access_token"] = access_token
    _token_cache["expires_at"] = time.time() + int(data.get("expires_in", 7200))
    return str(access_token)


def get_cover_image(cover_image_url: str) -> tuple[bytes, str]:
    return get_image_bytes(cover_image_url) or (build_fallback_png(), "image/png")


def get_image_bytes(image_url: str) -> tuple[bytes, str] | None:
    if image_url:
        try:
            with httpx.Client(timeout=15, follow_redirects=True) as client:
                response = client.get(image_url)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "image/jpeg").split(";")[0]
            if content_type in {"image/jpeg", "image/png", "image/gif", "image/bmp"} and len(response.content) <= 10 * 1024 * 1024:
                return response.content, content_type
        except httpx.HTTPError:
            pass
    return None


def upload_permanent_cover(access_token: str, image_bytes: bytes, content_type: str) -> str:
    extension = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/gif": "gif",
        "image/bmp": "bmp",
    }.get(content_type, "jpg")

    with httpx.Client(timeout=30) as client:
        response = client.post(
            f"{WECHAT_API_BASE}/cgi-bin/material/add_material",
            params={"access_token": access_token, "type": "image"},
            files={"media": (f"cover.{extension}", image_bytes, content_type)},
        )
    data = parse_wechat_response(response, "上传封面永久素材失败")
    media_id = data.get("media_id")
    if not media_id:
        raise WeChatAPIError(f"上传封面永久素材失败：微信返回缺少 media_id，响应为 {safe_wechat_payload(data)}")
    return str(media_id)


def upload_article_image(access_token: str, image_bytes: bytes, content_type: str) -> str:
    extension = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/gif": "gif",
        "image/bmp": "bmp",
    }.get(content_type, "jpg")

    with httpx.Client(timeout=30) as client:
        response = client.post(
            f"{WECHAT_API_BASE}/cgi-bin/media/uploadimg",
            params={"access_token": access_token},
            files={"media": (f"article-image.{extension}", image_bytes, content_type)},
        )
    data = parse_wechat_response(response, "上传正文图片失败")
    url = data.get("url")
    if not url:
        raise WeChatAPIError(f"上传正文图片失败：微信返回缺少 url，响应为 {safe_wechat_payload(data)}")
    return str(url)


def prepare_wechat_content_html(access_token: str, content_html: str, public_api_base_url: str) -> str:
    image_sources = extract_image_sources(content_html)
    replacements: dict[str, str] = {}

    for src in image_sources:
        absolute_src = make_absolute_image_url(src, public_api_base_url)
        image = get_image_bytes(absolute_src)
        if not image:
            continue
        image_bytes, content_type = image
        replacements[src] = upload_article_image(access_token, image_bytes, content_type)

    prepared = content_html
    for original, replacement in replacements.items():
        prepared = prepared.replace(f'src="{original}"', f'src="{replacement}"')
        prepared = prepared.replace(f"src='{original}'", f"src='{replacement}'")
    return prepared


def add_draft(access_token: str, article: Article, thumb_media_id: str, content_html: str) -> str:
    payload = {
        "articles": [
            {
                "title": article.title[:64],
                "author": "PubSync",
                "digest": article.intro[:120],
                "content": content_html,
                "content_source_url": "",
                "thumb_media_id": thumb_media_id,
                "show_cover_pic": 1,
                "need_open_comment": 0,
                "only_fans_can_comment": 0,
            }
        ]
    }

    with httpx.Client(timeout=30) as client:
        response = client.post(
            f"{WECHAT_API_BASE}/cgi-bin/draft/add",
            params={"access_token": access_token},
            json=payload,
        )
    data = parse_wechat_response(response, "新建微信草稿失败")
    media_id = data.get("media_id")
    if not media_id:
        raise WeChatAPIError(f"新建微信草稿失败：微信返回缺少 media_id，响应为 {safe_wechat_payload(data)}")
    return str(media_id)


class ImageSrcParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.sources: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "img":
            return
        for key, value in attrs:
            if key.lower() == "src" and value:
                self.sources.append(value)


def extract_image_sources(content_html: str) -> list[str]:
    parser = ImageSrcParser()
    parser.feed(content_html)
    sources: list[str] = []
    seen: set[str] = set()
    for src in parser.sources:
        if src not in seen:
            seen.add(src)
            sources.append(src)
    return sources


def make_absolute_image_url(src: str, public_api_base_url: str) -> str:
    if src.startswith(("http://", "https://")):
        return src
    if not public_api_base_url:
        return src
    return urljoin(f"{public_api_base_url.rstrip('/')}/", src.lstrip("/"))


def parse_wechat_response(response: httpx.Response, prefix: str) -> dict:
    try:
        data = response.json()
    except ValueError as exc:
        raise WeChatAPIError(f"{prefix}：微信返回了非 JSON 响应，HTTP {response.status_code}") from exc

    if response.status_code >= 400:
        raise WeChatAPIError(f"{prefix}：HTTP {response.status_code}，响应为 {safe_wechat_payload(data)}")

    errcode = data.get("errcode")
    if errcode not in (None, 0):
        errmsg = data.get("errmsg", "unknown error")
        raise WeChatAPIError(f"{prefix}：errcode={errcode}, errmsg={errmsg}")

    return data


def safe_wechat_payload(data: dict) -> str:
    redacted = dict(data)
    redacted.pop("access_token", None)
    return str(redacted)


def build_fallback_png(width: int = 1200, height: int = 675) -> bytes:
    rows = []
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            row.extend(
                (
                    18 + (x * 22 // width),
                    82 + (y * 48 // height),
                    92 + ((x + y) * 28 // (width + height)),
                )
            )
        rows.append(bytes(row))

    raw = b"".join(rows)

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    return b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)),
            chunk(b"IDAT", zlib.compress(raw, level=9)),
            chunk(b"IEND", b""),
        ]
    )
