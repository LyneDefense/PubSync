from typing import Any

from app.article_composition.prompts import build_article_composition_prompt
from app.article_composition.validators import validate_composed_article
from app.config import Settings
from app.services.ai_service import AIServiceError, create_json_response


def compose_article(settings: Settings, news_items: list[dict[str, Any]]):
    data = create_json_response(
        settings=settings,
        prompt=build_article_composition_prompt(news_items),
    )
    try:
        return validate_composed_article(data, news_items)
    except ValueError as exc:
        raise AIServiceError(str(exc)) from exc
