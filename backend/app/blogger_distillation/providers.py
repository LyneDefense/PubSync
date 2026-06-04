from app.models import BloggerProfile
from app.blogger_distillation.tikhub_client import TikHubError


SUPPORTED_PLATFORMS = {"xhs", "douyin"}


def validate_platform(platform: str) -> str:
    if platform not in SUPPORTED_PLATFORMS:
        raise ValueError("暂不支持这个平台")
    return platform


def platform_label(platform: str) -> str:
    return {"xhs": "小红书", "douyin": "抖音"}.get(platform, platform)


def ensure_collection_provider_available(blogger: BloggerProfile) -> None:
    if blogger.platform in {"xhs", "douyin"}:
        return
    raise TikHubError(f"{platform_label(blogger.platform)}采集器待接入")
