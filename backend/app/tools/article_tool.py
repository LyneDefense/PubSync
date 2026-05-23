from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.article_composition.models import ComposedArticle
from app.article_layout import render_basic_article_html, render_wechat_article_html
from app.article_selection import select_article_news
from app.article_selection.models import ArticleSelectionResult
from app.config import Settings
from app.models import ContentProfile, LayoutSettings, NewsItem
from app.services.ai_service import is_ai_enabled
from app.tools.image_tool import DEFAULT_COVER


class ArticleTool:
    def select_news(
        self,
        db: Session,
        settings: Settings,
        tenant_id: int,
        profile: ContentProfile | None = None,
        content_groups: list | None = None,
    ) -> ArticleSelectionResult:
        return select_article_news(db, settings, tenant_id, profile, content_groups or [])

    def build_news_payload(self, selected_news: list[NewsItem], content_groups: list | None = None) -> list[dict[str, Any]]:
        group_names = {group.group_key: group.name for group in (content_groups or [])}
        return [
            {
                "index": index,
                "title": item.title,
                "source": item.source,
                "url": item.url,
                "published_at": item.published_at.isoformat(),
                "summary": item.summary,
                "category": item.category,
                "group_key": item.group_key,
                "group_name": group_names.get(item.group_key, item.group_key),
                "region": item.region,
                "importance_score": item.importance_score,
                "image_url": None,
            }
            for index, item in enumerate(selected_news)
        ]

    def build_basic_article(
        self,
        selected_news: list[NewsItem],
        profile: ContentProfile | None = None,
    ) -> tuple[str, str, str, str]:
        today = datetime.now().strftime("%Y-%m-%d")
        title = normalize_article_title(f"{today} 重要动态", title_prefix(profile))
        domain = profile.content_domain if profile else "AI 行业"
        intro = f"今天精选 {len(selected_news)} 条{domain}重要动态，梳理产品、行业和关键变化。"
        content_html = render_basic_article_html(intro, selected_news)
        return title, intro, content_html, DEFAULT_COVER

    def render_article(
        self,
        composed_article: ComposedArticle,
        profile: ContentProfile | None = None,
        layout_settings: LayoutSettings | None = None,
    ) -> str:
        return render_wechat_article_html(composed_article, profile, layout_settings)

    def ai_enabled(self, settings: Settings) -> bool:
        return is_ai_enabled(settings)


def title_prefix(profile: ContentProfile | None) -> str:
    if profile and profile.title_prefix.strip():
        return profile.title_prefix.strip() + (" " if not profile.title_prefix.endswith(" ") else "")
    return "AI科技早报 | "


def normalize_article_title(title: str, prefix: str = "AI科技早报 | ") -> str:
    clean_title = " ".join(title.strip().split())
    if not clean_title:
        return f"{prefix}今日重要动态"
    if clean_title.startswith(prefix):
        return clean_title
    if clean_title.startswith("AI科技早报|"):
        return f"{prefix}{clean_title.split('|', 1)[1].strip()}"
    for stale_prefix in ("AI 早报：", "AI早报：", "AI科技早报："):
        if clean_title.startswith(stale_prefix):
            clean_title = clean_title.removeprefix(stale_prefix).strip()
            break
    return f"{prefix}{clean_title}"
