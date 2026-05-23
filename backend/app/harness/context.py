from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.article_composition.models import ComposedArticle
from app.article_selection.models import ArticleSelectionResult
from app.config import Settings
from app.models import Article, NewsItem
from app.news_fetching.models import NewsFetchResult, RawNewsCandidate


@dataclass
class HarnessContext:
    task_id: str
    task_type: str
    db: Session
    settings: Settings
    should_publish: bool = False
    fetch_result: NewsFetchResult | None = None
    raw_candidates: list[RawNewsCandidate] = field(default_factory=list)
    processed_items: list[dict[str, Any]] = field(default_factory=list)
    created_news: list[NewsItem] = field(default_factory=list)
    selection: ArticleSelectionResult | None = None
    selected_news: list[NewsItem] = field(default_factory=list)
    news_payload: list[dict[str, Any]] = field(default_factory=list)
    composed_article: ComposedArticle | None = None
    title: str = ""
    intro: str = ""
    content_html: str = ""
    cover_image_url: str = ""
    article: Article | None = None
    published_to_wechat: bool = False
