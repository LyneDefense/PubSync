import logging
from typing import Any

from app.config import Settings
from app.models import ContentProfile, NewsItem
from app.services.ai_service import AIServiceError, generate_image
from app.tools.llm_tool import LLMTool


logger = logging.getLogger(__name__)
DEFAULT_COVER = "https://images.unsplash.com/photo-1677442136019-21780ecad995?auto=format&fit=crop&w=1200&q=80"


class ImageTool:
    def __init__(self, llm_tool: LLMTool | None = None) -> None:
        self.llm_tool = llm_tool or LLMTool()

    def apply_article_images(
        self,
        settings: Settings,
        selected_news: list[NewsItem],
        news_payload: list[dict[str, Any]],
        profile: ContentProfile | None = None,
    ) -> int:
        max_images = max(0, settings.max_article_images)
        min_images = max(0, min(settings.min_article_images, max_images))
        if max_images <= 0:
            logger.info("正文配图生成跳过：最大图片数=%s", max_images)
            return 0

        logger.info("正文配图生成开始：最少=%s，最多=%s，新闻数=%s", min_images, max_images, len(selected_news))
        generated_indexes: set[int] = set()

        for index, news in enumerate(selected_news):
            if len(generated_indexes) >= max_images:
                break
            decision = self.decide_news_image(settings, news, profile, forced=False)
            if not truthy(decision.get("should_generate")):
                logger.info("正文配图决策为跳过：新闻ID=%s，标题=%s", news.id, truncate_log_text(news.title))
                continue
            if self.generate_news_image(settings, news, news_payload, index, decision, profile, forced=False):
                generated_indexes.add(index)

        if len(generated_indexes) >= min_images:
            logger.info("正文配图生成完成：已生成=%s", len(generated_indexes))
            return len(generated_indexes)

        logger.info("正文配图数量低于最小值，开始强制补图：已生成=%s，最少=%s", len(generated_indexes), min_images)
        for index, news in ranked_news_indexes(selected_news):
            if len(generated_indexes) >= min_images or len(generated_indexes) >= max_images:
                break
            if index in generated_indexes:
                continue
            decision = self.decide_news_image(settings, news, profile, forced=True)
            if self.generate_news_image(settings, news, news_payload, index, decision, profile, forced=True):
                generated_indexes.add(index)

        if len(generated_indexes) < min_images:
            logger.warning("正文配图生成后仍低于最小值：已生成=%s，最少=%s", len(generated_indexes), min_images)
        else:
            logger.info("正文配图生成完成：已生成=%s", len(generated_indexes))
        return len(generated_indexes)

    def decide_news_image(
        self,
        settings: Settings,
        news: NewsItem,
        profile: ContentProfile | None,
        forced: bool,
    ) -> dict[str, Any]:
        payload = news_image_decision_payload(news)
        try:
            image_style = profile.image_style if profile else None
            return self.llm_tool.decide_article_image(settings, payload, forced=forced, image_style=image_style)
        except AIServiceError as exc:
            logger.warning("正文配图决策失败：新闻ID=%s，强制补图=%s，错误=%s", news.id, yes_no(forced), exc)
            if forced:
                return {"should_generate": True, "fallback_prompt": build_forced_news_image_prompt(news, profile)}
            return {"should_generate": False, "fallback_prompt": build_forced_news_image_prompt(news, profile)}

    def generate_news_image(
        self,
        settings: Settings,
        news: NewsItem,
        news_payload: list[dict[str, Any]],
        index: int,
        decision: dict[str, Any],
        profile: ContentProfile | None,
        forced: bool,
    ) -> bool:
        raw_prompt = str(decision.get("prompt") or decision.get("fallback_prompt") or "").strip()
        if forced and not raw_prompt:
            raw_prompt = build_forced_news_image_prompt(news, profile)
        prompt = make_safe_image_prompt(raw_prompt)
        if not prompt or not is_safe_image_prompt(prompt):
            prompt = make_safe_image_prompt(build_forced_news_image_prompt(news, profile))
        if not is_safe_image_prompt(prompt):
            logger.warning("正文配图提示词被拒绝：新闻ID=%s，强制补图=%s", news.id, yes_no(forced))
            return False
        try:
            image_url = generate_image(settings, prompt, f"news-{news.id}")
        except AIServiceError as exc:
            logger.warning("正文配图生成失败：新闻ID=%s，强制补图=%s，错误=%s", news.id, yes_no(forced), exc)
            return False
        if not image_url:
            return False
        news_payload[index]["image_url"] = image_url
        logger.info("正文配图生成成功：新闻ID=%s，强制补图=%s", news.id, yes_no(forced))
        return True

    def generate_cover(
        self,
        settings: Settings,
        news_items: list[NewsItem],
        cover_prompt: str,
        profile: ContentProfile | None = None,
    ) -> str:
        try:
            logger.info("文章封面图生成开始")
            return generate_image(settings, cover_prompt or build_cover_prompt(news_items, profile), "cover") or DEFAULT_COVER
        except AIServiceError:
            logger.warning("文章封面图生成失败，使用默认封面")
            return DEFAULT_COVER


def news_image_decision_payload(news: NewsItem) -> dict[str, object]:
    return {
        "title": news.title,
        "summary": news.summary,
        "category": news.category,
        "group_key": news.group_key,
        "source": news.source,
        "importance_score": news.importance_score,
    }


def ranked_news_indexes(news_items: list[NewsItem]) -> list[tuple[int, NewsItem]]:
    return sorted(
        enumerate(news_items),
        key=lambda pair: (pair[1].importance_score, pair[1].published_at),
        reverse=True,
    )


def truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1", "是", "需要"}
    return bool(value)


def yes_no(value: bool) -> str:
    return "是" if value else "否"


def is_safe_image_prompt(prompt: str) -> bool:
    lower = prompt.lower()
    required_negative_terms = ["no human", "no face", "no logo", "no brand"]
    risky_terms = [
        "portrait of",
        "realistic portrait",
        "human face",
        "company logo",
        "brand logo",
        "photorealistic photo of",
        "screenshot of",
    ]
    return all(term in lower for term in required_negative_terms) and not any(term in lower for term in risky_terms)


def make_safe_image_prompt(prompt: str) -> str:
    if not prompt:
        return ""
    safety_suffix = (
        " Abstract editorial infographic style. No human, no face, no celebrity, no real person, "
        "no fictional person, no logo, no brand mark, no photorealistic news scene, no UI screenshot, no text."
    )
    return f"{prompt.rstrip()} {safety_suffix}"


def build_forced_news_image_prompt(news: NewsItem, profile: ContentProfile | None = None) -> str:
    summary = " ".join(news.summary.split())[:220]
    image_style = profile.image_style if profile else "abstract editorial infographic"
    return (
        f"Editorial abstract infographic for a newsletter article. Visual direction: {image_style}. "
        f"Theme: {news.category}. "
        "Represent the news with non-human symbols, structured information layers, and conceptual visual metaphors. "
        "Use the article context without depicting named people, logos, screenshots, or real scenes. "
        f"Context: {summary}. "
        "No human, no face, no celebrity, no real person, no fictional person, no logo, no brand mark, "
        "no photorealistic news scene, no UI screenshot, no text."
    )


def build_cover_prompt(news_items: list[NewsItem], profile: ContentProfile | None = None) -> str:
    topics = "; ".join(item.title for item in news_items[:5])
    image_style = profile.image_style if profile else "abstract technology infographic"
    return (
        f"Modern Chinese newsletter cover image, 16:9 composition, {image_style}, "
        "no human, no face, no celebrity, no real person, no fictional person, no logo, no brand mark, "
        "no photorealistic news scene, no UI screenshot, no text, polished editorial style. Topics: "
        f"{topics}"
    )


def truncate_log_text(value: str, limit: int = 80) -> str:
    text = " ".join(value.split())
    return text if len(text) <= limit else f"{text[:limit]}..."
