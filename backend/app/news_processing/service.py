import logging
from typing import Any

from app.config import Settings
from app.news_fetching.models import RawNewsCandidate
from app.news_processing.prompts import build_news_processing_prompt
from app.news_processing.validators import validate_processed_items
from app.services.ai_service import AIServiceError, create_json_response


logger = logging.getLogger(__name__)


def process_news_candidates(
    settings: Settings,
    candidates: list[RawNewsCandidate],
    profile: Any | None = None,
    content_groups: list | None = None,
) -> list[dict[str, object]]:
    if not candidates:
        raise AIServiceError("没有从新闻源抓取到候选新闻，请检查新闻源配置")

    logger.info("新闻后处理开始：候选数=%s", len(candidates))
    data = create_json_response(settings=settings, prompt=build_news_processing_prompt(candidates, profile, content_groups or []))
    items = validate_processed_items(data.get("items"), candidates)
    if not items:
        raise AIServiceError("AI 新闻后处理没有返回可用新闻，请检查候选源质量或模型输出")
    logger.info("新闻后处理校验通过：可用条数=%s", len(items))
    return [item.to_news_dict() for item in items]
