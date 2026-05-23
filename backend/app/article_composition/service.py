import logging
from typing import Any

from app.article_composition.prompts import build_article_composition_prompt
from app.article_composition.validators import validate_composed_article
from app.config import Settings
from app.services.ai_service import AIServiceError, create_json_response


logger = logging.getLogger(__name__)


def compose_article(settings: Settings, news_items: list[dict[str, Any]]):
    logger.info("文章正文生成请求开始：新闻数=%s", len(news_items))
    data = create_json_response(
        settings=settings,
        prompt=build_article_composition_prompt(news_items),
    )
    try:
        article = validate_composed_article(data, news_items)
    except ValueError as exc:
        raise AIServiceError(str(exc)) from exc
    logger.info("文章正文生成结果校验通过：段落数=%s，标题=%s", len(article.sections), article.title)
    return article
