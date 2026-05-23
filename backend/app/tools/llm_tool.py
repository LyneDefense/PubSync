from typing import Any

from app.article_composition import compose_article
from app.article_composition.models import ComposedArticle
from app.config import Settings
from app.news_fetching.models import RawNewsCandidate
from app.news_processing import process_news_candidates
from app.services.ai_service import decide_article_image


class LLMTool:
    def process_news(
        self,
        settings: Settings,
        candidates: list[RawNewsCandidate],
        profile: Any | None = None,
    ) -> list[dict[str, object]]:
        return process_news_candidates(settings, candidates, profile)

    def compose_article(
        self,
        settings: Settings,
        news_items: list[dict[str, Any]],
        profile: Any | None = None,
    ) -> ComposedArticle:
        return compose_article(settings, news_items, profile)

    def decide_article_image(
        self,
        settings: Settings,
        news_item: dict[str, Any],
        forced: bool,
        image_style: str | None = None,
    ) -> dict[str, Any]:
        return decide_article_image(settings, news_item, forced=forced, image_style=image_style or undefined_image_style())


def undefined_image_style() -> str:
    return "抽象科技视觉、信息图、芯片、网络、云与模型架构"
