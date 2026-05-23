from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.article_composition.models import ComposedArticle
from app.article_layout import render_basic_article_html, render_wechat_article_html
from app.article_selection import select_article_news
from app.article_selection.models import ArticleSelectionResult
from app.config import Settings
from app.models import NewsItem
from app.services.ai_service import is_ai_enabled
from app.tools.image_tool import DEFAULT_COVER


class ArticleTool:
    def select_news(self, db: Session, settings: Settings) -> ArticleSelectionResult:
        return select_article_news(db, settings)

    def build_news_payload(self, selected_news: list[NewsItem]) -> list[dict[str, Any]]:
        return [
            {
                "index": index,
                "title": item.title,
                "source": item.source,
                "url": item.url,
                "published_at": item.published_at.isoformat(),
                "summary": item.summary,
                "category": item.category,
                "region": item.region,
                "importance_score": item.importance_score,
                "image_url": None,
            }
            for index, item in enumerate(selected_news)
        ]

    def build_basic_article(self, selected_news: list[NewsItem]) -> tuple[str, str, str, str]:
        today = datetime.now().strftime("%Y-%m-%d")
        title = normalize_article_title(f"{today} 重要动态")
        intro = f"今天精选 {len(selected_news)} 条 AI 行业大事件，覆盖模型、产品、基础设施和监管动态。"
        content_html = render_basic_article_html(intro, selected_news)
        return title, intro, content_html, DEFAULT_COVER

    def render_article(self, composed_article: ComposedArticle) -> str:
        return render_wechat_article_html(composed_article)

    def ai_enabled(self, settings: Settings) -> bool:
        return is_ai_enabled(settings)


def normalize_article_title(title: str) -> str:
    clean_title = " ".join(title.strip().split())
    prefix = "AI科技早报 | "
    if not clean_title:
        return f"{prefix}今日 AI 行业重要动态"
    if clean_title.startswith(prefix):
        return clean_title
    if clean_title.startswith("AI科技早报|"):
        return f"{prefix}{clean_title.split('|', 1)[1].strip()}"
    for stale_prefix in ("AI 早报：", "AI早报：", "AI科技早报："):
        if clean_title.startswith(stale_prefix):
            clean_title = clean_title.removeprefix(stale_prefix).strip()
            break
    return f"{prefix}{clean_title}"
